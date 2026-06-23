from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager

from login_selectors import CHROME_PROFILE, CHROME_USER_DATA

from pathlib import Path


MAIN_DIR = Path(__file__).resolve().parent.parent
DRIVER_CACHE_DIR = MAIN_DIR / ".drivers"


def resolve_chromedriver_path() -> str | None:
    try:
        return ChromeDriverManager(
            cache_manager=DriverCacheManager(root_dir=str(DRIVER_CACHE_DIR))
        ).install()
    except Exception as exc:
        print(f"Project ChromeDriver cache unavailable, trying existing drivers: {exc}")

    try:
        existing_drivers = sorted(
            (Path.home() / ".wdm" / "drivers" / "chromedriver").glob("**/chromedriver.exe"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        existing_drivers = []

    return str(existing_drivers[0]) if existing_drivers else None


def create_driver(use_profile: bool = False) -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("detach", True)
    options.add_argument("--disable-blink-features=AutomationControlled")

    if use_profile:
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE}")

    DRIVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    driver_path = resolve_chromedriver_path()
    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)

    return webdriver.Chrome(options=options)


def find_clickable(driver: webdriver.Chrome, selectors: list, timeout: int = 10):
    wait = WebDriverWait(driver, timeout)
    last_error = None

    for by, value in selectors:
        try:
            return wait.until(EC.element_to_be_clickable((by, value)))
        except TimeoutException as exc:
            last_error = exc

    raise TimeoutException(f"No matching selector found. Last error: {last_error}")
