from selenium.webdriver.common.by import By

from tests.pages.base_page import BasePage


class WaiverPage(BasePage):
    path = "/waiver"

    TABLE = (By.CSS_SELECTOR, '[data-testid="waiver-table"]')
    ROWS = (By.CSS_SELECTOR, '[data-testid="waiver-row"]')
    NAMES = (By.CSS_SELECTOR, '[data-testid="waiver-player-name"]')
    TEAM_CELLS = (By.CSS_SELECTOR, '[data-testid="waiver-team-cell"]')
    POINTS = (By.CSS_SELECTOR, '[data-testid="waiver-points"]')
    SORT = (By.ID, "waiver-sort")
    TEAM = (By.ID, "waiver-team")
    APPLY = (By.ID, "waiver-apply")
    EMPTY = (By.CSS_SELECTOR, '[data-testid="waiver-empty"]')

    def load(self, **params):
        """Navigate and wait for the page to be READY before any read.

        This used to return immediately. Every accessor below reads with
        find_elements and no wait, so on a slower machine -- a container, or CI
        -- a read could land before the table rendered and quietly return an
        empty list, which looks like a legitimate result rather than a failure.
        """
        self.visit(**params)
        self.wait_visible(self.SORT)
        self.wait_until(
            lambda d: d.find_elements(*self.ROWS) or d.find_elements(*self.EMPTY),
            "waiver table did not render",
        )
        return self

    def names(self):
        return [e.text.strip() for e in self.driver.find_elements(*self.NAMES)]

    def teams(self):
        return [e.text.strip() for e in self.driver.find_elements(*self.TEAM_CELLS)]

    def points(self):
        return [float(e.text) for e in self.driver.find_elements(*self.POINTS)]

    def row_count(self):
        return len(self.driver.find_elements(*self.ROWS))

    def selected_sort(self):
        from selenium.webdriver.support.ui import Select
        return Select(self.find(self.SORT)).first_selected_option.get_attribute("value")

    def apply(self, sort=None, team=None):
        """Changes the controls, submits, and waits for the re-rendered table.

        The outcome is 'a new document whose table has finished rendering', so
        that is what is waited on. Checking the select values instead would not
        work: they already hold the requested values on the OLD page, because
        we just set them there.
        """
        if sort is not None:
            self.select_option(self.SORT, sort)
        if team is not None:
            self.select_option(self.TEAM, team)
        self.submit_and_wait(self.APPLY)
        # Either rows or the empty state -- a filter matching nothing is a
        # valid outcome, and waiting only for rows would hang on it.
        self.wait_until(
            lambda d: d.find_elements(*self.ROWS) or d.find_elements(*self.EMPTY),
            "waiver table did not render after applying filters",
        )
        return self
