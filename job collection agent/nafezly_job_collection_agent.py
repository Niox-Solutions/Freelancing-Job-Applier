from dataclasses import dataclass
import sys
from pathlib import Path

MAIN_DIR = Path(__file__).resolve().parent.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from config import JOBS_CSV_PATH
from login_cases import CASES, LoginCase, run_cases_until_success


@dataclass
class JobCollectionResult:
    agent_name: str
    site_url: str
    csv_path: str
    success: bool
    login_approach: str | None
    login_results: list[dict]


class NafezlyJobCollectionAgent:
    name = "Nafezly Job Collection Agent"
    site_url = "https://nafezly.com"

    def __init__(
        self,
        *,
        csv_path: str = JOBS_CSV_PATH,
        login_cases: list[LoginCase] | None = None,
    ) -> None:
        self.csv_path = csv_path
        self.login_cases = login_cases or CASES

    def run(self) -> JobCollectionResult:
        self.print_start()
        login_results = run_cases_until_success(self.login_cases)
        success_case = self.find_success_case(login_results)

        if success_case:
            print(f"Finished with login approach: {success_case['name']}")
        else:
            print("No login approach succeeded. CSV was not updated.")

        return JobCollectionResult(
            agent_name=self.name,
            site_url=self.site_url,
            csv_path=self.csv_path,
            success=success_case is not None,
            login_approach=success_case["name"] if success_case else None,
            login_results=login_results,
        )

    def print_start(self) -> None:
        print(f"Starting {self.name}...")
        print(f"Site: {self.site_url}")
        print(f"CSV output: {self.csv_path}")
        print("Mode: collect open development projects only.")

    @staticmethod
    def find_success_case(login_results: list[dict]) -> dict | None:
        return next(
            (result for result in login_results if result["status"] == "SUCCESS"),
            None,
        )


def main() -> None:
    NafezlyJobCollectionAgent().run()


if __name__ == "__main__":
    main()
