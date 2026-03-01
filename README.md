# MedLedger

**Cryptographically audited AI agent layer for patient portals.**

> Every AI action on a medical record — signed, hash-chained, and verifiable. Because "the AI changed it" is not an acceptable audit trail.

---

## The Problem

AI agents are increasingly navigating and modifying electronic health records. But there's no way to cryptographically prove what an agent did, when it did it, or whether the record was tampered with. In healthcare, this isn't just a compliance gap — it's a patient safety risk.

## Two Products, One Platform

### MedLedger Audit Trail
Works with **ANY patient portal** — Epic, Cerner, Athena, whatever your hospital uses. The Browser Use agent navigates it, and every action gets ECDSA-signed and hash-chained into a tamper-evident audit trail. Plug it into any existing system and get verifiable audit logs instantly.

### MedLedger Portal
A purpose-built, **agent-native EHR** designed from the ground up for AI agents AND human users. Structured DOM, clean accessibility tree, explicit action hooks. The best possible experience for browser-use agents — because we built the portal for them.

**Go-to-market:** Land with the audit trail at hospitals that already have portals (huge market, easy compliance sell). Upsell MedLedger Portal to smaller orgs who need the whole stack.

## How It Works

Every agent action — including **read-only** ones like search and view (HIPAA requires access logging) — goes through this pipeline:

1. **Action** — Agent performs a tool call (search, view, update, delete)
2. **Sign** — ECDSA P-256 private key signs the SHA-256 hash of the action record
3. **Chain** — Each action's `prev_hash` links to the previous action's hash (like a blockchain)
4. **Stream** — Signed action broadcasts to the dashboard via WebSocket in real-time
5. **Verify** — `verify_chain()` walks every link and validates every signature. If anyone modifies the DB, it catches it.

## Architecture

```
  Dashboard (:3000)          MedLedger API (:8000)          Portal (:8001)
 ┌────────────────┐         ┌──────────────────┐         ┌─────────────────┐
 │ Auditor View   │◄──ws──►│ WebSocket Hub    │         │ MedLedger Portal│
 │ Clinical View  │         │ POST /agent/run  │         │ Agent-Native EHR│
 │ Chain Explorer │         │ GET /audit/verify│         │ 10 patients     │
 │ Risk Scoring   │         │ GET /audit/log   │         │ CRUD + History  │
 │ Tamper Demo    │         │ POST /audit/tamper│        │ Server-rendered │
 └────────────────┘         └────────┬─────────┘         └────────┬────────┘
                                     │                             │
                            ┌────────┴─────────┐                   │
                            │  Browser Use Agent│──── navigates ───┘
                            │  + Custom Tools   │
                            │  ┌──────────────┐ │
                            │  │ audit_chain   │ │
                            │  │ ECDSA P-256   │ │
                            │  │ SHA-256 chain │ │
                            │  │ GENESIS → ... │ │
                            │  └──────────────┘ │
                            └──────────────────┘
```

## Features

- **Dual Dashboard Views** — Auditor view (crypto hashes, signatures, chain links) and Clinical view (plain English timeline for doctors/nurses)
- **Chain Explorer** — Click any action to see full payload, complete hash, signature, and visual chain links to prev/next actions
- **Tamper Simulation** — One-click demo: corrupt a record, watch the chain break, restore it. Perfect for live demos.
- **Risk Scoring** — Each action scored (LOW/MEDIUM/HIGH), aggregate session risk meter
- **Custom Agent Names** — Name your agent ("Dr. Bot", "Nurse AI"), shown in every audit entry
- **Task Templates** — Pre-built demo buttons: Patient Lookup, Medication Update, Full Audit, Multi-Patient Search
- **Export** — Download full audit log + verification report as JSON
- **Live Portal View** — Watch the agent navigate the portal in real-time via embedded iframe
- **API Key in UI** — Set your Anthropic key right in the dashboard, no terminal needed

## Quick Start

```bash
# 1. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Run everything
chmod +x run.sh
./run.sh
```

Or set the API key in the dashboard UI — no terminal required.

### Manual Start

```bash
pip install -r requirements.txt
playwright install chromium

# Terminal 1: Patient Portal
uvicorn backend.portal:app --port 8001 --reload

# Terminal 2: API + WebSocket Hub
uvicorn backend.main:app --port 8000 --reload

# Terminal 3: React Dashboard
cd frontend && npm install && npm start
```

## Demo Script (3-4 minutes)

This is the exact flow for recording a demo:

| Step | Action | What judges see |
|------|--------|-----------------|
| 1 | Open dashboard at `localhost:3000` | Empty state — "No actions yet" |
| 2 | Click **"Full Audit Demo"** template | Task auto-fills |
| 3 | Hit **Run Agent** | Actions stream in real-time, each with hash + signature |
| 4 | Switch to **Clinical View** | Same actions, plain English: "Searched for Sam Altman", "Updated medication..." |
| 5 | Switch back to **Auditor View** | Crypto chain visible — hashes linking to each other |
| 6 | Click an action card | **Chain Explorer** opens — full payload, signature, chain visualization |
| 7 | Click **Verify Chain** | "CHAIN INTACT" |
| 8 | Click **Tamper Demo** | Record corrupted, "CHAIN BROKEN" with red alert |
| 9 | Click **Restore Chain** | Back to "CHAIN INTACT" |
| 10 | Open portal, find Sam Altman | Version history shows the medication change with timestamp |
| 11 | Click **Export** | Download full audit log as JSON |

**Demo task:** "Find Sam Altman's record, update his medication from Vitamin C 1000mg daily to Emergen-C 1000mg daily, then search for all patients with seasonal allergies"

## Patient Data

All patients are famous YC founders/partners with lighthearted conditions:

| Patient | Condition | Medications |
|---------|-----------|-------------|
| Sam Altman | Seasonal Allergies | Claritin, Flonase |
| Paul Graham | Mild Eye Strain | Artificial tears, blue-light glasses |
| Jessica Livingston | Common Cold | Vitamin C, Zinc lozenges |
| Garry Tan | Caffeine Withdrawal Headaches | Ibuprofen, caffeine taper |
| Michael Seibel | Runner's Knee | Ibuprofen, PT, knee brace |
| Dalton Caldwell | Mild Tension Headache | Acetaminophen |
| Jared Friedman | Seasonal Allergies, Mild Sunburn | Zyrtec, Aloe vera, SPF 50 |
| Gustaf Alstromer | Tennis Elbow | Naproxen, elbow strap |
| Kevin Hale | Mild Sprained Ankle | RICE protocol, Ibuprofen |
| Adora Cheung | Persistent Hiccups (3 days) | Chlorpromazine, peppermint tea |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent | [Browser Use](https://github.com/browser-use/browser-use) + Claude Sonnet |
| Backend | Python FastAPI |
| Frontend | React (dark-mode dashboard) |
| Crypto | ECDSA P-256 (sign) + SHA-256 (hash chain) |
| Database | SQLite (aiosqlite) |
| Real-time | WebSocket |
| Browser | Playwright (headless Chromium) |

## Why This Matters

Healthcare AI is moving fast. Agents will read, modify, and manage patient records at scale. Without cryptographic auditability:

- **Compliance**: HIPAA requires audit trails. "The AI did it" doesn't cut it.
- **Liability**: When something goes wrong, who proves what the AI actually did?
- **Trust**: Patients and providers need to know AI actions are transparent and verifiable.
- **Tamper-evidence**: If anyone — human or AI — alters the audit log, the chain breaks immediately.

MedLedger makes every AI action provable, tamper-evident, and auditable. It's the infrastructure layer that healthcare AI needs before it can scale.

---

*Built for the Browser Use YC Hackathon (Feb 28 - Mar 1, 2026)*
