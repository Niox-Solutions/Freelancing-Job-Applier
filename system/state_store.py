import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "system" / "system_state.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            task_label TEXT NOT NULL,
            command TEXT NOT NULL,
            status TEXT NOT NULL,
            pid TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            exit_code TEXT,
            error TEXT
        )
        """
    )
    connection.commit()
    return connection


def create_task_run(*, task_type: str, task_label: str, command: str, started_at: str) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO task_runs (task_type, task_label, command, status, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_type, task_label, command, "running", started_at),
        )
        connection.commit()
        return int(cursor.lastrowid)


def mark_task_started(run_id: int, pid: str) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE task_runs SET pid = ? WHERE id = ?",
            (pid, run_id),
        )
        connection.commit()


def finish_task_run(
    *,
    run_id: int,
    finished_at: str,
    exit_code: str,
    error: str = "",
    status: str | None = None,
) -> None:
    status = status or ("success" if str(exit_code) == "0" else "failed")
    with connect() as connection:
        connection.execute(
            """
            UPDATE task_runs
            SET status = ?, finished_at = ?, exit_code = ?, error = ?
            WHERE id = ?
            """,
            (status, finished_at, str(exit_code), error, run_id),
        )
        connection.commit()


def recent_task_runs(limit: int = 20) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, task_type, task_label, command, status, pid, started_at,
                   finished_at, exit_code, error
            FROM task_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_task_run() -> dict:
    runs = recent_task_runs(1)
    return runs[0] if runs else {}


def mark_stale_running_tasks(finished_at: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE task_runs
            SET status = ?, finished_at = ?, exit_code = ?, error = ?
            WHERE status = ?
            """,
            ("stopped", finished_at, "stopped", "Controller restarted while task was running.", "running"),
        )
        connection.commit()
