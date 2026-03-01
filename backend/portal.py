"""
MedLedger Portal — Agent-Native EHR
Patient portal on port 8001 with rich interactive UI for browser-use navigation.
Lots of clickable elements: nav bar, dashboard, tabs, filters, sorting.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import aiosqlite
from backend.database import DB_PATH, init_db


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield


app = FastAPI(title="MedLedger Portal", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ──────────────────────────── HTML Templates ────────────────────────────

STYLE = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f0f4f8; color: #1a202c; }

  /* ── Nav Bar ── */
  .topbar { background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: white; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; height: 56px; }
  .topbar h1 { font-size: 20px; font-weight: 600; letter-spacing: 0.5px; }
  .topbar .badge { background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
  .topbar-left { display: flex; align-items: center; gap: 16px; }
  .topbar-right { display: flex; align-items: center; gap: 16px; }
  .topbar-right span { font-size: 13px; opacity: 0.8; }

  /* ── Navigation Links ── */
  .nav-bar { background: #1e293b; padding: 0 32px; display: flex; align-items: center; gap: 0; border-bottom: 2px solid #334155; }
  .nav-link { color: #94a3b8; text-decoration: none; font-size: 14px; font-weight: 500; padding: 12px 20px; border-bottom: 2px solid transparent; transition: all 0.15s; margin-bottom: -2px; }
  .nav-link:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
  .nav-link.active { color: #60a5fa; border-bottom-color: #3b82f6; }

  /* ── Layout ── */
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .breadcrumb { font-size: 13px; color: #64748b; margin-bottom: 16px; }
  .breadcrumb a { color: #2563eb; text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }

  /* ── Cards ── */
  .card { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 24px; margin-bottom: 20px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .card-title { font-size: 16px; font-weight: 600; color: #1e3a5f; }

  /* ── Stats Cards ── */
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 20px; text-align: center; cursor: pointer; transition: all 0.2s; border: 2px solid transparent; }
  .stat-card:hover { border-color: #2563eb; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
  .stat-card a { text-decoration: none; color: inherit; display: block; }
  .stat-value { font-size: 32px; font-weight: 700; color: #1e3a5f; }
  .stat-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-top: 4px; }
  .stat-card.stat-alert .stat-value { color: #dc2626; }
  .stat-card.stat-good .stat-value { color: #16a34a; }

  /* ── Tables ── */
  table { width: 100%; border-collapse: collapse; }
  th { background: #f7fafc; text-align: left; padding: 12px 16px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #718096; border-bottom: 2px solid #e2e8f0; }
  td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
  tr:hover { background: #f7fafc; }

  /* ── Buttons ── */
  .btn { display: inline-block; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500; cursor: pointer; border: none; transition: all 0.15s; }
  .btn-primary { background: #2563eb; color: white; }
  .btn-primary:hover { background: #1d4ed8; }
  .btn-danger { background: #ef4444; color: white; }
  .btn-danger:hover { background: #dc2626; }
  .btn-secondary { background: #e2e8f0; color: #475569; }
  .btn-secondary:hover { background: #cbd5e1; }
  .btn-outline { background: transparent; border: 1px solid #e2e8f0; color: #475569; }
  .btn-outline:hover { border-color: #2563eb; color: #2563eb; }
  .btn-sm { padding: 4px 12px; font-size: 12px; }

  /* ── Badges & Tags ── */
  .mrn { font-family: 'Courier New', monospace; font-size: 13px; color: #6366f1; }
  .diagnosis { color: #059669; font-weight: 500; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
  .tag-update { background: #fef3c7; color: #92400e; }
  .tag-delete { background: #fee2e2; color: #991b1b; }
  .tag-create { background: #d1fae5; color: #065f46; }
  .blood-type { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  .insurance-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }

  /* ── Search & Filter ── */
  .search-box { display: flex; gap: 8px; margin-bottom: 20px; }
  .search-box input { flex: 1; padding: 10px 16px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
  .search-box input:focus { outline: none; border-color: #2563eb; }
  .filter-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .filter-btn { padding: 6px 14px; border-radius: 20px; border: 1px solid #e2e8f0; background: white; color: #64748b; font-size: 12px; cursor: pointer; transition: all 0.15s; text-decoration: none; }
  .filter-btn:hover { border-color: #2563eb; color: #2563eb; }
  .filter-btn.active { background: #2563eb; color: white; border-color: #2563eb; }

  /* ── Alerts ── */
  .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
  .alert-success { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
  .alert-danger { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }

  /* ── Forms ── */
  label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.3px; }
  input[type=text], input[type=password], textarea { width: 100%; padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; margin-bottom: 16px; font-family: inherit; }
  input:focus, textarea:focus { outline: none; border-color: #2563eb; }
  .field-group { display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px; }

  /* ── Patient Detail ── */
  .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
  .detail-header h2 { font-size: 22px; color: #1e3a5f; }
  .detail-actions { display: flex; gap: 8px; align-items: center; }
  .patient-meta { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }

  /* ── Tabs ── */
  .tabs { display: flex; border-bottom: 2px solid #e2e8f0; margin-bottom: 20px; gap: 0; }
  .tab-link { padding: 12px 20px; font-size: 14px; font-weight: 500; color: #64748b; text-decoration: none; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.15s; }
  .tab-link:hover { color: #1e3a5f; background: #f7fafc; }
  .tab-link.active { color: #2563eb; border-bottom-color: #2563eb; }

  /* ── Vitals ── */
  .vitals-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .vital-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 12px; text-align: center; cursor: pointer; transition: all 0.15s; }
  .vital-card:hover { border-color: #2563eb; transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
  .vital-card.v-high { border-color: #fbbf24; background: #fffbeb; }
  .vital-card.v-low  { border-color: #f97316; background: #fff7ed; }
  .vital-label { font-size: 10px; text-transform: uppercase; color: #718096; font-weight: 600; letter-spacing: 0.5px; }
  .vital-value { font-size: 26px; font-weight: 700; color: #1e3a5f; margin: 4px 0; }
  .vital-card.v-high .vital-value { color: #dc2626; }
  .vital-card.v-low  .vital-value { color: #d97706; }
  .vital-unit { font-size: 11px; color: #94a3b8; }
  .vital-range { font-size: 10px; color: #a1a1aa; margin-top: 2px; }

  /* ── Labs ── */
  .lab-status { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
  .lab-normal { background: #d1fae5; color: #065f46; }
  .lab-high   { background: #fee2e2; color: #991b1b; }
  .lab-low    { background: #fef3c7; color: #92400e; }

  /* ── Appointments ── */
  .appt-item { display: flex; align-items: center; gap: 16px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; background: #f8fafc; cursor: pointer; transition: all 0.15s; }
  .appt-item:hover { border-color: #2563eb; background: #eff6ff; }
  .appt-date { font-weight: 700; color: #2563eb; min-width: 120px; font-size: 13px; }
  .appt-type { font-weight: 600; color: #1e3a5f; }
  .appt-doc  { color: #718096; font-size: 13px; }
  .appt-note { font-size: 12px; color: #94a3b8; flex: 1; }
  .appt-status { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background: #d1fae5; color: #065f46; }

  /* ── History ── */
  .history-table { font-size: 13px; }
  .history-table td { padding: 8px 12px; }

  /* ── Section ── */
  .section-title { color: #1e3a5f; margin-bottom: 14px; font-size: 16px; font-weight: 600; }

  /* ── Quick Links ── */
  .quick-links { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }
  .quick-link { display: flex; align-items: center; gap: 12px; padding: 16px; background: white; border-radius: 10px; border: 1px solid #e2e8f0; text-decoration: none; color: inherit; transition: all 0.15s; cursor: pointer; }
  .quick-link:hover { border-color: #2563eb; transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .ql-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
  .ql-text h4 { font-size: 14px; color: #1e3a5f; margin-bottom: 2px; }
  .ql-text p { font-size: 12px; color: #64748b; }

  /* ── Login ── */
  .login-wrap { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #7c3aed 100%); }
  .login-card { background: white; padding: 48px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 400px; }
  .login-card h1 { text-align: center; color: #1e3a5f; margin-bottom: 8px; font-size: 28px; }
  .login-card p { text-align: center; color: #64748b; margin-bottom: 32px; font-size: 14px; }

  /* ── Empty State ── */
  .empty-state { text-align: center; padding: 40px 20px; color: #94a3b8; }
  .empty-state p { margin-top: 8px; font-size: 14px; }
</style>
"""


def topbar(user="Dr. Agent"):
    return f"""
    <nav class="topbar">
      <div class="topbar-left">
        <h1>MedLedger Portal</h1>
        <span class="badge">Agent-Native EHR</span>
      </div>
      <div class="topbar-right">
        <span>Logged in as <strong>{user}</strong></span>
        <a href="/logout" class="btn btn-sm" style="background:rgba(255,255,255,0.15);color:white;border:1px solid rgba(255,255,255,0.3);">Sign Out</a>
      </div>
    </nav>
    """


def navbar(active="dashboard"):
    links = [
        ("dashboard", "/dashboard", "Dashboard"),
        ("patients", "/patients", "Patients"),
        ("appointments", "/appointments", "Appointments"),
        ("labs", "/labs", "Lab Results"),
    ]
    items = "".join(
        f'<a href="{href}" class="nav-link {"active" if key == active else ""}">{label}</a>'
        for key, href, label in links
    )
    return f'<nav class="nav-bar">{items}</nav>'


def base(title, body, user="Dr. Agent", active="dashboard"):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — MedLedger Portal</title>{STYLE}</head>
<body>{topbar(user)}{navbar(active)}<div class="container">{body}</div></body></html>"""


# ──────────────────────────── Auth ────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.cookies.get("session") == "authenticated":
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    error = request.query_params.get("error", "")
    err_html = f'<div class="alert alert-danger">{error}</div>' if error else ""
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Login — MedLedger Portal</title>{STYLE}</head><body>
<div class="login-wrap"><div class="login-card">
<h1>MedLedger Portal</h1>
<p>Agent-Native Electronic Health Records</p>
{err_html}
<form method="post" action="/login">
  <label for="username">Username</label>
  <input type="text" id="username" name="username" placeholder="Enter username" required>
  <label for="password">Password</label>
  <input type="password" id="password" name="password" placeholder="Enter password" required>
  <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;font-size:16px;">Sign In</button>
</form>
<p style="margin-top:16px;font-size:12px;color:#94a3b8;">Demo: demo / demo123</p>
</div></div></body></html>"""
    return HTMLResponse(html)


@app.post("/login")
async def do_login(username: str = Form(...), password: str = Form(...)):
    if username == "demo" and password == "demo123":
        response = RedirectResponse("/dashboard", status_code=302)
        response.set_cookie("session", "authenticated", max_age=86400)
        return response
    return RedirectResponse("/login?error=Invalid+credentials", status_code=302)


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response


# ──────────────────────────── Dashboard ────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        patient_count = (await (await db.execute("SELECT COUNT(*) as c FROM patients WHERE deleted = 0")).fetchone())["c"]
        deleted_count = (await (await db.execute("SELECT COUNT(*) as c FROM patients WHERE deleted = 1")).fetchone())["c"]
        appt_count = (await (await db.execute("SELECT COUNT(*) as c FROM appointments WHERE status = 'scheduled'")).fetchone())["c"]
        abnormal_labs = (await (await db.execute("SELECT COUNT(*) as c FROM lab_results WHERE status != 'normal'")).fetchone())["c"]

        cursor = await db.execute("SELECT id, first_name, last_name, mrn, diagnosis FROM patients WHERE deleted = 0 ORDER BY last_visit DESC LIMIT 5")
        recent_patients = await cursor.fetchall()

        cursor2 = await db.execute("SELECT * FROM appointments WHERE status = 'scheduled' ORDER BY scheduled_for ASC LIMIT 5")
        upcoming_appts = await cursor2.fetchall()

        cursor3 = await db.execute("SELECT ph.*, p.first_name as pfn, p.last_name as pln FROM patient_history ph JOIN patients p ON ph.patient_id = p.id ORDER BY ph.changed_at DESC LIMIT 5")
        recent_changes = await cursor3.fetchall()

    recent_rows = ""
    for p in recent_patients:
        recent_rows += f"""<tr>
          <td class="mrn">{p['mrn']}</td>
          <td><a href="/patients/{p['id']}" style="color:#2563eb;text-decoration:none;font-weight:500;">{p['last_name']}, {p['first_name']}</a></td>
          <td class="diagnosis">{p['diagnosis']}</td>
          <td><a href="/patients/{p['id']}" class="btn btn-sm btn-outline">View</a></td>
        </tr>"""

    appt_items = ""
    for a in upcoming_appts:
        dt = a['scheduled_for'][:16].replace('T', ' at ')
        appt_items += f"""<div class="appt-item">
          <span class="appt-date">{dt}</span>
          <span class="appt-type">{a['appointment_type']}</span>
          <span class="appt-doc">{a['doctor_name']}</span>
          <span class="appt-note">{a['patient_name']}</span>
          <span class="appt-status">Scheduled</span>
        </div>"""

    change_items = ""
    for c in recent_changes:
        tag_class = "tag-update" if c["change_type"] == "UPDATE" else "tag-delete"
        change_items += f"""<tr>
          <td><span class="tag {tag_class}">{c['change_type']}</span></td>
          <td><a href="/patients/{c['patient_id']}" style="color:#2563eb;text-decoration:none;">{c['pfn']} {c['pln']}</a></td>
          <td>{c['changed_field'] or '—'}</td>
          <td style="font-size:12px;color:#64748b;">{c['changed_at'][:19]}</td>
        </tr>"""

    body = f"""
    <h2 style="margin-bottom:20px;color:#1e3a5f;">Dashboard</h2>
    <div class="stats-grid">
      <div class="stat-card"><a href="/patients">
        <div class="stat-value">{patient_count}</div>
        <div class="stat-label">Active Patients</div>
      </a></div>
      <div class="stat-card stat-alert"><a href="/labs?filter=abnormal">
        <div class="stat-value">{abnormal_labs}</div>
        <div class="stat-label">Abnormal Lab Results</div>
      </a></div>
      <div class="stat-card"><a href="/appointments">
        <div class="stat-value">{appt_count}</div>
        <div class="stat-label">Upcoming Appointments</div>
      </a></div>
      <div class="stat-card stat-good"><a href="/patients?show=deleted">
        <div class="stat-value">{deleted_count}</div>
        <div class="stat-label">Archived Records</div>
      </a></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Recent Patients</span>
          <a href="/patients" class="btn btn-sm btn-outline">View All</a>
        </div>
        <table>
          <thead><tr><th>MRN</th><th>Name</th><th>Diagnosis</th><th></th></tr></thead>
          <tbody>{recent_rows or '<tr><td colspan="4" class="empty-state">No patients yet</td></tr>'}</tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Upcoming Appointments</span>
          <a href="/appointments" class="btn btn-sm btn-outline">View All</a>
        </div>
        {appt_items or '<div class="empty-state"><p>No upcoming appointments</p></div>'}
      </div>
    </div>

    <div class="card" style="margin-top:20px;">
      <div class="card-header"><span class="card-title">Recent Changes</span></div>
      <table class="history-table">
        <thead><tr><th>Action</th><th>Patient</th><th>Field</th><th>Time</th></tr></thead>
        <tbody>{change_items or '<tr><td colspan="4" class="empty-state">No recent changes</td></tr>'}</tbody>
      </table>
    </div>

    <div style="margin-top:24px;">
      <h3 class="section-title">Quick Links</h3>
      <div class="quick-links">
        <a href="/patients" class="quick-link">
          <div class="ql-icon" style="background:#eff6ff;color:#2563eb;">&#128100;</div>
          <div class="ql-text"><h4>Patient Registry</h4><p>Search and manage all patient records</p></div>
        </a>
        <a href="/appointments" class="quick-link">
          <div class="ql-icon" style="background:#f0fdf4;color:#16a34a;">&#128197;</div>
          <div class="ql-text"><h4>Appointments</h4><p>View and manage scheduled visits</p></div>
        </a>
        <a href="/labs" class="quick-link">
          <div class="ql-icon" style="background:#fef2f2;color:#dc2626;">&#128300;</div>
          <div class="ql-text"><h4>Lab Results</h4><p>Review lab results and flag abnormals</p></div>
        </a>
        <a href="/patients?sort=name" class="quick-link">
          <div class="ql-icon" style="background:#faf5ff;color:#7c3aed;">&#128203;</div>
          <div class="ql-text"><h4>Patient Directory</h4><p>Alphabetical patient listing</p></div>
        </a>
      </div>
    </div>
    """
    return HTMLResponse(base("Dashboard", body, active="dashboard"))


# ──────────────────────────── Patient List ────────────────────────────

@app.get("/patients", response_class=HTMLResponse)
async def patient_list(request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    q = request.query_params.get("q", "")
    sort = request.query_params.get("sort", "name")
    insurance_filter = request.query_params.get("insurance", "")
    show_deleted = request.query_params.get("show", "") == "deleted"
    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ""

    deleted_flag = 1 if show_deleted else 0
    order = {"name": "last_name ASC, first_name ASC", "mrn": "mrn ASC", "diagnosis": "diagnosis ASC", "visit": "last_visit DESC"}.get(sort, "last_name ASC")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if q:
            like = f"%{q}%"
            cursor = await db.execute(
                f"SELECT * FROM patients WHERE (first_name || ' ' || last_name LIKE ? OR mrn LIKE ? OR diagnosis LIKE ? OR medications LIKE ?) AND deleted = {deleted_flag} ORDER BY {order}",
                (like, like, like, like),
            )
        elif insurance_filter:
            cursor = await db.execute(
                f"SELECT * FROM patients WHERE insurance LIKE ? AND deleted = {deleted_flag} ORDER BY {order}",
                (f"%{insurance_filter}%",),
            )
        else:
            cursor = await db.execute(f"SELECT * FROM patients WHERE deleted = {deleted_flag} ORDER BY {order}")
        patients = await cursor.fetchall()

        ins_cursor = await db.execute("SELECT DISTINCT insurance FROM patients WHERE deleted = 0 AND insurance != '' ORDER BY insurance")
        insurances = [row["insurance"] for row in await ins_cursor.fetchall()]

    rows = ""
    for p in patients:
        rows += f"""<tr>
          <td class="mrn">{p['mrn']}</td>
          <td><a href="/patients/{p['id']}" style="color:#2563eb;text-decoration:none;font-weight:500;">{p['last_name']}, {p['first_name']}</a></td>
          <td>{p['dob']}</td>
          <td class="diagnosis">{p['diagnosis'][:40]}{'...' if len(p['diagnosis'])>40 else ''}</td>
          <td>{p['medications'][:35]}{'...' if len(p['medications'])>35 else ''}</td>
          <td><span class="blood-type">{p['blood_type']}</span></td>
          <td>
            <a href="/patients/{p['id']}" class="btn btn-primary btn-sm">View</a>
            <a href="/patients/{p['id']}/edit" class="btn btn-outline btn-sm" style="margin-left:4px;">Edit</a>
          </td>
        </tr>"""

    sort_buttons = "".join(
        f'<a href="/patients?sort={key}&q={q}" class="filter-btn {"active" if sort == key else ""}">{label}</a>'
        for key, label in [("name", "Name"), ("mrn", "MRN"), ("diagnosis", "Diagnosis"), ("visit", "Last Visit")]
    )

    ins_buttons = f'<a href="/patients?sort={sort}&q={q}" class="filter-btn {"active" if not insurance_filter else ""}">All</a>'
    for ins in insurances[:6]:
        short = ins.split()[0]
        active = "active" if insurance_filter == ins else ""
        ins_buttons += f'<a href="/patients?insurance={ins}&sort={sort}" class="filter-btn {active}">{short}</a>'

    search_val = f'value="{q}"' if q else ""
    toggle = '<a href="/patients" class="btn btn-sm btn-secondary">Show Active</a>' if show_deleted else '<a href="/patients?show=deleted" class="btn btn-sm btn-outline">Show Archived</a>'

    body = f"""
    <div class="breadcrumb"><a href="/dashboard">Dashboard</a> / Patients</div>
    {msg_html}
    <div class="card">
      <div class="card-header"><span class="card-title">Patient Registry</span>{toggle}</div>
      <form method="get" action="/patients/search" class="search-box">
        <input type="text" name="q" placeholder="Search by name, MRN, diagnosis, or medication..." {search_val} id="search-input" aria-label="Search patients">
        <button type="submit" class="btn btn-primary">Search</button>
        {f'<a href="/patients" class="btn btn-secondary">Clear</a>' if q else ''}
      </form>
      <div style="margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;">Sort by</div>
      <div class="filter-row">{sort_buttons}</div>
      <div style="margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;">Filter by Insurance</div>
      <div class="filter-row">{ins_buttons}</div>
      <table>
        <thead><tr><th>MRN</th><th>Patient Name</th><th>DOB</th><th>Diagnosis</th><th>Medications</th><th>Blood</th><th>Actions</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:16px;color:#718096;font-size:13px;">Showing {len(patients)} patient(s){f' matching "{q}"' if q else ''}{f' — {insurance_filter}' if insurance_filter else ''}</p>
    </div>
    """
    return HTMLResponse(base("Patients", body, active="patients"))


@app.get("/patients/search", response_class=HTMLResponse)
async def search_patients(request: Request):
    q = request.query_params.get("q", "")
    return RedirectResponse(f"/patients?q={q}", status_code=302)


# ──────────────────────────── Patient Detail (with tabs) ────────────────────────────

@app.get("/patients/{patient_id}", response_class=HTMLResponse)
async def patient_detail(patient_id: int, request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    tab = request.query_params.get("tab", "overview")
    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        p = await cursor.fetchone()
        if not p:
            return HTMLResponse(base("Not Found", '<div class="card"><h2>Patient not found</h2><a href="/patients">Back to list</a></div>', active="patients"))

        history = await (await db.execute("SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC LIMIT 20", (patient_id,))).fetchall()
        labs = await (await db.execute("SELECT * FROM lab_results WHERE patient_id = ? ORDER BY resulted_at DESC", (patient_id,))).fetchall()
        appointments = await (await db.execute("SELECT * FROM appointments WHERE patient_id = ? AND status = 'scheduled' ORDER BY scheduled_for ASC", (patient_id,))).fetchall()

    deleted_banner = '<div class="alert alert-danger"><strong>[ARCHIVED]</strong> This patient record has been deleted.</div>' if p["deleted"] else ""

    tabs_html = f"""<div class="tabs">
      <a href="/patients/{patient_id}?tab=overview" class="tab-link {"active" if tab=="overview" else ""}">Overview</a>
      <a href="/patients/{patient_id}?tab=vitals" class="tab-link {"active" if tab=="vitals" else ""}">Vitals & Labs ({len(labs)})</a>
      <a href="/patients/{patient_id}?tab=medications" class="tab-link {"active" if tab=="medications" else ""}">Medications</a>
      <a href="/patients/{patient_id}?tab=appointments" class="tab-link {"active" if tab=="appointments" else ""}">Appointments ({len(appointments)})</a>
      <a href="/patients/{patient_id}?tab=history" class="tab-link {"active" if tab=="history" else ""}">History ({len(history)})</a>
    </div>"""

    # ── Overview Tab ──
    if tab == "overview":
        tab_content = f"""
        <div class="field-group">
          <div><label>MRN</label><p class="mrn" style="font-size:16px;">{p['mrn']}</p></div>
          <div><label>Date of Birth</label><p>{p['dob']}</p></div>
          <div><label>Phone</label><p>{p['phone']}</p></div>
          <div><label>Insurance</label><p><span class="insurance-badge">{p['insurance']}</span></p></div>
          <div><label>Blood Type</label><p><span class="blood-type">{p['blood_type']}</span></p></div>
          <div><label>Emergency Contact</label><p>{p['emergency_contact']}</p></div>
        </div>
        <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
        <div><label>Diagnosis</label><p class="diagnosis" style="font-size:15px;">{p['diagnosis']}</p></div>
        <div style="margin-top:16px;"><label>Current Medications</label><p>{p['medications']}</p></div>
        <div style="margin-top:16px;"><label>Allergies</label><p style="color:#dc2626;font-weight:500;">{p['allergies']}</p></div>
        <div style="margin-top:16px;"><label>Clinical Notes</label><p style="color:#64748b;">{p['notes']}</p></div>
        <div style="margin-top:16px;"><label>Last Visit</label><p>{p['last_visit']}</p></div>
        """
    # ── Vitals & Labs Tab ──
    elif tab == "vitals":
        if labs:
            vitals_html = ""
            lab_rows = ""
            for lab in labs:
                cls = "v-high" if lab["status"] == "high" else "v-low" if lab["status"] == "low" else ""
                vitals_html += f"""<div class="vital-card {cls}">
                  <div class="vital-label">{lab['test_name']}</div>
                  <div class="vital-value">{lab['value']}</div>
                  <div class="vital-unit">{lab['unit']}</div>
                  <div class="vital-range">{lab['reference_range_low']}\u2013{lab['reference_range_high']}</div>
                </div>"""
                scls = f"lab-{lab['status']}" if lab['status'] in ('normal', 'high', 'low') else 'lab-normal'
                lab_rows += f"""<tr>
                  <td>{lab['test_name']}</td>
                  <td style="font-weight:600;">{lab['value']} {lab['unit']}</td>
                  <td>{lab['reference_range_low']}\u2013{lab['reference_range_high']} {lab['unit']}</td>
                  <td><span class="lab-status {scls}">{lab['status']}</span></td>
                  <td>{lab['resulted_at']}</td>
                  <td style="color:#718096;font-size:12px;">{lab['ordered_by']}</td>
                </tr>"""
            tab_content = f"""
            <h3 class="section-title">Vitals Overview</h3>
            <div class="vitals-grid">{vitals_html}</div>
            <h3 class="section-title" style="margin-top:24px;">Lab Results Detail</h3>
            <table><thead><tr><th>Test</th><th>Result</th><th>Reference</th><th>Status</th><th>Date</th><th>Ordered By</th></tr></thead>
            <tbody>{lab_rows}</tbody></table>"""
        else:
            tab_content = '<div class="empty-state"><p>No lab results on file for this patient.</p></div>'
    # ── Medications Tab ──
    elif tab == "medications":
        meds_list = [m.strip() for m in (p['medications'] or '').split(',') if m.strip()]
        meds_items = "".join(
            f"""<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:8px;background:#f8fafc;">
              <span style="font-weight:500;">{med}</span>
              <a href="/patients/{patient_id}/edit" class="btn btn-sm btn-outline">Edit</a>
            </div>""" for med in meds_list
        )
        allergies_html = ""
        if p['allergies'] and p['allergies'].lower() not in ('none known', 'nkda', 'none'):
            allergies_html = f'<div class="alert alert-danger" style="margin-bottom:16px;"><strong>Allergies:</strong> {p["allergies"]}</div>'
        tab_content = f"""
        {allergies_html}
        <h3 class="section-title">Current Medications ({len(meds_list)})</h3>
        {meds_items or '<div class="empty-state"><p>No medications listed</p></div>'}
        <div style="margin-top:16px;"><a href="/patients/{patient_id}/edit" class="btn btn-primary">Edit Medications</a></div>"""
    # ── Appointments Tab ──
    elif tab == "appointments":
        if appointments:
            items = ""
            for a in appointments:
                dt = a['scheduled_for'][:16].replace('T', ' at ')
                items += f"""<div class="appt-item">
                  <span class="appt-date">{dt}</span>
                  <span class="appt-type">{a['appointment_type']}</span>
                  <span class="appt-doc">{a['doctor_name']}</span>
                  <span class="appt-note">{a['notes'] or ''}</span>
                  <span class="appt-status">Scheduled</span>
                </div>"""
            tab_content = f'<h3 class="section-title">Upcoming Appointments ({len(appointments)})</h3>{items}'
        else:
            tab_content = '<div class="empty-state"><p>No upcoming appointments scheduled.</p></div>'
    # ── History Tab ──
    elif tab == "history":
        if history:
            hrows = ""
            for h in history:
                tc = "tag-update" if h["change_type"] == "UPDATE" else "tag-delete" if h["change_type"] == "DELETE" else "tag-create"
                hrows += f"""<tr>
                  <td><span class="tag {tc}">{h['change_type']}</span></td>
                  <td>{h['changed_at']}</td>
                  <td>{h['changed_field'] or '—'}</td>
                  <td>{(h['old_value'] or '—')[:50]}</td>
                  <td>{(h['new_value'] or '—')[:50]}</td>
                </tr>"""
            tab_content = f"""<h3 class="section-title">Version History</h3>
            <table class="history-table"><thead><tr><th>Action</th><th>Timestamp</th><th>Field</th><th>Old Value</th><th>New Value</th></tr></thead>
            <tbody>{hrows}</tbody></table>"""
        else:
            tab_content = '<div class="empty-state"><p>No change history for this patient.</p></div>'
    else:
        tab_content = ""

    body = f"""
    <div class="breadcrumb"><a href="/dashboard">Dashboard</a> / <a href="/patients">Patients</a> / {p['first_name']} {p['last_name']}</div>
    {msg_html}{deleted_banner}
    <div class="card">
      <div class="detail-header">
        <div>
          <h2>{p['first_name']} {p['last_name']}</h2>
          <div class="patient-meta">
            <span class="mrn">{p['mrn']}</span>
            <span class="blood-type">{p['blood_type']}</span>
            <span class="insurance-badge">{p['insurance']}</span>
          </div>
        </div>
        <div class="detail-actions">
          <a href="/patients" class="btn btn-secondary">Back to List</a>
          <a href="/patients/{p['id']}/edit" class="btn btn-primary">Edit</a>
          <form method="post" action="/patients/{p['id']}/delete" style="display:inline;">
            <button type="submit" class="btn btn-danger" onclick="return confirm('Delete this patient?')">Delete</button>
          </form>
        </div>
      </div>
      {tabs_html}
      {tab_content}
    </div>
    """
    return HTMLResponse(base(f"{p['first_name']} {p['last_name']}", body, active="patients"))


# ──────────────────────────── Edit Patient ────────────────────────────

@app.get("/patients/{patient_id}/edit", response_class=HTMLResponse)
async def edit_form(patient_id: int, request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
        p = await cursor.fetchone()
        if not p:
            return HTMLResponse(base("Not Found", '<div class="card"><h2>Patient not found</h2></div>', active="patients"))

    body = f"""
    <div class="breadcrumb"><a href="/dashboard">Dashboard</a> / <a href="/patients">Patients</a> / <a href="/patients/{p['id']}">{p['first_name']} {p['last_name']}</a> / Edit</div>
    <div class="card">
      <div class="detail-header">
        <h2>Edit: {p['first_name']} {p['last_name']}</h2>
        <a href="/patients/{p['id']}" class="btn btn-secondary">Cancel</a>
      </div>
      <form method="post" action="/patients/{p['id']}/update">
        <div class="field-group">
          <div><label for="first_name">First Name</label><input type="text" name="first_name" id="first_name" value="{p['first_name']}"></div>
          <div><label for="last_name">Last Name</label><input type="text" name="last_name" id="last_name" value="{p['last_name']}"></div>
          <div><label for="dob">Date of Birth</label><input type="text" name="dob" id="dob" value="{p['dob']}"></div>
          <div><label for="phone">Phone</label><input type="text" name="phone" id="phone" value="{p['phone']}"></div>
          <div><label for="insurance">Insurance</label><input type="text" name="insurance" id="insurance" value="{p['insurance']}"></div>
          <div><label for="allergies">Allergies</label><input type="text" name="allergies" id="allergies" value="{p['allergies']}"></div>
        </div>
        <div style="margin-top:16px;"><label for="diagnosis">Diagnosis</label><input type="text" name="diagnosis" id="diagnosis" value="{p['diagnosis']}"></div>
        <div style="margin-top:16px;"><label for="medications">Medications</label><textarea name="medications" id="medications" rows="3">{p['medications']}</textarea></div>
        <div style="margin-top:16px;"><label for="notes">Clinical Notes</label><textarea name="notes" id="notes" rows="4">{p['notes']}</textarea></div>
        <div style="margin-top:16px;display:flex;gap:8px;">
          <button type="submit" class="btn btn-primary">Save Changes</button>
          <a href="/patients/{p['id']}" class="btn btn-secondary">Cancel</a>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(base("Edit Patient", body, active="patients"))


@app.post("/patients/{patient_id}/update")
async def update_patient(patient_id: int, request: Request):
    form = await request.form()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
        old = await cursor.fetchone()
        if not old:
            return RedirectResponse("/patients?msg=Patient+not+found", status_code=302)
        now = datetime.now(timezone.utc).isoformat()
        for field in ["first_name", "last_name", "dob", "phone", "insurance", "allergies", "diagnosis", "medications", "notes"]:
            new_val = form.get(field, "")
            old_val = old[field] or ""
            if new_val and new_val != old_val:
                await db.execute(
                    """INSERT INTO patient_history (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at, changed_field, old_value, new_value)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UPDATE', ?, ?, ?, ?)""",
                    (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'], old['diagnosis'], old['medications'], old['allergies'], old['last_visit'], old['phone'], old['insurance'], now, field, old_val, new_val),
                )
                await db.execute(f"UPDATE patients SET {field} = ? WHERE id = ?", (new_val, patient_id))
        await db.commit()
    return RedirectResponse(f"/patients/{patient_id}?msg=Patient+updated+successfully", status_code=302)


@app.post("/patients/{patient_id}/delete")
async def delete_patient(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
        old = await cursor.fetchone()
        if not old:
            return RedirectResponse("/patients?msg=Patient+not+found", status_code=302)
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO patient_history (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at, changed_field, old_value, new_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DELETE', ?, NULL, NULL, NULL)""",
            (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'], old['diagnosis'], old['medications'], old['allergies'], old['last_visit'], old['phone'], old['insurance'], now),
        )
        await db.execute("UPDATE patients SET deleted = 1, deleted_at = ? WHERE id = ?", (now, patient_id))
        await db.commit()
    return RedirectResponse("/patients?msg=Patient+deleted", status_code=302)


# ──────────────────────────── Appointments Page ────────────────────────────

@app.get("/appointments", response_class=HTMLResponse)
async def appointments_page(request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM appointments WHERE status = 'scheduled' ORDER BY scheduled_for ASC")
        appointments = await cursor.fetchall()

    by_doctor = {}
    for a in appointments:
        by_doctor.setdefault(a['doctor_name'], []).append(a)

    rows = ""
    for a in appointments:
        dt = a['scheduled_for'][:16].replace('T', ' at ')
        rows += f"""<tr>
          <td style="font-weight:600;color:#2563eb;font-size:13px;">{dt}</td>
          <td><a href="/patients/{a['patient_id']}" style="color:#2563eb;text-decoration:none;font-weight:500;">{a['patient_name']}</a></td>
          <td>{a['appointment_type']}</td>
          <td>{a['doctor_name']}</td>
          <td style="font-size:12px;color:#64748b;">{a['notes'] or '—'}</td>
          <td><span class="appt-status">Scheduled</span></td>
        </tr>"""

    doc_buttons = '<a href="/appointments" class="filter-btn active">All Doctors</a>'
    for doc in sorted(by_doctor.keys()):
        doc_buttons += f'<a href="/appointments?doctor={doc}" class="filter-btn">{doc} ({len(by_doctor[doc])})</a>'

    body = f"""
    <div class="breadcrumb"><a href="/dashboard">Dashboard</a> / Appointments</div>
    <div class="card">
      <div class="card-header"><span class="card-title">Upcoming Appointments ({len(appointments)})</span></div>
      <div class="filter-row">{doc_buttons}</div>
      <table>
        <thead><tr><th>Date & Time</th><th>Patient</th><th>Type</th><th>Doctor</th><th>Notes</th><th>Status</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="6" class="empty-state">No upcoming appointments</td></tr>'}</tbody>
      </table>
    </div>
    """
    return HTMLResponse(base("Appointments", body, active="appointments"))


# ──────────────────────────── Lab Results Page ────────────────────────────

@app.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    fs = request.query_params.get("filter", "")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if fs == "abnormal":
            cursor = await db.execute("SELECT lr.*, p.first_name, p.last_name FROM lab_results lr JOIN patients p ON lr.patient_id = p.id WHERE lr.status != 'normal' ORDER BY lr.resulted_at DESC")
        elif fs in ("high", "low"):
            cursor = await db.execute("SELECT lr.*, p.first_name, p.last_name FROM lab_results lr JOIN patients p ON lr.patient_id = p.id WHERE lr.status = ? ORDER BY lr.resulted_at DESC", (fs,))
        else:
            cursor = await db.execute("SELECT lr.*, p.first_name, p.last_name FROM lab_results lr JOIN patients p ON lr.patient_id = p.id ORDER BY lr.resulted_at DESC")
        labs = await cursor.fetchall()

    rows = ""
    for lab in labs:
        scls = f"lab-{lab['status']}" if lab['status'] in ('normal', 'high', 'low') else 'lab-normal'
        rows += f"""<tr>
          <td><a href="/patients/{lab['patient_id']}?tab=vitals" style="color:#2563eb;text-decoration:none;font-weight:500;">{lab['first_name']} {lab['last_name']}</a></td>
          <td>{lab['test_name']}</td>
          <td style="font-weight:600;">{lab['value']} {lab['unit']}</td>
          <td>{lab['reference_range_low']}\u2013{lab['reference_range_high']} {lab['unit']}</td>
          <td><span class="lab-status {scls}">{lab['status']}</span></td>
          <td>{lab['resulted_at']}</td>
          <td style="color:#718096;font-size:12px;">{lab['ordered_by']}</td>
        </tr>"""

    body = f"""
    <div class="breadcrumb"><a href="/dashboard">Dashboard</a> / Lab Results</div>
    <div class="card">
      <div class="card-header"><span class="card-title">Lab Results ({len(labs)})</span></div>
      <div class="filter-row">
        <a href="/labs" class="filter-btn {"active" if not fs else ""}">All Results</a>
        <a href="/labs?filter=abnormal" class="filter-btn {"active" if fs=="abnormal" else ""}">Abnormal Only</a>
        <a href="/labs?filter=high" class="filter-btn {"active" if fs=="high" else ""}">High</a>
        <a href="/labs?filter=low" class="filter-btn {"active" if fs=="low" else ""}">Low</a>
      </div>
      <table>
        <thead><tr><th>Patient</th><th>Test</th><th>Result</th><th>Reference</th><th>Status</th><th>Date</th><th>Ordered By</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="7" class="empty-state">No lab results found</td></tr>'}</tbody>
      </table>
    </div>
    """
    return HTMLResponse(base("Lab Results", body, active="labs"))


# ──────────────────────────── API endpoints (JSON) ────────────────────────────

@app.get("/api/patients")
async def api_patients():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients ORDER BY id")
        return [dict(row) for row in await cursor.fetchall()]


@app.get("/api/patients/{patient_id}/history")
async def api_patient_history(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC", (patient_id,))
        return [dict(row) for row in await cursor.fetchall()]
