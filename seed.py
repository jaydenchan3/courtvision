"""Deterministic seed data for CourtVision.

Puts the database into a known, fixed state so end-to-end tests can assert on
exact values. Reads only from spikes/samples/*.json, so it runs offline: no API
key, no quota, no 429. That is what lets the whole Selenium suite run in CI
with no secrets configured.

IDEMPOTENT: running this five times leaves the same state as running it once.

    python seed.py
"""

import json
import pathlib
from datetime import datetime, timedelta, timezone

from app.data import models

SAMPLES = pathlib.Path(__file__).parent / "spikes" / "samples"

# The NBA schedules by US/Eastern date. Fixed offset is fine for the MVP: the
# seed only needs to agree with itself, and DST would shift every game by an
# hour, not across a day boundary.
EASTERN = timezone(timedelta(hours=-5))

PLAYER_COUNT = 40
ROSTER_SIZE = 8

# player_id -> (status, description). Spread across rostered and unrostered
# players so the dashboard widget AND the waiver warnings both have data.
INJURIES = {
    3: ("out", "Left knee soreness"),
    5: ("questionable", "Ankle sprain"),
    9: ("probable", "Illness"),
    14: ("out", "Achilles strain"),
    18: ("doubtful", "Lower back tightness"),
    23: ("questionable", "Hamstring"),
    31: ("probable", "Wrist contusion"),
    37: ("out", "Concussion protocol"),
}


def current_teams():
    """The 30 active franchises.

    /teams returns 45 records: 30 current plus 15 defunct 1940s-50s franchises.
    Filter on division, NOT conference -- on defunct records conference is four
    spaces, and a whitespace string is truthy in Python.
    """
    teams = json.loads((SAMPLES / "teams.json").read_text())["data"]
    return [t for t in teams if t["division"].strip()]


def sample_players(valid_team_ids):
    players = json.loads((SAMPLES / "players_page.json").read_text())["data"]
    keep = [p for p in players if p["team"]["id"] in valid_team_ids]
    return keep[:PLAYER_COUNT]


def synthetic_stats(player_id):
    """Derived from the id, so it is stable across runs and machines.

    Real per-game averages would cost dozens of API calls at 5 req/min, and a
    computed trend would drift daily and break assertions.
    """
    return (
        60 + player_id % 20,                     # games_played
        round(6.0 + (player_id * 7 % 190) / 10, 1),   # points_pg
        round(2.0 + (player_id * 3 % 90) / 10, 1),    # rebounds_pg
        round(1.0 + (player_id * 5 % 70) / 10, 1),    # assists_pg
        ("up", "flat", "down")[player_id % 3],
    )


def seed():
    models.init_db()
    conn = models.get_connection()
    today = datetime.now(EASTERN).date().isoformat()

    # Children before parents: user_roster and injuries reference players,
    # players references teams. Foreign keys are ON, so the order is enforced.
    for table in ("user_roster", "injuries", "player_stats", "games",
                  "players", "teams", "cache_meta"):
        conn.execute(f"DELETE FROM {table}")

    teams = current_teams()
    conn.executemany(
        "INSERT INTO teams VALUES (?,?,?,?,?,?,?)",
        [(t["id"], t["abbreviation"], t["city"], t["name"], t["full_name"],
          t["conference"].strip(), t["division"]) for t in teams],
    )

    players = sample_players({t["id"] for t in teams})
    conn.executemany(
        "INSERT INTO players VALUES (?,?,?,?,?,?,?,?)",
        [(p["id"], p["first_name"], p["last_name"], p["position"], p["height"],
          p["weight"], p["jersey_number"], p["team"]["id"]) for p in players],
    )
    conn.executemany(
        "INSERT INTO player_stats VALUES (?,?,?,?,?,?)",
        [(p["id"], *synthetic_stats(p["id"])) for p in players],
    )

    # Exactly three games, dated today, so "tonight's games" is assertable on
    # any day the seed is run. Ids are in a synthetic range: these are fixtures,
    # not cached API rows, and must never collide with real game ids.
    pairs = [(t["id"], u["id"]) for t, u in zip(teams[:3], teams[3:6])]
    conn.executemany(
        "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(900_001 + i, today, f"{today}T23:30:00.000Z", 2025, "Scheduled", 0,
          home, away, None, None) for i, (home, away) in enumerate(pairs)],
    )

    seeded_ids = {p["id"] for p in players}
    conn.executemany(
        "INSERT INTO injuries VALUES (?,?,?,?)",
        [(pid, status, desc, today)
         for pid, (status, desc) in INJURIES.items() if pid in seeded_ids],
    )
    conn.executemany(
        "INSERT INTO user_roster (player_id, added_at) VALUES (?,?)",
        [(p["id"], today) for p in players[:ROSTER_SIZE]],
    )

    conn.commit()
    return conn, today


if __name__ == "__main__":
    conn, today = seed()
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("teams", "players", "player_stats", "games",
                        "injuries", "user_roster")}
    print(f"Seeded {models.DB_PATH}")
    print(f"  date (US/Eastern): {today}")
    for table, n in counts.items():
        print(f"  {table:14} {n}")
