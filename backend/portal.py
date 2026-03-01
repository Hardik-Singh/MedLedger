"""
MedLedger Portal — Agent-Native EHR
Mock patient portal on port 8001. Server-rendered HTML for browser-use DOM access.
"""

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timezone
import aiosqlite
from backend.database import DB_PATH, init_db

app = FastAPI(title="MedLedger Portal")

# ──────────────────────────── HTML Templates ────────────────────────────

STYLE = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f0f4f8; color: #1a202c; }
  .topbar { background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: white; padding: 12px 32px; display: flex; justify-content: space-between; align-items: center; }
  .topbar h1 { font-size: 20px; font-weight: 600; letter-spacing: 0.5px; }
  .topbar .badge { background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
  .topbar a { color: white; text-decoration: none; margin-left: 24px; font-size: 14px; opacity: 0.9; }
  .topbar a:hover { opacity: 1; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .card { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 24px; margin-bottom: 20px; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #f7fafc; text-align: left; padding: 12px 16px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #718096; border-bottom: 2px solid #e2e8f0; }
  td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
  tr:hover { background: #f7fafc; }
  .btn { display: inline-block; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500; cursor: pointer; border: none; }
  .btn-primary { background: #2563eb; color: white; }
  .btn-primary:hover { background: #1d4ed8; }
  .btn-danger { background: #ef4444; color: white; }
  .btn-danger:hover { background: #dc2626; }
  .btn-secondary { background: #e2e8f0; color: #475569; }
  .mrn { font-family: 'Courier New', monospace; font-size: 13px; color: #6366f1; }
  .diagnosis { color: #059669; font-weight: 500; }
  .deleted-row { opacity: 0.5; text-decoration: line-through; }
  .search-box { display: flex; gap: 8px; margin-bottom: 20px; }
  .search-box input { flex: 1; padding: 10px 16px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
  .search-box input:focus { outline: none; border-color: #2563eb; }
  label { display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.3px; }
  input[type=text], input[type=password], textarea { width: 100%; padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; margin-bottom: 16px; font-family: inherit; }
  input:focus, textarea:focus { outline: none; border-color: #2563eb; }
  .field-group { display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px; }
  .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
  .detail-header h2 { font-size: 22px; color: #1e3a5f; }
  .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
  .alert-success { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
  .alert-danger { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
  .login-wrap { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #7c3aed 100%); }
  .login-card { background: white; padding: 48px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 400px; }
  .login-card h1 { text-align: center; color: #1e3a5f; margin-bottom: 8px; font-size: 28px; }
  .login-card p { text-align: center; color: #64748b; margin-bottom: 32px; font-size: 14px; }
  .login-card .btn { width: 100%; padding: 12px; font-size: 16px; }
  .history-table { font-size: 13px; }
  .history-table td { padding: 8px 12px; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
  .tag-update { background: #fef3c7; color: #92400e; }
  .tag-delete { background: #fee2e2; color: #991b1b; }
  .tag-create { background: #d1fae5; color: #065f46; }
</style>
"""


def topbar(user="Dr. Agent"):
    return f"""
    <nav class="topbar">
      <div style="display:flex;align-items:center;gap:16px;">
        <h1>MedLedger Portal</h1>
        <span class="badge">Agent-Native EHR</span>
      </div>
      <div>
        <span style="font-size:13px;opacity:0.8;">Logged in as <strong>{user}</strong></span>
        <a href="/logout">Sign Out</a>
      </div>
    </nav>
    """


def base(title, body, user="Dr. Agent"):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — MedLedger Portal</title>{STYLE}</head>
<body>{topbar(user)}<div class="container">{body}</div></body></html>"""


# ──────────────────────────── Auth (simple cookie) ────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.cookies.get("session") == "authenticated":
        return RedirectResponse("/patients", status_code=302)
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
  <button type="submit" class="btn btn-primary">Sign In</button>
</form>
<p style="margin-top:16px;font-size:12px;color:#94a3b8;">Demo: demo / demo123</p>
</div></div></body></html>"""
    return HTMLResponse(html)


@app.post("/login")
async def do_login(username: str = Form(...), password: str = Form(...)):
    if username == "demo" and password == "demo123":
        response = RedirectResponse("/patients", status_code=302)
        response.set_cookie("session", "authenticated", max_age=86400)
        return response
    return RedirectResponse("/login?error=Invalid+credentials", status_code=302)


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response


# ──────────────────────────── Patient List ────────────────────────────

@app.get("/patients", response_class=HTMLResponse)
async def patient_list(request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    q = request.query_params.get("q", "")
    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if q:
            cursor = await db.execute(
                "SELECT * FROM patients WHERE (first_name || ' ' || last_name LIKE ? OR mrn LIKE ?) AND deleted = 0",
                (f"%{q}%", f"%{q}%"),
            )
        else:
            cursor = await db.execute("SELECT * FROM patients WHERE deleted = 0 ORDER BY last_name ASC")
        patients = await cursor.fetchall()

    rows = ""
    for p in patients:
        rows += f"""<tr>
          <td class="mrn">{p['mrn']}</td>
          <td><a href="/patients/{p['id']}">{p['last_name']}, {p['first_name']}</a></td>
          <td>{p['dob']}</td>
          <td class="diagnosis">{p['diagnosis']}</td>
          <td>{p['medications'][:50]}{'...' if len(p['medications'])>50 else ''}</td>
          <td>{p['last_visit']}</td>
          <td><a href="/patients/{p['id']}" class="btn btn-primary" style="padding:4px 12px;">View</a></td>
        </tr>"""

    search_val = f'value="{q}"' if q else ""
    body = f"""
    {msg_html}
    <div class="card">
      <h2 style="margin-bottom:16px;color:#1e3a5f;">Patient Registry</h2>
      <form method="get" action="/patients/search" class="search-box">
        <input type="text" name="q" placeholder="Search by patient name or MRN..." {search_val} id="search-input" aria-label="Search patients">
        <button type="submit" class="btn btn-primary">Search</button>
      </form>
      <table>
        <thead><tr><th>MRN</th><th>Patient Name</th><th>DOB</th><th>Diagnosis</th><th>Medications</th><th>Last Visit</th><th></th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {f'<p style="margin-top:16px;color:#718096;">Showing {len(patients)} patient(s)' + (f' matching "{q}"' if q else '') + '</p>'}
    </div>
    """
    return HTMLResponse(base("Patients", body))


@app.get("/patients/search", response_class=HTMLResponse)
async def search_patients(request: Request):
    q = request.query_params.get("q", "")
    return RedirectResponse(f"/patients?q={q}", status_code=302)


# ──────────────────────────── Patient Detail ────────────────────────────

@app.get("/patients/{patient_id}", response_class=HTMLResponse)
async def patient_detail(patient_id: int, request: Request):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse("/login", status_code=302)

    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        p = await cursor.fetchone()
        if not p:
            return HTMLResponse(base("Not Found", '<div class="card"><h2>Patient not found</h2><a href="/patients">Back to list</a></div>'))

        cursor2 = await db.execute(
            "SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC LIMIT 20",
            (patient_id,),
        )
        history = await cursor2.fetchall()

    history_rows = ""
    for h in history:
        tag_class = "tag-update" if h["change_type"] == "UPDATE" else "tag-delete" if h["change_type"] == "DELETE" else "tag-create"
        history_rows += f"""<tr>
          <td><span class="tag {tag_class}">{h['change_type']}</span></td>
          <td>{h['changed_at']}</td>
          <td>{h['changed_field'] or '—'}</td>
          <td>{h['old_value'] or '—'}</td>
          <td>{h['new_value'] or '—'}</td>
        </tr>"""

    history_section = ""
    if history:
        history_section = f"""
        <div class="card">
          <h3 style="margin-bottom:12px;color:#1e3a5f;">Version History</h3>
          <table class="history-table"><thead><tr><th>Action</th><th>Timestamp</th><th>Field</th><th>Old Value</th><th>New Value</th></tr></thead>
          <tbody>{history_rows}</tbody></table>
        </div>"""

    deleted_banner = ""
    if p["deleted"]:
        deleted_banner = '<div class="alert alert-danger"><strong>[DELETED]</strong> This patient record has been deleted.</div>'

    body = f"""
    {msg_html}{deleted_banner}
    <div class="card">
      <div class="detail-header">
        <h2>{p['first_name']} {p['last_name']}</h2>
        <div>
          <a href="/patients" class="btn btn-secondary">Back to List</a>
          <a href="/patients/{p['id']}/edit" class="btn btn-primary" style="margin-left:8px;">Edit</a>
          <form method="post" action="/patients/{p['id']}/delete" style="display:inline;margin-left:8px;">
            <button type="submit" class="btn btn-danger" onclick="return confirm('Delete this patient?')">Delete</button>
          </form>
        </div>
      </div>
      <div class="field-group">
        <div><label>MRN</label><p class="mrn" style="font-size:16px;">{p['mrn']}</p></div>
        <div><label>Date of Birth</label><p>{p['dob']}</p></div>
        <div><label>Phone</label><p>{p['phone']}</p></div>
        <div><label>Insurance</label><p>{p['insurance']}</p></div>
      </div>
      <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
      <div><label>Diagnosis</label><p class="diagnosis">{p['diagnosis']}</p></div>
      <div style="margin-top:16px;"><label>Medications</label><p>{p['medications']}</p></div>
      <div style="margin-top:16px;"><label>Allergies</label><p>{p['allergies']}</p></div>
      <div style="margin-top:16px;"><label>Last Visit</label><p>{p['last_visit']}</p></div>
    </div>
    {history_section}
    """
    return HTMLResponse(base(f"{p['first_name']} {p['last_name']}", body))


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
            return HTMLResponse(base("Not Found", '<div class="card"><h2>Patient not found</h2></div>'))

    body = f"""
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
        <button type="submit" class="btn btn-primary" style="margin-top:8px;">Save Changes</button>
      </form>
    </div>
    """
    return HTMLResponse(base("Edit Patient", body))


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
        fields = ["first_name", "last_name", "dob", "phone", "insurance", "allergies", "diagnosis", "medications"]
        for field in fields:
            new_val = form.get(field, "")
            old_val = old[field] or ""
            if new_val and new_val != old_val:
                # Save history
                await db.execute(
                    """INSERT INTO patient_history
                       (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at, changed_field, old_value, new_value)
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
            """INSERT INTO patient_history
               (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at, changed_field, old_value, new_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DELETE', ?, NULL, NULL, NULL)""",
            (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'], old['diagnosis'], old['medications'], old['allergies'], old['last_visit'], old['phone'], old['insurance'], now),
        )
        await db.execute("UPDATE patients SET deleted = 1, deleted_at = ? WHERE id = ?", (now, patient_id))
        await db.commit()

    return RedirectResponse("/patients?msg=Patient+deleted", status_code=302)


# ──────────────────────────── API endpoints (JSON) for agent ────────────────────────────

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


# ──────────────────────────── Startup ────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
