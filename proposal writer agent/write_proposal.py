import argparse
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")

MAIN_DIR = Path(__file__).resolve().parent.parent
JOB_AGENT_DIR = MAIN_DIR / "job collection agent"
if str(JOB_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(JOB_AGENT_DIR))

from browser import create_driver  # noqa: E402
from proposal_writer_agent import NafezlyProposalWriterAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a proposal for a Nafezly project.")
    parser.add_argument("project_link", help="The Nafezly project URL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    driver = create_driver()
    try:
        result = NafezlyProposalWriterAgent().run(
            args.project_link,
            driver=driver,
        )
    finally:
        driver.quit()

    print("\n" + "=" * 60)
    print("PROPOSAL")
    print("=" * 60)
    print(f"Period: {result.period} day(s)")
    print(f"Cost: {result.cost} $")
    print("-" * 60)
    print(result.proposal)


if __name__ == "__main__":
    main()
