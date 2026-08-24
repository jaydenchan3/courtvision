"""Roster table, add/remove flows, and the boundary rules.

Message assertions import the constants from app.server rather than pasting
the text, so rewording a message does not break a test that is not about
wording.
"""

import pytest

from app.data import models
from app.server import MSG_DUPLICATE, MSG_ROSTER_FULL
from tests.pages.roster_page import RosterPage

pytestmark = [pytest.mark.e2e, pytest.mark.roster]


def test_seeded_roster_renders(driver, live_server, logged_in):
    page = RosterPage(driver, live_server).load()
    assert page.count() == 8
    assert len(page.player_ids()) == 8
    assert page.maximum() == models.ROSTER_MAX


def test_add_player_adds_a_row(driver, live_server, logged_in):
    page = RosterPage(driver, live_server).load()
    before = page.player_ids()
    candidate = page.available_ids()[0]
    assert candidate not in before

    page.add_player(candidate)

    assert page.count() == len(before) + 1
    assert page.has_player(candidate)


def test_remove_player_removes_the_row(driver, live_server, logged_in):
    page = RosterPage(driver, live_server).load()
    target = page.player_ids()[0]

    page.remove_player(target)

    assert page.count() == 7
    assert not page.has_player(target)


def test_removed_player_returns_to_the_add_list(driver, live_server, logged_in):
    page = RosterPage(driver, live_server).load()
    target = page.player_ids()[0]
    page.remove_player(target)
    assert target in page.available_ids()


def test_duplicate_add_is_rejected(driver, live_server, logged_in):
    """The select only offers unrostered players, so the duplicate is forced by
    posting an id that is already on the roster -- exercising the server-side
    UNIQUE constraint rather than the UI's convenience filtering."""
    page = RosterPage(driver, live_server).load()
    existing = page.player_ids()[0]

    driver.execute_script(
        """
        const f = document.createElement('form');
        f.method = 'post'; f.action = '/roster/add';
        const i = document.createElement('input');
        i.name = 'player_id'; i.value = arguments[0];
        f.appendChild(i); document.body.appendChild(f); f.submit();
        """,
        existing,
    )
    page.wait_visible(page.COUNT)

    assert page.flash_error() == MSG_DUPLICATE
    assert page.count() == 8
    assert page.player_ids().count(existing) == 1


def test_roster_cap_is_enforced(driver, live_server, logged_in):
    page = RosterPage(driver, live_server).load()
    page.fill_to_capacity()
    assert page.count() == models.ROSTER_MAX

    page.add_player(page.available_ids()[0])

    assert page.flash_error() == MSG_ROSTER_FULL
    assert page.count() == models.ROSTER_MAX


def test_each_test_starts_from_the_seeded_roster(driver, live_server, logged_in):
    """Explicit guard on isolation: the two tests above leave the roster at 13
    and at 7. If reseeding ever broke, this fails and names the reason."""
    page = RosterPage(driver, live_server).load()
    assert page.count() == 8
