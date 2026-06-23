import sys
import unittest
from pathlib import Path
from urllib.parse import quote


MAIN_DIR = Path(__file__).resolve().parent.parent
JOB_AGENT_DIR = MAIN_DIR / "job collection agent"
SUBMIT_AGENT_DIR = MAIN_DIR / "proposal submit agent"
for path in (JOB_AGENT_DIR, SUBMIT_AGENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from browser import create_driver  # noqa: E402
from proposal_submit_agent import NafezlyProposalSubmitAgent  # noqa: E402


class ProposalSubmitFormTest(unittest.TestCase):
    def test_fills_form_behind_support_widget(self) -> None:
        page = """
        <html>
          <body style="height: 1800px">
            <form id="offer-form" style="margin-top: 800px">
              <input type="number" id="period">
              <input type="number" id="cost">
              <textarea id="offer_description"></textarea>
              <button id="make-offer" type="button">Submit</button>
            </form>
            <span
              class="support-widget"
              style="position: fixed; right: 0; bottom: 0; width: 100%;
                     height: 300px; z-index: 1200"
            >overlay</span>
          </body>
        </html>
        """
        driver = create_driver()
        agent = NafezlyProposalSubmitAgent(timeout=10)

        try:
            driver.get("data:text/html;charset=utf-8," + quote(page))
            agent.wait_for_offer_form(driver)
            agent.dismiss_obstructions(driver)
            agent.fill_offer_form(
                driver,
                period=7,
                cost=45,
                proposal="Test proposal",
            )

            self.assertEqual(
                driver.find_element("id", "period").get_attribute("value"),
                "7",
            )
            self.assertEqual(
                driver.find_element("id", "cost").get_attribute("value"),
                "45",
            )
            self.assertEqual(
                driver.find_element("id", "offer_description").get_attribute(
                    "value"
                ),
                "Test proposal",
            )
        finally:
            driver.quit()


if __name__ == "__main__":
    unittest.main()
