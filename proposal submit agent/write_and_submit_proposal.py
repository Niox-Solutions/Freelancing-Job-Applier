import argparse
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")


MAIN_DIR = Path(__file__).resolve().parent.parent
JOB_AGENT_DIR = MAIN_DIR / "job collection agent"
PROPOSAL_WRITER_DIR = MAIN_DIR / "proposal writer agent"
for path in (JOB_AGENT_DIR, PROPOSAL_WRITER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from login_flows import sign_in_with_first_approach  # noqa: E402
from proposal_submit_agent import NafezlyProposalSubmitAgent  # noqa: E402
from proposal_writer_agent import NafezlyProposalWriterAgent  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write and optionally submit a proposal for a Nafezly project."
    )
    parser.add_argument("project_link", help="The Nafezly project URL.")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Actually click the submit button. Without this, the form is only filled.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    driver = sign_in_with_first_approach()
    try:
        proposal_result = NafezlyProposalWriterAgent().run(
            args.project_link,
            driver=driver,
        )
        submit_result = NafezlyProposalSubmitAgent().run(
            proposal_result,
            driver=driver,
            submit=args.submit,
        )
    finally:
        driver.quit()

    print("\n" + "=" * 60)
    print("SUBMISSION RESULT")
    print("=" * 60)
    print(f"Project: {submit_result.project_link}")
    print(f"Period: {submit_result.period} day(s)")
    print(f"Cost: {submit_result.cost} $")
    print(f"Submitted: {submit_result.submitted}")


if __name__ == "__main__":
    main()
