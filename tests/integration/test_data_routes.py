"""Integration layer: dashboard, roster, waiver and search routes.

Status codes and message constants are asserted here rather than in the
browser -- the E2E layer only needs to prove they reach the rendered page.
"""

import pytest

from app.data import models, queries
from app.server import (MSG_DUPLICATE, MSG_INVALID, MSG_NOT_ROSTERED,
                        MSG_ROSTER_FULL, MSG_UNKNOWN)

pytestmark = pytest.mark.integration


@pytest.fixture
def auth(client):
    client.post("/login", data={"username": "demo", "password": "courtvision"})
    return client


# -- dashboard -------------------------------------------------------------

@pytest.mark.dashboard
def test_dashboard_json_carries_games_injuries_and_count(auth):
    body = auth.get("/api/dashboard").get_json()

    assert body["date"] == models.today_local()
    assert len(body["games"]) == 3
    assert len(body["injuries"]) == 8
    assert body["roster_count"] == 8
    assert body["no_games"] is False


@pytest.mark.dashboard
def test_dashboard_no_games_flag_on_an_empty_day(auth):
    """?date= makes the zero-games state reachable without waiting for a real
    day with no fixtures, so the empty-state assertion is calendar-independent."""
    body = auth.get("/api/dashboard?date=1999-01-01").get_json()

    assert body["games"] == []
    assert body["no_games"] is True


@pytest.mark.dashboard
def test_dashboard_shell_renders_both_state_containers(auth):
    html = auth.get("/").get_data(as_text=True)
    assert 'data-testid="dashboard-loading"' in html
    assert 'data-testid="dashboard-content"' in html


# -- roster ----------------------------------------------------------------

@pytest.mark.roster
def test_roster_page_renders_the_seeded_rows(auth):
    html = auth.get("/roster").get_data(as_text=True)
    assert html.count('data-testid="roster-row"') == 8


@pytest.mark.roster
def test_add_redirects_and_grows_the_roster(auth, seeded_db):
    """Roster mutations use Post/Redirect/Get, so the response is a 302 and the
    outcome is reported by a flash on the followed page. PRG is deliberate: it
    stops a browser refresh from re-submitting the add."""
    candidate = queries.waiver_players(seeded_db)[0]["id"]
    response = auth.post("/roster/add", data={"player_id": candidate})

    assert response.status_code == 302
    assert response.headers["Location"] == "/roster"

    html = auth.get("/roster").get_data(as_text=True)
    assert html.count('data-testid="roster-row"') == 9
    assert f'data-id="{candidate}"' in html


@pytest.mark.roster
def test_duplicate_add_flashes_the_message_constant(auth, seeded_db):
    existing = queries.roster(seeded_db)[0]["id"]
    html = auth.post("/roster/add", data={"player_id": existing},
                     follow_redirects=True).get_data(as_text=True)

    assert MSG_DUPLICATE in html
    assert 'data-testid="flash-error"' in html
    assert html.count('data-testid="roster-row"') == 8


@pytest.mark.roster
def test_unknown_player_flashes_unknown(auth):
    html = auth.post("/roster/add", data={"player_id": 999999},
                     follow_redirects=True).get_data(as_text=True)
    assert MSG_UNKNOWN in html


@pytest.mark.roster
def test_malformed_player_id_flashes_a_distinct_message(auth):
    """Malformed input is not the same as a player that does not exist, and the
    two messages must not be interchangeable."""
    html = auth.post("/roster/add", data={"player_id": "banana"},
                     follow_redirects=True).get_data(as_text=True)

    assert MSG_INVALID in html
    assert MSG_INVALID != MSG_UNKNOWN


@pytest.mark.roster
def test_adding_past_the_cap_flashes_roster_full(auth, seeded_db):
    while queries.roster_count(seeded_db) < models.ROSTER_MAX:
        queries.add_to_roster(seeded_db, queries.waiver_players(seeded_db)[0]["id"])

    candidate = queries.waiver_players(seeded_db)[0]["id"]
    html = auth.post("/roster/add", data={"player_id": candidate},
                     follow_redirects=True).get_data(as_text=True)

    assert MSG_ROSTER_FULL in html
    assert html.count('data-testid="roster-row"') == models.ROSTER_MAX


@pytest.mark.roster
def test_remove_succeeds_then_reports_not_rostered(auth, seeded_db):
    target = queries.roster(seeded_db)[0]["id"]

    first = auth.post("/roster/remove", data={"player_id": target},
                      follow_redirects=True).get_data(as_text=True)
    assert 'data-testid="flash-success"' in first
    assert first.count('data-testid="roster-row"') == 7

    second = auth.post("/roster/remove", data={"player_id": target},
                       follow_redirects=True).get_data(as_text=True)
    assert MSG_NOT_ROSTERED in second


# -- waiver ----------------------------------------------------------------

@pytest.mark.waiver
def test_waiver_lists_unrostered_players_with_the_sort_control(auth):
    html = auth.get("/waiver").get_data(as_text=True)
    assert html.count('data-testid="waiver-row"') == 32
    assert 'id="waiver-sort"' in html


@pytest.mark.waiver
def test_waiver_team_filter_narrows_the_page(auth):
    html = auth.get("/waiver?team=CLE").get_data(as_text=True)
    assert 0 < html.count('data-testid="waiver-row"') < 32


@pytest.mark.waiver
def test_waiver_hostile_sort_falls_back_and_leaves_the_table_intact(auth):
    default = auth.get("/waiver").get_data(as_text=True)
    hostile = auth.get("/waiver?sort='; DROP TABLE players--").get_data(as_text=True)

    assert hostile.count('data-testid="waiver-row"') == 32
    assert _names(hostile) == _names(default)
    assert models.get_connection().execute(
        "SELECT COUNT(*) FROM players").fetchone()[0] == 40


@pytest.mark.waiver
def test_waiver_offers_exactly_the_whitelisted_sort_keys(auth):
    html = auth.get("/waiver").get_data(as_text=True)
    for key in queries.SORTABLE:
        assert f'value="{key}"' in html


# -- search ----------------------------------------------------------------

@pytest.mark.search
def test_search_initial_state_prompts_rather_than_reporting_no_results(auth):
    """'Has not searched' and 'searched, found nothing' are different states.
    Collapsing them makes the page claim a search failed that never ran."""
    html = auth.get("/search").get_data(as_text=True)

    assert 'data-testid="search-prompt"' in html
    assert 'data-testid="search-empty"' not in html


@pytest.mark.search
def test_search_match_renders_rows(auth):
    html = auth.get("/search?q=allen").get_data(as_text=True)
    assert html.count('data-testid="search-row"') == 2
    assert 'data-testid="search-prompt"' not in html


@pytest.mark.search
def test_search_unknown_term_renders_the_empty_state(auth):
    html = auth.get("/search?q=zzzznotaplayer").get_data(as_text=True)

    assert 'data-testid="search-empty"' in html
    assert 'data-testid="search-prompt"' not in html
    assert html.count('data-testid="search-row"') == 0


@pytest.mark.search
def test_whitespace_query_is_treated_as_not_searched(auth):
    html = auth.get("/search?q=%20%20").get_data(as_text=True)
    assert 'data-testid="search-prompt"' in html


def _names(html):
    import re
    return re.findall(r'data-testid="waiver-player-name">([^<]+)', html)
