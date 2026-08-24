"""Fixtures for the end-to-end suite.

Three deliberate decisions:

1. NO IMPLICIT WAIT IS EVER SET. Selenium's implicit wait and explicit
   WebDriverWait do not compose -- mixing them produces unpredictable, often
   much longer, timeouts. Every wait in this suite is an explicit
   WebDriverWait on a named expected_condition, and there is no time.sleep
   anywhere.

2. The browser and the server are SESSION scoped; the DATA is FUNCTION
   scoped. Launching Chrome per test would dominate the runtime, but sharing
   data between tests would make them order-dependent. So the expensive thing
   is shared and the state is reset before every test.

3. Readiness is polled, never slept on. The live_server fixture hits /healthz
   until it answers, so a slow start delays the suite rather than breaking it.
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


@pytest.fixture(scope="session")
def test_db(tmp_path_factory):
    """A throwaway database. The suite must never touch courtvision.db."""
    path = tmp_path_factory.mktemp("courtvision") / "test.db"
    models.use_database(path)
    models.init_db()
    return path


@pytest.fixture(scope="session")
def live_server(test_db):
    """A real HTTP server in a background thread.

    Selenium drives a real browser, so it needs a real origin -- Flask's test
    client is not reachable from Chrome.
    """
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
    there is no driver binary to install or version to keep in sync.
    Quitting in teardown matters: a driver that is not quit leaves orphaned
    chrome and chromedriver processes behind on every run.
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
def fresh_state(test_db, request):
    """Reset BOTH halves of the shared state before every test.

    Server state: re-seed the database, so a test that adds or removes roster
    players cannot influence the next one. Safe under a running server because
    the app opens a connection per request and closes it in teardown.

    Browser state: the driver is session scoped, so its cookies outlive a test.
    Without clearing them, a test that logs in leaves the next one already
    authenticated -- /login then redirects instead of rendering a form, and
    tests pass alone but fail in a suite. Resetting the database is not
    sufficient isolation when the client is shared too.
    """
    needs_server = "live_server" in request.fixturenames
    if needs_server or "driver" in request.fixturenames:
        import seed
        seed.seed()
    if needs_server and "driver" in request.fixturenames:
        driver = request.getfixturevalue("driver")
        base = request.getfixturevalue("live_server")
        # Cookies can only be cleared while on the origin that set them.
        driver.get(base + "/healthz")
        driver.delete_all_cookies()
    yield


@pytest.fixture
def logged_in(driver, live_server):
    """Most tests start authenticated; the auth tests do not use this."""
    from tests.pages.login_page import LoginPage
    page = LoginPage(driver, live_server)
    page.load()
    page.sign_in("demo", "courtvision")
    return page
