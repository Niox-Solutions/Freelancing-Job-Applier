import re
import time
import sys
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

MAIN_DIR = Path(__file__).resolve().parent.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from browser import find_clickable
from config import JOBS_CSV_PATH
from csv_store import append_jobs
from login_selectors import (
    DEVELOPMENT_FILTER_SELECTORS,
    NEXT_PAGE_SELECTORS,
    PROJECT_SEARCH_SELECTORS,
)
from nafezly_bs4_scraper import handle_scrap


OFFERS_LABEL = "\u0639\u0631\u0648\u0636"
OPEN_STATE = "\u0645\u0641\u062a\u0648\u062d"
JOB_SAVED_CALLBACK = None
ARABIC_DIGIT_TRANSLATION = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
    "01234567890123456789",
)


def set_job_saved_callback(callback) -> None:
    global JOB_SAVED_CALLBACK
    JOB_SAVED_CALLBACK = callback


def scrape_open_development_projects(
    driver: webdriver.Chrome,
    *,
    max_pages: int = 5,
    max_age_minutes: int = 5,
) -> int:
    wait = WebDriverWait(driver, 20)
    select_development_filter(driver)
    submit_project_search(driver)
    wait.until(lambda d: OFFERS_LABEL in d.find_element(By.TAG_NAME, "body").text)

    seen_links = set()
    saved_total = 0
    ready_total = 0

    for page_number in range(1, max(1, max_pages) + 1):
        time.sleep(2)
        results_page_url = driver.current_url
        jobs = extract_jobs_from_current_page(
            driver,
            max_age_minutes=max_age_minutes,
        )
        new_jobs = [job for job in jobs if job["job_link"] not in seen_links]

        for job in new_jobs:
            seen_links.add(job["job_link"])

        saved_count, ready_count, stop_requested = save_and_process_jobs(
            driver,
            new_jobs,
        )
        saved_total += saved_count
        ready_total += ready_count
        print(
            f"Page {page_number}: found {len(new_jobs)} session-new project(s), "
            f"saved {saved_count} project(s), sent {ready_count} project(s) to pipeline."
        )

        if stop_requested:
            print("Pipeline requested stop.")
            break

        if driver.current_url != results_page_url:
            driver.get(results_page_url)
            wait.until(lambda d: OFFERS_LABEL in d.find_element(By.TAG_NAME, "body").text)

        if not go_to_next_page(driver):
            break

    print(f"Saved {saved_total} new project(s) to: {JOBS_CSV_PATH}")
    print(f"Sent {ready_total} project(s) to pipeline.")
    return saved_total


def save_and_process_jobs(
    driver: webdriver.Chrome,
    jobs: list[dict],
) -> tuple[int, int, bool]:
    saved_count = 0
    ready_count = 0
    stop_requested = False

    for job in jobs:
        saved_count += append_jobs(JOBS_CSV_PATH, [job])

        if JOB_SAVED_CALLBACK:
            should_continue = JOB_SAVED_CALLBACK(job, driver)
            ready_count += 1
            if should_continue is False:
                stop_requested = True
                break

    return saved_count, ready_count, stop_requested


def select_development_filter(driver: webdriver.Chrome) -> None:
    filter_element = find_clickable(driver, DEVELOPMENT_FILTER_SELECTORS, timeout=20)

    if filter_element.tag_name.lower() == "input":
        if not filter_element.is_selected():
            filter_element.click()
    else:
        filter_element.click()

    print("Development filter selected.")


def submit_project_search(driver: webdriver.Chrome) -> None:
    try:
        search_button = find_clickable(driver, PROJECT_SEARCH_SELECTORS, timeout=10)
        search_button.click()
    except TimeoutException:
        driver.execute_script(
            """
            const checked = document.querySelector('#development');
            const form = checked ? checked.closest('form') : document.querySelector('form');

            if (form) {
                form.requestSubmit ? form.requestSubmit() : form.submit();
            }
            """
        )

    print("Project search submitted.")


def extract_jobs_from_current_page(
    driver: webdriver.Chrome,
    *,
    max_age_minutes: int,
) -> list[dict]:
    jobs = handle_scrap(driver)
    open_jobs = [
        job for job in jobs if clean_text(job.get("project_state")) == OPEN_STATE
    ]
    recent_jobs = [
        job
        for job in open_jobs
        if is_recent_job(
            job.get("job_submit_time"),
            max_age_minutes=max_age_minutes,
        )
    ]

    print(
        f"Recent open projects on page: {len(recent_jobs)} "
        f"of {len(open_jobs)} open / {len(jobs)} total."
    )
    return unique_jobs(recent_jobs)


def is_recent_job(
    value: str | None,
    *,
    max_age_minutes: int,
) -> bool:
    age_minutes = project_age_minutes(value)
    return age_minutes is not None and age_minutes < max(1, max_age_minutes)


def project_age_minutes(value: str | None) -> float | None:
    text = clean_text(value).translate(ARABIC_DIGIT_TRANSLATION).lower()
    if not text:
        return None

    if any(word in text for word in ("الآن", "لحظات", "ثوان", "ثانية")):
        return 0

    if "دقيقتين" in text:
        return 2

    if "دقيقة" in text or "دقائق" in text:
        match = re.search(r"\d+", text)
        if match:
            return float(match.group())
        if "دقيقة" in text:
            return 1

    return None


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def unique_jobs(jobs: list[dict]) -> list[dict]:
    unique = []
    seen_links = set()

    for job in jobs:
        link = job["job_link"]
        if link in seen_links:
            continue

        seen_links.add(link)
        unique.append(job)

    return unique


def go_to_next_page(driver: webdriver.Chrome) -> bool:
    current_url = driver.current_url

    try:
        next_link = find_clickable(driver, NEXT_PAGE_SELECTORS, timeout=5)
    except TimeoutException:
        return False

    next_link.click()

    try:
        WebDriverWait(driver, 15).until(lambda d: d.current_url != current_url)
    except TimeoutException:
        time.sleep(2)

    return True
