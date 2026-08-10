"""Read and write helpers over the SQLite tables.

Every SQL statement in the application lives here. Routes call these functions
and never build queries themselves, so the data layer stays testable without
HTTP or a browser, and a schema change touches one file instead of every view.
"""

import sqlite3

from app.data import models


class RosterFull(Exception):
    """Roster is at ROSTER_MAX. Enforced here: SQLite cannot express it."""


class DuplicatePlayer(Exception):
    """Player is already rostered. Enforced by UNIQUE(player_id) in the schema."""


class UnknownPlayer(Exception):
    """No such player id."""


# A column name cannot be parameterised -- ORDER BY ? is invalid SQL. Building
# the clause with an f-string would be a SQL injection hole, so the caller's
# choice must be a member of this set or it is ignored.
SORTABLE = {
    "points": "s.points_pg DESC",
    "rebounds": "s.rebounds_pg DESC",
    "assists": "s.assists_pg DESC",
    "name": "p.last_name ASC",
}
DEFAULT_SORT = "points"

_PLAYER_SELECT = """
    SELECT p.id, p.first_name, p.last_name, p.position,
           t.abbreviation AS team, t.full_name AS team_name,
           s.points_pg, s.rebounds_pg, s.assists_pg, s.trend,
           i.status AS injury_status, i.description AS injury_note
      FROM players p
      JOIN teams t ON t.id = p.team_id
 LEFT JOIN player_stats s ON s.player_id = p.id
 LEFT JOIN injuries i ON i.player_id = p.id
"""


def games_tonight(conn, date=None):
    """Games on the league-local date. Empty list is a valid answer."""
    date = date or models.today_local()
    return conn.execute(
        """SELECT g.id, g.game_date_local, g.tipoff_utc, g.status,
                  h.abbreviation AS home, h.full_name AS home_name,
                  v.abbreviation AS visitor, v.full_name AS visitor_name,
                  g.home_team_score, g.visitor_team_score
             FROM games g
             JOIN teams h ON h.id = g.home_team_id
             JOIN teams v ON v.id = g.visitor_team_id
            WHERE g.game_date_local = ?
         ORDER BY g.tipoff_utc, g.id""",
        (date,),
    ).fetchall()


def injury_report(conn):
    """Every injured player, worst first, so the widget leads with the outs."""
    return conn.execute(
        _PLAYER_SELECT + """
        WHERE i.status IS NOT NULL
     ORDER BY CASE i.status WHEN 'out' THEN 0 WHEN 'doubtful' THEN 1
                            WHEN 'questionable' THEN 2 ELSE 3 END,
              p.last_name"""
    ).fetchall()


def roster(conn):
    return conn.execute(
        _PLAYER_SELECT + """
        JOIN user_roster r ON r.player_id = p.id
    ORDER BY r.id"""
    ).fetchall()


def waiver_players(conn, sort=DEFAULT_SORT, team=None):
    """Players not on the roster. `sort` is whitelisted, `team` is a filter."""
    order = SORTABLE.get(sort, SORTABLE[DEFAULT_SORT])
    sql = _PLAYER_SELECT + """
        WHERE p.id NOT IN (SELECT player_id FROM user_roster)"""
    params = []
    if team:
        sql += " AND t.abbreviation = ?"
        params.append(team)
    return conn.execute(f"{sql} ORDER BY {order}", params).fetchall()


def search_players(conn, term):
    """Name search. A blank term returns nothing, not everything."""
    term = (term or "").strip()
    if not term:
        return []
    like = f"%{term}%"
    return conn.execute(
        _PLAYER_SELECT + """
        WHERE p.first_name LIKE ? OR p.last_name LIKE ?
           OR (p.first_name || ' ' || p.last_name) LIKE ?
     ORDER BY p.last_name""",
        (like, like, like),
    ).fetchall()


def roster_count(conn):
    return conn.execute("SELECT COUNT(*) FROM user_roster").fetchone()[0]


def add_to_roster(conn, player_id):
    """Cap is checked here; duplicates are caught by the UNIQUE constraint."""
    if not conn.execute("SELECT 1 FROM players WHERE id = ?", (player_id,)).fetchone():
        raise UnknownPlayer(player_id)
    if roster_count(conn) >= models.ROSTER_MAX:
        raise RosterFull(models.ROSTER_MAX)
    try:
        conn.execute(
            "INSERT INTO user_roster (player_id, added_at) VALUES (?, ?)",
            (player_id, models.today_local()),
        )
    except sqlite3.IntegrityError as exc:
        raise DuplicatePlayer(player_id) from exc
    conn.commit()


def remove_from_roster(conn, player_id):
    """Returns True if a row was removed, False if it was not there."""
    removed = conn.execute(
        "DELETE FROM user_roster WHERE player_id = ?", (player_id,)
    ).rowcount
    conn.commit()
    return bool(removed)
