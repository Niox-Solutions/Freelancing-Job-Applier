import argparse
import csv
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from selenium import webdriver


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()

MAIN_DIR = Path(__file__).resolve().parent
JOB_AGENT_DIR = MAIN_DIR / "job collection agent"
PROPOSAL_WRITER_DIR = MAIN_DIR / "proposal writer agent"
PROPOSAL_SUBMIT_DIR = MAIN_DIR / "proposal submit agent"
for path in (MAIN_DIR, JOB_AGENT_DIR, PROPOSAL_WRITER_DIR, PROPOSAL_SUBMIT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import (  # noqa: E402
    JOBS_CSV_PATH,
    JOB_LIST_PAGES_PER_CYCLE,
    JOB_POLL_INTERVAL_MINUTES,
    PROJECTS_URL,
    RECENT_JOB_MAX_AGE_MINUTES,
)
from login_flows import sign_in_with_first_approach  # noqa: E402
from project_scraper import (  # noqa: E402
    scrape_open_development_projects,
    set_job_saved_callback,
)
from proposal_submit_agent import (  # noqa: E402
    NafezlyProposalSubmitAgent,
    OfferFormUnavailableError,
)
from proposal_writer_agent import NafezlyProposalWriterAgent  # noqa: E402


PIPELINE_LOG_PATH = MAIN_DIR / "pipeline_runs.csv"
PIPELINE_LOG_HEADERS = [
    "processed_at",
    "job_title",
    "job_link",
    "proposal_path",
    "period",
    "cost",
    "submitted",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect Nafezly jobs, save each new open job, write a proposal, "
            "and fill or submit the offer form before continuing."
        )
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Actually submit proposals. Without this, the submitter only fills forms.",
    )
    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Leave the shared Chrome window open after the pipeline finishes.",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=0,
        help="Stop after processing this many pipeline jobs. 0 means no limit.",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Process jobs even if they already exist in pipeline_runs.csv.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one monitoring cycle instead of polling continuously.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=JOB_LIST_PAGES_PER_CYCLE,
        help="Number of job-list pages checked in every cycle.",
    )
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        default=RECENT_JOB_MAX_AGE_MINUTES,
        help="Only process jobs newer than this many minutes.",
    )
    parser.add_argument(
        "--poll-interval-minutes",
        type=int,
        default=JOB_POLL_INTERVAL_MINUTES,
        help="Minutes between monitoring cycles.",
    )
    return parser.parse_args()


class PipelineRunner:
    def __init__(
        self,
        *,
        submit: bool,
        keep_browser_open: bool,
        max_jobs: int,
        reprocess: bool,
        once: bool,
        pages: int,
        max_age_minutes: int,
        poll_interval_minutes: int,
    ) -> None:
        self.submit = submit
        self.keep_browser_open = keep_browser_open
        self.max_jobs = max_jobs
        self.reprocess = reprocess
        self.once = once
        self.pages = max(1, pages)
        self.max_age_minutes = max(1, max_age_minutes)
        self.poll_interval_minutes = max(1, poll_interval_minutes)
        self.processed_count = 0
        self.failed_count = 0
        self.seen_pipeline_links = read_pipeline_links()
        self.writer = NafezlyProposalWriterAgent(
            output_dir=MAIN_DIR / "proposal writer agent" / "generated proposals"
        )
        self.submitter = NafezlyProposalSubmitAgent()

    def run(self) -> None:
        print("Starting Nafezly full pipeline...")
        print(f"CSV output: {JOBS_CSV_PATH}")
        print(f"Submit mode: {'REAL SUBMIT' if self.submit else 'DRY RUN'}")
        print(f"Reprocess existing pipeline jobs: {self.reprocess}")
        print(
            f"Monitoring: {self.pages} page(s), jobs under "
            f"{self.max_age_minutes} minute(s), every "
            f"{self.poll_interval_minutes} minute(s)."
        )

        driver = None
        try:
            driver = sign_in_with_first_approach()
            set_job_saved_callback(self.process_saved_job)
            cycle_number = 0

            while True:
                cycle_number += 1
                failures_before_cycle = self.failed_count
                print(
                    f"\nStarting monitoring cycle {cycle_number} at "
                    f"{datetime.now().isoformat(timespec='seconds')}."
                )
                driver.get(PROJECTS_URL)
                scrape_open_development_projects(
                    driver,
                    max_pages=self.pages,
                    max_age_minutes=self.max_age_minutes,
                )

                cycle_failures = self.failed_count - failures_before_cycle
                if cycle_failures:
                    print(
                        f"Cycle {cycle_number} completed with "
                        f"{cycle_failures} failed job(s); monitoring will continue."
                    )
                else:
                    print(f"Cycle {cycle_number} completed successfully.")

                if self.max_jobs and self.processed_count >= self.max_jobs:
                    print("Maximum pipeline job count reached.")
                    break
                if self.once:
                    break

                next_cycle = datetime.now() + timedelta(
                    minutes=self.poll_interval_minutes
                )
                print(
                    f"Next refresh at "
                    f"{next_cycle.isoformat(timespec='seconds')}."
                )
                time.sleep(self.poll_interval_minutes * 60)

            print("Pipeline monitoring finished.")
        except KeyboardInterrupt:
            print("Pipeline monitoring stopped by user.")
        finally:
            set_job_saved_callback(None)
            if driver and not self.keep_browser_open:
                driver.quit()
                print("Shared browser closed.")
            elif driver:
                print("Shared browser left open.")

    def process_saved_job(
        self,
        job: dict,
        driver: webdriver.Chrome,
    ) -> bool:
        if self.max_jobs and self.processed_count >= self.max_jobs:
            return False

        job_link = job.get("job_link", "")
        if job_link in self.seen_pipeline_links and not self.reprocess:
            print(f"Skipping already processed pipeline job: {job_link}")
            return True

        self.processed_count += 1
        print("\n" + "=" * 60)
        print(f"PIPELINE JOB #{self.processed_count}")
        print(f"Title: {job.get('job_title', '')}")
        print(f"Link: {job.get('job_link', '')}")
        print("=" * 60)

        status = "success"
        error = ""
        proposal_result = None
        submit_result = None
        collector_window = driver.current_window_handle

        try:
            driver.switch_to.new_window("tab")
            try:
                proposal_result = self.writer.run(
                    job["job_link"],
                    driver=driver,
                )
                submit_result = self.submitter.run(
                    proposal_result,
                    driver=driver,
                    submit=self.submit,
                )
            finally:
                restore_collector_window(driver, collector_window)
        except OfferFormUnavailableError as exc:
            status = "skipped"
            error = str(exc)[:500]
            print(f"Pipeline job skipped: {error}")
        except Exception as exc:
            status = "failed"
            error = str(exc)[:500]
            self.failed_count += 1
            print(f"Pipeline job failed: {error}")
            traceback.print_exc()

        append_pipeline_log(
            {
                "processed_at": datetime.now().isoformat(timespec="seconds"),
                "job_title": job.get("job_title", ""),
                "job_link": job.get("job_link", ""),
                "proposal_path": str(proposal_result.output_path)
                if proposal_result
                else "",
                "period": proposal_result.period if proposal_result else "",
                "cost": proposal_result.cost if proposal_result else "",
                "submitted": submit_result.submitted if submit_result else False,
                "status": status,
                "error": error,
            }
        )
        if status in {"success", "skipped"}:
            self.seen_pipeline_links.add(job_link)
        return not (self.max_jobs and self.processed_count >= self.max_jobs)


def restore_collector_window(
    driver: webdriver.Chrome,
    collector_window: str,
) -> None:
    handles = driver.window_handles
    for handle in handles:
        if handle == collector_window:
            continue
        driver.switch_to.window(handle)
        driver.close()

    if collector_window not in driver.window_handles:
        raise RuntimeError("The collector browser tab was closed unexpectedly.")

    driver.switch_to.window(collector_window)


def append_pipeline_log(row: dict) -> None:
    file_exists = PIPELINE_LOG_PATH.exists() and PIPELINE_LOG_PATH.stat().st_size > 0

    with PIPELINE_LOG_PATH.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=PIPELINE_LOG_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({header: row.get(header, "") for header in PIPELINE_LOG_HEADERS})


def read_pipeline_links() -> set[str]:
    if not PIPELINE_LOG_PATH.exists() or PIPELINE_LOG_PATH.stat().st_size == 0:
        return set()

    with PIPELINE_LOG_PATH.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return {
            row.get("job_link", "").strip()
            for row in reader
            if row.get("job_link", "").strip()
            and row.get("status", "").strip().lower() in {"success", "skipped"}
        }


def main() -> None:
    args = parse_args()
    PipelineRunner(
        submit=args.submit,
        keep_browser_open=args.keep_browser_open,
        max_jobs=max(0, args.max_jobs),
        reprocess=args.reprocess,
        once=args.once,
        pages=max(1, args.pages),
        max_age_minutes=max(1, args.max_age_minutes),
        poll_interval_minutes=max(1, args.poll_interval_minutes),
    ).run()


if __name__ == "__main__":
    main()
