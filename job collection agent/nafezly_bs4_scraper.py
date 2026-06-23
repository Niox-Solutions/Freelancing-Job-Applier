from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver


PROJECT_CARD_CLASS = "col-12 main-nafez-box-styles p-3 p-lg-4 mb-lg-3 mb-3 project-box"


def scrape_nafezly_cards(driver: webdriver.Chrome) -> list[dict]:
    scraped_at = datetime.now().isoformat(timespec="seconds")
    current_url = driver.current_url

    print(f"Scraped at: {scraped_at}")
    print(f"Current URL: {current_url}")

    page = driver.page_source
    soup = BeautifulSoup(page, "html.parser")
    job_cards = soup.find_all("div", class_=PROJECT_CARD_CLASS)

    jobs = []
    for job_card in job_cards:
        job = extract_job_card(job_card, current_url, scraped_at)
        if job:
            jobs.append(job)

    print(f"Found {len(jobs)} project(s).")
    return jobs


def handle_scrap(driver: webdriver.Chrome) -> list[dict]:
    return scrape_nafezly_cards(driver)


def extract_job_card(job_card, current_url: str, scraped_at: str) -> dict | None:
    title_link = job_card.find("a", class_="text-truncate")
    if not title_link:
        return None

    title = clean_text(title_link.get_text())
    project_link = urljoin(current_url, title_link.get("href", ""))
    description = clean_text(
        get_text_or_empty(
            job_card.find("h3", class_="naskh font-1 m-0 col-12 col-lg-10 px-0")
        )
    )
    
    return {
        "hiring_person_name": extract_hiring_person_name(job_card, title_link),
        "scraped_at": scraped_at,
        "job_title": title,
        "job_link": project_link,
        "description": description,
        "budget": extract_icon_value(job_card, "fa-usd-circle"),
        "duration": extract_icon_value(job_card, "fa-business-time"),
        "offers_count": extract_icon_value(job_card, "fa-ballot"),
        "job_submit_time": extract_icon_value(job_card, "fa-clock"),
        "location": extract_icon_value(job_card, "fa-map-marker-alt"),
        "project_state": extract_icon_value(job_card, "fa-check-circle"),
    }


def extract_icon_value(job_card, icon_class: str) -> str:
    icon = job_card.find("span", class_=lambda classes: has_class(classes, icon_class))
    if not icon:
        return ""

    container = icon.find_parent("span")
    return clean_text(container.get_text(" ", strip=True) if container else icon.get_text())


def extract_hiring_person_name(job_card, title_link) -> str:
    title_href = title_link.get("href", "")
    profile_links = []

    for link in job_card.find_all("a", href=True):
        href = link.get("href", "")
        name = clean_text(link.get_text())
        if name and href != title_href and "/project/" not in href:
            profile_links.append(name)

    return profile_links[-1] if profile_links else ""


def has_class(classes, class_name: str) -> bool:
    if not classes:
        return False
    if isinstance(classes, str):
        classes = classes.split()
    return class_name in classes


def get_text_or_empty(element) -> str:
    return element.get_text(" ", strip=True) if element else ""


def clean_text(value: str) -> str:
    return " ".join((value or "").split())
