"""Live-data refresh from BALLDONTLIE.

OUT OF BAND BY DESIGN. Nothing here is reachable from a request. The measured
free tier is 5 requests/minute, so the API cannot sit in a page-load path;
this is a separate step that writes into the same cache tables seed.py fills,
and Flask keeps reading SQLite either way.

Failure is expected, not exceptional -- rate limits, outages and shape changes
are all normal for a free tier. So refresh_cache never raises at the caller:
it FETCHES EVERYTHING FIRST, validates it, and only then writes, inside a
single transaction. Any failure leaves the existing cache exactly as it was,
and is reported as a result value.
"""

import os
import sqlite3
from datetime import datetime

import requests

from app.data import models

BASE_URL = "https://api.balldontlie.io/nba/v1"
TIMEOUT = 15
# The free tier allows 5 requests/minute. Capping pages keeps one refresh
# inside that budget rather than tripping a 429 halfway through.
MAX_PAGES = 3
PER_PAGE = 100


class RefreshError(Exception):
    """Base for every anticipated refresh failure."""


class RateLimited(RefreshError):
    """HTTP 429. Expected on a 5 req/min tier, not a bug."""


class UpstreamError(RefreshError):
    """Any other non-200, including 401 for a paid-tier endpoint."""


class MalformedResponse(RefreshError):
    """Body was not JSON, or did not have the shape we require."""


class NetworkUnavailable(RefreshError):
    """Timeout, DNS failure, connection refused."""


class RefreshResult:
    """What happened, as a value. Callers check .ok rather than catching."""

    def __init__(self, ok, written=None, reason=None, kind=None, skipped=None):
        self.ok = ok
        self.written = written or {}
        self.reason = reason
        self.kind = kind
        self.skipped = skipped or {}

    def __repr__(self):
        if self.ok:
            return f"<RefreshResult ok written={self.written}>"
        return f"<RefreshResult failed kind={self.kind}>"


def api_key():
    """Read at call time, never at import: the app must start with no key set."""
    return os.environ.get("BALLDONTLIE_API_KEY")


def http_get(path, params=None):
    """The real network call. Every anticipated failure becomes a RefreshError.

    Auth is the raw key with no Bearer prefix, per the measured spike findings.
    """
    key = api_key()
    if not key:
        raise RefreshError("BALLDONTLIE_API_KEY is not set")

    try:
        response = requests.get(
            f"{BASE_URL}/{path}",
            headers={"Authorization": key},
            params=params or {},
            timeout=TIMEOUT,
        )
    except requests.Timeout as exc:
        raise NetworkUnavailable(f"request timed out after {TIMEOUT}s") from exc
    except requests.RequestException as exc:
        raise NetworkUnavailable(f"could not reach the API: {exc}") from exc

    if response.status_code == 429:
        retry_after = response.headers.get("retry-after", "unknown")
        raise RateLimited(f"rate limited; retry after {retry_after}s")
    if response.status_code != 200:
        raise UpstreamError(f"HTTP {response.status_code} from /{path}")

    try:
        body = response.json()
    except ValueError as exc:
        raise MalformedResponse(f"/{path} did not return JSON") from exc

    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise MalformedResponse(f"/{path} response had no data list")
    return body


def _paginate(fetch_fn, path, params=None, max_pages=MAX_PAGES):
    """Follow cursor pagination. A failure on any page aborts the whole fetch,
    which is what keeps a partial refresh from ever being written."""
    records, cursor = [], None
    for _ in range(max_pages):
        page_params = dict(params or {})
        if cursor is not None:
            page_params["cursor"] = cursor
        body = fetch_fn(path, page_params)
        data = body.get("data")
        if not isinstance(data, list):
            raise MalformedResponse(f"/{path} page had no data list")
        records.extend(data)
        cursor = (body.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
    return records


def _require(record, keys, what):
    missing = [k for k in keys if record.get(k) is None]
    if missing:
        raise MalformedResponse(f"{what} record missing " + ", ".join(missing))


def fetch_teams(fetch_fn=http_get):
    body = fetch_fn("teams", {})
    data = body.get("data")
    if not isinstance(data, list):
        raise MalformedResponse("/teams response had no data list")
    return data


def fetch_players(fetch_fn=http_get):
    return _paginate(fetch_fn, "players", {"per_page": PER_PAGE})


def fetch_games(fetch_fn=http_get, date=None):
    date = date or models.today_local()
    return _paginate(fetch_fn, "games", {"per_page": PER_PAGE, "dates[]": date})


def _local_date(record):
    """The league schedules by US/Eastern date and the API datetime is UTC.
    A 02:00Z tip-off belongs to the previous local evening."""
    stamp = record.get("datetime")
    if stamp:
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            return parsed.astimezone(models.EASTERN).date().isoformat()
        except ValueError:
            pass
    return record.get("date")


def _team_rows(records):
    """Only current franchises, matching seed.py. /teams also returns 15 defunct
    clubs whose division is empty. Their conference is four spaces, which is
    truthy in Python, so the filter is on division."""
    rows = []
    for record in records:
        _require(record, ["id", "abbreviation", "full_name"], "team")
        if not (record.get("division") or "").strip():
            continue
        rows.append((record["id"], record["abbreviation"], record.get("city", ""),
                     record.get("name", ""), record["full_name"],
                     (record.get("conference") or "").strip(), record["division"]))
    return rows


def _player_rows(records):
    rows = []
    for record in records:
        _require(record, ["id", "first_name", "last_name", "team"], "player")
        team = record["team"]
        if not isinstance(team, dict) or "id" not in team:
            raise MalformedResponse("player record had no nested team id")
        rows.append((record["id"], record["first_name"], record["last_name"],
                     record.get("position"), record.get("height"),
                     record.get("weight"), record.get("jersey_number"), team["id"]))
    return rows


def _game_rows(records):
    rows = []
    for record in records:
        _require(record, ["id", "home_team", "visitor_team"], "game")
        home, visitor = record["home_team"], record["visitor_team"]
        if not (isinstance(home, dict) and isinstance(visitor, dict)):
            raise MalformedResponse("game record had no nested team objects")
        local = _local_date(record)
        if not local:
            raise MalformedResponse("game record had no usable date")
        rows.append((record["id"], local, record.get("datetime"),
                     record.get("season"), record.get("status"),
                     1 if record.get("postseason") else 0,
                     home["id"], visitor["id"],
                     record.get("home_team_score"),
                     record.get("visitor_team_score")))
    return rows


# Upsert on the API's own id. This is the natural-key invariant: re-running a
# refresh updates the same row instead of inserting a duplicate.
_UPSERT_TEAMS = """
INSERT INTO teams (id, abbreviation, city, name, full_name, conference, division)
VALUES (?,?,?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET
    abbreviation=excluded.abbreviation, city=excluded.city, name=excluded.name,
    full_name=excluded.full_name, conference=excluded.conference,
    division=excluded.division
"""

_UPSERT_PLAYERS = """
INSERT INTO players (id, first_name, last_name, position, height, weight,
                     jersey_number, team_id)
VALUES (?,?,?,?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET
    first_name=excluded.first_name, last_name=excluded.last_name,
    position=excluded.position, height=excluded.height, weight=excluded.weight,
    jersey_number=excluded.jersey_number, team_id=excluded.team_id
"""

_UPSERT_GAMES = """
INSERT INTO games (id, game_date_local, tipoff_utc, season, status, postseason,
                   home_team_id, visitor_team_id, home_team_score,
                   visitor_team_score)
VALUES (?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET
    game_date_local=excluded.game_date_local, tipoff_utc=excluded.tipoff_utc,
    season=excluded.season, status=excluded.status,
    postseason=excluded.postseason, home_team_id=excluded.home_team_id,
    visitor_team_id=excluded.visitor_team_id,
    home_team_score=excluded.home_team_score,
    visitor_team_score=excluded.visitor_team_score
"""


def refresh_cache(conn, fetch_fn=http_get, resources=("teams", "players", "games"),
                  date=None):
    """Refresh the API-cache tables. Never touches the app-owned tables.

    Fetch-all-then-write, in one transaction. A failure at any point -- a 429
    on page two, a malformed record, a dropped connection -- leaves the
    existing cache byte-for-byte unchanged.
    """
    payload = {}
    try:
        if "teams" in resources:
            payload["teams"] = _team_rows(fetch_teams(fetch_fn))
        if "players" in resources:
            payload["players"] = _player_rows(fetch_players(fetch_fn))
        if "games" in resources:
            payload["games"] = _game_rows(fetch_games(fetch_fn, date=date))
    except RefreshError as exc:
        return RefreshResult(False, reason=str(exc), kind=type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 -- deliberate boundary
        # A deliberately broad catch, and the only one in the codebase. This is
        # an out-of-band step: its caller is a scheduler or a CLI that wanted
        # fresher data, and an unhandled exception there takes down the whole
        # job rather than skipping one refresh. Nothing is hidden -- the
        # exception type and message are both reported on the result, so an
        # unexpected failure is still diagnosable. BaseException (KeyboardInt-
        # errupt, SystemExit) deliberately still propagates.
        return RefreshResult(False, reason=f"unexpected: {exc}",
                             kind=type(exc).__name__)

    written, skipped = {}, {}
    try:
        with conn:  # commits on success, rolls back on any exception
            if "teams" in payload:
                conn.executemany(_UPSERT_TEAMS, payload["teams"])
                written["teams"] = len(payload["teams"])

            # Players and games reference teams. Rows pointing at a franchise we
            # do not carry (a defunct club) are skipped rather than allowed to
            # fail the whole refresh on a foreign key violation.
            known = {r[0] for r in conn.execute("SELECT id FROM teams")}
            if "players" in payload:
                rows = [r for r in payload["players"] if r[7] in known]
                conn.executemany(_UPSERT_PLAYERS, rows)
                written["players"] = len(rows)
                skipped["players"] = len(payload["players"]) - len(rows)
            if "games" in payload:
                rows = [r for r in payload["games"]
                        if r[6] in known and r[7] in known]
                conn.executemany(_UPSERT_GAMES, rows)
                written["games"] = len(rows)
                skipped["games"] = len(payload["games"]) - len(rows)

            stamp = datetime.now(models.EASTERN).isoformat()
            conn.executemany(
                "INSERT INTO cache_meta (resource, fetched_at) VALUES (?,?) "
                "ON CONFLICT(resource) DO UPDATE SET fetched_at=excluded.fetched_at",
                [(name, stamp) for name in written],
            )
    except sqlite3.Error as exc:
        return RefreshResult(False, reason=f"database error: {exc}",
                             kind="DatabaseError")

    return RefreshResult(True, written=written, skipped=skipped)
