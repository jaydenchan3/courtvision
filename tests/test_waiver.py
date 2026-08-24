"""Waiver wire: sorting, filtering, and the sort-key whitelist."""

import pytest

from tests.pages.waiver_page import WaiverPage

pytestmark = pytest.mark.waiver

# Generational suffixes are not surnames: "Marvin Bagley III".split()[-1] is
# "III". The app sorts on the last_name column, so the test needs the same
# notion of a surname to check the order it sees on screen.
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def surname(full_name):
    parts = full_name.split()
    while len(parts) > 1 and parts[-1].lower().strip(".") in SUFFIXES:
        parts.pop()
    return parts[-1]


def test_default_sort_is_points_descending(driver, live_server, logged_in):
    page = WaiverPage(driver, live_server).load()
    points = page.points()

    assert page.row_count() == 32
    assert page.selected_sort() == "points"
    assert points == sorted(points, reverse=True)


def test_changing_sort_reorders_the_table(driver, live_server, logged_in):
    page = WaiverPage(driver, live_server).load()
    by_points = page.names()

    page.apply(sort="name")
    by_name = page.names()

    assert by_name != by_points
    assert sorted(by_name, key=surname) == by_name
    assert set(by_name) == set(by_points), "sorting must reorder, not filter"


def test_team_filter_narrows_the_table(driver, live_server, logged_in):
    page = WaiverPage(driver, live_server).load()
    total = page.row_count()

    page.apply(team="CLE")

    assert 0 < page.row_count() < total
    assert set(page.teams()) == {"CLE"}


def test_clearing_the_filter_restores_the_table(driver, live_server, logged_in):
    page = WaiverPage(driver, live_server).load()
    total = page.row_count()
    page.apply(team="CLE")
    page.apply(team="")
    assert page.row_count() == total


def test_hostile_sort_value_falls_back_to_the_default(driver, live_server, logged_in):
    """A column name cannot be parameterised, so the sort key is whitelisted.
    An unknown value must be ignored, not interpolated into SQL."""
    page = WaiverPage(driver, live_server).load()
    expected = page.names()

    page.load(sort="'; DROP TABLE players--")

    assert page.row_count() == 32, "table must be intact"
    assert page.names() == expected, "order must be the default"
    assert page.selected_sort() == "points"
