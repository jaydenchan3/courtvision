"""Shared page-object behaviour.

Every wait in the suite funnels through here. That is the point of a base
page: if waiting were copy-pasted into each test, a single bad pattern would
have to be fixed in dozens of places, and one forgotten wait becomes a flaky
test nobody can reproduce.

Page objects hold LOCATORS and ACTIONS. They do not assert. Tests call these
methods and make the assertions themselves.
"""

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

DEFAULT_TIMEOUT = 10


class BasePage:
    path = "/"

    def __init__(self, driver, base_url, timeout=DEFAULT_TIMEOUT):
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, timeout)

    # -- navigation ------------------------------------------------------
    def visit(self, path=None, **params):
        url = self.base_url + (self.path if path is None else path)
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        self.driver.get(url)
        return self

    @property
    def current_path(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.driver.current_url)
        return parsed.path + (f"?{parsed.query}" if parsed.query else "")

    # -- waits -----------------------------------------------------------
    # presence  = in the DOM, may be invisible
    # visible   = in the DOM and rendered, which is what a user can see
    # clickable = visible AND enabled, required before click()
    def wait_present(self, locator):
        return self.wait.until(EC.presence_of_element_located(locator))

    def wait_visible(self, locator):
        return self.wait.until(EC.visibility_of_element_located(locator))

    def wait_clickable(self, locator):
        return self.wait.until(EC.element_to_be_clickable(locator))

    def wait_invisible(self, locator):
        """True once the element is hidden or gone from the DOM."""
        return self.wait.until(EC.invisibility_of_element_located(locator))

    def wait_url_contains(self, fragment):
        return self.wait.until(EC.url_contains(fragment))

    # Marker on `window`, not on any element. A new document gets a fresh
    # window object, so the marker vanishing means the navigation landed.
    _NAV_MARKER = "__cvNav"

    def wait_until(self, predicate, message=""):
        """Poll a predicate, treating a mid-navigation DOM as 'not yet'.

        While a document is being swapped, Chrome can raise from almost any
        driver call. Inside a poll that means 'ask again', not 'fail', so the
        predicate is guarded and the wait still times out with a message if the
        condition never becomes true.
        """
        def guarded(driver):
            try:
                return predicate(driver)
            except WebDriverException:
                return False
        return self.wait.until(guarded, message)

    def submit_and_wait(self, click_locator, ready_locator=None):
        """Click something that navigates, then wait for the NEW document.

        This deliberately does NOT use EC.staleness_of. staleness_of treats
        only StaleElementReferenceException as success, but Chrome can instead
        raise a generic WebDriverException while the document is being replaced
        ("Node with given id does not belong to the document"). That escapes
        the wait entirely and fails the test outright rather than retrying --
        which is exactly how this suite failed in CI under random ordering.

        Waiting on a window-scoped marker keys on document identity instead, so
        no element reference is involved and there is nothing to go stale. If
        the click does not navigate at all, this times out with a clear message
        rather than hanging on an element that will never go stale.
        """
        self.driver.execute_script(f"window.{self._NAV_MARKER} = 1;")
        self.click(click_locator)
        self.wait_until(
            lambda d: d.execute_script(
                f"return window.{self._NAV_MARKER} === undefined;"),
            "navigation did not complete after submit",
        )
        if ready_locator is not None:
            self.wait_visible(ready_locator)
        return self

    # -- queries ---------------------------------------------------------
    def find(self, locator):
        return self.wait_visible(locator)

    def find_all(self, locator):
        self.wait_present(locator)
        return self.driver.find_elements(*locator)

    def is_present(self, locator, timeout=2):
        """Short-timeout existence check, for asserting a thing is ABSENT."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator))
            return True
        except TimeoutException:
            return False

    def text_of(self, locator):
        return self.find(locator).text.strip()

    def texts_of(self, locator):
        return [e.text.strip() for e in self.find_all(locator)]

    # -- actions ---------------------------------------------------------
    def click(self, locator):
        self.wait_clickable(locator).click()

    def type_into(self, locator, value):
        field = self.wait_visible(locator)
        field.clear()
        field.send_keys(value)

    def select_option(self, locator, value):
        Select(self.wait_visible(locator)).select_by_value(value)

    # -- shared chrome ---------------------------------------------------
    NAV = (By.CSS_SELECTOR, '[data-testid="main-nav"]')
    LOGOUT = (By.ID, "logout-button")
    FLASH_ERROR = (By.CSS_SELECTOR, '[data-testid="flash-error"]')
    FLASH_SUCCESS = (By.CSS_SELECTOR, '[data-testid="flash-success"]')

    def flash_error(self):
        return self.text_of(self.FLASH_ERROR)

    def has_nav(self):
        return self.is_present(self.NAV)

    def log_out(self):
        self.click(self.LOGOUT)
        self.wait_url_contains("/login")
