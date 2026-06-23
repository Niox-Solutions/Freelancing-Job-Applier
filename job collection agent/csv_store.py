import csv
from pathlib import Path


CSV_HEADERS = [
    "hiring_person_name",
    "scraped_at",
    "job_title",
    "job_link",
    "description",
    "offers_count",
    "job_submit_time",
    "budget",
    "duration",
    "location",
    "project_state",
]


def append_jobs(csv_path: str, jobs: list[dict]) -> int:
    if not jobs:
        return 0

    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ensure_csv_headers(path)
    existing_links = read_existing_links(path)
    new_jobs = [job for job in jobs if job.get("job_link") not in existing_links]
    if not new_jobs:
        return 0

    file_exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()

        for job in new_jobs:
            writer.writerow({header: job.get(header, "") for header in CSV_HEADERS})

    return len(new_jobs)


def ensure_csv_headers(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        existing_headers = reader.fieldnames or []
        if all(header in existing_headers for header in CSV_HEADERS):
            return

        rows = list(reader)

    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in CSV_HEADERS})


def read_existing_links(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()

    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return {
            row.get("job_link", "").strip()
            for row in reader
            if row.get("job_link", "").strip()
        }
