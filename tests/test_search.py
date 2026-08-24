"""Player search: results, and the two distinct empty states."""

import pytest

from tests.pages.search_page import SearchPage

pytestmark = [pytest.mark.e2e, pytest.mark.search]


def test_initial_state_prompts_rather_than_reporting_no_results(driver, live_server, logged_in):
    """Before searching, the page must not claim a search found nothing.
    Collapsing 'has not searched' into 'no results' would let the empty-state
    test below pass on a page that never ran a query."""
    page = SearchPage(driver, live_server).load()

    assert page.showing_prompt()
    assert not page.showing_empty()
    assert page.row_count() == 0


def test_matching_query_shows_results(driver, live_server, logged_in):
    page = SearchPage(driver, live_server).load()
    page.search_for("allen")

    assert page.row_count() == 2
    assert all("Allen" in name for name in page.names())
    assert not page.showing_prompt()
    assert not page.showing_empty()


def test_partial_and_case_insensitive_match(driver, live_server, logged_in):
    page = SearchPage(driver, live_server).load()
    page.search_for("ADAMS")
    assert page.row_count() >= 1
    assert all("Adams" in name for name in page.names())


def test_unknown_query_shows_an_empty_state_not_a_blank_page(driver, live_server, logged_in):
    page = SearchPage(driver, live_server).load()
    page.search_for("zzzznotaplayer")

    assert page.row_count() == 0
    assert page.showing_empty()
    assert not page.showing_prompt()
    assert "zzzznotaplayer" in page.empty_text()
