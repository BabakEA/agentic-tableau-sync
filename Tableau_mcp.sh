docker run -d \
  --name tableau-mcp-sse \
  -p 7777:8080 \
  --env-file env.list \
  ghcr.io/tableau/tableau-mcp:latest

