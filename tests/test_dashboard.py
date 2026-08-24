"""Dashboard: asynchronous load behind a deliberate server-side delay.

This is the explicit-wait case. The page renders a spinner first and fills in
content only after a fetch resolves, so any read taken without waiting races
the application.
"""

import pytest

from tests.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.dashboard


def test_spinner_shows_then_content_replaces_it(driver, live_server, logged_in):
    """The core wait test.

    load() deliberately does not wait, so the spinner is observable. Then both
    conditions are waited on: the spinner becoming invisible AND the content
    becoming visible. Waiting on only one would pass against a half-rendered
    page -- content present but still hidden behind the spinner, or the spinner
    gone with nothing yet drawn.
    """
    page = DashboardPage(driver, live_server).load()
    assert page.spinner_visible(), "spinner should be on screen before data arrives"

    page.wait_loaded()

    assert not page.is_present(page.SPINNER, timeout=1)
    assert page.find(page.CONTENT).is_displayed()


def test_seeded_games_render(driver, live_server, logged_in):
    page = DashboardPage(driver, live_server).load().wait_loaded()

    assert len(page.game_rows()) == 3
    assert not page.no_games_visible()
    for text in page.game_texts():
        assert "@" in text


def test_injury_widget_renders_seeded_injuries(driver, live_server, logged_in):
    page = DashboardPage(driver, live_server).load().wait_loaded()
    assert len(page.injury_rows()) == 8

    # Worst first: the widget must lead with players who are actually out.
    statuses = [r.get_attribute("data-status") for r in page.injury_rows()]
    assert statuses[0] == "out"


def test_roster_count_reflects_the_seed(driver, live_server, logged_in):
    page = DashboardPage(driver, live_server).load().wait_loaded()
    assert page.roster_count() == 8


def test_empty_state_when_no_games(driver, live_server, logged_in):
    """Reaches a zero-games day deterministically via ?date=, so the assertion
    does not depend on what day the suite happens to run."""
    page = DashboardPage(driver, live_server).load(date="1999-01-01").wait_loaded()

    assert page.game_rows() == []
    assert page.no_games_visible()
    assert page.no_games_text() == "No games scheduled tonight"


def test_empty_state_is_absent_when_games_exist(driver, live_server, logged_in):
    """Guards against the empty state being rendered unconditionally, which
    would make the previous test pass for the wrong reason."""
    page = DashboardPage(driver, live_server).load().wait_loaded()
    assert not page.no_games_visible()
