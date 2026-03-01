# MedLedger

**Cryptographic Audit Trail for AI Patient Portal Agents**

*Browser Use YC Hackathon (Feb 28 - Mar 1, 2026)*

> Every AI action on a medical record -- signed, hash-chained, and verifiable. Because "the AI changed it" is not an acceptable audit trail.

---

## The Problem

AI agents are increasingly navigating and modifying electronic health records. But there's no way to cryptographically prove what an agent did, when it did it, or whether the record was tampered with. In healthcare, this isn't just a compliance gap -- it's a patient safety risk.

## Two Products, One Platform

### MedLedger Audit Trail
Works with **ANY patient portal** -- Epic, Cerner, Athena, whatever your hospital uses. The Browser Use agent navigates it, and every action gets ECDSA-signed and hash-chained into a tamper-evident audit trail. Plug it into any existing system and get verifiable audit logs instantly.

### MedLedger Portal
A purpose-built, **agent-native EHR** designed from the ground up for AI agents AND human users. Structured DOM, clean accessibility tree, explicit action hooks. The best possible experience for browser-use agents -- because we built the portal for them.

**Go-to-market:** Land with the audit trail at hospitals that already have portals (huge market, easy compliance sell). Upsell MedLedger Portal to smaller orgs who need the whole stack.

---

## Architecture

```
React Dashboard (:3000)       Portal (:8001)        FastAPI API (:8000)
       |                          |                        |
       +--- WebSocket stream <----+--- REST/HTML ----------+
                                                           |
                                  +------------------------+
                                  |
                        +---------+---------+
                        |  Browser Use v0.12 |
                        |  Agent Runtime     |
                        +----+----+----+----+
                             |    |    |
                   +---------+    |    +---------+
                   |              |              |
              ARIA (P-256)  DELTA (P-256)  AUDITOR (P-256)
                   |              |              |
                   +------+-------+------+------+
                          |              |
                   SHA-256 Hash Chain    Supermemory
                    (audit_log DB)      (Long-term Memory)
```

**How it works:**
1. **Action** -- Agent performs a tool call (search, view, update, delete, review labs, schedule...)
2. **Sign** -- ECDSA P-256 private key signs the SHA-256 hash of the action record
3. **Chain** -- Each action's `prev_hash` links to the previous action's hash
4. **Store** -- Action stored in Supermemory for cross-session recall
5. **Stream** -- Signed action broadcasts to the dashboard via WebSocket in real-time
6. **Verify** -- `verify_chain()` walks every link and validates every signature

---

## Features

### Cryptographic Audit Chain
- **ECDSA P-256 digital signatures** per agent identity (ARIA, DELTA, AUDITOR, custom)
- **SHA-256 hash-chaining** with `prev_hash` linking (GENESIS -> current)
- **Multi-agent cross-signing** -- Agent B's first action links to Agent A's last, creating a unified audit trail across agent handoffs
- Real-time chain verification -- detect any tampered record instantly
- Tamper simulation demo -- corrupt a record, watch verification fail, then restore
- Full audit log export (JSON + CSV) with signature verification status

### Browser Use Agent Integration (v0.12)
- `BrowserSession` with headless Chromium via Playwright
- 13 registered controller actions, each cryptographically signed before execution:

| Tool | Action Type | Description |
|------|-------------|-------------|
| `list_patients` | SEARCH | List all patients with basic info |
| `search_patient` | SEARCH | Search by name, MRN, diagnosis, or medication |
| `view_patient` | VIEW | Full record + recalled memory from past sessions |
| `update_patient` | UPDATE | Update with medication safety checks before write |
| `delete_patient` | DELETE | Soft delete, preserved for audit |
| `get_patient_history` | HISTORY | Full version history with diffs |
| `recall_memory` | -- | Query Supermemory for past interactions |
| `review_labs` | LAB_REVIEW | Lab results with abnormal flagging |
| `view_appointments` | APPOINTMENTS | Patient appointment list |
| `schedule_appointment` | SCHEDULE | Create a follow-up appointment |
| `review_high_risk_patients` | RISK_REVIEW | Risk stratification across all patients |
| `check_care_team` | CARE_TEAM | Care team coordination log |

- `extend_system_message` for context-rich prompts with recalled Supermemory context
- Claude Sonnet 4 via `langchain-anthropic`

### Supermemory Integration (v3.27)
- Persistent long-term memory across agent sessions
- **Per-patient memory isolation** via `container_tags` -- each patient gets their own memory silo
- **Per-agent tagging** -- track which agent stored which memory
- Three memory operations:
  - `store_interaction()` -- every agent action stored with structured metadata (`client.add()`)
  - `recall_patient()` -- semantic search within a patient's container (`client.search.memories()`)
  - `recall_context()` -- broad task-based recall with summaries (`client.search.documents()`)
- `get_patient_profile()` -- Supermemory profile API for static facts + dynamic context (`client.profile()`)
- API key configurable at runtime via dashboard UI
- Graceful fallback when SDK not installed or key not configured

### Medication Safety System
- **Allergy Conflict Checker** -- cross-references patient allergies against drug classes (penicillin -> amoxicillin, sulfa -> furosemide, NSAID -> aspirin, etc.)
- **Drug Interaction Database** -- 16 hardcoded critical/high/medium interactions (warfarin+aspirin, SSRI+tramadol, digoxin+amiodarone, metformin+contrast, etc.)
- **Class-aware matching** -- SSRI and NSAID drug classes resolved automatically
- **Dosage Safety Checker** -- 17 drugs with min/max therapeutic bounds + elderly-specific limits
- **Three-layer gate on medication updates**:
  1. Allergy conflict check -- **BLOCKS** on conflict
  2. Drug interaction check -- **BLOCKS** on CRITICAL, warns on HIGH/MEDIUM
  3. Dosage safety check -- **BLOCKS** on overdose, warns near max
- All safety events broadcast via WebSocket as `interaction_alert`

### Patient Risk Stratification
- Scoring engine based on: age, conditions, medication count (polypharmacy), allergies, recent activity
- Condition factors: diabetes (+2), afib (+3), hypertension (+1), cancer (+4), CHF (+3), COPD (+2), renal (+2)
- Age: >75 (+3), >60 (+1). Polypharmacy: >5 meds (+2), >3 meds (+1)
- Risk levels: **CRITICAL** (>=8), **HIGH** (>=5), **MEDIUM** (>=3), **LOW** (<3)
- All-patient risk dashboard sorted by score descending
- Per-patient risk endpoint with factor breakdown

### Clinical Features
| Feature | Description |
|---------|-------------|
| Lab Results Tracker | 24 seeded lab results with normal/abnormal/critical flagging |
| Appointment Scheduler | 17 seeded appointments with create/cancel |
| Patient Notes | SOAP-format clinical notes with finalize workflow |
| Care Team Log | Tracks which agents/providers accessed each record |
| Shift Handoff Report | JSON + printable HTML summarizing all patient activity |
| Rounds Summary | Printable one-pager per patient (demographics, risk, labs, appointments, allergies) |

### Auditing Agent
- Runs without browser-use (pure tool calls, no browser needed)
- Three-phase audit:
  1. **Chain integrity** -- verifies every hash and signature in the chain
  2. **Pattern analysis** -- flags excessive deletions, failed verifications, high modification activity
  3. **Data completeness** -- checks for missing medications, phone numbers, emergency contacts
- Stores findings in Supermemory for cross-session audit history
- Results broadcast via WebSocket to dashboard

### Real-Time Dashboard (React)
- **Clinical View** -- human-readable action descriptions with color-coded types
- **Audit View** -- hash chains, signatures, block explorer with prev/next navigation
- **Chain Integrity Panel** -- live verification status, risk score, agent roster
- **12 action type colors** -- SEARCH, VIEW, UPDATE, DELETE, HISTORY, AUDIT, LAB_REVIEW, APPOINTMENTS, SCHEDULE, RISK_REVIEW, CARE_TEAM, TASK_COMPLETE
- **Smart Alerts** -- bell icon with severity badges (CRITICAL, HIGH, MEDIUM, LOW)
- **Template bar** -- one-click agent tasks (Lookup, Update Meds, Multi-Agent, Audit)
- **Agent selector** -- ARIA, DELTA, AUDITOR, or custom agent names
- **API key bar** -- set Anthropic + Supermemory keys directly in the UI
- **WebSocket streaming** -- actions appear in real time as agents work
- **Tamper demo** -- corrupt a record, watch the chain break, then restore

### Patient Portal (Server-Rendered)
- Server-rendered HTML on port 8001 for browser-use DOM access
- Login system (demo / demo123)
- Patient list with search, patient detail pages
- Fully accessible to browser-use agents via Playwright

---

## Patient Data

15 YC founders/partners with realistic medical data:

| Patient | Condition | Medications | Risk |
|---------|-----------|-------------|------|
| Sam Altman | Seasonal Allergies | Claritin, Flonase | LOW |
| Paul Graham | Mild Eye Strain | Artificial tears, blue-light glasses | LOW |
| Jessica Livingston | Common Cold | Vitamin C, Zinc lozenges | LOW |
| Garry Tan | Caffeine Withdrawal | Ibuprofen, caffeine taper | LOW |
| Michael Seibel | Runner's Knee | Ibuprofen, PT, knee brace | LOW |
| Dalton Caldwell | Mild Tension Headache | Acetaminophen | LOW |
| Jared Friedman | Allergies + Sunburn | Zyrtec, Aloe vera, SPF 50 | LOW |
| Gustaf Alstromer | Tennis Elbow | Naproxen, elbow strap | LOW |
| Kevin Hale | Sprained Ankle | RICE protocol, Ibuprofen | LOW |
| Adora Cheung | Persistent Hiccups | Chlorpromazine, peppermint tea | LOW |
| Brian Chesky | Type 2 Diabetes + Hypertension | Metformin 500mg, Lisinopril 10mg, Aspirin 81mg | HIGH |
| Patrick Collison | Atrial Fibrillation | Eliquis 5mg, Metoprolol 50mg | HIGH |
| Drew Houston | Vitamin D Deficiency | Vitamin D3 5000IU, Calcium 600mg | LOW |
| Tracy Young | Carpal Tunnel Syndrome | Wrist splint, Ibuprofen 400mg, B6 | LOW |
| Emmett Shear | Mild Anxiety + Insomnia | Sertraline 50mg, Melatonin 3mg | MEDIUM |

Plus 24 condition-appropriate lab results (IgE for allergies, BP for caffeine withdrawal, HbA1c for diabetes, nerve conduction for carpal tunnel) and 17 upcoming appointments.

---

## Quick Start

```bash
# 1. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# 2. (Optional) Set Supermemory key for persistent agent memory
export SUPERMEMORY_API_KEY=sm-...

# 3. Run everything
chmod +x run.sh
./run.sh
```

Or set both API keys in the dashboard UI -- no terminal required.

### Manual Start

```bash
pip install -r requirements.txt
playwright install chromium
cd frontend && npm install && npm run build && cd ..

# Terminal 1: Patient Portal
uvicorn backend.portal:app --host 0.0.0.0 --port 8001

# Terminal 2: API + WebSocket Hub
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For agents | Claude API key (or set in dashboard UI) |
| `SUPERMEMORY_API_KEY` | Optional | Supermemory API key for persistent agent memory |

---

## Using It

Type whatever you want the agent to do in plain English:

```
"Look up Sam Altman and update his allergy meds to Zyrtec"
"Who has a headache? Change Dalton's prescription to Excedrin"
"Show me everyone on ibuprofen"
"Review labs for Brian Chesky and flag anything abnormal"
"Schedule a follow-up for Patrick Collison in 2 weeks"
"Review all high-risk patients"
"Check the care team log for Emmett Shear"
```

### Things to try

- **Toggle views** -- Auditor view shows crypto hashes, Clinical view shows plain English
- **Click any action** -- Chain Explorer shows full payload, signature, and chain links
- **Tamper Demo** -- Corrupt a record, watch the chain break, restore it
- **Run Audit** -- The auditing agent checks chain integrity, patterns, and data completeness
- **Multi-Agent** -- ARIA searches, DELTA updates, both share the same cross-signed chain
- **Export** -- Download the full verified audit log as JSON or CSV

---

## API Endpoints

### Audit Chain
| Method | Path | Description |
|--------|------|-------------|
| GET | `/audit/log` | Full audit log with verification status |
| GET | `/audit/verify` | Chain integrity verification |
| POST | `/audit/tamper` | Corrupt last record (demo) |
| POST | `/audit/restore` | Restore tampered record |
| GET | `/audit/export` | Export audit log as JSON |
| GET | `/audit/export/csv` | Export audit log as CSV |

### Patients
| Method | Path | Description |
|--------|------|-------------|
| GET | `/patients/current` | All active patients |
| GET | `/patients/{id}/history` | Version history |
| GET | `/patients/{id}/labs` | Lab results |
| GET | `/patients/{id}/risk` | Risk score + factors |
| GET | `/patients/{id}/care-team` | Care team log |
| GET | `/patients/{id}/notes` | Clinical notes |
| POST | `/patients/{id}/notes` | Create a note |
| POST | `/notes/{id}/finalize` | Finalize a note |
| GET | `/patients/{id}/rounds-summary` | Printable rounds one-pager (HTML) |
| GET | `/patients/risks` | All risk scores sorted by severity |

### Appointments
| Method | Path | Description |
|--------|------|-------------|
| GET | `/appointments/upcoming` | All upcoming appointments |
| GET | `/patients/{id}/appointments` | Appointments for a patient |
| POST | `/appointments` | Create an appointment |
| POST | `/appointments/{id}/cancel` | Cancel an appointment |

### Reports
| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports/handoff` | Shift handoff report (JSON) |
| GET | `/reports/handoff/html` | Printable handoff report (HTML) |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/agent/run` | Run a single browser-use agent |
| POST | `/agent/multi` | Run a multi-agent workflow |
| POST | `/agent/audit` | Run the auditing agent |

### Configuration
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/set-key` | Set Anthropic API key |
| GET | `/api/key-status` | Check API key status |
| POST | `/api/set-memory-key` | Set Supermemory API key |
| GET | `/api/memory-status` | Check Supermemory status |
| GET | `/stats` | Dashboard statistics |
| GET | `/alerts` | Smart alerts list |
| POST | `/alerts/{id}/acknowledge` | Acknowledge an alert |
| WS | `/ws` | WebSocket stream for real-time events |

---

## Testing

```bash
python -m pytest tests/test_backend.py -v
```

**64 tests** covering:
- Database: init, seeding, idempotency, all 7 tables
- Audit chain: signing, hash linking, verification, tamper/restore, multi-agent keys
- REST API: all 30+ endpoints (patients, audit, export, appointments, labs, risk, handoff, rounds, memory)
- Portal: login flow, auth guards, patient API
- Alerts: delete/update/verification triggers
- Medication interactions: critical combos, safe combos, allergy conflicts, NSAID class matching
- Dosage checker: safe/overdose/elderly limits, string parsing
- Risk engine: low/high/critical scoring, all-patient ranking, factor breakdown
- Memory: status checking, graceful no-client fallback

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Runtime | [browser-use](https://github.com/browser-use/browser-use) v0.12 + Playwright |
| LLM | Claude Sonnet 4 via [langchain-anthropic](https://python.langchain.com/docs/integrations/chat/anthropic/) |
| Long-term Memory | [Supermemory](https://supermemory.ai) v3.27 |
| Backend | FastAPI + aiosqlite + uvicorn |
| Frontend | React (single-page, builds to static) |
| Crypto | ECDSA P-256 (cryptography lib) + SHA-256 |
| Database | SQLite (async via aiosqlite) |
| Portal | Server-rendered HTML (FastAPI) |
| Real-time | WebSocket (native FastAPI) |

---

## Project Structure

```
MedLedger/
  backend/
    main.py            # FastAPI API server (port 8000) — 30+ endpoints
    portal.py          # Patient portal (port 8001) — server-rendered HTML
    agent.py           # Browser-use agent runtime + 13 registered tools
    audit_chain.py     # ECDSA P-256 signing + SHA-256 hash chain
    database.py        # SQLite schema, 15 patients, seed data
    memory.py          # Supermemory integration (add, search, profile)
    interactions.py    # Medication interaction checker (16 interactions)
    dosage_checker.py  # Drug dosage safety validator (17 drugs)
    risk_engine.py     # Patient risk stratification engine
    models.py          # Pydantic models
  frontend/
    src/App.js         # React dashboard (clinical + audit views)
    src/App.css        # Dashboard styles
  tests/
    test_backend.py    # 64 tests
  run.sh               # One-command start script
  requirements.txt     # Python dependencies
```

---

## Why This Matters

Healthcare AI is moving fast. Agents will read, modify, and manage patient records at scale. Without cryptographic auditability:

- **Compliance**: HIPAA requires audit trails. "The AI did it" doesn't cut it.
- **Liability**: When something goes wrong, who proves what the AI actually did?
- **Trust**: Patients and providers need to know AI actions are transparent and verifiable.
- **Tamper-evidence**: If anyone -- human or AI -- alters the audit log, the chain breaks immediately.
- **Safety**: Medication interactions and dosage errors are caught before they reach the patient.

MedLedger makes every AI action provable, tamper-evident, and auditable. It's the infrastructure layer that healthcare AI needs before it can scale.

---

*Built for the Browser Use YC Hackathon (Feb 28 - Mar 1, 2026)*
