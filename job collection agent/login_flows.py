import time
import sys
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

MAIN_DIR = Path(__file__).resolve().parent.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from browser import create_driver, find_clickable
from config import Password, Username
from login_selectors import (
    GOOGLE_BTN_SELECTORS,
    GOOGLE_PASSWORD_NEXT_SELECTORS,
    GOOGLE_PASSWORD_SELECTORS,
    GOOGLE_TRY_AGAIN_SELECTORS,
    HOME_URL,
    LOGIN_BTN_SELECTORS,
    LOGIN_URL,
    NAFEZLY_EMAIL_SELECTORS,
    NAFEZLY_PASSWORD_SELECTORS,
    NAFEZLY_SUBMIT_SELECTORS,
    PROJECTS_SELECTORS,
)
from project_scraper import scrape_open_development_projects


def open_login_page(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    *,
    via_homepage: bool,
) -> None:
    if via_homepage:
        driver.get(HOME_URL)
        login_button = find_clickable(driver, LOGIN_BTN_SELECTORS)
        login_button.click()
    else:
        driver.get(LOGIN_URL)

    wait.until(lambda d: "/login" in d.current_url)


def click_google_button(driver: webdriver.Chrome) -> None:
    google_btn = find_clickable(driver, GOOGLE_BTN_SELECTORS)
    google_btn.click()


def switch_to_google_popup(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    *,
    wait_for_popup: bool,
) -> str:
    main_window = driver.current_window_handle

    if wait_for_popup:
        wait.until(lambda d: len(d.window_handles) > 1)

    for handle in driver.window_handles:
        if handle != main_window:
            driver.switch_to.window(handle)
            break

    return main_window


def fill_google_email_once(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    email_input = wait.until(EC.element_to_be_clickable((By.ID, "identifierId")))
    email_input.clear()
    email_input.send_keys(Username)
    driver.find_element(By.ID, "identifierNext").click()


def click_google_try_again_if_present(
    driver: webdriver.Chrome,
    timeout: int = 8,
) -> bool:
    try:
        try_again_btn = find_clickable(driver, GOOGLE_TRY_AGAIN_SELECTORS, timeout=timeout)
        try_again_btn.click()
        print("Google 'Try again' button clicked.")
        return True
    except TimeoutException:
        return False


def fill_google_email(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    fill_google_email_once(driver, wait)
    time.sleep(2)

    if click_google_try_again_if_present(driver):
        fill_google_email_once(driver, wait)


def fill_google_password(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    password_input = None

    for _ in range(3):
        password_input = find_clickable(driver, GOOGLE_PASSWORD_SELECTORS, timeout=30)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", password_input)
        password_input.click()
        password_input.send_keys(Keys.CONTROL, "a")
        password_input.send_keys(Password)
        time.sleep(1)

        if password_input.get_attribute("value") == Password:
            break

        set_input_value(driver, password_input, Password)
        time.sleep(1)

        if password_input.get_attribute("value") == Password:
            break
    else:
        raise TimeoutException("Google password field stayed empty after typing.")

    wait.until(lambda d: password_input.get_attribute("value") == Password)
    print("Google password field filled.")

    next_button = find_clickable(driver, GOOGLE_PASSWORD_NEXT_SELECTORS, timeout=15)
    next_button.click()


def set_input_value(driver: webdriver.Chrome, input_element, value: str) -> None:
    driver.execute_script(
        """
        const input = arguments[0];
        const value = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            'value'
        ).set;

        input.focus();
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        input_element,
        value,
    )


def wait_for_login_complete(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    main_window: str,
) -> None:
    try:
        wait.until(lambda d: len(d.window_handles) == 1)
    except TimeoutException:
        pass

    if main_window in driver.window_handles:
        driver.switch_to.window(main_window)

    wait.until(lambda d: "accounts.google.com" not in d.current_url)


def is_logged_in(driver: webdriver.Chrome) -> bool:
    url = driver.current_url.lower()
    if "accounts.google.com" in url or "/login" in url:
        return False

    logged_in_hints = [
        (By.XPATH, "//a[contains(@href, '/logout') or contains(@href, '/profile')]"),
        (By.XPATH, "//*[contains(@class, 'avatar') or contains(@class, 'user-menu')]"),
    ]

    for by, value in logged_in_hints:
        if driver.find_elements(by, value):
            return True

    return "nafezly.com" in url and "/login" not in url


def click_projects(driver: webdriver.Chrome) -> None:
    projects_link = find_clickable(driver, PROJECTS_SELECTORS, timeout=20)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", projects_link)
    projects_link.click()
    print("Projects page clicked.")


def collect_projects_after_sign_in(driver: webdriver.Chrome) -> None:
    click_projects(driver)
    scrape_open_development_projects(driver)


def sign_in_with_first_approach() -> webdriver.Chrome:
    driver = create_driver(use_profile=False)
    wait = WebDriverWait(driver, 20)

    try:
        open_login_page(driver, wait, via_homepage=True)
        click_google_button(driver)
        wait.until(
            lambda d: "accounts.google.com" in d.current_url
            or len(d.window_handles) > 1
        )
        main_window = switch_to_google_popup(
            driver,
            wait,
            wait_for_popup=False,
        )
        fill_google_email(driver, wait)
        fill_google_password(driver, wait)
        wait_for_login_complete(driver, wait, main_window)

        if not is_logged_in(driver):
            raise TimeoutException(
                f"Login not confirmed. Current URL: {driver.current_url}"
            )

        print("Signed in once with the first login approach.")
        return driver
    except Exception:
        driver.quit()
        raise


def fill_nafezly_credentials(driver: webdriver.Chrome) -> None:
    email_input = find_clickable(driver, NAFEZLY_EMAIL_SELECTORS)
    email_input.clear()
    email_input.send_keys(Username)

    password_input = find_clickable(driver, NAFEZLY_PASSWORD_SELECTORS)
    password_input.clear()
    password_input.send_keys(Password)

    submit_btn = find_clickable(driver, NAFEZLY_SUBMIT_SELECTORS)
    submit_btn.click()


def run_google_login_case(
    *,
    use_profile: bool,
    via_homepage: bool,
    wait_for_popup: bool,
    fill_email: bool,
    fill_password: bool,
) -> None:
    driver = create_driver(use_profile=use_profile)
    wait = WebDriverWait(driver, 7)
    main_window = None

    try:
        open_login_page(driver, wait, via_homepage=via_homepage)
        click_google_button(driver)

        main_window = switch_to_google_popup(
            driver, wait, wait_for_popup=wait_for_popup
        )

        if fill_email:
            fill_google_email(driver, wait)

        if fill_password:
            fill_google_password(driver, wait)

        if not fill_email and not fill_password:
            time.sleep(5)

        wait_for_login_complete(driver, wait, main_window)

        if not is_logged_in(driver):
            raise TimeoutException(
                f"Login not confirmed. Current URL: {driver.current_url}"
            )

        collect_projects_after_sign_in(driver)

    finally:
        driver.quit()
        print("Browser closed.")


def run_nafezly_email_login_case(*, via_homepage: bool) -> None:
    driver = create_driver(use_profile=False)
    wait = WebDriverWait(driver, 20)

    try:
        open_login_page(driver, wait, via_homepage=via_homepage)
        fill_nafezly_credentials(driver)
        wait.until(lambda d: "/login" not in d.current_url)

        if not is_logged_in(driver):
            raise TimeoutException(
                f"Site login not confirmed. Current URL: {driver.current_url}"
            )

        collect_projects_after_sign_in(driver)

    finally:
        driver.quit()
        print("Browser closed.")
