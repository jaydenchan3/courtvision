from selenium.webdriver.common.by import By

from tests.pages.base_page import BasePage


class LoginPage(BasePage):
    path = "/login"

    FORM = (By.ID, "login-form")
    USERNAME = (By.ID, "username")
    PASSWORD = (By.ID, "password")
    SUBMIT = (By.ID, "login-submit")
    ERROR = (By.CSS_SELECTOR, '[data-testid="login-error"]')

    def load(self, **params):
        self.visit(**params)
        self.wait_visible(self.FORM)
        return self

    def sign_in(self, username, password):
        """Submits and waits for the resulting navigation to settle.

        Waiting on the old form going stale is what stops the next query from
        reading the pre-submit DOM -- the classic source of a test that passes
        locally and fails on a slower machine.
        """
        form = self.driver.find_element(*self.FORM)
        self.type_into(self.USERNAME, username)
        self.type_into(self.PASSWORD, password)
        self.click(self.SUBMIT)
        self.wait_stale(form)
        return self

    def error_text(self):
        return self.text_of(self.ERROR)

    def has_error(self):
        return self.is_present(self.ERROR)
