"""CourtVision application factory.

create_app() builds a fresh app per call instead of a module-level
`app = Flask(__name__)`. That matters for testing: the Selenium suite needs an
app pointed at a scratch database, and a global app bakes its configuration in
at import time. It also keeps importing this module free of side effects.
"""

import functools
import os
import secrets

from flask import Flask, g, redirect, request, session, url_for

from app.data import models


def get_db():
    """One connection per request, reused within it, stored on flask.g."""
    if "db" not in g:
        g.db = models.get_connection()
    return g.db


def close_db(exc=None):
    """Closes the request's connection whether the view returned or raised.

    Without this, connections leak: file handles accumulate and SQLite starts
    reporting lock errors that look random and are not.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(view):
    """Redirect anonymous users to the login page, remembering where they went.

    The Phase 6 plan tests exactly this: a protected route while logged out
    must redirect rather than render.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        # Flask signs the session cookie with this. A hardcoded key in a public
        # repo lets anyone forge a signed cookie and skip login, so it comes
        # from the environment. The random fallback keeps development working
        # while making sessions die on restart -- a visible nudge to set it.
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        # Single-user by design: multi-user auth is an explicit scope guard.
        DEMO_USER=os.environ.get("COURTVISION_USER", "demo"),
        DEMO_PASSWORD=os.environ.get("COURTVISION_PASSWORD", "courtvision"),
        # Deliberate delay on the dashboard data fetch. This is what makes
        # the spinner observable and explicit waits necessary.
        DASHBOARD_DELAY_MS=int(os.environ.get("DASHBOARD_DELAY_MS", "400")),
    )
    if config:
        app.config.update(config)

    app.teardown_appcontext(close_db)

    # Imported here, not at module scope, to avoid a circular import:
    # app.server needs get_db and login_required from this module.
    from app.server import bp

    app.register_blueprint(bp)
    return app
