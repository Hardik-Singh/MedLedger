#!/usr/bin/env bash
set -e

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   MedLedger — Cryptographic Audit Trail      ║"
echo "  ║   Browser Use YC Hackathon (Feb 28-Mar 1)    ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ── Check for API key ──
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "  [!] ANTHROPIC_API_KEY not set."
  echo "      You can still start the dashboard and set it in the UI."
  echo "      Or: export ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
else
  echo "  [OK] ANTHROPIC_API_KEY detected (${ANTHROPIC_API_KEY:0:12}...)"
  echo ""
fi

# ── Install Python dependencies ──
echo "  [1/5] Installing Python dependencies..."
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

# ── Install Playwright browser ──
echo "  [2/5] Installing Playwright Chromium..."
playwright install chromium 2>/dev/null || python -m playwright install chromium 2>/dev/null || echo "  (Playwright install skipped — optional for agent)"

# ── Build React frontend ──
echo "  [3/5] Building React dashboard..."
cd frontend
npm install --silent 2>/dev/null || npm install
npm run build 2>/dev/null || echo "  (frontend build skipped — use npm start for dev mode on :3000)"
cd ..

# ── Start services ──
echo "  [4/5] Starting MedLedger Portal (port 8001)..."
python -m uvicorn backend.portal:app --host 0.0.0.0 --port 8001 --reload &
PORTAL_PID=$!
sleep 1

echo "  [5/5] Starting MedLedger API + Dashboard (port 8000)..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   MedLedger is running!                      ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║                                              ║"
echo "  ║   Dashboard:  http://localhost:3000           ║"
echo "  ║   Portal:     http://localhost:8001           ║"
echo "  ║               Login: demo / demo123           ║"
echo "  ║   API:        http://localhost:8000           ║"
echo "  ║   WebSocket:  ws://localhost:8000/ws          ║"
echo "  ║                                              ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║   Quick Demo:                                ║"
echo "  ║   1. Open Dashboard at localhost:3000         ║"
echo "  ║   2. Set API key (if not in env)              ║"
echo "  ║   3. Pick a template (e.g. 'Lookup')         ║"
echo "  ║   4. Hit 'Run' and watch the audit trail!    ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  Press Ctrl+C to stop all services"

# For dev mode, also start React dev server
if [ ! -d "frontend/build" ]; then
  echo ""
  echo "  Starting React dev server on port 3000..."
  cd frontend && PORT=3000 npm start &
  REACT_PID=$!
  cd ..
  trap "kill $PORTAL_PID $API_PID $REACT_PID 2>/dev/null; exit" INT TERM
else
  trap "kill $PORTAL_PID $API_PID 2>/dev/null; exit" INT TERM
fi

wait
