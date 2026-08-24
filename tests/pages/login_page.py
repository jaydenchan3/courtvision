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
        """Submits and waits for one of the two possible OUTCOMES.

        Success navigates away from /login; failure re-renders in place with an
        error. Waiting on either is deterministic.

        An earlier version waited on staleness_of(form) instead. That waits on
        a DOM-identity side effect rather than the result, and it timed out
        intermittently -- roughly one full-suite run in ten -- when the click
        and the document swap interleaved badly, even though the login had
        actually succeeded. Waiting on the outcome removes the race.
        """
        before = self.driver.current_url
        self.type_into(self.USERNAME, username)
        self.type_into(self.PASSWORD, password)
        self.click(self.SUBMIT)
        self.wait.until(
            lambda d: d.current_url != before or d.find_elements(*self.ERROR),
            "login neither navigated away nor reported an error",
        )
        return self

    def error_text(self):
        return self.text_of(self.ERROR)

    def has_error(self):
        return self.is_present(self.ERROR)
