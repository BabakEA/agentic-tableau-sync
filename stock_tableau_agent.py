import argparse
import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import yfinance as yf


@dataclass
class AgentConfig:
    litellm_complete_url: str
    litellm_model: str
    litellm_api_key: str
    litellm_max_seconds: int


class MCPError(RuntimeError):
    pass


class TableauMCPClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session_id: Optional[str] = None
        self._request_id = 1

    def _next_id(self) -> int:
        current = self._request_id
        self._request_id += 1
        return current

    def initialize(self) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "stock-tableau-agent", "version": "1.0.0"},
            },
        }
        data, headers = self._post(payload, use_session=False)
        self.session_id = headers.get("mcp-session-id")
        if not self.session_id:
            raise MCPError("MCP initialize did not return mcp-session-id")
        return data

    def list_tools(self) -> List[Dict[str, Any]]:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}}
        data, _ = self._post(payload, use_session=True)
        tools = data.get("result", {}).get("tools", [])
        if not isinstance(tools, list):
            raise MCPError("Unexpected tools/list response format")
        return tools

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        }
        data, _ = self._post(payload, use_session=True)
        return data

    def _post(self, payload: Dict[str, Any], use_session: bool) -> Tuple[Dict[str, Any], Dict[str, str]]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if use_session:
            if not self.session_id:
                raise MCPError("Session ID not set. Call initialize first.")
            headers["mcp-session-id"] = self.session_id

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise MCPError(f"MCP HTTP {response.status_code}: {response.text[:500]}")

        data = self._parse_response(response.text, expected_id=payload["id"])
        if "error" in data:
            raise MCPError(f"MCP RPC error: {data['error']}")

        return data, {k.lower(): v for k, v in response.headers.items()}

    @staticmethod
    def _parse_response(text: str, expected_id: int) -> Dict[str, Any]:
        stripped = text.strip()
        if not stripped:
            raise MCPError("Empty MCP response body")

        # Streamable HTTP commonly returns SSE blocks like: event: message / data: {...}
        if stripped.startswith("event:") or "\ndata:" in stripped:
            events: List[Dict[str, Any]] = []
            for line in stripped.splitlines():
                if line.startswith("data:"):
                    payload = line[len("data:") :].strip()
                    if payload:
                        try:
                            events.append(json.loads(payload))
                        except json.JSONDecodeError:
                            continue

            for event in events:
                if event.get("id") == expected_id:
                    return event

            raise MCPError("No JSON-RPC response matching request id found in SSE stream")

        return json.loads(stripped)


class LiteLLMClient:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def summarize(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.config.litellm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.litellm_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a quantitative market analyst. Provide concise actionable insight.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(
            self.config.litellm_complete_url,
            headers=headers,
            json=payload,
            timeout=self.config.litellm_max_seconds,
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"].strip()


def load_agent_config(config_path: Path) -> AgentConfig:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return AgentConfig(
        litellm_complete_url=data["LITELLM_COMPLETE_URL"],
        litellm_model=data["LITELLM_MODEL"],
        litellm_api_key=data["LITELLM_API_KEY"],
        litellm_max_seconds=int(data.get("LITELLM_MAX_SECONDS", 120)),
    )


def fetch_sp500_tickers(limit: int = 30) -> List[str]:
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    tickers = table["Symbol"].astype(str).tolist()
    # Yahoo uses '-' instead of '.' in symbol names like BRK.B
    tickers = [t.replace(".", "-") for t in tickers]
    return tickers[:limit]


def fetch_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    history = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if history.empty:
        raise ValueError(f"No price history returned for {ticker}")
    history = history.reset_index().rename(columns={"Date": "timestamp"})
    if "timestamp" not in history.columns:
        # For intraday intervals, yfinance may return Datetime index name variation.
        idx_name = history.columns[0]
        history = history.rename(columns={idx_name: "timestamp"})
    history["ticker"] = ticker
    return history


def fetch_options_snapshot(ticker: str) -> pd.DataFrame:
    yf_ticker = yf.Ticker(ticker)
    expirations = yf_ticker.options
    if not expirations:
        return pd.DataFrame(
            [{"ticker": ticker, "expiration": None, "avg_call_iv": np.nan, "avg_put_iv": np.nan, "calls": 0, "puts": 0}]
        )

    nearest = expirations[0]
    chain = yf_ticker.option_chain(nearest)
    calls = chain.calls if chain.calls is not None else pd.DataFrame()
    puts = chain.puts if chain.puts is not None else pd.DataFrame()

    call_iv = float(calls["impliedVolatility"].dropna().mean()) if not calls.empty else np.nan
    put_iv = float(puts["impliedVolatility"].dropna().mean()) if not puts.empty else np.nan

    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "expiration": nearest,
                "avg_call_iv": call_iv,
                "avg_put_iv": put_iv,
                "calls": int(len(calls)),
                "puts": int(len(puts)),
            }
        ]
    )


def compute_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for ticker, frame in prices.groupby("ticker"):
        frame = frame.sort_values("timestamp").copy()
        frame["daily_return"] = frame["Close"].pct_change()
        mean_ret = float(frame["daily_return"].mean(skipna=True))
        vol = float(frame["daily_return"].std(skipna=True))
        close_last = float(frame["Close"].iloc[-1])
        close_first = float(frame["Close"].iloc[0])
        perf = (close_last / close_first - 1.0) if close_first else np.nan
        rows.append(
            {
                "ticker": ticker,
                "period_return": perf,
                "avg_daily_return": mean_ret,
                "daily_volatility": vol,
                "last_close": close_last,
            }
        )
    return pd.DataFrame(rows).sort_values("period_return", ascending=False)


def build_charts(prices: pd.DataFrame, metrics: pd.DataFrame, output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: List[Path] = []

    # Chart 1: normalized price trend
    plt.figure(figsize=(12, 6))
    for ticker, frame in prices.groupby("ticker"):
        frame = frame.sort_values("timestamp")
        norm = frame["Close"] / frame["Close"].iloc[0]
        plt.plot(frame["timestamp"], norm, label=ticker)
    plt.title("Normalized Price Performance")
    plt.xlabel("Date")
    plt.ylabel("Normalized Price")
    plt.legend()
    plt.tight_layout()
    p1 = output_dir / "normalized_performance.png"
    plt.savefig(p1)
    plt.close()
    chart_paths.append(p1)

    # Chart 2: return vs volatility scatter
    plt.figure(figsize=(10, 6))
    plt.scatter(metrics["daily_volatility"], metrics["period_return"]) 
    for _, row in metrics.iterrows():
        plt.annotate(row["ticker"], (row["daily_volatility"], row["period_return"]))
    plt.title("Return vs Volatility")
    plt.xlabel("Daily Volatility")
    plt.ylabel("Period Return")
    plt.tight_layout()
    p2 = output_dir / "return_vs_volatility.png"
    plt.savefig(p2)
    plt.close()
    chart_paths.append(p2)

    return chart_paths


def check_or_prepare_dashboard(client: TableauMCPClient, dashboard_name: str, output_dir: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "dashboard_name": dashboard_name,
        "exists": False,
        "creation_supported": False,
        "note": "",
    }

    tools = client.list_tools()
    tool_names = {t.get("name") for t in tools if isinstance(t, dict)}

    # We can discover whether a dashboard already exists by querying content.
    for candidate in ["search-content", "list-views", "list-workbooks"]:
        if candidate in tool_names:
            try:
                payload = {"query": dashboard_name} if candidate == "search-content" else {}
                search_resp = client.call_tool(candidate, payload)
                content_str = json.dumps(search_resp).lower()
                if dashboard_name.lower() in content_str:
                    result["exists"] = True
                    result["note"] = f"Dashboard appears in {candidate} response."
                    return result
            except Exception:
                # Continue trying other discovery tools.
                pass

    # Tableau MCP tool set exposed here is read-heavy; dashboard creation might not be available.
    create_tool = next((name for name in tool_names if "create" in str(name).lower()), None)
    if create_tool:
        result["creation_supported"] = True
        result["note"] = f"A create-capable tool exists ({create_tool}). You can extend this script to call it."
        return result

    spec = {
        "dashboardName": dashboard_name,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "not-found",
        "action": "create_dashboard_manually_or_with_additional_write_tool",
        "recommendedSheets": [
            "Normalized Price Performance",
            "Return vs Volatility",
            "Option IV Snapshot",
        ],
    }
    spec_path = output_dir / "tableau_dashboard_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    result["note"] = (
        "Dashboard was not found. A creation spec was written, but the current MCP tool list does not expose a clear write/create dashboard tool."
    )
    return result


def run_agent(config_path: Path, mcp_url: str, dashboard_name: str, tickers: List[str], include_sp500: bool) -> None:
    out_dir = Path("outputs") / "stock_market"
    run_dir = out_dir / dt.datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    config = load_agent_config(config_path)
    llm = LiteLLMClient(config)

    client = TableauMCPClient(mcp_url)
    init_data = client.initialize()
    tools = client.list_tools()
    tool_names = sorted([t.get("name", "") for t in tools if isinstance(t, dict)])

    working_tickers = [t.upper() for t in tickers]
    if include_sp500:
        # Add a small S&P sample for analysis breadth.
        working_tickers.extend([t for t in fetch_sp500_tickers(limit=10) if t not in working_tickers])

    price_frames: List[pd.DataFrame] = []
    options_frames: List[pd.DataFrame] = []
    for ticker in working_tickers:
        try:
            price_frames.append(fetch_price_history(ticker))
            options_frames.append(fetch_options_snapshot(ticker))
        except Exception as exc:
            print(f"WARN: skipping {ticker}: {exc}")

    if not price_frames:
        raise RuntimeError("No market data could be fetched from Yahoo Finance.")

    prices = pd.concat(price_frames, ignore_index=True)
    options = pd.concat(options_frames, ignore_index=True) if options_frames else pd.DataFrame()
    metrics = compute_metrics(prices)
    chart_paths = build_charts(prices, metrics, run_dir)

    prices_path = run_dir / "stock_prices.csv"
    metrics_path = run_dir / "stock_metrics.csv"
    options_path = run_dir / "options_snapshot.csv"
    prices.to_csv(prices_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    if not options.empty:
        options.to_csv(options_path, index=False)

    dashboard_state = check_or_prepare_dashboard(client, dashboard_name, run_dir)

    prompt = (
        "You are preparing a market briefing for a Tableau dashboard.\n"
        f"Dashboard target: {dashboard_name}.\n"
        f"Available Tableau MCP tools: {tool_names}.\n"
        "Give a concise 8-12 bullet analysis across trend, volatility, and options sentiment.\n"
        f"Metrics table:\n{metrics.to_markdown(index=False)}\n"
        f"Options table:\n{options.to_markdown(index=False) if not options.empty else 'No options data'}\n"
    )

    try:
        llm_summary = llm.summarize(prompt)
    except Exception as exc:
        llm_summary = f"LLM summary unavailable: {exc}"

    report = {
        "initialized": init_data,
        "mcp_session_id": client.session_id,
        "mcp_tools": tool_names,
        "dashboard": dashboard_state,
        "artifacts": {
            "prices_csv": str(prices_path),
            "metrics_csv": str(metrics_path),
            "options_csv": str(options_path) if options_path.exists() else None,
            "charts": [str(p) for p in chart_paths],
        },
        "llm_summary": llm_summary,
    }

    report_path = run_dir / "agent_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Agent run complete.")
    print(f"Session ID: {client.session_id}")
    print(f"Dashboard check: {dashboard_state}")
    print(f"Artifacts written to: {run_dir}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock + Tableau MCP agent")
    parser.add_argument("--config", default="config/config.json", help="Path to Litellm config JSON")
    parser.add_argument("--mcp-url", default="http://localhost:7777/tableau-mcp", help="Tableau MCP streamable HTTP URL")
    parser.add_argument("--dashboard-name", default="Sstock_market", help="Target Tableau dashboard name")
    parser.add_argument("--tickers", default="AAPL,MSFT,NVDA,^GSPC", help="Comma-separated base tickers")
    parser.add_argument("--include-sp500", action="store_true", help="Add sample of S&P 500 symbols")

    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    run_agent(
        config_path=Path(args.config),
        mcp_url=args.mcp_url,
        dashboard_name=args.dashboard_name,
        tickers=tickers,
        include_sp500=args.include_sp500,
    )
