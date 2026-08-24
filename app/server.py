"""HTTP routes.

The dashboard is deliberately NOT server-rendered: it serves a shell and
fetches /api/dashboard after load, behind an artificial delay. Content that
appears asynchronously is what makes explicit waits necessary, and that page
is the basis of the wait tests. Roster, waiver and search are ordinary
server-rendered form flows, so the suite covers both styles.

No SQL lives here -- every query goes through app.data.queries.
"""

import time

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)

from app import get_db, login_required
from app.data import models, queries

bp = Blueprint("main", __name__)

# Defined once because the templates render these and the tests import them.
# Two copies of the same sentence drift apart and the assertion stops meaning
# anything.
MSG_ROSTER_FULL = f"Roster is full ({models.ROSTER_MAX} players maximum)."
MSG_DUPLICATE = "That player is already on your roster."
MSG_UNKNOWN = "No such player."
MSG_NOT_ROSTERED = "That player is not on your roster."
MSG_INVALID = "Invalid player selection."
MSG_BAD_LOGIN = "Invalid username or password."


def safe_next(target):
    """Only allow same-site relative redirects.

    Without this, /login?next=https://evil.example turns our own login page
    into a phishing hop. A protocol-relative //host is rejected too.
    """
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


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
    """Readiness probe. CI and the live-server fixture poll this instead of
    sleeping for an arbitrary number of seconds."""
    return jsonify(status="ok")


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.values.get("next"))

    if request.method == "GET":
        if session.get("user"):
            return redirect(next_url or url_for("main.dashboard"))
        return render_template("login.html", next_url=next_url)

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if (username == current_app.config["DEMO_USER"]
            and password == current_app.config["DEMO_PASSWORD"]):
        # Clearing first prevents session fixation.
        session.clear()
        session["user"] = username
        return redirect(next_url or url_for("main.dashboard"))

    # 401 and re-render in place: the URL must not change, which is what the
    # failed-login test asserts on.
    return render_template("login.html", error=MSG_BAD_LOGIN,
                           username=username, next_url=next_url), 401


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.get("/")
@login_required
def dashboard():
    """Shell only. The data arrives via fetch from /api/dashboard."""
    return render_template("dashboard.html", date_param=request.args.get("date", ""))


@bp.get("/api/dashboard")
@login_required
def api_dashboard():
    # Deliberate delay so the spinner is genuinely observable. Without it the
    # fetch resolves too fast to teach anything, and a sloppy test would pass
    # by luck rather than because it waits correctly.
    time.sleep(current_app.config["DASHBOARD_DELAY_MS"] / 1000)

    db = get_db()
    # An explicit ?date= makes a zero-games state reachable deterministically,
    # which is how the empty-state test avoids depending on the calendar.
    date = request.args.get("date") or models.today_local()
    games = queries.games_tonight(db, date)
    return jsonify(
        date=date,
        games=rows(games),
        no_games=not games,
        injuries=rows(queries.injury_report(db)),
        roster_count=queries.roster_count(db),
    )


@bp.get("/roster")
@login_required
def roster_view():
    db = get_db()
    return render_template(
        "roster.html",
        players=rows(queries.roster(db)),
        available=rows(queries.waiver_players(db, sort="name")),
        count=queries.roster_count(db),
        max=models.ROSTER_MAX,
    )


@bp.post("/roster/add")
@login_required
def roster_add():
    """The data layer decides that something is invalid; the route decides how
    to say so. That split lets the rules be tested directly and the messages
    through the browser."""
    player_id = player_id_from_request()
    if player_id is None:
        flash(MSG_INVALID, "error")
        return redirect(url_for("main.roster_view"))
    try:
        queries.add_to_roster(get_db(), player_id)
    except queries.RosterFull:
        flash(MSG_ROSTER_FULL, "error")
    except queries.DuplicatePlayer:
        flash(MSG_DUPLICATE, "error")
    except queries.UnknownPlayer:
        flash(MSG_UNKNOWN, "error")
    else:
        flash("Player added to your roster.", "success")
    return redirect(url_for("main.roster_view"))


@bp.post("/roster/remove")
@login_required
def roster_remove():
    player_id = player_id_from_request()
    if player_id is None:
        flash(MSG_INVALID, "error")
    elif not queries.remove_from_roster(get_db(), player_id):
        flash(MSG_NOT_ROSTERED, "error")
    else:
        flash("Player removed from your roster.", "success")
    return redirect(url_for("main.roster_view"))


@bp.get("/waiver")
@login_required
def waiver():
    """An unknown sort key falls back to the default rather than erroring: a
    column name cannot be parameterised, so queries.SORTABLE whitelists the
    permitted values and anything else never becomes SQL."""
    db = get_db()
    requested = request.args.get("sort", queries.DEFAULT_SORT)
    sort = requested if requested in queries.SORTABLE else queries.DEFAULT_SORT
    team = (request.args.get("team") or "").strip() or None
    players = rows(queries.waiver_players(db, sort=requested, team=team))
    teams = [r[0] for r in db.execute(
        "SELECT DISTINCT abbreviation FROM teams ORDER BY abbreviation")]
    return render_template("waiver.html", players=players, sort=sort, team=team,
                           sortable=sorted(queries.SORTABLE), teams=teams)


@bp.get("/search")
@login_required
def search():
    """A blank query is not an error and not 'everything' -- it is the
    not-yet-searched state, which the page renders distinctly from a search
    that found nothing."""
    term = (request.args.get("q") or "").strip()
    results = rows(queries.search_players(get_db(), term))
    return render_template("search.html", query=term, results=results,
                           searched=bool(term), empty=bool(term) and not results)
