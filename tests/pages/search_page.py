from selenium.webdriver.common.by import By

from tests.pages.base_page import BasePage


class SearchPage(BasePage):
    path = "/search"

    INPUT = (By.ID, "search-input")
    SUBMIT = (By.ID, "search-submit")
    RESULTS = (By.CSS_SELECTOR, '[data-testid="search-results"]')
    ROWS = (By.CSS_SELECTOR, '[data-testid="search-row"]')
    NAMES = (By.CSS_SELECTOR, '[data-testid="search-player-name"]')
    # Three distinct states: not yet searched, searched with no match, results.
    PROMPT = (By.CSS_SELECTOR, '[data-testid="search-prompt"]')
    EMPTY = (By.CSS_SELECTOR, '[data-testid="search-empty"]')

    def load(self, **params):
        self.visit(**params)
        self.wait_visible(self.RESULTS)
        return self

    def search_for(self, term):
        body = self.driver.find_element(By.TAG_NAME, "body")
        self.type_into(self.INPUT, term)
        self.click(self.SUBMIT)
        self.wait_stale(body)
        self.wait_visible(self.RESULTS)
        return self

    def names(self):
        return [e.text.strip() for e in self.driver.find_elements(*self.NAMES)]

    def row_count(self):
        return len(self.driver.find_elements(*self.ROWS))

    def showing_prompt(self):
        return self.is_present(self.PROMPT, timeout=1)

    def showing_empty(self):
        return self.is_present(self.EMPTY, timeout=1)

    def empty_text(self):
        return self.text_of(self.EMPTY)
