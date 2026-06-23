import csv
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import traceback
from collections import Counter
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from config import CONFIG_OVERRIDES_PATH
from system import pages as system_pages
from system import state_store


MAIN_DIR = Path(__file__).resolve().parent
PIPELINE_LOG_PATH = MAIN_DIR / "pipeline_runs.csv"
SYSTEM_LOG_PATH = MAIN_DIR / "system.log"
RUN_SCRIPT_PATH = MAIN_DIR / "run.py"
JOB_COLLECTION_SCRIPT_PATH = MAIN_DIR / "job collection agent" / "scrape_projects_to_csv.py"
PROPOSAL_WRITER_SCRIPT_PATH = MAIN_DIR / "proposal writer agent" / "write_proposal.py"
PROPOSAL_SUBMIT_SCRIPT_PATH = MAIN_DIR / "proposal submit agent" / "write_and_submit_proposal.py"
PROPOSAL_DIRS = [
    MAIN_DIR / "proposal writer agent" / "generated proposals",
    MAIN_DIR / "proposal submit agent" / "generated proposals",
]
DASHBOARD_USERNAME = os.getenv("FATMA_DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("FATMA_DASHBOARD_PASSWORD", "change-me")
SESSION_COOKIE = "agent_dashboard_session"
SESSIONS: set[str] = set()
RUN_STATE = {
    "running": False,
    "started_at": "",
    "finished_at": "",
    "exit_code": "",
    "command": "",
    "pid": "",
    "last_error": "",
    "task_type": "",
    "task_label": "",
    "status": "idle",
    "run_id": "",
    "timeout_minutes": "",
}
TASK_LABELS = {
    "full_pipeline": "Full Pipeline",
    "collect_jobs": "Collect Jobs",
    "write_proposal": "Write Proposal",
    "write_and_submit": "Write And Submit",
}
CSV_READ_ERRORS_LOGGED: set[str] = set()

CONFIG_FIELDS = [
    ("NAFEZLY_USERNAME", "Nafezly Username", "text"),
    ("NAFEZLY_PASSWORD", "Nafezly Password", "password"),
    ("JOBS_CSV_PATH", "Jobs CSV Path", "text"),
    ("HOME_URL", "Home URL", "url"),
    ("LOGIN_URL", "Login URL", "url"),
    ("PROJECTS_URL", "Projects URL", "url"),
    ("CHROME_USER_DATA", "Chrome User Data", "text"),
    ("CHROME_PROFILE", "Chrome Profile", "text"),
    ("RECENT_JOB_MAX_AGE_MINUTES", "Maximum Job Age Minutes", "number"),
    ("JOB_POLL_INTERVAL_MINUTES", "Polling Interval Minutes", "number"),
    ("JOB_LIST_PAGES_PER_CYCLE", "Pages Per Cycle", "number"),
    ("GROQ_API_KEY", "Groq API Key", "password"),
    ("GROQ_BASE_URL", "Groq Base URL", "url"),
    ("GROQ_PROPOSAL_MODEL", "Proposal Model", "text"),
    ("GROQ_CALL_INTERVAL_SECONDS", "Groq Call Interval Seconds", "number"),
    ("DEFAULT_PROPOSAL_PERIOD_DAYS", "Default Period Days", "number"),
    ("DEFAULT_PROPOSAL_COST_USD", "Default Cost USD", "number"),
]
CONFIG_ATTRS = {
    "NAFEZLY_USERNAME": "Username",
    "NAFEZLY_PASSWORD": "Password",
    "GROQ_PROPOSAL_MODEL": "PROPOSAL_MODEL",
}


def read_csv(path: Path | str) -> list[dict]:
    path = Path(path)
    try:
        if not path.exists() or path.stat().st_size == 0:
            return []
    except OSError as exc:
        log_csv_read_error(path, exc)
        return []

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            return list(csv.DictReader(csv_file))
    except OSError as exc:
        log_csv_read_error(path, exc)
        return []


def log_csv_read_error(path: Path, exc: OSError) -> None:
    key = str(path)
    if key in CSV_READ_ERRORS_LOGGED:
        return
    CSV_READ_ERRORS_LOGGED.add(key)
    append_system_log(f"Could not read CSV path {path}: {exc}")


def read_config_values() -> dict:
    defaults = {}
    try:
        import config

        for key, _, _ in CONFIG_FIELDS:
            defaults[key] = str(getattr(config, CONFIG_ATTRS.get(key, key), ""))
    except Exception:
        defaults = {key: "" for key, _, _ in CONFIG_FIELDS}

    if CONFIG_OVERRIDES_PATH.exists():
        try:
            with CONFIG_OVERRIDES_PATH.open("r", encoding="utf-8") as config_file:
                overrides = json.load(config_file)
        except (OSError, json.JSONDecodeError):
            overrides = {}
        if isinstance(overrides, dict):
            defaults.update({key: str(value) for key, value in overrides.items()})

    return defaults


def current_jobs_csv_path() -> Path:
    return Path(read_config_values().get("JOBS_CSV_PATH", ""))


def write_config_values(values: dict) -> None:
    clean_values = {key: values.get(key, "").strip() for key, _, _ in CONFIG_FIELDS}
    with CONFIG_OVERRIDES_PATH.open("w", encoding="utf-8") as config_file:
        json.dump(clean_values, config_file, indent=2)


def number_from_text(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def latest_file_time(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        timestamp = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def collect_proposal_files() -> list[Path]:
    files = []
    for proposal_dir in PROPOSAL_DIRS:
        try:
            if proposal_dir.exists():
                files.extend(proposal_dir.glob("proposal_*.txt"))
        except OSError as exc:
            append_system_log(f"Could not inspect proposal directory {proposal_dir}: {exc}")
    return sorted(files, key=safe_mtime, reverse=True)


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def build_stats(jobs: list[dict], runs: list[dict]) -> dict:
    budgets = [number_from_text(job.get("budget", "")) for job in jobs]
    budgets = [budget for budget in budgets if budget is not None]
    offers = [number_from_text(job.get("offers_count", "")) for job in jobs]
    offers = [count for count in offers if count is not None]
    statuses = Counter(row.get("status", "unknown") or "unknown" for row in runs)
    successful_rows = [
        row for row in runs if str(row.get("status", "")).lower() == "success"
    ]
    submitted = sum(
        1
        for row in successful_rows
        if str(row.get("submitted", "")).lower() == "true"
    )
    proposal_files = collect_proposal_files()

    return {
        "total_jobs": len(jobs),
        "total_pipeline_runs": len(runs),
        "successful_runs": statuses.get("success", 0),
        "failed_runs": statuses.get("failed", 0),
        "submitted_runs": submitted,
        "dry_runs": sum(
            1
            for row in successful_rows
            if str(row.get("submitted", "")).lower() != "true"
        ),
        "proposal_files": len(proposal_files),
        "avg_budget": round(sum(budgets) / len(budgets), 2) if budgets else 0,
        "avg_offers": round(sum(offers) / len(offers), 2) if offers else 0,
        "states": Counter(job.get("project_state", "unknown") or "unknown" for job in jobs),
        "locations": Counter(job.get("location", "unknown") or "unknown" for job in jobs),
        "statuses": statuses,
    }


def build_agent_states(jobs: list[dict], runs: list[dict]) -> list[dict]:
    last_run = runs[-1] if runs else {}
    proposals = collect_proposal_files()
    latest_proposal = proposals[0] if proposals else None
    pipeline_running = bool(RUN_STATE["running"])
    pipeline_status = "Running" if pipeline_running else "Idle"

    return [
        {
            "agent": "Job Collection Agent",
            "state": pipeline_status if pipeline_running else ("Ready" if path_exists(current_jobs_csv_path()) else "Waiting for CSV"),
            "last_activity": latest_file_time(current_jobs_csv_path()),
            "items": len(jobs),
            "info": f"Scrapes jobs into {current_jobs_csv_path()}",
        },
        {
            "agent": "Proposal Writer Agent",
            "state": pipeline_status if pipeline_running else ("Ready" if proposals else "No proposals yet"),
            "last_activity": latest_file_time(latest_proposal) if latest_proposal else "",
            "items": len(proposals),
            "info": "Generates proposal text files from collected job links.",
        },
        {
            "agent": "Proposal Submit Agent",
            "state": pipeline_status if pipeline_running else (last_run.get("status", "No runs yet") or "No runs yet"),
            "last_activity": last_run.get("processed_at", ""),
            "items": sum(1 for row in runs if str(row.get("submitted", "")).lower() == "true"),
            "info": "Fills proposal forms in dry-run mode unless real submit is selected.",
        },
        {
            "agent": "System Runner",
            "state": pipeline_status,
            "last_activity": RUN_STATE["started_at"] or RUN_STATE["finished_at"],
            "items": RUN_STATE["pid"] or "",
            "info": RUN_STATE["command"] or "Use Run Agents to start the pipeline.",
        },
    ]


def card(label: str, value) -> str:
    return f"""
    <section class="metric">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(str(value))}</strong>
    </section>
    """


def compact_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<small>{html.escape(detail)}</small>" if detail else ""
    return f"""
    <section class="compact-card">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(str(value))}</strong>
      {detail_html}
    </section>
    """


def badge(value: str) -> str:
    status = (value or "unknown").lower()
    tone = "ok" if status in {"success", "ready", "idle"} else "warn"
    if status in {"failed", "error"}:
        tone = "bad"
    if status == "running":
        tone = "live"
    return f"<span class='badge {tone}'>{html.escape(value or 'unknown')}</span>"


def run_control_panel(compact: bool = False) -> str:
    form_class = "run-form compact" if compact else "run-form"
    button_text = "Running" if RUN_STATE["running"] else "Run Agents"
    return f"""
    <form class="{form_class}" method="post" action="/run">
      <label>Max Jobs<input name="max_jobs" type="number" min="0" value="0"></label>
      <label>Mode<select name="submit"><option value="">Dry run</option><option value="on">Real submit</option></select></label>
      <label>After Run<select name="keep_browser_open"><option value="">Close browser</option><option value="on">Keep browser open</option></select></label>
      <button type="submit" {'disabled' if RUN_STATE['running'] else ''}>{button_text}</button>
    </form>
    """


def system_snapshot(jobs: list[dict], runs: list[dict]) -> str:
    last_run = runs[-1] if runs else {}
    csv_state = "Accessible" if path_exists(current_jobs_csv_path()) else "Needs attention"
    last_status = last_run.get("status", "No runs")
    return "".join(
        [
            compact_card("Runner", "Running" if RUN_STATE["running"] else "Idle", RUN_STATE["started_at"] or RUN_STATE["finished_at"]),
            compact_card("Jobs CSV", csv_state, str(current_jobs_csv_path())),
            compact_card("Last Run", last_status, last_run.get("processed_at", "")),
            compact_card("Proposals", str(len(collect_proposal_files())), "generated files"),
        ]
    )


def table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "<p class='empty'>No data yet.</p>"

    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if column.endswith("link") and value:
                safe_url = html.escape(value, quote=True)
                cells.append(f"<td><a href='{safe_url}' target='_blank'>open</a></td>")
            elif column in {"status", "state"}:
                cells.append(f"<td>{badge(str(value))}</td>")
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")

    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def counter_list(counter: Counter) -> str:
    if not counter:
        return "<p class='empty'>No data yet.</p>"

    items = "".join(
        f"<li><span>{html.escape(str(key))}</span><strong>{value}</strong></li>"
        for key, value in counter.most_common(10)
    )
    return f"<ul class='ranked'>{items}</ul>"


def recent_system_log(limit: int = 40000) -> str:
    if not SYSTEM_LOG_PATH.exists():
        return "No system log yet."

    text = SYSTEM_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    return text[-limit:] if len(text) > limit else text


def append_system_log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    with SYSTEM_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def layout(title: str, active: str, body: str, notice: str = "") -> str:
    nav_items = [
        ("/", "Dashboard", "dashboard"),
        ("/agents", "Agents", "agents"),
        ("/data", "Data", "data"),
        ("/configs", "Configs", "configs"),
        ("/logs", "Logs", "logs"),
    ]
    nav = "".join(
        f"<a class='{'active' if item_key == active else ''}' href='{href}'>{label}</a>"
        for href, label, item_key in nav_items
    )
    notice_html = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    run_state = "Running" if RUN_STATE["running"] else "Idle"
    last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - Agent System</title>
  <style>
    :root {{ color-scheme: light; --ink:#182230; --muted:#667085; --line:#d9e0ea; --panel:#ffffff; --band:#f5f7fa; --accent:#0f766e; --accent-2:#2563eb; --danger:#b42318; --warn:#b54708; --rail:#111827; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: var(--band); color: var(--ink); }}
    .app-shell {{ display: grid; grid-template-columns: 238px minmax(0, 1fr); min-height: 100vh; }}
    aside {{ background: var(--rail); color: white; padding: 22px 16px; position: sticky; top: 0; height: 100vh; }}
    .brand {{ display: grid; gap: 5px; padding: 0 8px 18px; border-bottom: 1px solid rgba(255,255,255,.13); }}
    .brand strong {{ font-size: 18px; }}
    .brand span {{ color: #cbd5e1; font-size: 12px; }}
    nav {{ display: grid; gap: 7px; margin-top: 18px; }}
    nav a {{ color: #cbd5e1; text-decoration: none; padding: 11px 12px; border-radius: 8px; font-size: 14px; white-space: nowrap; }}
    nav a.active, nav a:hover {{ background: rgba(255,255,255,.12); color: white; }}
    .workspace {{ min-width: 0; }}
    header {{ background: #ffffff; border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 28px; }}
    .title-stack {{ display: grid; gap: 5px; min-width: 0; }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    .subline {{ color: var(--muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    main {{ padding: 22px 28px 44px; }}
    .actions {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    button, .button {{ border: 1px solid transparent; background: var(--accent); color: white; border-radius: 6px; padding: 10px 14px; font-weight: 700; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; }}
    button.secondary, .button.secondary {{ background: white; color: var(--ink); border-color: var(--line); }}
    button.danger {{ background: var(--danger); }}
    button:disabled {{ opacity: .6; cursor: default; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    .metric {{ background: white; border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 92px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .metric strong {{ font-size: 25px; overflow-wrap: anywhere; }}
    .hero-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; margin-bottom: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 16px; margin-top: 18px; }}
    .panel {{ background: white; border: 1px solid var(--line); border-radius: 8px; padding: 16px; overflow: auto; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 17px; }}
    .panel-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
    .panel-head h2 {{ margin: 0; }}
    .stack {{ display: grid; gap: 16px; }}
    .compact-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .compact-card {{ background: white; border: 1px solid var(--line); border-radius: 8px; padding: 13px; min-width: 0; }}
    .compact-card span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }}
    .compact-card strong {{ display: block; font-size: 17px; overflow-wrap: anywhere; }}
    .compact-card small {{ display: block; color: var(--muted); font-size: 12px; margin-top: 6px; overflow-wrap: anywhere; }}
    .run-form {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }}
    .run-form button {{ min-height: 39px; justify-content: center; }}
    .run-form.compact {{ grid-template-columns: 1fr; }}
    .agent-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .agent-card {{ background: white; border: 1px solid var(--line); border-radius: 8px; padding: 15px; display: grid; gap: 10px; }}
    .agent-card h3 {{ margin: 0; font-size: 15px; }}
    .agent-card dl {{ display: grid; gap: 7px; margin: 0; }}
    .agent-card div {{ display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid #eef2f6; padding-top: 8px; }}
    .agent-card dt {{ color: var(--muted); font-size: 12px; }}
    .agent-card dd {{ margin: 0; font-size: 12px; text-align: right; overflow-wrap: anywhere; }}
    .config-section {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid #eef2f6; }}
    .config-section:first-of-type {{ margin-top: 0; padding-top: 0; border-top: 0; }}
    .config-section h3 {{ margin: 0 0 12px; font-size: 15px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e7ebf1; padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: #4b5563; background: #f8fafc; position: sticky; top: 0; }}
    a {{ color: var(--accent-2); text-decoration: none; }}
    .ranked {{ list-style: none; padding: 0; margin: 0; }}
    .ranked li {{ display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #e7ebf1; }}
    .empty {{ color: var(--muted); }}
    .notice {{ background: #ecfdf3; color: #05603a; border: 1px solid #abefc6; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }}
    .badge {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #eef2f6; color: #364152; }}
    .badge.ok {{ background: #dcfae6; color: #067647; }}
    .badge.warn {{ background: #fef0c7; color: #93370d; }}
    .badge.bad {{ background: #fee4e2; color: #b42318; }}
    .badge.live {{ background: #dbeafe; color: #1d4ed8; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
    label {{ display: grid; gap: 7px; color: #344054; font-size: 13px; font-weight: 700; }}
    input, select {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 10px 11px; color: var(--ink); background: white; }}
    .toolbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
    pre {{ margin: 0; padding: 14px; background: #101828; color: #d0d5dd; border-radius: 8px; overflow: auto; line-height: 1.45; max-height: 70vh; white-space: pre-wrap; }}
    .login {{ min-height: 100vh; display: grid; place-items: center; padding: 24px; }}
    .login .panel {{ width: min(420px, 100%); }}
    @media (max-width: 980px) {{ .app-shell {{ grid-template-columns: 1fr; }} aside {{ position: static; height: auto; }} nav {{ grid-template-columns: repeat(5, minmax(max-content, 1fr)); overflow-x: auto; }} .hero-grid {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 640px) {{ .topbar, main {{ padding-left: 16px; padding-right: 16px; }} .topbar {{ align-items: flex-start; flex-direction: column; }} .metric strong {{ font-size: 21px; }} .run-form {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside>
      <div class="brand">
        <strong>Nafezly Agents</strong>
        <span>Freelancing job applier</span>
      </div>
      <nav>{nav}</nav>
    </aside>
    <div class="workspace">
      <header>
        <div class="topbar">
          <div class="title-stack">
            <h1>{html.escape(title)}</h1>
            <div class="subline">Updated {html.escape(last_seen)} | State: {badge(run_state)}</div>
          </div>
          <form method="post" action="/logout"><button class="secondary" type="submit">Log out</button></form>
        </div>
      </header>
      <main>
        {notice_html}
        {body}
      </main>
    </div>
  </div>
</body>
</html>"""


def render_login(error: str = "") -> str:
    error_html = f"<p class='empty' style='color:#b42318'>{html.escape(error)}</p>" if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login - Agent System</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #172026; }}
    .login {{ min-height: 100vh; display: grid; place-items: center; padding: 24px; }}
    .panel {{ width: min(420px, 100%); background: white; border: 1px solid #d8dee8; border-radius: 8px; padding: 20px; }}
    h1 {{ margin: 0 0 16px; font-size: 23px; }}
    label {{ display: grid; gap: 7px; margin-bottom: 13px; color: #344054; font-size: 13px; font-weight: 700; }}
    input {{ width: 100%; border: 1px solid #d8dee8; border-radius: 6px; padding: 11px; }}
    button {{ width: 100%; border: 0; background: #0f766e; color: white; border-radius: 6px; padding: 11px 14px; font-weight: 700; cursor: pointer; }}
    .empty {{ color: #667085; }}
  </style>
</head>
<body>
  <main class="login">
    <form class="panel" method="post" action="/login">
      <h1>Agent System Login</h1>
      {error_html}
      <label>Username<input name="username" autocomplete="username" autofocus></label>
      <label>Password<input name="password" type="password" autocomplete="current-password"></label>
      <button type="submit">Log in</button>
    </form>
  </main>
</body>
</html>"""


def render_dashboard(notice: str = "") -> str:
    jobs = read_csv(current_jobs_csv_path())
    runs = read_csv(PIPELINE_LOG_PATH)
    stats = build_stats(jobs, runs)
    proposal_count = len(collect_proposal_files())
    return system_pages.render_dashboard(
        {
            "notice": notice,
            "stats": stats,
            "latest_jobs": list(reversed(jobs[-20:])),
            "latest_runs": list(reversed(runs[-20:])),
            "run_state": RUN_STATE,
            "system_log": recent_system_log(20000),
            "task_history": state_store.recent_task_runs(10),
            "snapshot": {
                "jobs_csv_path": str(current_jobs_csv_path()),
                "jobs_csv_accessible": path_exists(current_jobs_csv_path()),
                "proposal_count": proposal_count,
                "run_state": RUN_STATE,
                "runs": runs,
            },
        }
    )


def render_agents(notice: str = "") -> str:
    jobs = read_csv(current_jobs_csv_path())
    runs = read_csv(PIPELINE_LOG_PATH)
    agents = build_agent_states(jobs, runs)
    return system_pages.render_agents(
        {
            "notice": notice,
            "agents": agents,
            "run_state": RUN_STATE,
            "task_history": state_store.recent_task_runs(20),
        }
    )


def render_data() -> str:
    jobs = list(reversed(read_csv(current_jobs_csv_path())))
    runs = list(reversed(read_csv(PIPELINE_LOG_PATH)))
    proposals = [
        {
            "file": str(path),
            "updated_at": latest_file_time(path),
            "size": safe_file_size(path),
        }
        for path in collect_proposal_files()[:100]
    ]
    return system_pages.render_data(
        {
            "jobs": jobs,
            "runs": runs,
            "proposals": proposals,
            "run_state": RUN_STATE,
        }
    )


def render_configs(notice: str = "") -> str:
    return system_pages.render_configs(
        {
            "notice": notice,
            "values": read_config_values(),
            "config_fields": CONFIG_FIELDS,
            "run_state": RUN_STATE,
        }
    )


def render_logs() -> str:
    runs = list(reversed(read_csv(PIPELINE_LOG_PATH)[-100:]))
    return system_pages.render_logs(
        {
            "runs": runs,
            "system_log": recent_system_log(),
            "run_state": RUN_STATE,
        }
    )


def form_value(form: dict, key: str, default: str = "") -> str:
    return form.get(key, [default])[0].strip()


def build_task_command(form: dict) -> tuple[list[str] | None, str, str]:
    task_type = form_value(form, "task_type", "full_pipeline")
    if task_type not in TASK_LABELS:
        return None, task_type, "Unknown task selected."

    args = [sys.executable]
    project_link = form_value(form, "project_link")

    if task_type == "full_pipeline":
        args.append(str(RUN_SCRIPT_PATH))
        if form_value(form, "submit") == "on":
            args.append("--submit")
        if form_value(form, "keep_browser_open") == "on":
            args.append("--keep-browser-open")
        if form_value(form, "reprocess") == "on":
            args.append("--reprocess")
        max_jobs = form_value(form, "max_jobs", "0") or "0"
        if max_jobs.isdigit() and int(max_jobs) > 0:
            args.extend(["--max-jobs", max_jobs])
    elif task_type == "collect_jobs":
        args.append(str(JOB_COLLECTION_SCRIPT_PATH))
    elif task_type == "write_proposal":
        if not project_link:
            return None, task_type, "Project link is required for proposal writing."
        args.extend([str(PROPOSAL_WRITER_SCRIPT_PATH), project_link])
    elif task_type == "write_and_submit":
        if not project_link:
            return None, task_type, "Project link is required for write and submit."
        args.extend([str(PROPOSAL_SUBMIT_SCRIPT_PATH), project_link])
        if form_value(form, "submit") == "on":
            args.append("--submit")

    return args, task_type, ""


def start_task(form: dict) -> str:
    if RUN_STATE["running"]:
        return "A task is already running."

    args, task_type, error = build_task_command(form)
    if error:
        return error
    if not args:
        return "Could not build task command."

    RUN_STATE.update(
        {
            "running": True,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": "",
            "exit_code": "",
            "command": " ".join(args),
            "pid": "",
            "last_error": "",
            "task_type": task_type,
            "task_label": TASK_LABELS[task_type],
            "status": "running",
            "timeout_minutes": form_value(form, "timeout_minutes", "15") or "15",
        }
    )
    RUN_STATE["run_id"] = str(
        state_store.create_task_run(
            task_type=task_type,
            task_label=TASK_LABELS[task_type],
            command=RUN_STATE["command"],
            started_at=RUN_STATE["started_at"],
        )
    )
    append_system_log(f"Starting task {RUN_STATE['task_label']}: {RUN_STATE['command']}")
    thread = threading.Thread(
        target=run_pipeline_process,
        args=(args, int(RUN_STATE["run_id"]), int(RUN_STATE["timeout_minutes"])),
        daemon=True,
    )
    thread.start()
    return f"{RUN_STATE['task_label']} started."


def stop_process_tree(pid: str) -> None:
    if not pid:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        subprocess.run(
            ["kill", "-TERM", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def stop_task() -> str:
    if not RUN_STATE["running"]:
        return "No task is running."

    stop_process_tree(RUN_STATE["pid"])
    RUN_STATE["last_error"] = "Stopped by user."
    RUN_STATE["status"] = "stopped"
    append_system_log(f"Stop requested for task {RUN_STATE['task_label']} pid={RUN_STATE['pid']}")
    return "Stop requested."


def run_pipeline_process(args: list[str], run_id: int, timeout_minutes: int) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    task_status = "failed"
    try:
        with SYSTEM_LOG_PATH.open("a", encoding="utf-8", errors="replace") as log_file:
            process = subprocess.Popen(
                args,
                cwd=str(MAIN_DIR),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            RUN_STATE["pid"] = str(process.pid)
            state_store.mark_task_started(run_id, RUN_STATE["pid"])
            try:
                if timeout_minutes > 0:
                    exit_code = process.wait(timeout=timeout_minutes * 60)
                else:
                    exit_code = process.wait()
                task_status = "success" if str(exit_code) == "0" else "failed"
            except subprocess.TimeoutExpired:
                RUN_STATE["last_error"] = f"Timed out after {timeout_minutes} minute(s)."
                stop_process_tree(RUN_STATE["pid"])
                exit_code = "timeout"
                task_status = "timeout"
    except Exception as exc:
        RUN_STATE["last_error"] = str(exc)
        exit_code = "error"
        append_system_log(f"Agent run failed to start: {exc}")

    finished_at = datetime.now().isoformat(timespec="seconds")
    state_store.finish_task_run(
        run_id=run_id,
        finished_at=finished_at,
        exit_code=str(exit_code),
        error=RUN_STATE["last_error"],
        status=RUN_STATE["status"] if RUN_STATE["status"] == "stopped" else task_status,
    )
    RUN_STATE.update(
        {
            "running": False,
            "finished_at": finished_at,
            "exit_code": str(exit_code),
            "status": RUN_STATE["status"] if RUN_STATE["status"] == "stopped" else task_status,
        }
    )
    append_system_log(f"Task {RUN_STATE['task_label']} finished with exit code {exit_code}")


def api_status_payload() -> dict:
    jobs = read_csv(current_jobs_csv_path())
    runs = read_csv(PIPELINE_LOG_PATH)
    stats = build_stats(jobs, runs)
    return {
        "run_state": RUN_STATE,
        "stats": {
            "total_jobs": stats["total_jobs"],
            "total_pipeline_runs": stats["total_pipeline_runs"],
            "successful_runs": stats["successful_runs"],
            "failed_runs": stats["failed_runs"],
            "submitted_runs": stats["submitted_runs"],
            "dry_runs": stats["dry_runs"],
            "proposal_files": stats["proposal_files"],
        },
        "last_run": runs[-1] if runs else {},
        "jobs_csv_path": str(current_jobs_csv_path()),
        "jobs_csv_accessible": path_exists(current_jobs_csv_path()),
        "system_log": recent_system_log(20000),
        "task_history": state_store.recent_task_runs(20),
        "latest_task": state_store.latest_task_run(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/login":
            self.respond(system_pages.render_login())
            return

        if not self.is_authenticated():
            self.redirect("/login")
            return

        if path == "/api/status":
            self.respond_json(api_status_payload())
            return

        notice = parse_qs(urlparse(self.path).query).get("notice", [""])[0]
        pages = {
            "/": lambda: render_dashboard(notice),
            "/dashboard": lambda: render_dashboard(notice),
            "/agents": lambda: render_agents(notice),
            "/data": render_data,
            "/configs": lambda: render_configs(notice),
            "/logs": render_logs,
        }
        page = pages.get(path)
        if not page:
            self.send_error(404)
            return
        try:
            self.respond(page())
        except Exception:
            append_system_log("Page render failed:\n" + traceback.format_exc())
            self.respond(system_pages.render_error(RUN_STATE), status=500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        form = self.read_form()

        if path == "/login":
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
                token = secrets.token_urlsafe(32)
                SESSIONS.add(token)
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/")
                self.end_headers()
                return
            self.respond(system_pages.render_login("Invalid username or password."), status=401)
            return

        if not self.is_authenticated():
            self.redirect("/login")
            return

        if path == "/logout":
            token = self.session_token()
            if token:
                SESSIONS.discard(token)
            self.send_response(303)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; Path=/")
            self.end_headers()
            return

        if path == "/configs":
            values = {key: form.get(key, [""])[0] for key, _, _ in CONFIG_FIELDS}
            write_config_values(values)
            append_system_log("Configuration saved from dashboard.")
            self.redirect("/configs?" + urlencode({"notice": "Configurations saved."}))
            return

        if path == "/run":
            notice = start_task(form)
            self.redirect("/agents?" + urlencode({"notice": notice}))
            return

        if path == "/stop":
            notice = stop_task()
            self.redirect("/agents?" + urlencode({"notice": notice}))
            return

        self.send_error(404)

    def read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8") if length else ""
        return parse_qs(raw_body)

    def session_token(self) -> str:
        header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        try:
            jar.load(header)
        except cookies.CookieError:
            return ""
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def is_authenticated(self) -> bool:
        return self.session_token() in SESSIONS

    def redirect(self, target: str) -> None:
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def respond(self, content: str, status: int = 200) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def respond_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        if args and isinstance(args[0], str) and args[0].startswith("GET /api/status "):
            return
        append_system_log("HTTP " + (format % args))


def main() -> None:
    state_store.mark_stale_running_tasks(datetime.now().isoformat(timespec="seconds"))
    append_system_log("Dashboard server starting at http://127.0.0.1:8765")
    server = HTTPServer(("127.0.0.1", 8765), DashboardHandler)
    print("Dashboard running at http://127.0.0.1:8765")
    print(f"Login username: {DASHBOARD_USERNAME}")
    if DASHBOARD_PASSWORD == "change-me":
        print(
            "WARNING: Set FATMA_DASHBOARD_PASSWORD before using the dashboard "
            "outside a trusted local machine."
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
