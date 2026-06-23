from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import urlparse

from selenium import webdriver

from groq_proposal_service import generate_proposal_data_sync
from project_description_scraper import scrape_project_description


@dataclass
class ProposalWriterResult:
    project_link: str
    project_title: str
    project_description: str
    proposal: str
    period: int
    cost: int
    output_path: Path


class NafezlyProposalWriterAgent:
    name = "Nafezly Proposal Writer Agent"

    def __init__(self, *, output_dir: str | Path = "generated proposals") -> None:
        self.output_dir = Path(output_dir)

    def run(
        self,
        project_link: str,
        *,
        driver: webdriver.Chrome,
    ) -> ProposalWriterResult:
        print(f"Starting {self.name}...")
        print(f"Project link: {project_link}")

        project = scrape_project_description(project_link, driver)
        if not project["project_description"]:
            raise RuntimeError("Could not find the project description on this page.")

        print("Project description extracted.")
        proposal_data = generate_proposal_data_sync(project)
        output_path = self.save_proposal(project, proposal_data)

        print(f"Proposal saved to: {output_path}")
        return ProposalWriterResult(
            project_link=project["project_link"],
            project_title=project["project_title"],
            project_description=project["project_description"],
            proposal=proposal_data["proposal"],
            period=proposal_data["period"],
            cost=proposal_data["cost"],
            output_path=output_path,
        )

    def save_proposal(self, project: dict, proposal_data: dict) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        project_slug = proposal_file_slug(project["project_link"])
        output_path = self.output_dir / f"proposal_{project_slug}_{timestamp}.txt"

        content = "\n\n".join(
            [
                f"Project link: {project['project_link']}",
                f"Project title: {project['project_title']}",
                f"Project description:\n{project['project_description']}",
                f"Period days: {proposal_data['period']}",
                f"Cost USD: {proposal_data['cost']}",
                f"Proposal:\n{proposal_data['proposal']}",
            ]
        )
        output_path.write_text(content, encoding="utf-8")
        return output_path


def proposal_file_slug(project_link: str) -> str:
    path_name = Path(urlparse(project_link).path).name
    match = re.match(r"(\d+)", path_name)
    return match.group(1) if match else "project"
