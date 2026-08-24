"""Unit layer: data-access functions called directly against a seeded database.

No HTTP, no browser, no Flask app. These cover the query and rule logic that
would otherwise only be exercised through three slower layers of indirection.
Behaviour proved here is deliberately not re-proved in the browser.
"""

import pytest

from app.data import models, queries

pytestmark = pytest.mark.unit


# -- reads -----------------------------------------------------------------

def test_games_tonight_returns_the_seeded_games(seeded_db):
    games = queries.games_tonight(seeded_db)
    assert len(games) == 3
    assert {g["game_date_local"] for g in games} == {models.today_local()}


def test_games_tonight_on_an_empty_day_returns_empty_list(seeded_db):
    """Zero games is a valid answer, not an error. The route turns this into
    the confident 'No games scheduled tonight' state."""
    assert queries.games_tonight(seeded_db, "1999-01-01") == []


def test_games_join_both_team_names(seeded_db):
    game = queries.games_tonight(seeded_db)[0]
    assert game["home"] and game["visitor"]
    assert game["home"] != game["visitor"]


def test_injury_report_is_ordered_worst_first(seeded_db):
    """The widget must lead with players who are actually out."""
    statuses = [r["injury_status"] for r in queries.injury_report(seeded_db)]
    rank = {"out": 0, "doubtful": 1, "questionable": 2, "probable": 3}
    assert len(statuses) == 8
    assert [rank[s] for s in statuses] == sorted(rank[s] for s in statuses)
    assert statuses[0] == "out"


def test_roster_and_count_agree(seeded_db):
    roster = queries.roster(seeded_db)
    assert len(roster) == 8
    assert queries.roster_count(seeded_db) == 8


# -- waiver ----------------------------------------------------------------

def test_waiver_excludes_rostered_players(seeded_db):
    rostered = {r["id"] for r in queries.roster(seeded_db)}
    available = {p["id"] for p in queries.waiver_players(seeded_db)}
    assert rostered & available == set()
    assert len(available) == 32


def test_waiver_default_sort_is_points_descending(seeded_db):
    points = [p["points_pg"] for p in queries.waiver_players(seeded_db)]
    assert points == sorted(points, reverse=True)


def test_waiver_team_filter_narrows_results(seeded_db):
    filtered = queries.waiver_players(seeded_db, team="CLE")
    assert filtered
    assert {p["team"] for p in filtered} == {"CLE"}
    assert len(filtered) < len(queries.waiver_players(seeded_db))


def test_waiver_hostile_sort_falls_back_and_leaves_the_table_intact(seeded_db):
    """A column name cannot be parameterised, so the sort key is whitelisted:
    an unknown value is looked up, misses, and never becomes SQL."""
    expected = [p["id"] for p in queries.waiver_players(seeded_db)]

    hostile = queries.waiver_players(seeded_db, sort="; DROP TABLE players")

    assert [p["id"] for p in hostile] == expected
    assert seeded_db.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 40


@pytest.mark.parametrize("sort_key", sorted(queries.SORTABLE))
def test_every_whitelisted_sort_key_returns_the_full_set(seeded_db, sort_key):
    assert len(queries.waiver_players(seeded_db, sort=sort_key)) == 32


# -- search ----------------------------------------------------------------

def test_search_finds_matching_players(seeded_db):
    results = queries.search_players(seeded_db, "allen")
    assert len(results) == 2
    assert all("Allen" in r["last_name"] for r in results)


def test_search_is_case_insensitive(seeded_db):
    assert queries.search_players(seeded_db, "ADAMS")


def test_search_unknown_term_returns_empty(seeded_db):
    assert queries.search_players(seeded_db, "zzzznotaplayer") == []


@pytest.mark.parametrize("term", ["", "   ", None])
def test_search_blank_returns_nothing_not_everything(seeded_db, term):
    """A blank query must not silently mean 'select all'."""
    assert queries.search_players(seeded_db, term) == []


# -- roster mutations ------------------------------------------------------

def test_add_to_roster_adds_the_player(seeded_db):
    candidate = queries.waiver_players(seeded_db)[0]["id"]
    queries.add_to_roster(seeded_db, candidate)

    assert queries.roster_count(seeded_db) == 9
    assert candidate in {r["id"] for r in queries.roster(seeded_db)}


def test_add_duplicate_raises(seeded_db):
    """Enforced by UNIQUE(player_id) in the schema, not a Python pre-check --
    a check-then-insert has a time-of-check/time-of-use gap."""
    existing = queries.roster(seeded_db)[0]["id"]
    with pytest.raises(queries.DuplicatePlayer):
        queries.add_to_roster(seeded_db, existing)
    assert queries.roster_count(seeded_db) == 8


def test_add_unknown_player_raises(seeded_db):
    with pytest.raises(queries.UnknownPlayer):
        queries.add_to_roster(seeded_db, 999999)


def test_add_past_the_cap_raises(seeded_db):
    """The cap is application logic because SQLite cannot express
    'at most N rows' as a constraint."""
    while queries.roster_count(seeded_db) < models.ROSTER_MAX:
        queries.add_to_roster(seeded_db, queries.waiver_players(seeded_db)[0]["id"])

    with pytest.raises(queries.RosterFull):
        queries.add_to_roster(seeded_db, queries.waiver_players(seeded_db)[0]["id"])
    assert queries.roster_count(seeded_db) == models.ROSTER_MAX


def test_remove_returns_true_when_present_false_when_absent(seeded_db):
    target = queries.roster(seeded_db)[0]["id"]
    assert queries.remove_from_roster(seeded_db, target) is True
    assert queries.remove_from_roster(seeded_db, target) is False
    assert queries.roster_count(seeded_db) == 7


def test_each_test_starts_from_the_seeded_state(seeded_db):
    """Isolation guard: the tests above leave the roster at 13, 9 and 7."""
    assert queries.roster_count(seeded_db) == 8
