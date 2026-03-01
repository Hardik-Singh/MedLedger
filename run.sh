#!/usr/bin/env bash
set -e

echo "============================================"
echo "  MedLedger — Cryptographic Audit Trail"
echo "  Browser Use YC Hackathon (Feb 28-Mar 1)"
echo "============================================"
echo ""

# ── Install Python dependencies ──
echo "[1/5] Installing Python dependencies..."
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

# ── Install Playwright browser ──
echo "[2/5] Installing Playwright Chromium..."
playwright install chromium 2>/dev/null || python -m playwright install chromium

# ── Build React frontend ──
echo "[3/5] Building React dashboard..."
cd frontend
npm install --silent 2>/dev/null || npm install
npm run build 2>/dev/null || echo "  (frontend build skipped — dev mode available on port 3000)"
cd ..

# ── Start services ──
echo "[4/5] Starting MedLedger Portal (port 8001)..."
python -m uvicorn backend.portal:app --host 0.0.0.0 --port 8001 --reload &
PORTAL_PID=$!
sleep 1

echo "[5/5] Starting MedLedger API + Dashboard (port 8000)..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

echo ""
echo "============================================"
echo "  MedLedger is running!"
echo ""
echo "  Portal:    http://localhost:8001"
echo "             Login: demo / demo123"
echo ""
echo "  Dashboard: http://localhost:8000"
echo "  API:       http://localhost:8000/audit/log"
echo "  WebSocket: ws://localhost:8000/ws"
echo ""
echo "  Demo task:"
echo "  curl -X POST http://localhost:8000/agent/run \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"task\": \"Find patient John Smith, update his medication from Metformin to Ozempic, then search for any patients with diabetes\"}'"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "============================================"

# Wait for background processes
trap "kill $PORTAL_PID $API_PID 2>/dev/null; exit" INT TERM
wait
