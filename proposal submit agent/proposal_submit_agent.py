from dataclasses import dataclass
import sys
import time
from pathlib import Path
from typing import Protocol

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


MAIN_DIR = Path(__file__).resolve().parent.parent
JOB_AGENT_DIR = MAIN_DIR / "job collection agent"
PROPOSAL_WRITER_DIR = MAIN_DIR / "proposal writer agent"
for path in (MAIN_DIR, JOB_AGENT_DIR, PROPOSAL_WRITER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class ProposalWriterResultLike(Protocol):
    project_link: str
    proposal: str
    period: int
    cost: int


class OfferFormUnavailableError(RuntimeError):
    pass


@dataclass
class ProposalSubmitResult:
    project_link: str
    period: int
    cost: int
    submitted: bool
    verified: bool


class NafezlyProposalSubmitAgent:
    name = "Nafezly Proposal Submit Agent"

    def __init__(self, *, timeout: int = 25) -> None:
        self.timeout = timeout

    def run(
        self,
        proposal_result: ProposalWriterResultLike,
        *,
        driver: webdriver.Chrome,
        submit: bool = False,
    ) -> ProposalSubmitResult:
        print(f"Starting {self.name}...")
        print(f"Project link: {proposal_result.project_link}")
        driver.get(proposal_result.project_link)

        for attempt in range(1, 3):
            try:
                self.wait_for_page_ready(driver)
                self.wait_for_offer_form(driver)
                break
            except OfferFormUnavailableError:
                if attempt == 2:
                    raise
                print("Offer form unavailable on first load; refreshing once.")
                driver.refresh()

        last_error = None
        for attempt in range(1, 3):
            try:
                self.dismiss_obstructions(driver)
                self.fill_offer_form(
                    driver,
                    period=proposal_result.period,
                    cost=proposal_result.cost,
                    proposal=proposal_result.proposal,
                )
                break
            except (TimeoutException, ElementClickInterceptedException, RuntimeError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
                print(f"Offer form fill attempt {attempt} failed; retrying.")
                driver.refresh()
                self.wait_for_page_ready(driver)
                self.wait_for_offer_form(driver)
        else:
            raise RuntimeError(f"Could not fill offer form: {last_error}")

        if submit:
            self.submit_offer(driver)
            self.wait_for_submission_success(driver)
            print("Proposal submitted and confirmed.")
        else:
            print("Dry run complete. Form values were filled and verified.")

        return ProposalSubmitResult(
            project_link=proposal_result.project_link,
            period=proposal_result.period,
            cost=proposal_result.cost,
            submitted=submit,
            verified=True,
        )

    def wait_for_page_ready(self, driver: webdriver.Chrome) -> None:
        WebDriverWait(driver, self.timeout).until(
            lambda current: current.execute_script("return document.readyState")
            == "complete"
        )

    def wait_for_offer_form(self, driver: webdriver.Chrome) -> None:
        wait = WebDriverWait(driver, self.timeout)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "offer-form")))
            wait.until(EC.presence_of_element_located((By.ID, "period")))
            wait.until(EC.presence_of_element_located((By.ID, "cost")))
            wait.until(EC.presence_of_element_located((By.ID, "offer_description")))
        except TimeoutException as exc:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            raise OfferFormUnavailableError(
                "The offer form is unavailable. The project may be closed, "
                "already submitted, ineligible for this account, or the "
                "session may have expired. "
                f"Page: {driver.current_url}. Text: {body_text[:250]}"
            ) from exc

    def fill_offer_form(
        self,
        driver: webdriver.Chrome,
        *,
        period: int,
        cost: int,
        proposal: str,
    ) -> None:
        values = {
            "period": str(period),
            "cost": str(cost),
            "offer_description": proposal.strip(),
        }
        if not values["offer_description"]:
            raise RuntimeError("Cannot submit an empty proposal.")

        for element_id, value in values.items():
            set_input_value(driver, element_id, value, timeout=self.timeout)

        actual_values = {
            element_id: driver.find_element(By.ID, element_id).get_attribute("value")
            for element_id in values
        }
        mismatches = [
            element_id
            for element_id, expected in values.items()
            if actual_values[element_id].strip() != expected.strip()
        ]
        if mismatches:
            raise RuntimeError(
                "Offer form verification failed for: " + ", ".join(mismatches)
            )

        print("Offer form filled and verified.")

    def dismiss_obstructions(self, driver: webdriver.Chrome) -> None:
        driver.execute_script(
            """
            const selectors = [
                '.support-widget',
                '.contact-wedgit-toggle',
                '.contact-widget-toggle'
            ];
            for (const selector of selectors) {
                document.querySelectorAll(selector).forEach((node) => {
                    node.style.setProperty('display', 'none', 'important');
                    node.style.setProperty('pointer-events', 'none', 'important');
                });
            }
            """
        )

    def submit_offer(self, driver: webdriver.Chrome) -> None:
        button = WebDriverWait(driver, self.timeout).until(
            EC.element_to_be_clickable((By.ID, "make-offer"))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            button,
        )
        self.dismiss_obstructions(driver)
        time.sleep(0.3)

        try:
            button.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", button)

    def wait_for_submission_success(self, driver: webdriver.Chrome) -> None:
        success_phrases = (
            "تم إضافة عرضك",
            "تم تقديم عرضك",
            "تم ارسال عرضك",
            "تم إرسال عرضك",
            "عرضك بنجاح",
        )

        def submission_finished(current: webdriver.Chrome) -> bool:
            body_text = current.find_element(By.TAG_NAME, "body").text
            form_missing = not current.find_elements(By.ID, "offer-form")
            success_text = any(phrase in body_text for phrase in success_phrases)
            return form_missing or success_text

        try:
            WebDriverWait(driver, self.timeout).until(submission_finished)
        except TimeoutException as exc:
            validation_messages = driver.execute_script(
                """
                return Array.from(
                    document.querySelectorAll(
                        '.invalid-feedback, .alert-danger, .text-danger, [role="alert"]'
                    )
                ).map((node) => node.innerText.trim()).filter(Boolean);
                """
            )
            details = " | ".join(validation_messages or [])
            raise RuntimeError(
                "The submit button was clicked, but Nafezly did not confirm the "
                f"proposal submission. {details}"
            ) from exc


def set_input_value(
    driver: webdriver.Chrome,
    element_id: str,
    value: str,
    *,
    timeout: int,
) -> None:
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, element_id))
    )
    driver.execute_script(
        """
        const element = arguments[0];
        const value = arguments[1];
        const prototype = element instanceof HTMLTextAreaElement
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set;

        element.scrollIntoView({block: 'center', inline: 'center'});
        setter.call(element, value);
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('blur', { bubbles: true }));
        """,
        element,
        value,
    )
