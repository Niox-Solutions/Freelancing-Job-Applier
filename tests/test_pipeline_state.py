import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MAIN_DIR = Path(__file__).resolve().parent.parent
WRITER_AGENT_DIR = MAIN_DIR / "proposal writer agent"
for path in (MAIN_DIR, WRITER_AGENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run  # noqa: E402
import groq_proposal_service  # noqa: E402
from project_scraper import is_recent_job, project_age_minutes  # noqa: E402
from proposal_writer_agent import proposal_file_slug  # noqa: E402


class PipelineStateTest(unittest.TestCase):
    def test_successful_and_ineligible_jobs_are_considered_handled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "pipeline_runs.csv"
            with log_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=run.PIPELINE_LOG_HEADERS,
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "job_link": "https://nafezly.com/project/1-failed",
                        "status": "failed",
                    }
                )
                writer.writerow(
                    {
                        "job_link": "https://nafezly.com/project/2-success",
                        "status": "success",
                    }
                )
                writer.writerow(
                    {
                        "job_link": "https://nafezly.com/project/3-skipped",
                        "status": "skipped",
                    }
                )

            original_path = run.PIPELINE_LOG_PATH
            run.PIPELINE_LOG_PATH = log_path
            try:
                self.assertEqual(
                    run.read_pipeline_links(),
                    {
                        "https://nafezly.com/project/2-success",
                        "https://nafezly.com/project/3-skipped",
                    },
                )
            finally:
                run.PIPELINE_LOG_PATH = original_path

    def test_proposal_filename_uses_project_id(self) -> None:
        self.assertEqual(
            proposal_file_slug("https://nafezly.com/project/50644-example"),
            "50644",
        )

    def test_arabic_job_age_parser(self) -> None:
        cases = {
            "منذ لحظات": 0,
            "منذ دقيقة": 1,
            "منذ دقيقتين": 2,
            "منذ ٣ دقائق": 3,
            "منذ 4 دقائق": 4,
            "منذ 5 دقائق": 5,
            "منذ ساعة": None,
            "منذ يومين": None,
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(project_age_minutes(label), expected)

    def test_recent_job_boundary_is_strictly_under_five_minutes(self) -> None:
        self.assertTrue(is_recent_job("منذ 4 دقائق", max_age_minutes=5))
        self.assertFalse(is_recent_job("منذ 5 دقائق", max_age_minutes=5))
        self.assertFalse(is_recent_job("منذ 6 دقائق", max_age_minutes=5))

    def test_groq_calls_wait_for_two_second_interval(self) -> None:
        original_last_call = groq_proposal_service._last_groq_call_at
        original_interval = groq_proposal_service.GROQ_CALL_INTERVAL_SECONDS
        groq_proposal_service._last_groq_call_at = 100.0
        groq_proposal_service.GROQ_CALL_INTERVAL_SECONDS = 2

        try:
            with (
                patch.object(
                    groq_proposal_service.time,
                    "monotonic",
                    side_effect=[101.25, 102.0],
                ),
                patch.object(groq_proposal_service.time, "sleep") as sleep,
            ):
                groq_proposal_service.wait_for_groq_call_interval()

            sleep.assert_called_once_with(0.75)
        finally:
            groq_proposal_service._last_groq_call_at = original_last_call
            groq_proposal_service.GROQ_CALL_INTERVAL_SECONDS = original_interval


if __name__ == "__main__":
    unittest.main()
