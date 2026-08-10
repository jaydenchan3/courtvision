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


def rows(records):
    """sqlite3.Row is not JSON-serialisable; make plain dicts."""
    return [dict(r) for r in records]


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
