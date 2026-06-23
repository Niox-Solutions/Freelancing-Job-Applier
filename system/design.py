APP_CSS = """
:root { color-scheme: light; --ink:#182230; --muted:#667085; --line:#d9e0ea; --panel:#ffffff; --band:#f5f7fa; --accent:#0f766e; --accent-2:#2563eb; --danger:#b42318; --warn:#b54708; --rail:#111827; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; background: var(--band); color: var(--ink); }
.app-shell { display: grid; grid-template-columns: 238px minmax(0, 1fr); min-height: 100vh; }
aside { background: var(--rail); color: white; padding: 22px 16px; position: sticky; top: 0; height: 100vh; }
.brand { display: grid; gap: 5px; padding: 0 8px 18px; border-bottom: 1px solid rgba(255,255,255,.13); }
.brand strong { font-size: 18px; }
.brand span { color: #cbd5e1; font-size: 12px; }
nav { display: grid; gap: 7px; margin-top: 18px; }
nav a { color: #cbd5e1; text-decoration: none; padding: 11px 12px; border-radius: 8px; font-size: 14px; white-space: nowrap; }
nav a.active, nav a:hover { background: rgba(255,255,255,.12); color: white; }
.workspace { min-width: 0; }
header { background: #ffffff; border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 28px; }
.title-stack { display: grid; gap: 5px; min-width: 0; }
h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
.subline { color: var(--muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
main { padding: 22px 28px 44px; }
.actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
button, .button { border: 1px solid transparent; background: var(--accent); color: white; border-radius: 6px; padding: 10px 14px; font-weight: 700; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; }
button.secondary, .button.secondary { background: white; color: var(--ink); border-color: var(--line); }
button.danger { background: var(--danger); }
button:disabled { opacity: .6; cursor: default; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.metric { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 92px; }
.metric span { display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.metric strong { font-size: 25px; overflow-wrap: anywhere; }
.hero-grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 16px; margin-top: 18px; }
.panel { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 16px; overflow: auto; }
.panel h2 { margin: 0 0 12px; font-size: 17px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.panel-head h2 { margin: 0; }
.stack { display: grid; gap: 16px; }
.compact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.compact-card { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 13px; min-width: 0; }
.compact-card span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }
.compact-card strong { display: block; font-size: 17px; overflow-wrap: anywhere; }
.compact-card small { display: block; color: var(--muted); font-size: 12px; margin-top: 6px; overflow-wrap: anywhere; }
.run-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.run-form button { min-height: 39px; justify-content: center; }
.run-form.compact { grid-template-columns: 1fr; }
.agent-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.agent-card { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 15px; display: grid; gap: 10px; }
.agent-card h3 { margin: 0; font-size: 15px; }
.agent-card dl { display: grid; gap: 7px; margin: 0; }
.agent-card div { display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid #eef2f6; padding-top: 8px; }
.agent-card dt { color: var(--muted); font-size: 12px; }
.agent-card dd { margin: 0; font-size: 12px; text-align: right; overflow-wrap: anywhere; }
.config-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid #eef2f6; }
.config-section:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }
.config-section h3 { margin: 0 0 12px; font-size: 15px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border-bottom: 1px solid #e7ebf1; padding: 10px 8px; text-align: left; vertical-align: top; }
th { color: #4b5563; background: #f8fafc; position: sticky; top: 0; }
a { color: var(--accent-2); text-decoration: none; }
.ranked { list-style: none; padding: 0; margin: 0; }
.ranked li { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #e7ebf1; }
.empty { color: var(--muted); }
.notice { background: #ecfdf3; color: #05603a; border: 1px solid #abefc6; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }
.badge { display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #eef2f6; color: #364152; }
.badge.ok { background: #dcfae6; color: #067647; }
.badge.warn { background: #fef0c7; color: #93370d; }
.badge.bad { background: #fee4e2; color: #b42318; }
.badge.live { background: #dbeafe; color: #1d4ed8; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
label { display: grid; gap: 7px; color: #344054; font-size: 13px; font-weight: 700; }
input, select { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 10px 11px; color: var(--ink); background: white; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
pre { margin: 0; padding: 14px; background: #101828; color: #d0d5dd; border-radius: 8px; overflow: auto; line-height: 1.45; max-height: 70vh; white-space: pre-wrap; }
.login { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.login .panel { width: min(420px, 100%); }
@media (max-width: 980px) { .app-shell { grid-template-columns: 1fr; } aside { position: static; height: auto; } nav { grid-template-columns: repeat(5, minmax(max-content, 1fr)); overflow-x: auto; } .hero-grid { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .topbar, main { padding-left: 16px; padding-right: 16px; } .topbar { align-items: flex-start; flex-direction: column; } .metric strong { font-size: 21px; } .run-form { grid-template-columns: 1fr; } }
"""

LOGIN_CSS = """
body { margin: 0; font-family: Arial, sans-serif; background: #f4f6f8; color: #172026; }
.login { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.panel { width: min(420px, 100%); background: white; border: 1px solid #d8dee8; border-radius: 8px; padding: 20px; }
h1 { margin: 0 0 16px; font-size: 23px; }
label { display: grid; gap: 7px; margin-bottom: 13px; color: #344054; font-size: 13px; font-weight: 700; }
input { width: 100%; border: 1px solid #d8dee8; border-radius: 6px; padding: 11px; }
button { width: 100%; border: 0; background: #0f766e; color: white; border-radius: 6px; padding: 11px 14px; font-weight: 700; cursor: pointer; }
.empty { color: #667085; }
"""
