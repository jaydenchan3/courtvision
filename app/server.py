"""HTTP routes.

Phase 1 returns JSON so the backend can be verified before any HTML exists.
Phase 2 swaps the response layer for render_template; the auth, parameter
handling and error mapping below stay as they are.

No SQL lives here -- every query goes through app.data.queries.
"""

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from app import get_db, login_required
from app.data import models, queries

bp = Blueprint("main", __name__)

# Defined once because Phase 2 renders these and Phase 6 asserts on them. Two
# copies of the same sentence drift apart and the test stops meaning anything.
MSG_ROSTER_FULL = f"Roster is full ({models.ROSTER_MAX} players maximum)."
MSG_DUPLICATE = "That player is already on your roster."
MSG_UNKNOWN = "No such player."
MSG_NOT_ROSTERED = "That player is not on your roster."
# Distinct from MSG_UNKNOWN: the input was malformed, not merely absent.
MSG_INVALID = "Invalid player selection."


def rows(records):
    """sqlite3.Row is not JSON-serialisable; make plain dicts."""
    return [dict(r) for r in records]


def player_id_from_request():
    """Accepts a form post or JSON. Returns None when it is not an integer."""
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        return int(payload.get("player_id"))
    except (TypeError, ValueError):
        return None


@bp.get("/healthz")
def healthz():
    """Liveness only. Phase 8 CI polls a readiness endpoint instead of sleeping."""
    return jsonify(status="ok")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return jsonify(logged_in=bool(session.get("user")))

    payload = request.form if request.form else (request.get_json(silent=True) or {})
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if (username == current_app.config["DEMO_USER"]
            and password == current_app.config["DEMO_PASSWORD"]):
        session.clear()
        session["user"] = username
        return jsonify(ok=True, user=username)

    # Deliberately vague: saying which field was wrong tells an attacker
    # whether a username exists.
    return jsonify(ok=False, error="Invalid username or password"), 401


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/")
@login_required
def dashboard():
    db = get_db()
    today = models.today_local()
    games = queries.games_tonight(db, today)
    return jsonify(
        date=today,
        games=rows(games),
        # An empty list is a real answer ("no games tonight"), which the UI must
        # render differently from "we have not checked". Phase 2 uses this flag.
        no_games=not games,
        injuries=rows(queries.injury_report(db)),
        roster_count=queries.roster_count(db),
    )


@bp.get("/roster")
@login_required
def roster_view():
    db = get_db()
    return jsonify(
        players=rows(queries.roster(db)),
        count=queries.roster_count(db),
        max=models.ROSTER_MAX,
    )


@bp.post("/roster/add")
@login_required
def roster_add():
    """Translates the data layer's domain errors into HTTP responses.

    The data layer decides that something is invalid; the route decides how to
    say so. Keeping that split is what lets Phase 6 test the rules directly and
    the messages through the browser.
    """
    player_id = player_id_from_request()
    if player_id is None:
        return jsonify(ok=False, error=MSG_INVALID), 400
    try:
        queries.add_to_roster(get_db(), player_id)
    except queries.RosterFull:
        return jsonify(ok=False, error=MSG_ROSTER_FULL), 409
    except queries.DuplicatePlayer:
        return jsonify(ok=False, error=MSG_DUPLICATE), 409
    except queries.UnknownPlayer:
        return jsonify(ok=False, error=MSG_UNKNOWN), 404
    return jsonify(ok=True, player_id=player_id), 201


@bp.post("/roster/remove")
@login_required
def roster_remove():
    player_id = player_id_from_request()
    if player_id is None:
        return jsonify(ok=False, error=MSG_INVALID), 400
    if not queries.remove_from_roster(get_db(), player_id):
        return jsonify(ok=False, error=MSG_NOT_ROSTERED), 404
    return jsonify(ok=True, player_id=player_id)


@bp.get("/waiver")
@login_required
def waiver():
    """An unknown sort key falls back to the default rather than erroring.

    A column name cannot be parameterised, so queries.SORTABLE whitelists the
    permitted values; anything else simply misses and never becomes SQL.
    """
    sort = request.args.get("sort", queries.DEFAULT_SORT)
    team = (request.args.get("team") or "").strip() or None
    players = queries.waiver_players(get_db(), sort=sort, team=team)
    return jsonify(
        players=rows(players),
        sort=sort if sort in queries.SORTABLE else queries.DEFAULT_SORT,
        team=team,
        sortable=sorted(queries.SORTABLE),
        empty=not players,
    )


@bp.get("/search")
@login_required
def search():
    """A blank query is not an error and not 'everything' -- it is no results."""
    term = (request.args.get("q") or "").strip()
    results = queries.search_players(get_db(), term)
    return jsonify(
        query=term,
        results=rows(results),
        # Distinguishes "searched and found nothing" from "have not searched",
        # which the Phase 2 empty state renders differently.
        searched=bool(term),
        empty=bool(term) and not results,
    )
