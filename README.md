# Tableau Agent Workspace

This workspace runs a local Tableau automation stack with three layers:

1. Tableau MCP server in Docker on port `7777`
2. FastAPI backend on port `7778`
3. Streamlit chat UI on port `7779`

The backend can:

1. List Tableau dashboards, views, and datasources
2. Generate stock market analytics from Yahoo Finance
3. Publish a stock datasource to Tableau
4. Clone a workbook into Tableau for a visible dashboard object
5. Generate Markdown and PowerPoint reports from a workbook or a single view
6. Run a chat-style orchestration flow through `/agent/chat`

## Workspace Files

Core files:

1. [agent_api.py](f:/tableau/agent_api.py): FastAPI backend and agent orchestration
2. [streamlit_app.py](f:/tableau/streamlit_app.py): Chat UI
3. [api_start.sh](f:/tableau/api_start.sh): Starts Docker, API, and UI
4. [docker-compose.yaml](f:/tableau/docker-compose.yaml): Tableau MCP container
5. [env.list](f:/tableau/env.list): Tableau server, site, and PAT settings
6. [config/config.json](f:/tableau/config/config.json): Litellm endpoint and model config

Supporting scripts:

1. [mcp_start.sh](f:/tableau/mcp_start.sh): Starts Tableau MCP container only
2. [mcp_down.sh](f:/tableau/mcp_down.sh): Stops Tableau MCP container only
3. [stock_tableau_agent.py](f:/tableau/stock_tableau_agent.py): Standalone stock agent script
4. [tableau_dashboard_briefing_agent.py](f:/tableau/tableau_dashboard_briefing_agent.py): Standalone dashboard briefing script

Local-only files that are intentionally ignored:

1. [env.list](f:/tableau/env.list): Real Tableau PAT and server values for this machine
2. [config/config.json](f:/tableau/config/config.json): Real Litellm endpoint and API key for this machine

Sanitized example files committed to the repo:

1. [env.example](f:/tableau/env.example)
2. [config/config.example.json](f:/tableau/config/config.example.json)

Reference docs:

1. [TABLEAU_MCP_GUIDE.md](f:/tableau/TABLEAU_MCP_GUIDE.md)

## Prerequisites

1. Docker Desktop running
2. Conda environment named `MCP`
3. Tableau PAT configured in [env.list](f:/tableau/env.list)
4. Litellm endpoint configured in [config/config.json](f:/tableau/config/config.json)

If you are cloning this repository onto a new machine:

1. Copy [env.example](f:/tableau/env.example) to `env.list`
2. Copy [config/config.example.json](f:/tableau/config/config.example.json) to `config/config.json`
3. Fill in the real Tableau PAT and Litellm values locally

## Tableau MCP Client Setup

For the full Tableau-side setup, PAT generation steps, and client connection examples for GitHub Copilot and Claude Code, see [TABLEAU_MCP_GUIDE.md](f:/tableau/TABLEAU_MCP_GUIDE.md).

That guide covers:

1. Enabling Personal Access Tokens in Tableau Cloud
2. Creating the PAT for `ai_forest`
3. Connecting Tableau MCP over `stdio`
4. Connecting Tableau MCP over Docker/HTTP
5. Wiring the MCP server into VS Code GitHub Copilot
6. Reusing the same connection details in Claude Code or another MCP client

For this repository specifically, the working default connection is:

1. Tableau MCP endpoint: `http://localhost:7777/tableau-mcp`
2. VS Code MCP config file: [f:/tableau/.vscode/mcp.json](f:/tableau/.vscode/mcp.json)
3. Tableau server settings source: [env.list](f:/tableau/env.list)

Install Python dependencies inside the `MCP` environment:

```bash
conda activate MCP
python -m pip install -r requirements.txt
```

## Start Everything

Run:

```bash
bash api_start.sh
```

What it does:

1. Starts the Tableau MCP Docker service on `7777`
2. Starts the FastAPI backend on `7778`
3. Starts the Streamlit UI on `7779`

Open:

1. API health: `http://localhost:7778/health`
2. Streamlit UI: `http://localhost:7779`

## Main API Endpoints

Catalog endpoints:

1. `GET /health`
2. `GET /meta/options`
3. `GET /dashboards`
4. `GET /views`
5. `GET /datasources`

Generation endpoints:

1. `POST /dashboards/stock-market`
2. `POST /dashboards/briefing`
3. `POST /views/briefing-comprehensive`
4. `POST /agent/chat`

## Chat UI Usage

The Streamlit UI sends natural-language prompts to `/agent/chat`.

Example prompts:

1. `show me your dashboards and views`
2. `show me your datasources`
3. `summarize workbook sample and generate a ppt`
4. `create a report for view Executive Summary`
5. `generate stock dashboard for AAPL over 3 months hourly and publish it`

The UI returns downloadable artifacts when available, such as:

1. `.pptx`
2. `.md`
3. `.csv`
4. `.png`
5. `.txt`

## Stock Dashboard Flow

`POST /dashboards/stock-market` does the following:

1. Parses requested tickers and always adds an S&P 500 baseline
2. Pulls Yahoo Finance time-series data
3. Calculates moving average and hourly buy/sell style summaries
4. Generates charts and CSVs
5. Publishes a Tableau datasource
6. Optionally clones or publishes a workbook so a visible Tableau dashboard exists

Important publish behavior:

1. Datasource-only publish will not appear in Tableau views or Home
2. A workbook must also be published or cloned for a visible dashboard object
3. If `workbook_template_path` is invalid, the backend can fall back to `source_workbook_id`

## Reporting Flow

Workbook-level reporting:

1. Uses Tableau MCP to pull every view in the workbook
2. Gets view images and view data
3. Uses the Litellm-configured model to analyze visuals and data
4. Builds Markdown and PowerPoint outputs

View-level reporting:

1. Pulls one Tableau view image and its data
2. Generates extra charts from extracted data
3. Uses the model to produce analytic notes and kid-friendly explanation
4. Saves a comprehensive PPT and Markdown file

## Output Files

Generated artifacts are usually written under:

1. `outputs/stock_market_api/...`
2. `outputs/dashboard_briefing_api/...`
3. `outputs/view_briefing_api/...`

## Troubleshooting

If the UI does not open:

1. Confirm the backend is healthy at `http://localhost:7778/health`
2. Re-run `bash api_start.sh`
3. Make sure Docker Desktop is running
4. Make sure the `MCP` conda env exists at `E:\Program Files\anaconda3\envs\MCP`

If a stock dashboard does not appear in Tableau views:

1. Check whether only the datasource was published
2. Look at `dashboard.publish_status` in the API response
3. If needed, provide a valid `source_workbook_id` or workbook template path

If report generation succeeds but the content is weak:

1. Confirm [config/config.json](f:/tableau/config/config.json) points to the correct Litellm model
2. Use workbook-level reporting for richer PPTs
