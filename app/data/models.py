"""SQLite schema and connection handling for CourtVision.

Two categories of table, and the distinction is load-bearing:

  API CACHE  teams, players, games      Disposable. Refetchable from
                                        BALLDONTLIE. Safe to wipe.
  APP-OWNED  injuries, player_stats,    Not refetchable. user_roster is the
             user_roster                only data in the system that cannot
                                        be reconstructed from anywhere.

A cache refresh must never touch the app-owned tables.
"""

import os
import pathlib
import sqlite3
from datetime import datetime, timedelta, timezone

# The NBA schedules by US/Eastern date. A fixed offset is fine for the MVP:
# DST would shift a tip-off by an hour, not across a day boundary. Both the
# seed and the queries must agree on "today", so it is defined once, here.
EASTERN = timezone(timedelta(hours=-5))


def today_local():
    """Today's date in the league's timezone, as an ISO string."""
    return datetime.now(EASTERN).date().isoformat()

DEFAULT_DB = pathlib.Path(__file__).resolve().parents[2] / "courtvision.db"
DB_PATH = pathlib.Path(os.environ.get("COURTVISION_DB", DEFAULT_DB))

# Primary keys on teams/players/games are BALLDONTLIE's own ids (natural keys),
# not autoincrement. That makes refresh idempotent: re-fetching upserts the same
# row instead of duplicating it.
SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY,
    abbreviation  TEXT NOT NULL,
    city          TEXT NOT NULL,
    name          TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    conference    TEXT,
    division      TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id             INTEGER PRIMARY KEY,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    position       TEXT,
    height         TEXT,
    weight         TEXT,
    jersey_number  TEXT,
    team_id        INTEGER REFERENCES teams(id)
);

-- game_date_local is the US/Eastern calendar date, computed once at write time
-- so "tonight's games" is an indexed lookup, not timezone math in a WHERE.
CREATE TABLE IF NOT EXISTS games (
    id                  INTEGER PRIMARY KEY,
    game_date_local     TEXT NOT NULL,
    tipoff_utc          TEXT,
    season              INTEGER,
    status              TEXT,
    postseason          INTEGER NOT NULL DEFAULT 0,
    home_team_id        INTEGER NOT NULL REFERENCES teams(id),
    visitor_team_id     INTEGER NOT NULL REFERENCES teams(id),
    home_team_score     INTEGER,
    visitor_team_score  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date_local);

CREATE TABLE IF NOT EXISTS injuries (
    player_id    INTEGER PRIMARY KEY REFERENCES players(id),
    status       TEXT NOT NULL CHECK (status IN
                     ('out', 'doubtful', 'questionable', 'probable')),
    description  TEXT,
    updated_at   TEXT NOT NULL
);

-- Seeded, never fetched: assembling per-game averages would blow the
-- 5 req/min budget, and a computed trend would shift daily and break assertions.
CREATE TABLE IF NOT EXISTS player_stats (
    player_id     INTEGER PRIMARY KEY REFERENCES players(id),
    games_played  INTEGER NOT NULL DEFAULT 0,
    points_pg     REAL NOT NULL DEFAULT 0,
    rebounds_pg   REAL NOT NULL DEFAULT 0,
    assists_pg    REAL NOT NULL DEFAULT 0,
    trend         TEXT NOT NULL CHECK (trend IN ('up', 'flat', 'down'))
);

-- UNIQUE(player_id) is the database-level guarantee behind the "duplicate
-- player rejected" test. The 13-player cap is app logic: SQLite cannot express
-- "at most N rows", and the user needs a message, not an integrity error.
-- Deliberately NOT AUTOINCREMENT. That keyword makes SQLite remember the
-- highest id ever used in sqlite_sequence, which DELETE FROM does not reset,
-- so ids would climb on every re-seed and the seed would stop being
-- deterministic. Plain INTEGER PRIMARY KEY restarts at 1 on an empty table.
CREATE TABLE IF NOT EXISTS user_roster (
    id         INTEGER PRIMARY KEY,
    player_id  INTEGER NOT NULL UNIQUE REFERENCES players(id),
    added_at   TEXT NOT NULL
);

-- One row per cached resource. Lets the app distinguish "no games today" from
-- "we have not checked today" -- identical in the rows, different in the UI.
CREATE TABLE IF NOT EXISTS cache_meta (
    resource    TEXT PRIMARY KEY,
    fetched_at  TEXT NOT NULL
);
"""

ROSTER_MAX = 13

# Seconds before a cached resource is considered stale. Teams effectively never
# change; games are the only resource that genuinely moves day to day.
CACHE_TTL = {
    "teams": 60 * 60 * 24 * 365,
    "players": 60 * 60 * 24 * 7,
    "games": 60 * 60 * 24,
}


def use_database(path):
    """Point the whole application at a different SQLite file.

    The test suite calls this with a temp file so it never touches the
    developer's courtvision.db. Test isolation starts here: without a
    throwaway database, a suite that adds and removes roster players would
    mutate real state and stop being repeatable.
    """
    global DB_PATH
    DB_PATH = pathlib.Path(path)
    return DB_PATH


def get_connection():
    """Open a connection with foreign keys ON and dict-like rows.

    SQLite disables foreign key enforcement by default, per connection. Without
    this PRAGMA every REFERENCES clause above is documentation, not a constraint.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create any missing tables. Safe to run repeatedly."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    return DB_PATH
