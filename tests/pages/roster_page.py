from selenium.webdriver.common.by import By

from tests.pages.base_page import BasePage


class RosterPage(BasePage):
    path = "/roster"

    TABLE = (By.CSS_SELECTOR, '[data-testid="roster-table"]')
    ROWS = (By.CSS_SELECTOR, '[data-testid="roster-row"]')
    NAMES = (By.CSS_SELECTOR, '[data-testid="roster-player-name"]')
    COUNT = (By.CSS_SELECTOR, '[data-testid="roster-count"]')
    MAX = (By.CSS_SELECTOR, '[data-testid="roster-max"]')
    ADD_SELECT = (By.ID, "add-player-select")
    ADD_SUBMIT = (By.ID, "add-player-submit")
    EMPTY = (By.CSS_SELECTOR, '[data-testid="roster-empty"]')

    def load(self):
        self.visit()
        self.wait_visible(self.COUNT)
        return self

    def count(self):
        return int(self.text_of(self.COUNT))

    def maximum(self):
        return int(self.text_of(self.MAX))

    def player_ids(self):
        """Rows are identified by player id, never by index. Row order and
        position change as players are added and removed; the id does not."""
        return [e.get_attribute("data-id")
                for e in self.driver.find_elements(*self.ROWS)]

    def names(self):
        return [e.text.strip() for e in self.driver.find_elements(*self.NAMES)]

    def has_player(self, player_id):
        return str(player_id) in self.player_ids()

    def available_ids(self):
        options = self.find(self.ADD_SELECT).find_elements(By.TAG_NAME, "option")
        return [o.get_attribute("value") for o in options]

    def add_player(self, player_id):
        """Selects, submits, and waits for the outcome: the row is on the page.

        Waiting for the specific row rather than merely for a reload means a
        successful add is distinguishable from a rejected one, and the wait
        cannot pass against the pre-submit table.
        """
        self.select_option(self.ADD_SELECT, str(player_id))
        self.submit_and_wait(self.ADD_SUBMIT, self.COUNT)
        self.wait_until(
            lambda d: d.find_elements(*self._row_for(player_id))
            or d.find_elements(*self.FLASH_ERROR),
            f"player {player_id} neither appeared on the roster nor was refused",
        )
        return self

    def remove_player(self, player_id):
        """Submits, then waits for the row to be GONE -- the actual outcome."""
        self.submit_and_wait(self._remove_button(player_id), self.COUNT)
        self.wait_until(
            lambda d: not d.find_elements(*self._row_for(player_id)),
            f"player {player_id} was still on the roster after removal",
        )
        return self

    @staticmethod
    def _row_for(player_id):
        return (By.CSS_SELECTOR, f'[data-testid="roster-row"][data-id="{player_id}"]')

    @staticmethod
    def _remove_button(player_id):
        return (By.CSS_SELECTOR,
                f'[data-testid="remove-player"][data-id="{player_id}"]')

    def fill_to_capacity(self):
        """Adds available players until the roster is at its cap."""
        while self.count() < self.maximum():
            self.add_player(self.available_ids()[0])
        return self
