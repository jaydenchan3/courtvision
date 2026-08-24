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
        self.visit(**params)
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
        """Changes the controls and waits for the re-rendered table."""
        body = self.driver.find_element(By.TAG_NAME, "body")
        if sort is not None:
            self.select_option(self.SORT, sort)
        if team is not None:
            self.select_option(self.TEAM, team)
        self.click(self.APPLY)
        self.wait_stale(body)
        return self
