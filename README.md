# MedLedger

**Cryptographically audited AI agent layer for patient portals.**

> Every AI action on a medical record — signed, hash-chained, and verifiable. Because "the AI changed it" is not an acceptable audit trail.

---

## The Problem

AI agents are increasingly being used to navigate and modify electronic health records. But today, there's no way to cryptographically prove what an AI agent did, when it did it, or whether the record was tampered with after the fact. In healthcare, this isn't just a compliance gap — it's a patient safety risk.

## What MedLedger Does

MedLedger creates a **tamper-evident, cryptographically signed audit trail** for every action an AI agent takes on a patient portal. Every tool call — search, view, update, delete — is:

1. **Signed** with an ECDSA P-256 private key
2. **Hash-chained** to the previous action (SHA-256), creating a pseudo-blockchain
3. **Streamed** in real-time to a visualization dashboard
4. **Verifiable** — if anyone modifies the audit log, the chain breaks and verification fails

## Two Products, One Platform

**MedLedger Audit Trail** — Works with ANY patient portal. Epic, Cerner, Athena, whatever your hospital uses. The Browser Use agent navigates it, and every action gets signed and chained. Plug it in, get verifiable audit logs. Easy compliance sell.

**MedLedger Portal** — A purpose-built, agent-native EHR designed from the ground up for AI agents. Structured DOM, clean accessibility tree, explicit action hooks. For smaller clinics or hospitals that need the whole stack.

*Land with the audit trail at hospitals that already have portals. Upsell MedLedger Portal to orgs who need everything.*

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React Dashboard (:3000)                     │
│  ┌─────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│  │ Portal  │  │   Audit Feed     │  │  Chain Integrity     │ │
│  │ View    │  │   (live cards)   │  │  ECDSA P-256         │ │
│  │ (iframe)│  │   ↑ WebSocket    │  │  SHA-256 chain       │ │
│  └─────────┘  └──────────────────┘  └──────────────────────┘ │
└──────────────────────┬───────────────────────────────────────┘
                       │ ws://localhost:8000/ws
┌──────────────────────┴───────────────────────────────────────┐
│               MedLedger API (:8000)                           │
│  FastAPI + WebSocket Hub                                      │
│  POST /agent/run  GET /audit/log  GET /audit/verify           │
└──────────┬───────────────────────────────────────────────────┘
           │
┌──────────┴───────────────────────────────────────────────────┐
│           Browser Use Agent (Playwright + Claude)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ search   │  │  view    │  │ update   │  │   delete     │ │
│  │ _patient │  │ _patient │  │ _patient │  │  _patient    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
│       └──────────────┴─────────────┴───────────────┘         │
│                    ↓ sign_action()                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Audit Chain (audit_chain.py)                │ │
│  │  ECDSA P-256 keypair → SHA-256 hash → sign → chain      │ │
│  │  prev_hash: GENESIS → abc123... → def456... → ...       │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
           │ navigates
┌──────────┴───────────────────────────────────────────────────┐
│            MedLedger Portal (:8001)                            │
│  Agent-Native EHR — Server-rendered HTML                      │
│  10 patients │ CRUD │ Version history │ SQLite                │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and run
git clone https://github.com/Hardik-Singh/MedLedger.git
cd MedLedger

# One command to start everything
chmod +x run.sh
./run.sh
```

Or manually:

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Terminal 1: Patient Portal
uvicorn backend.portal:app --port 8001 --reload

# Terminal 2: API + WebSocket Hub
uvicorn backend.main:app --port 8000 --reload

# Terminal 3: React Dashboard
cd frontend && npm install && npm start
```

## Demo Scenario

```bash
# After starting the services, trigger the demo agent task:
curl -X POST http://localhost:8000/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"task": "Find patient John Smith, update his medication from Metformin to Ozempic, then search for any patients with diabetes"}'
```

Watch the dashboard at `http://localhost:3000` as the agent:
1. **Searches** for "John Smith" → signed + chained
2. **Views** his patient record → signed + chained
3. **Updates** his medication from Metformin to Ozempic → signed + chained
4. **Searches** for "diabetes" → signed + chained

Every action appears as a card in the live feed with its hash, previous hash, and signature — all verifiable.

## Verify the Chain

```bash
# Check that no one has tampered with the audit log
curl http://localhost:8000/audit/verify
# → {"intact": true, "total_actions": 5, ...}

# Try tampering: manually edit the SQLite DB, then verify again
# → {"intact": false, "error": "Hash mismatch at action 2: record may have been tampered with"}
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent | [Browser Use](https://github.com/browser-use/browser-use) + Claude Sonnet |
| Backend | Python FastAPI |
| Frontend | React |
| Crypto | ECDSA P-256 (sign) + SHA-256 (hash chain) |
| Database | SQLite (aiosqlite) |
| Real-time | WebSocket |
| Browser | Playwright (headless Chromium) |

## Why This Matters

Healthcare AI is moving fast. Agents will read, modify, and manage patient records at scale. Without cryptographic auditability:

- **Compliance**: HIPAA requires audit trails. "The AI did it" doesn't cut it.
- **Liability**: When something goes wrong, who proves what the AI actually did?
- **Trust**: Patients and providers need to trust that AI actions are transparent and verifiable.

MedLedger makes every AI action provable, tamper-evident, and auditable — the infrastructure layer that healthcare AI needs before it can scale.

---

*Built for the Browser Use YC Hackathon (Feb 28 - Mar 1, 2026)*
