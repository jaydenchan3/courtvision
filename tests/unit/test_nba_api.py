"""Failure-mode tests for the live refresh path. No network is ever touched.

The refresh is the one part of the system that talks to something we do not
control, so its failure modes are the ones worth testing hardest: a free tier
will rate-limit, go down, and change shape. The contract under test is that any
of those leaves the cache exactly as it was and reports the failure as a value.

Two seams are mocked:
  * `fetch_fn` is injected into refresh_cache, so transport failures are
    simulated without HTTP at all.
  * `requests.get` is patched for the tests that exercise http_get itself.

stdlib unittest.mock is sufficient; no new dependency was added.
"""

import hashlib
from unittest.mock import Mock, patch

import pytest
import requests

from app.data import nba_api, queries

pytestmark = pytest.mark.unit

CACHE_TABLES = ("teams", "players", "games")


def fingerprint(conn):
    """Hash every row of the cache tables. Row counts alone would not notice a
    refresh that overwrote values while keeping the same number of rows."""
    digest = hashlib.sha256()
    for table in CACHE_TABLES:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        digest.update(repr([tuple(r) for r in rows]).encode())
    return digest.hexdigest()


# -- fake payloads ---------------------------------------------------------

def team(team_id, abbr, division="Atlantic"):
    return {"id": team_id, "abbreviation": abbr, "city": "City",
            "name": abbr, "full_name": f"{abbr} Team",
            "conference": "East", "division": division}


def player(player_id, team_id, last="Tester"):
    return {"id": player_id, "first_name": "Mock", "last_name": last,
            "position": "G", "height": "6-6", "weight": "200",
            "jersey_number": "1", "team": {"id": team_id}}


def game(game_id, home, away, stamp="2026-08-20T23:30:00.000Z"):
    return {"id": game_id, "date": "2026-08-20", "datetime": stamp,
            "season": 2025, "status": "Final", "postseason": False,
            "home_team": {"id": home}, "visitor_team": {"id": away},
            "home_team_score": 101, "visitor_team_score": 99}


def good_fetch(payloads=None):
    """A fetch_fn that returns canned bodies keyed by path."""
    payloads = payloads or {
        "teams": {"data": [team(1, "ATL"), team(2, "BOS")]},
        "players": {"data": [player(9001, 1), player(9002, 2)], "meta": {}},
        "games": {"data": [game(950001, 1, 2)], "meta": {}},
    }

    def fetch(path, params=None):
        return payloads[path]
    return fetch


def failing_fetch(exc):
    def fetch(path, params=None):
        raise exc
    return fetch


# -- happy path ------------------------------------------------------------

def test_refresh_upserts_fetched_rows(seeded_db):
    result = nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch())

    assert result.ok is True
    assert result.written == {"teams": 2, "players": 2, "games": 1}
    assert seeded_db.execute(
        "SELECT last_name FROM players WHERE id = 9001").fetchone()[0] == "Tester"


def test_refresh_is_idempotent(seeded_db):
    """The natural-key invariant: rows are keyed by the API id, so replaying
    the same response updates in place instead of duplicating."""
    nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch())
    after_first = fingerprint(seeded_db)
    counts = {t: seeded_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in CACHE_TABLES}

    nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch())

    assert fingerprint(seeded_db) == after_first
    for table, count in counts.items():
        assert seeded_db.execute(
            f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count


def test_refresh_updates_an_existing_row_rather_than_inserting(seeded_db):
    before = seeded_db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    renamed = {"teams": {"data": [team(1, "ZZZ")]}}

    result = nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch(renamed),
                                   resources=("teams",))

    assert result.ok is True
    assert seeded_db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == before
    assert seeded_db.execute(
        "SELECT abbreviation FROM teams WHERE id = 1").fetchone()[0] == "ZZZ"


def test_refresh_never_touches_the_app_owned_tables(seeded_db):
    """user_roster, injuries and player_stats are not refetchable. A cache
    refresh must not be able to disturb them."""
    owned = {t: seeded_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("user_roster", "injuries", "player_stats")}

    nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch())

    for table, count in owned.items():
        assert seeded_db.execute(
            f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count


def test_refresh_skips_rows_referencing_an_unknown_team(seeded_db):
    """A player on a franchise we do not carry is skipped, not allowed to fail
    the whole refresh on a foreign key."""
    payload = {"teams": {"data": [team(1, "ATL")]},
               "players": {"data": [player(9001, 1), player(9002, 999)], "meta": {}}}

    result = nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch(payload),
                                   resources=("teams", "players"))

    assert result.ok is True
    assert result.written["players"] == 1
    assert result.skipped["players"] == 1


# -- failure modes ---------------------------------------------------------

@pytest.mark.parametrize("exc,kind", [
    (nba_api.RateLimited("429"), "RateLimited"),
    (nba_api.UpstreamError("HTTP 500"), "UpstreamError"),
    (nba_api.MalformedResponse("not JSON"), "MalformedResponse"),
    (nba_api.NetworkUnavailable("timed out"), "NetworkUnavailable"),
    (nba_api.RefreshError("no key"), "RefreshError"),
])
def test_failures_leave_the_cache_untouched(seeded_db, exc, kind):
    before = fingerprint(seeded_db)

    result = nba_api.refresh_cache(seeded_db, fetch_fn=failing_fetch(exc))

    assert result.ok is False
    assert result.kind == kind
    assert result.reason
    assert fingerprint(seeded_db) == before


def test_failure_does_not_raise_at_the_caller(seeded_db):
    """Callers check .ok. An unhandled exception escaping a background refresh
    would take down whatever scheduled it."""
    result = nba_api.refresh_cache(seeded_db,
                                   fetch_fn=failing_fetch(RuntimeError("boom")))
    assert result.ok is False
    assert result.kind == "RuntimeError"


@pytest.mark.parametrize("body", [
    {"data": "not-a-list"},
    {"meta": {}},
    {},
])
def test_malformed_top_level_shape_is_rejected(seeded_db, body):
    before = fingerprint(seeded_db)

    result = nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch({"teams": body}),
                                   resources=("teams",))

    assert result.ok is False
    assert result.kind == "MalformedResponse"
    assert fingerprint(seeded_db) == before


@pytest.mark.parametrize("bad_record", [
    {"abbreviation": "ATL", "full_name": "Atlanta", "division": "Southeast"},
    {"id": 1, "full_name": "Atlanta", "division": "Southeast"},
    {"id": 1, "abbreviation": "ATL", "division": "Southeast"},
])
def test_records_missing_required_keys_are_rejected(seeded_db, bad_record):
    before = fingerprint(seeded_db)

    result = nba_api.refresh_cache(
        seeded_db, fetch_fn=good_fetch({"teams": {"data": [bad_record]}}),
        resources=("teams",))

    assert result.ok is False
    assert result.kind == "MalformedResponse"
    assert fingerprint(seeded_db) == before


def test_player_without_a_nested_team_is_rejected(seeded_db):
    payload = {"teams": {"data": [team(1, "ATL")]},
               "players": {"data": [{"id": 1, "first_name": "A",
                                     "last_name": "B", "team": 7}], "meta": {}}}
    before = fingerprint(seeded_db)

    result = nba_api.refresh_cache(seeded_db, fetch_fn=good_fetch(payload),
                                   resources=("teams", "players"))

    assert result.ok is False
    assert result.kind == "MalformedResponse"
    assert fingerprint(seeded_db) == before


def test_a_failure_on_page_two_writes_nothing_at_all(seeded_db):
    """Partial-failure guard. Page one succeeds and page two rate-limits; the
    rows from page one must not survive, or the cache would hold a silently
    truncated view of the data."""
    before = fingerprint(seeded_db)
    calls = {"players": 0}

    def fetch(path, params=None):
        if path == "teams":
            return {"data": [team(1, "ATL")]}
        calls["players"] += 1
        if calls["players"] == 1:
            return {"data": [player(9001, 1)], "meta": {"next_cursor": 100}}
        raise nba_api.RateLimited("429 on page two")

    result = nba_api.refresh_cache(seeded_db, fetch_fn=fetch,
                                   resources=("teams", "players"))

    assert result.ok is False
    assert result.kind == "RateLimited"
    assert calls["players"] == 2, "the second page really was requested"
    assert fingerprint(seeded_db) == before
    assert seeded_db.execute(
        "SELECT COUNT(*) FROM players WHERE id = 9001").fetchone()[0] == 0


def test_a_failed_refresh_leaves_the_app_fully_readable(seeded_db):
    """Graceful degradation, proven rather than asserted: after a refresh
    fails, every read the app performs still returns the cached data."""
    nba_api.refresh_cache(seeded_db,
                          fetch_fn=failing_fetch(nba_api.RateLimited("429")))

    assert len(queries.games_tonight(seeded_db)) == 3
    assert len(queries.injury_report(seeded_db)) == 8
    assert queries.roster_count(seeded_db) == 8
    assert len(queries.waiver_players(seeded_db)) == 32


# -- http_get, with requests patched --------------------------------------

def _response(status=200, json_body=None, raises=None, headers=None):
    mock = Mock()
    mock.status_code = status
    mock.headers = headers or {}
    if raises is not None:
        mock.json.side_effect = raises
    else:
        mock.json.return_value = json_body
    return mock


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
def test_http_get_sends_the_raw_key_with_no_bearer_prefix(mock_get):
    """The measured spike finding: this API rejects a Bearer prefix."""
    mock_get.return_value = _response(json_body={"data": []})

    nba_api.http_get("teams")

    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "test-key"
    assert not headers["Authorization"].startswith("Bearer")


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
def test_http_get_raises_rate_limited_on_429(mock_get):
    mock_get.return_value = _response(status=429, headers={"retry-after": "59"})

    with pytest.raises(nba_api.RateLimited) as caught:
        nba_api.http_get("teams")
    assert "59" in str(caught.value)


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_http_get_raises_upstream_error_on_other_non_200(mock_get, status):
    mock_get.return_value = _response(status=status)

    with pytest.raises(nba_api.UpstreamError):
        nba_api.http_get("standings")


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
def test_http_get_raises_malformed_on_a_non_json_body(mock_get):
    mock_get.return_value = _response(raises=ValueError("no JSON"))

    with pytest.raises(nba_api.MalformedResponse):
        nba_api.http_get("teams")


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
def test_http_get_raises_malformed_when_data_is_absent(mock_get):
    mock_get.return_value = _response(json_body={"meta": {}})

    with pytest.raises(nba_api.MalformedResponse):
        nba_api.http_get("teams")


@patch.dict("os.environ", {"BALLDONTLIE_API_KEY": "test-key"})
@patch("app.data.nba_api.requests.get")
@pytest.mark.parametrize("exc", [
    requests.Timeout("timed out"),
    requests.ConnectionError("refused"),
])
def test_http_get_converts_transport_errors(mock_get, exc):
    mock_get.side_effect = exc

    with pytest.raises(nba_api.NetworkUnavailable):
        nba_api.http_get("teams")


@patch.dict("os.environ", {}, clear=True)
def test_http_get_without_a_key_fails_before_any_network_call():
    with patch("app.data.nba_api.requests.get") as mock_get:
        with pytest.raises(nba_api.RefreshError):
            nba_api.http_get("teams")
        mock_get.assert_not_called()
