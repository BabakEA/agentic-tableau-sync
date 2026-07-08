#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

mkdir -p logs

MCP_PYTHON="/e/Program Files/anaconda3/envs/MCP/python.exe"
if [[ ! -x "$MCP_PYTHON" ]]; then
	echo "MCP python not found at $MCP_PYTHON"
	exit 1
fi

echo "Starting Tableau MCP Docker service..."
bash mcp_start.sh

if curl -sf http://localhost:7778/health >/dev/null 2>&1; then
	echo "FastAPI backend is already running on port 7778."
else
	echo "Starting FastAPI backend on port 7778..."
	"$MCP_PYTHON" -m uvicorn agent_api:app --host 0.0.0.0 --port 7778 > logs/agent_api.log 2>&1 &
	echo $! > logs/agent_api.pid
fi

echo "Starting Streamlit chat UI on port 7779..."
exec "$MCP_PYTHON" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 7779 --server.headless true
