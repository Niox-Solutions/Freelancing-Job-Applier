import html
from collections import Counter
from datetime import datetime

from .design import APP_CSS, LOGIN_CSS


def card(label: str, value) -> str:
    live_keys = {
        "Collected Jobs": "total_jobs",
        "Pipeline Runs": "pipeline_runs",
        "Successful Runs": "successful_runs",
        "Failed Runs": "failed_runs",
        "Submitted": "submitted_runs",
        "Dry Runs": "dry_runs",
        "Proposal Files": "proposal_files",
    }
    live_attr = f" data-live=\"{live_keys[label]}\"" if label in live_keys else ""
    return f"""
    <section class="metric">
      <span>{html.escape(label)}</span>
      <strong{live_attr}>{html.escape(str(value))}</strong>
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


def live_card(label: str, value_html: str, detail: str = "") -> str:
    detail_html = f"<small>{html.escape(detail)}</small>" if detail else ""
    return f"""
    <section class="compact-card">
      <span>{html.escape(label)}</span>
      <strong>{value_html}</strong>
      {detail_html}
    </section>
    """


def badge(value: str) -> str:
    status = (value or "unknown").lower()
    tone = "ok" if status in {"success", "ready", "idle", "accessible"} else "warn"
    if status in {"failed", "error", "needs attention"}:
        tone = "bad"
    if status == "running":
        tone = "live"
    return f"<span class='badge {tone}'>{html.escape(value or 'unknown')}</span>"


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


def run_control_panel(run_state: dict, compact: bool = False) -> str:
    form_class = "run-form compact" if compact else "run-form"
    button_text = "Running" if run_state["running"] else "Run Agents"
    disabled = "disabled" if run_state["running"] else ""
    return f"""
    <form class="{form_class}" method="post" action="/run" data-task-form>
      <label>Task<select name="task_type" data-task-select>
        <option value="full_pipeline">Full pipeline</option>
        <option value="collect_jobs">Collect jobs only</option>
        <option value="write_proposal">Write proposal only</option>
        <option value="write_and_submit">Write and submit</option>
      </select></label>
      <label data-project-link>Project Link<input name="project_link" type="url" placeholder="https://nafezly.com/project/..."></label>
      <label data-max-jobs>Max Jobs<input name="max_jobs" type="number" min="0" value="0"></label>
      <label data-submit-option>Mode<select name="submit"><option value="">Dry run</option><option value="on">Real submit</option></select></label>
      <label data-browser-option>After Run<select name="keep_browser_open"><option value="">Close browser</option><option value="on">Keep browser open</option></select></label>
      <label data-reprocess-option>Existing Jobs<select name="reprocess"><option value="">Skip processed</option><option value="on">Reprocess</option></select></label>
      <label>Timeout Minutes<input name="timeout_minutes" type="number" min="0" value="0"></label>
      <button type="submit" {disabled}>{button_text}</button>
    </form>
    """


def system_snapshot(
    *,
    jobs_csv_path: str,
    jobs_csv_accessible: bool,
    proposal_count: int,
    run_state: dict,
    runs: list[dict],
) -> str:
    last_run = runs[-1] if runs else {}
    csv_state = "Accessible" if jobs_csv_accessible else "Needs attention"
    last_status = last_run.get("status", "No runs")
    return "".join(
        [
            compact_card("Runner", "Running" if run_state["running"] else "Idle", run_state["started_at"] or run_state["finished_at"]),
            compact_card("Jobs CSV", csv_state, jobs_csv_path),
            compact_card("Last Run", last_status, last_run.get("processed_at", "")),
            compact_card("Proposals", str(proposal_count), "generated files"),
        ]
    )


def layout(title: str, active: str, body: str, notice: str, run_state: dict) -> str:
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
    run_label = "Running" if run_state["running"] else (run_state.get("status") or "Idle")
    last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - Agent System</title>
  <style>{APP_CSS}</style>
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
            <div class="subline">Updated <span data-live="updated_at">{html.escape(last_seen)}</span> | State: <span data-live="run_badge">{badge(run_label)}</span></div>
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
  <script>
    const badgeHtml = (value) => {{
      const label = value || "unknown";
      const status = label.toLowerCase();
      let tone = ["success", "ready", "idle", "accessible"].includes(status) ? "ok" : "warn";
      if (["failed", "error", "needs attention"].includes(status)) tone = "bad";
      if (status === "running") tone = "live";
      return `<span class="badge ${{tone}}">${{label}}</span>`;
    }};

    const setText = (selector, value) => {{
      document.querySelectorAll(selector).forEach((node) => {{ node.textContent = value || ""; }});
    }};

    const updateTaskVisibility = (form) => {{
      const task = form.querySelector("[data-task-select]")?.value || "full_pipeline";
      const showProject = ["write_proposal", "write_and_submit"].includes(task);
      const showPipeline = task === "full_pipeline";
      const showSubmit = task === "full_pipeline" || task === "write_and_submit";
      const showBrowser = task === "full_pipeline";
      form.querySelectorAll("[data-project-link]").forEach((node) => node.style.display = showProject ? "" : "none");
      form.querySelectorAll("[data-max-jobs]").forEach((node) => node.style.display = showPipeline ? "" : "none");
      form.querySelectorAll("[data-reprocess-option]").forEach((node) => node.style.display = showPipeline ? "" : "none");
      form.querySelectorAll("[data-submit-option]").forEach((node) => node.style.display = showSubmit ? "" : "none");
      form.querySelectorAll("[data-browser-option]").forEach((node) => node.style.display = showBrowser ? "" : "none");
    }};

    document.querySelectorAll("[data-task-form]").forEach((form) => {{
      updateTaskVisibility(form);
      form.querySelector("[data-task-select]")?.addEventListener("change", () => updateTaskVisibility(form));
    }});

    async function refreshStatus() {{
      try {{
        const response = await fetch("/api/status", {{ cache: "no-store" }});
        if (!response.ok) return;
        const data = await response.json();
        const state = data.run_state || {{}};
        const runLabel = state.running ? "Running" : "Idle";
        document.querySelectorAll("[data-live='run_badge']").forEach((node) => {{ node.innerHTML = badgeHtml(runLabel); }});
        setText("[data-live='updated_at']", data.updated_at || "");
        setText("[data-live='task_label']", state.task_label || "None");
        setText("[data-live='task_status']", state.status || (state.running ? "running" : "idle"));
        setText("[data-live='pid']", state.pid || "");
        setText("[data-live='command']", state.command || "");
        setText("[data-live='exit_code']", state.exit_code || "");
        setText("[data-live='started_at']", state.started_at || "");
        setText("[data-live='finished_at']", state.finished_at || "");
        setText("[data-live='total_jobs']", data.stats?.total_jobs ?? "0");
        setText("[data-live='pipeline_runs']", data.stats?.total_pipeline_runs ?? "0");
        setText("[data-live='successful_runs']", data.stats?.successful_runs ?? "0");
        setText("[data-live='failed_runs']", data.stats?.failed_runs ?? "0");
        setText("[data-live='submitted_runs']", data.stats?.submitted_runs ?? "0");
        setText("[data-live='dry_runs']", data.stats?.dry_runs ?? "0");
        setText("[data-live='proposal_files']", data.stats?.proposal_files ?? "0");
        document.querySelectorAll("[data-live='system_log']").forEach((node) => {{ node.textContent = data.system_log || ""; node.scrollTop = node.scrollHeight; }});
        document.querySelectorAll("[data-task-form] button[type='submit']").forEach((button) => {{
          button.disabled = !!state.running;
          button.textContent = state.running ? "Running" : "Run Agents";
        }});
      }} catch (error) {{}}
    }}

    refreshStatus();
    setInterval(refreshStatus, 2000);
  </script>
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
  <style>{LOGIN_CSS}</style>
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


def render_dashboard(context: dict) -> str:
    stats = context["stats"]
    metrics = "".join(
        [
            card("Collected Jobs", stats["total_jobs"]),
            card("Pipeline Runs", stats["total_pipeline_runs"]),
            card("Successful Runs", stats["successful_runs"]),
            card("Failed Runs", stats["failed_runs"]),
            card("Submitted", stats["submitted_runs"]),
            card("Dry Runs", stats["dry_runs"]),
            card("Proposal Files", stats["proposal_files"]),
            card("Avg Budget", f"{stats['avg_budget']} $"),
            card("Avg Offers", stats["avg_offers"]),
        ]
    )
    body = f"""
    <section class="hero-grid">
      <div class="stack">
        <div class="compact-grid">{system_snapshot(**context["snapshot"])}</div>
        <section class="compact-grid">
          {live_card("Active Task", '<span data-live="task_label">None</span>', "current selection")}
          {live_card("Task Status", '<span data-live="task_status">idle</span>', "latest state")}
          {live_card("Process ID", '<span data-live="pid"></span>', "running process")}
          {live_card("Exit Code", '<span data-live="exit_code"></span>', "last finished task")}
        </section>
        <section class="metrics">{metrics}</section>
      </div>
      <section class="panel">
        <div class="panel-head"><h2>Run Control</h2><a class="button secondary" href="/logs">Logs</a></div>
        {run_control_panel(context["run_state"], compact=True)}
        <form method="post" action="/stop" style="margin-top:12px"><button class="danger" type="submit">Stop Running Task</button></form>
      </section>
    </section>
    <section class="grid">
      <div class="panel"><h2>Project States</h2>{counter_list(stats["states"])}</div>
      <div class="panel"><h2>Locations</h2>{counter_list(stats["locations"])}</div>
      <div class="panel"><h2>Pipeline Status</h2>{counter_list(stats["statuses"])}</div>
    </section>
    <section class="panel" style="margin-top:18px">
      <h2>Latest Pipeline Runs</h2>
      {table(context["latest_runs"], ["processed_at", "status", "submitted", "job_title", "period", "cost", "job_link", "error"])}
    </section>
    <section class="panel" style="margin-top:18px">
      <h2>Latest Jobs</h2>
      {table(context["latest_jobs"], ["scraped_at", "job_title", "budget", "duration", "offers_count", "location", "project_state", "job_link"])}
    </section>
    <section class="panel" style="margin-top:18px">
      <div class="panel-head"><h2>Live System Log</h2><a class="button secondary" href="/logs">Open Logs</a></div>
      <pre data-live="system_log">{html.escape(context.get("system_log", ""))}</pre>
    </section>
    """
    return layout("Agent Dashboard", "dashboard", body, context.get("notice", ""), context["run_state"])


def render_agents(context: dict) -> str:
    agent_cards = "".join(
        f"""
        <article class="agent-card">
          <div><h3>{html.escape(agent["agent"])}</h3>{badge(str(agent["state"]))}</div>
          <dl>
            <div><dt>Last activity</dt><dd>{html.escape(str(agent["last_activity"] or "None"))}</dd></div>
            <div><dt>Items</dt><dd>{html.escape(str(agent["items"]))}</dd></div>
            <div><dt>Info</dt><dd>{html.escape(str(agent["info"]))}</dd></div>
          </dl>
        </article>
        """
        for agent in context["agents"]
    )
    body = f"""
    <section class="panel">
      <div class="panel-head"><h2>Run Control</h2><a class="button secondary" href="/logs">Logs</a></div>
      {run_control_panel(context["run_state"])}
      <form method="post" action="/stop" style="margin-top:12px"><button class="danger" type="submit">Stop Running Task</button></form>
    </section>
    <section class="compact-grid" style="margin-top:16px">
      {live_card("Active Task", '<span data-live="task_label">None</span>', "current selection")}
      {live_card("Task Status", '<span data-live="task_status">idle</span>', "latest state")}
      {live_card("Started", '<span data-live="started_at"></span>', "current task")}
      {live_card("Finished", '<span data-live="finished_at"></span>', "last task")}
      {live_card("Command", '<span data-live="command"></span>', "exact command")}
    </section>
    <section class="agent-cards" style="margin-top:16px">{agent_cards}</section>
    <section class="panel" style="margin-top:16px">
      <h2>Agent State</h2>
      {table(context["agents"], ["agent", "state", "last_activity", "items", "info"])}
    </section>
    <section class="panel" style="margin-top:16px">
      <h2>Task History</h2>
      {table(context.get("task_history", []), ["id", "task_label", "status", "pid", "started_at", "finished_at", "exit_code", "error"])}
    </section>
    """
    return layout("Agents", "agents", body, context.get("notice", ""), context["run_state"])


def render_data(context: dict) -> str:
    body = f"""
    <section class="panel">
      <h2>All Scraped Jobs</h2>
      {table(context["jobs"], ["scraped_at", "job_title", "budget", "duration", "offers_count", "location", "project_state", "job_link"])}
    </section>
    <section class="panel" style="margin-top:18px">
      <h2>All Pipeline Runs</h2>
      {table(context["runs"], ["processed_at", "status", "submitted", "job_title", "proposal_path", "period", "cost", "job_link", "error"])}
    </section>
    <section class="panel" style="margin-top:18px">
      <h2>Proposal Files</h2>
      {table(context["proposals"], ["updated_at", "size", "file"])}
    </section>
    """
    return layout("Data", "data", body, "", context["run_state"])


def render_configs(context: dict) -> str:
    grouped_fields = [
        ("Login", context["config_fields"][0:2]),
        ("Data And Browser", context["config_fields"][2:8]),
        ("Job Monitoring", context["config_fields"][8:11]),
        ("Proposal Generation", context["config_fields"][11:17]),
    ]
    sections = []
    for heading, fields in grouped_fields:
        inputs = []
        for key, label, input_type in fields:
            value = html.escape(context["values"].get(key, ""), quote=True)
            inputs.append(
                f"<label>{html.escape(label)}<input name='{html.escape(key)}' type='{input_type}' value='{value}'></label>"
            )
        sections.append(
            f"<section class='config-section'><h3>{html.escape(heading)}</h3><div class='form-grid'>{''.join(inputs)}</div></section>"
        )
    body = f"""
    <form class="panel" method="post" action="/configs">
      <div class="panel-head"><h2>Configuration</h2><button type="submit">Save Configs</button></div>
      {''.join(sections)}
    </form>
    """
    return layout("Configs", "configs", body, context.get("notice", ""), context["run_state"])


def render_logs(context: dict) -> str:
    body = f"""
    <section class="panel">
      <h2>System Log</h2>
      <pre data-live="system_log">{html.escape(context["system_log"])}</pre>
    </section>
    <section class="panel" style="margin-top:18px">
      <h2>Pipeline CSV Log</h2>
      {table(context["runs"], ["processed_at", "status", "submitted", "job_title", "period", "cost", "job_link", "error"])}
    </section>
    """
    return layout("Logs", "logs", body, "", context["run_state"])


def render_error(run_state: dict) -> str:
    body = "<section class='panel'><h2>Page Error</h2><p class='empty'>Check Logs for the traceback.</p></section>"
    return layout("Error", "dashboard", body, "", run_state)
