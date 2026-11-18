#!/usr/bin/env bash
# Start TicketPilot: FastAPI API (background) + Streamlit UI.
set -u
cd "$(dirname "$0")/.."

echo "Stopping any existing server on port 8000..."
pkill -f uvicorn || true

echo "Starting FastAPI API in the background (http://127.0.0.1:8000)..."
nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    > /tmp/ticketpilot-api.log 2>&1 &
sleep 4
curl -s http://127.0.0.1:8000/health && echo " <- API up"

echo "Starting Streamlit UI (http://127.0.0.1:8501)..."
echo "Press Ctrl+C to stop the UI. API log: /tmp/ticketpilot-api.log"
python3 -m streamlit run ui/app.py --server.port 8501 \
    --server.headless true
