import sys
from pathlib import Path

from selenium.webdriver.common.by import By


MAIN_DIR = Path(__file__).resolve().parent.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from config import CHROME_PROFILE, CHROME_USER_DATA, HOME_URL, LOGIN_URL  # noqa: E402

LOGIN_BTN_SELECTORS = [
    (By.XPATH, "//a[@title='login' or contains(@href, '/login')]"),
    (By.XPATH, "//a[contains(@href, '/login')]"),
]

GOOGLE_BTN_SELECTORS = [
    (By.XPATH, "//a[contains(@href, 'google') or contains(@href, 'oauth')]"),
    (By.XPATH, "//button[contains(., 'Google')]"),
    (By.XPATH, "//a[contains(@class, 'google')]"),
    (By.XPATH, "//*[contains(@class, 'google') and (self::a or self::button)]"),
]

GOOGLE_TRY_AGAIN_SELECTORS = [
    (By.XPATH, "//button[contains(., 'Try again')]"),
    (By.XPATH, "//span[contains(text(), 'Try again')]/ancestor::button[1]"),
    (By.XPATH, "//*[normalize-space(text())='Try again' and (self::button or self::a)]"),
]

GOOGLE_PASSWORD_SELECTORS = [
    (By.NAME, "Passwd"),
    (By.CSS_SELECTOR, "input[type='password']"),
    (By.XPATH, "//input[contains(translate(@aria-label, 'PASSWORD', 'password'), 'password')]"),
    (By.XPATH, "//input[@name='Passwd' or @type='password']"),
]

GOOGLE_PASSWORD_NEXT_SELECTORS = [
    (By.ID, "passwordNext"),
    (By.XPATH, "//button[.//span[contains(., 'Next')]]"),
    (By.XPATH, "//*[normalize-space(text())='Next']/ancestor::button[1]"),
]

PROJECTS_SELECTORS = [
    (By.XPATH, "//span[normalize-space(.)='المشاريع']/ancestor::a[1]"),
    (By.XPATH, "//*[normalize-space(.)='المشاريع' and (self::a or self::button)]"),
    (By.XPATH, "//a[contains(@href, '/projects') or contains(@href, '/project')]"),
]

DEVELOPMENT_FILTER_SELECTORS = [
    (By.ID, "development"),
    (By.CSS_SELECTOR, "input#development"),
    (By.XPATH, "//label[@for='development']"),
    (By.XPATH, "//label[contains(normalize-space(.), 'برمجة')]"),
]

PROJECT_SEARCH_SELECTORS = [
    (By.XPATH, "//button[@type='submit']"),
    (By.XPATH, "//button[contains(normalize-space(.), 'بحث')]"),
    (By.XPATH, "//input[@type='submit']"),
]

NEXT_PAGE_SELECTORS = [
    (By.XPATH, "//a[@rel='next']"),
    (By.XPATH, "//a[contains(normalize-space(.), 'التالي')]"),
    (By.XPATH, "//li[contains(@class, 'next')]/a"),
]

NAFEZLY_EMAIL_SELECTORS = [
    (By.CSS_SELECTOR, "input[type='email']"),
    (By.CSS_SELECTOR, "input[name='email']"),
    (By.XPATH, "//input[@type='email' or @name='email']"),
]

NAFEZLY_PASSWORD_SELECTORS = [
    (By.CSS_SELECTOR, "input[type='password']"),
    (By.CSS_SELECTOR, "input[name='password']"),
    (By.XPATH, "//input[@type='password' or @name='password']"),
]

NAFEZLY_SUBMIT_SELECTORS = [
    (By.XPATH, "//button[@type='submit']"),
    (By.XPATH, "//button[contains(., 'تسجيل') or contains(., 'login')]"),
    (By.CSS_SELECTOR, "button[type='submit']"),
]
