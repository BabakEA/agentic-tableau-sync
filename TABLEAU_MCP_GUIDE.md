# Tableau MCP Setup Guide

This guide covers the Tableau-specific setup needed before this workspace can connect to Tableau through MCP. It includes:

1. Creating a Tableau Personal Access Token (PAT)
2. Configuring Tableau MCP over `stdio`
3. Configuring Tableau MCP over Docker/HTTP
4. Connecting GitHub Copilot in VS Code
5. Connecting Claude Code or another MCP-capable client

This workspace currently uses the Docker/HTTP pattern by default.

## 1. Enable Personal Access Tokens in Tableau Cloud

If PATs are disabled at the site level, no user token will work.

For this site, go to:

`https://10ax.online.tableau.com/#/site/ai_forest/home`

Then:

1. Open **Settings** from the left navigation.
2. In the **General** settings area, find **Personal Access Tokens**.
3. Enable PAT usage for the site.
4. Save the change.

## 2. Create the Tableau PAT

Create the token from the same Tableau site where the MCP server will connect.

1. Go to `https://10ax.online.tableau.com/#/site/ai_forest/home`
2. Open your profile menu in the upper-right corner.
3. Open **My Account Settings**.
4. Find the **Personal Access Tokens** section.
5. Create a token with a clear name, for example `ai_forest_agent`.
6. Copy the token secret immediately.

Important:

1. The token secret is shown once.
2. Do not wrap `PAT_NAME` or `PAT_VALUE` in quotes when you place them in `env.list`.
3. Tokens are site-specific. Use the token created inside `ai_forest` for this site.

## 3. Required Tableau Values

For this workspace, the important Tableau values are:

1. `SERVER=https://10ax.online.tableau.com`
2. `SITE_NAME=ai_forest`
3. `PAT_NAME=your_token_name`
4. `PAT_VALUE=your_token_secret`

The repository already expects these values in [env.list](f:/tableau/env.list).

## 4. Option A: MCP Over `stdio`

This runs the Tableau MCP server as a local child process.

Example configuration for a client that supports an `mcpServers` block:

```json
{
  "mcpServers": {
    "tableau-native-stdio": {
      "command": "npx",
      "args": ["-y", "@tableau/mcp-server@latest"],
      "env": {
        "TRANSPORT": "stdio",
        "SERVER": "https://10ax.online.tableau.com",
        "SITE_NAME": "ai_forest",
        "PAT_NAME": "ai_forest_agent",
        "PAT_VALUE": "YOUR_SECRET_UNQUOTED_TOKEN_VALUE",
        "DANGEROUSLY_DISABLE_OAUTH": "true"
      }
    }
  }
}
```

Use `stdio` when:

1. You want the simplest local connection
2. You do not need the server exposed over a local HTTP port

## 5. Option B: MCP Over Docker/HTTP

This is the mode used by this repository.

The Docker container runs Tableau MCP on port `7777` and exposes the main endpoint at:

`http://localhost:7777/tableau-mcp`

### Docker Compose

The repository already includes [docker-compose.yaml](f:/tableau/docker-compose.yaml) and [env.list](f:/tableau/env.list).

The effective configuration is:

```yaml
version: '3.8'

services:
  tableau-mcp:
    image: ghcr.io/tableau/tableau-mcp:latest
    container_name: tableau-mcp-sse
    ports:
      - "7777:8080"
    env_file:
      - env.list
    restart: always
```

Example `env.list` shape:

```text
TRANSPORT=http
PORT=8080
SERVER=https://10ax.online.tableau.com
SITE_NAME=ai_forest
PAT_NAME=ai_forest_agent
PAT_VALUE=YOUR_SECRET_UNQUOTED_TOKEN_VALUE
DANGEROUSLY_DISABLE_OAUTH=true
```

Start the MCP container with:

```bash
bash mcp_start.sh
```

Stop it with:

```bash
bash mcp_down.sh
```

## 6. Connect GitHub Copilot in VS Code

This repository already uses [f:/tableau/.vscode/mcp.json](f:/tableau/.vscode/mcp.json).

The current working HTTP setup is:

```json
{
  "servers": {
    "tableau-agent-tools": {
      "url": "http://localhost:7777/tableau-mcp"
    }
  }
}
```

Notes:

1. Some MCP clients use a top-level `servers` key.
2. Some use `mcpServers` instead.
3. The transport values stay the same; only the wrapper schema changes by client.
4. Do not point the client at `/sse`. For this workspace, use `/tableau-mcp`.

In VS Code:

1. Save the MCP config.
2. Open GitHub Copilot Chat.
3. Switch to **Agent** mode if needed.
4. Open the tools/plugins picker.
5. Enable the Tableau MCP server.

Test prompt:

```text
Use my connected Tableau tool to list all the views available in the ai_forest site.
```

## 7. Connect Claude Code or Another MCP Client

The same Tableau settings work in any MCP-capable client.

Use one of these two transport patterns:

1. `stdio` with `npx -y @tableau/mcp-server@latest`
2. HTTP with `http://localhost:7777/tableau-mcp`

If the client expects an `mcpServers`-style config, the HTTP version looks like this:

```json
{
  "mcpServers": {
    "tableau": {
      "url": "http://localhost:7777/tableau-mcp"
    }
  }
}
```

If it expects a command-based config, use the `stdio` example from Section 4.

## 8. Repository Runtime Flow

This workspace provides a single launcher:

```bash
bash api_start.sh
```

That script:

1. Starts the Tableau MCP Docker service
2. Starts the FastAPI backend on `7778`
3. Starts the Streamlit chat UI on `7779`

After startup:

1. MCP server: `http://localhost:7777/tableau-mcp`
2. Backend API: `http://localhost:7778`
3. Streamlit UI: `http://localhost:7779`

## 9. Verification Checklist

Use this sequence when troubleshooting connection issues:

1. Confirm Docker is running.
2. Confirm the MCP container is up.
3. Confirm Tableau PAT values in [env.list](f:/tableau/env.list) are correct.
4. Confirm the MCP endpoint responds at `http://localhost:7777/tableau-mcp`.
5. Confirm the backend responds at `http://localhost:7778/health`.
6. Confirm the Streamlit UI responds at `http://localhost:7779`.

## 10. Common Problems

### Invalid or missing session ID

Cause:

1. The client called MCP methods before completing `initialize`
2. The MCP server could not create a session because Tableau auth failed

Fix:

1. Confirm PAT credentials are valid
2. Confirm the site name is correct
3. Reconnect through the client so it performs a fresh handshake

### Tableau auth fails but Docker is running

Cause:

1. Wrong or expired PAT
2. Wrong `SITE_NAME`
3. Token created in the wrong site

Fix:

1. Create a new PAT in `ai_forest`
2. Update [env.list](f:/tableau/env.list)
3. Restart the MCP container

### MCP client shows no Tableau tools

Cause:

1. The client is pointed at the wrong URL
2. The client is using `/sse` instead of `/tableau-mcp`

Fix:

1. Use `http://localhost:7777/tableau-mcp`

## 11. Recommended Entry Points

If you are using this repository end-to-end:

1. Read [README.md](f:/tableau/README.md) for the workspace overview and runtime flow
2. Use this guide for PAT creation and MCP client connection details
3. Start everything with [api_start.sh](f:/tableau/api_start.sh)
