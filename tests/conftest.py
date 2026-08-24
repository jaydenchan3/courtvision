"""Shared fixtures, arranged so the three test layers compose.

    unit         seeded_db                  one function, no HTTP, no browser
    integration  seeded_db -> client        app + routing via Flask's test
                                            client, still no browser
    e2e          test_db -> live_server
                          -> driver         a real browser against real HTTP

Each layer reuses the temp-database setup below it rather than duplicating it.
The pyramid matters: E2E is the slowest and most brittle layer, so it is
reserved for what genuinely needs a browser -- explicit waits, the async
dashboard, rendered rows. Anything the test client can prove is proved there.

Three deliberate Selenium decisions, unchanged:

1. NO IMPLICIT WAIT IS EVER SET. Implicit and explicit waits do not compose;
   mixing them produces unpredictable timeouts. Every wait is an explicit
   WebDriverWait on a named expected_condition, and there is no time.sleep.
2. Browser and server are SESSION scoped, data is FUNCTION scoped. Launching
   Chrome per test would dominate the runtime; sharing data would make tests
   order-dependent.
3. Readiness is polled, never slept on.
"""

import socket
import threading
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from app import create_app
from app.data import models

WAIT_TIMEOUT = 10          # seconds, for every explicit wait
READY_TIMEOUT = 20         # seconds, for the server to answer /healthz


def _free_port():
    """Bind port 0 and let the OS choose, so concurrent runs cannot collide."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db(tmp_path_factory):
    """Point the whole app at a throwaway file. The suite must never touch
    courtvision.db -- without that, a test that adds roster players would
    mutate real state and the suite would stop being repeatable."""
    path = tmp_path_factory.mktemp("courtvision") / "test.db"
    models.use_database(path)
    models.init_db()
    return path


@pytest.fixture
def seeded_db(test_db):
    """A connection to a freshly seeded database. The base of the pyramid:
    everything a unit test needs, with no server and no browser."""
    import seed
    seed.seed()
    conn = models.get_connection()
    yield conn
    conn.close()


# --------------------------------------------------------------------------
# integration layer
# --------------------------------------------------------------------------

@pytest.fixture
def client(seeded_db):
    """Flask test client over the seeded temp database.

    DASHBOARD_DELAY_MS is zeroed here: the delay exists to make the spinner
    observable in a browser, and paying it on every integration test would buy
    nothing. The delay itself is covered at the E2E layer, where it matters.
    """
    app = create_app({"TESTING": True, "DASHBOARD_DELAY_MS": 0})
    return app.test_client()


# --------------------------------------------------------------------------
# e2e layer
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_server(test_db):
    """A real HTTP server in a background thread. Selenium drives a real
    browser, which cannot reach Flask's test client."""
    app = create_app({"TESTING": True})
    port = _free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    import urllib.request
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            continue
    else:
        server.shutdown()
        pytest.fail("live server never became ready")

    yield base
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def driver():
    """One headless Chrome for the whole session.

    Selenium Manager resolves the matching chromedriver automatically, so
    there is no driver binary to install or version to keep in sync. Quitting
    in teardown matters: a driver that is not quit leaves orphaned chrome and
    chromedriver processes behind on every run.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    drv = webdriver.Chrome(options=options)
    yield drv
    drv.quit()


@pytest.fixture
def wait(driver):
    return WebDriverWait(driver, WAIT_TIMEOUT)


@pytest.fixture(autouse=True)
def fresh_browser_state(request):
    """Reset BOTH halves of the shared state before every browser test.

    Server state: re-seed, so one test cannot leak into the next.

    Browser state: the driver is session scoped, so its cookies outlive a
    test. Without clearing them a test that logs in leaves the next already
    authenticated, /login redirects instead of rendering a form, and tests
    pass alone but fail in a suite. Resetting the database is not sufficient
    isolation when the client is shared too.

    Only applies to the E2E layer; unit and integration tests get their fresh
    state from seeded_db.
    """
    if "live_server" not in request.fixturenames:
        yield
        return

    import seed
    seed.seed()
    if "driver" in request.fixturenames:
        driver = request.getfixturevalue("driver")
        base = request.getfixturevalue("live_server")
        # Cookies can only be cleared while on the origin that set them.
        driver.get(base + "/healthz")
        driver.delete_all_cookies()
    yield


@pytest.fixture
def logged_in(driver, live_server):
    """Most browser tests start authenticated; the auth tests do not use this."""
    from tests.pages.login_page import LoginPage
    page = LoginPage(driver, live_server)
    page.load()
    page.sign_in("demo", "courtvision")
    return page
