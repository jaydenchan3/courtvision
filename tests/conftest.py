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

import os
import pathlib
import re
import socket
import threading
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from app import create_app
from app.data import models

WAIT_TIMEOUT = int(os.environ.get("SELENIUM_WAIT_TIMEOUT", "10"))
READY_TIMEOUT = 20         # seconds, for the server to answer /healthz


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """On a browser-test failure, save where the browser actually was.

    A headless run cannot be watched, so a timeout waiting for an element tells
    you nothing about why -- the single most useful fact is usually that the
    browser was on a different page than the test assumed. URL, title and a
    screenshot are written to the artifacts directory, which docker-compose
    mounts from the host so they outlive the container.
    """
    report = yield
    if report.when != "call" or not report.failed:
        return report
    driver = item.funcargs.get("driver") if hasattr(item, "funcargs") else None
    if driver is None:
        return report

    out = pathlib.Path(os.environ.get("TEST_ARTIFACTS", "reports"))
    try:
        out.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", item.nodeid)[:120]
        (out / f"{name}.txt").write_text(
            f"url:   {driver.current_url}\ntitle: {driver.title}\n", encoding="utf-8")
        driver.save_screenshot(str(out / f"{name}.png"))
    except Exception:
        # Diagnostics must never turn a test failure into an error.
        pass
    return report


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

    On a laptop, Selenium Manager resolves the matching chromedriver itself, so
    there is nothing to install or pin. In the container CHROME_BIN and
    CHROMEDRIVER_BIN point at the distro's chromium packages instead, which
    keeps the image self-contained: no driver download at test time, and browser
    and driver versions matched by the package manager. Same test code either
    way -- when the variables are unset this behaves exactly as before.

    Quitting in teardown matters: a driver that is not quit leaves orphaned
    chrome and chromedriver processes behind on every run.
    """
    options = Options()
    options.add_argument("--headless=new")
    # --no-sandbox is required as root in a container; --disable-dev-shm-usage
    # avoids Chrome crashing on the default 64MB /dev/shm that Docker provides.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Trim work that a headless test browser never needs. None of this changes
    # what is being tested; it lowers Chrome's startup and background cost,
    # which is what pushes a contended container past its wait budgets.
    for flag in ("--disable-gpu", "--disable-extensions", "--no-first-run",
                 "--no-default-browser-check", "--disable-background-networking",
                 "--disable-renderer-backgrounding",
                 "--disable-backgrounding-occluded-windows"):
        options.add_argument(flag)

    browser = os.environ.get("CHROME_BIN")
    if browser:
        options.binary_location = browser

    driver_path = os.environ.get("CHROMEDRIVER_BIN")
    service = ChromeService(executable_path=driver_path) if driver_path else None

    drv = webdriver.Chrome(options=options, service=service)
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
    """Most browser tests start authenticated; the auth tests do not use this.

    The sign-in is verified before the fixture hands back. sign_in() resolves on
    either outcome -- navigated, or an error appeared -- so on its own it can
    return with the browser still anonymous, and the test then fails somewhere
    downstream with a timeout that points at the wrong thing. Asserting the
    authenticated nav here fails at the cause instead.
    """
    from tests.pages.base_page import BasePage
    from tests.pages.login_page import LoginPage

    page = LoginPage(driver, live_server)
    page.load()
    page.sign_in("demo", "courtvision")
    page.wait_until(
        lambda d: d.find_elements(*BasePage.NAV),
        "logged_in fixture: sign-in did not produce an authenticated session",
    )
    return page
