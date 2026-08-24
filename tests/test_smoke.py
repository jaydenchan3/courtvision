"""Harness smoke test: proves the fixtures wire up before any real assertions."""

import pytest

from tests.pages.login_page import LoginPage


@pytest.mark.auth
def test_login_page_loads(driver, live_server):
    page = LoginPage(driver, live_server).load()
    assert page.is_present(page.FORM)
    assert not page.has_error()
    assert not page.has_nav()


def test_suite_uses_a_throwaway_database(test_db):
    """Guards the isolation claim: if this ever points at courtvision.db, the
    suite would mutate real data and stop being repeatable."""
    from app.data import models
    assert models.DB_PATH == test_db
    assert models.DB_PATH.name != "courtvision.db"
    assert "courtvision.db" not in str(models.DB_PATH)
