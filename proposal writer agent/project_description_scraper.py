from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


DESCRIPTION_H2_CLASSES = ["col-12", "p-0", "naskh", "font-2", "m-0"]


def scrape_project_description(
    project_link: str,
    driver: webdriver.Chrome,
) -> dict:
    driver.get(project_link)
    wait = WebDriverWait(driver, 20)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    wait.until(lambda d: d.find_element(By.TAG_NAME, "body").text.strip())
    wait.until(
        lambda d: extract_description(BeautifulSoup(d.page_source, "html.parser"))
    )

    soup = BeautifulSoup(driver.page_source, "html.parser")
    description = extract_description(soup)
    title = extract_title(soup)

    return {
        "project_link": driver.current_url,
        "project_title": title,
        "project_description": description,
    }


def extract_description(soup: BeautifulSoup) -> str:
    description_heading = soup.find(
        "h2",
        class_=lambda classes: has_all_classes(classes, DESCRIPTION_H2_CLASSES),
    )

    if description_heading:
        return clean_text(description_heading.get_text(" ", strip=True))

    fallback = soup.find("h2")
    return clean_text(fallback.get_text(" ", strip=True)) if fallback else ""


def extract_title(soup: BeautifulSoup) -> str:
    title = soup.find("h1")
    if title:
        return clean_text(title.get_text(" ", strip=True))

    page_title = soup.find("title")
    return clean_text(page_title.get_text(" ", strip=True)) if page_title else ""


def has_all_classes(classes, required_classes: list[str]) -> bool:
    if not classes:
        return False
    if isinstance(classes, str):
        classes = classes.split()
    return all(class_name in classes for class_name in required_classes)


def clean_text(value: str) -> str:
    return " ".join((value or "").split())
