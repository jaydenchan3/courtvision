from selenium.webdriver.common.by import By

from tests.pages.base_page import BasePage


class DashboardPage(BasePage):
    """The async page. Its data arrives after load, behind a server-side delay,
    so every read here must be preceded by an explicit wait."""

    path = "/"

    SPINNER = (By.CSS_SELECTOR, '[data-testid="dashboard-loading"]')
    CONTENT = (By.CSS_SELECTOR, '[data-testid="dashboard-content"]')
    DATE = (By.CSS_SELECTOR, '[data-testid="dashboard-date"]')
    GAME_ROWS = (By.CSS_SELECTOR, '[data-testid="game-row"]')
    NO_GAMES = (By.CSS_SELECTOR, '[data-testid="no-games"]')
    INJURY_ROWS = (By.CSS_SELECTOR, '[data-testid="injury-row"]')
    ROSTER_COUNT = (By.CSS_SELECTOR, '[data-testid="dashboard-roster-count"]')
    ERROR = (By.CSS_SELECTOR, '[data-testid="dashboard-error"]')

    def load(self, date=None):
        """Navigates and returns immediately -- deliberately does NOT wait, so a
        test can observe the spinner before the fetch resolves."""
        self.visit(**({"date": date} if date else {}))
        return self

    def spinner_visible(self):
        return self.is_present(self.SPINNER, timeout=1)

    def wait_loaded(self):
        """The explicit-wait case this app exists to teach: wait for the
        spinner to go away AND the content to become visible. Waiting on only
        one of the two would pass against a half-rendered page."""
        self.wait_invisible(self.SPINNER)
        self.wait_visible(self.CONTENT)
        return self

    def game_rows(self):
        return self.driver.find_elements(*self.GAME_ROWS)

    def game_texts(self):
        return [e.text.strip() for e in self.game_rows()]

    def injury_rows(self):
        return self.driver.find_elements(*self.INJURY_ROWS)

    def no_games_visible(self):
        elements = self.driver.find_elements(*self.NO_GAMES)
        return bool(elements) and elements[0].is_displayed()

    def no_games_text(self):
        return self.find(self.NO_GAMES).text.strip()

    def date_text(self):
        return self.text_of(self.DATE)

    def roster_count(self):
        return int(self.text_of(self.ROSTER_COUNT))
