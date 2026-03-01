# ============================================================
# MedLedger — Full Build Prompt
# Browser Use YC Hackathon (Feb 28 - Mar 1, 2026)
# ============================================================
#
# WHAT IS MEDLEDGER?
# MedLedger is a cryptographically audited AI agent layer for
# patient portals. It has TWO products:
#
#   1. MedLedger Audit Trail — works with ANY patient portal.
#      Epic, Cerner, Athena, whatever. A Browser Use agent
#      navigates it, every action gets ECDSA-signed and
#      hash-chained into a pseudo-blockchain. Plug it into
#      any existing hospital system and get verifiable,
#      tamper-evident audit logs. This is the wedge — easy
#      compliance sell to hospitals that already have portals.
#
#   2. MedLedger Portal — our own purpose-built, agent-native
#      EHR. Structured DOM, clean accessibility tree, explicit
#      action hooks. Designed from day one for both AI agents
#      AND human users (doctors, nurses). This is the
#      "batteries included" offering for smaller clinics.
#      The portal is part of our product. It's not a mock —
#      it's a real, rich patient portal optimized for browser-use.
#
# PITCH: "Bring your own portal, we audit it. Or use ours,
#         which is built for agents from day one."
#
# ============================================================
# PATIENT DATA
# ============================================================
#
# Use famous YC founders, partners, and well-known startup
# people as patient names. Make it fun and recognizable.
# Example: Sam Altman, Paul Graham, Jessica Livingston,
# Garry Tan, Michael Seibel, etc.
#
# CONDITIONS MUST BE LIGHTHEARTED ONLY:
#   - Common cold, seasonal allergies, mild headache
#   - Sprained ankle, paper cut, hiccups
#   - Mild sunburn, caffeine withdrawal, eye strain
#   - Tennis elbow, runner's knee, "too many meetings" fatigue
#   - Nothing serious, nothing offensive, nothing embarrassing
#
# Medications should match — ibuprofen, Claritin, eye drops,
# vitamin C, etc. Keep it fun and demo-friendly.
#
# ============================================================
# DASHBOARD — TWO VIEWS
# ============================================================
#
# The dashboard must have TWO distinct views that you can
# toggle between:
#
# 1. AUDITOR VIEW (default)
#    - For compliance officers, security teams, regulators
#    - Shows the full crypto chain: hashes, signatures, prev_hash
#    - Chain integrity verification (CHAIN INTACT / CHAIN BROKEN)
#    - Tamper detection alerts
#    - Every action with cryptographic proof
#    - Think: terminal aesthetic, monospace hashes, dark mode
#
# 2. CLINICAL VIEW
#    - For doctors and nurses
#    - Shows what the AI agent DID in plain English
#    - "Agent searched for Sam Altman"
#    - "Agent updated Paul Graham's medication from Tylenol to Advil"
#    - Timeline view, friendly colors, medical UI aesthetic
#    - Patient impact summary
#    - No raw hashes — just clear, human-readable action log
#    - Shows which patients were affected and what changed
#
# Both views pull from the same audit log. The toggle should
# be prominent — a big button or tab at the top of the feed.
#
# ============================================================
# CUSTOM AGENT NAMES + VISUALIZATION
# ============================================================
#
# - Let users set a custom agent name before running a task
#   (e.g., "Dr. Bot", "Nurse AI", "Compliance Checker")
# - The agent name shows up in every audit log entry
# - The agent name appears in the dashboard header
# - Show agent avatar/icon in the action feed
# - End-of-task summary card showing:
#   - Total actions taken
#   - Patients viewed/modified
#   - Time elapsed
#   - Chain integrity status
#   - A "result" section with what the agent accomplished
#
# ============================================================
# API KEY SETUP — EASY DEMO
# ============================================================
#
# The user should ONLY need to set their ANTHROPIC_API_KEY
# environment variable and then run the project. That's it.
#
#   export ANTHROPIC_API_KEY=sk-ant-...
#   ./run.sh
#
# The run.sh script should check for the key and give a
# clear error message if it's missing. The dashboard should
# also show the API key status (connected/not connected)
# without revealing the actual key.
#
# Alternatively, allow setting the key in the dashboard UI
# via an input field (stored in memory only, never persisted).
#
# ============================================================
# COOL NEW FEATURES
# ============================================================
#
# 1. CHAIN EXPLORER — click any action card to see:
#    - Full payload JSON
#    - Complete hash (not truncated)
#    - Full signature (hex)
#    - Visual chain link to previous and next actions
#    - One-click "verify this action" button
#
# 2. TAMPER SIMULATION — a button that intentionally corrupts
#    one record in the audit log, then shows the chain breaking
#    in real-time. Perfect for demo. "Watch what happens when
#    someone tries to alter the record." Then a "restore" button.
#
# 3. RISK SCORING — each action gets a risk badge:
#    - LOW (search, view) — green
#    - MEDIUM (update) — yellow
#    - HIGH (delete) — red
#    - Show aggregate risk score for the entire session
#
# 4. EXPORT — button to download:
#    - Full audit log as JSON
#    - Verification report as PDF-ready format
#    - Chain visualization as image
#
# 5. AGENT TASK TEMPLATES — pre-built task buttons:
#    - "Patient Lookup" — searches and views a patient
#    - "Medication Update" — finds patient and changes meds
#    - "Full Audit" — searches, views, updates, verifies
#    - "Compliance Check" — views all patients, generates report
#    - Custom free-text input still available
#
# 6. LIVE AGENT BROWSER VIEW — show what the browser-use agent
#    is actually seeing/doing. Either via:
#    - Periodic screenshots streamed to dashboard
#    - Or the portal iframe auto-refreshing
#    - The user should be able to WATCH the agent navigate
#
# ============================================================
# DEMO SCRIPT
# ============================================================
#
# Here's the exact demo flow for recording:
#
# 1. Show the empty dashboard — "No actions yet"
# 2. Click "Load Demo" or type a task:
#    "Find Sam Altman's record, update his medication from
#     Vitamin C to Emergen-C, then search for all patients
#     with seasonal allergies"
# 3. Watch actions stream in real-time — each one signed
# 4. Switch to Clinical View — show the plain English summary
# 5. Switch back to Auditor View — show the crypto chain
# 6. Click "Verify Chain" — show CHAIN INTACT
# 7. Click "Tamper Simulation" — corrupt a record
# 8. Click "Verify Chain" again — show CHAIN BROKEN with
#    exactly which record was tampered
# 9. Click "Restore" — chain intact again
# 10. Show the patient portal — navigate to Sam Altman's
#     record, show the version history with the medication change
# 11. Export the audit log
#
# This should take about 3-4 minutes to demo.
#
# ============================================================
# IMPORTANT NOTES
# ============================================================
#
# - MedLedger Portal is NOT a mock. It's a real product.
#   Brand it: "MedLedger Portal — Agent-Native EHR"
#   with a banner emphasizing it's designed for AI agents.
#
# - The audit trail works with ANY portal. The portal iframe
#   in the dashboard should have a URL input — you could
#   point it at any website and the agent would still
#   sign every action. MedLedger Portal is just the best
#   experience because it's built for it.
#
# - Every single agent action — including read-only ones —
#   MUST be signed. Viewing a record is still an auditable
#   event in healthcare (HIPAA access logs).
#
# - The dashboard should feel like it could be a real
#   product. Hackathon judges should think "I'd use this."
#
# - Use claude-sonnet-4-20250514 as the agent LLM.
#
# ============================================================
