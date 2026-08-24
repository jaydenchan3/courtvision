"""Authentication, session, and protected-route behaviour."""

import pytest

from app.server import MSG_BAD_LOGIN
from tests.pages.dashboard_page import DashboardPage
from tests.pages.login_page import LoginPage
from tests.pages.roster_page import RosterPage

pytestmark = pytest.mark.auth


def test_valid_login_reaches_dashboard(driver, live_server):
    page = LoginPage(driver, live_server).load()
    page.sign_in("demo", "courtvision")

    dashboard = DashboardPage(driver, live_server)
    assert dashboard.current_path == "/"
    assert dashboard.has_nav()


def test_invalid_password_shows_error_and_does_not_navigate(driver, live_server):
    """The URL must not change. A redirect-and-flash implementation would let a
    test pass while the user was actually navigated away and back."""
    page = LoginPage(driver, live_server).load()
    page.sign_in("demo", "wrong-password")

    assert page.current_path == "/login"
    assert page.error_text() == MSG_BAD_LOGIN
    assert not page.has_nav()


def test_unknown_username_gives_the_same_message(driver, live_server):
    """Identical wording for a bad user and a bad password: a different message
    would let an attacker enumerate valid usernames."""
    page = LoginPage(driver, live_server).load()
    page.sign_in("not-a-user", "courtvision")
    assert page.error_text() == MSG_BAD_LOGIN


def test_protected_route_while_logged_out_redirects_with_next(driver, live_server):
    RosterPage(driver, live_server).visit()
    page = LoginPage(driver, live_server)
    page.wait_visible(page.FORM)
    assert page.current_path == "/login?next=/roster"


def test_valid_next_is_honoured_after_login(driver, live_server):
    page = LoginPage(driver, live_server)
    page.visit("/login", next="/waiver")
    page.wait_visible(page.FORM)
    page.sign_in("demo", "courtvision")
    assert page.current_path == "/waiver"


def test_hostile_next_is_discarded(driver, live_server):
    """An off-site next value must not be followed, or the login page becomes a
    phishing hop. The user lands on the dashboard instead."""
    page = LoginPage(driver, live_server)
    page.visit("/login", next="https://evil.example/steal")
    page.wait_visible(page.FORM)
    page.sign_in("demo", "courtvision")

    assert page.current_path == "/"
    assert "evil.example" not in driver.current_url


def test_logout_clears_the_session(driver, live_server, logged_in):
    dashboard = DashboardPage(driver, live_server).load()
    dashboard.wait_loaded()
    dashboard.log_out()

    assert not dashboard.has_nav()

    # Going back to a protected route must bounce, not serve a cached page.
    RosterPage(driver, live_server).visit()
    login = LoginPage(driver, live_server)
    login.wait_visible(login.FORM)
    assert login.current_path == "/login?next=/roster"
