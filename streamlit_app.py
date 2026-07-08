from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st


DEFAULT_BACKEND_URL = "http://localhost:7778"


def call_backend(message: str, history: List[Dict[str, str]], backend_url: str) -> Dict[str, Any]:
    response = requests.post(
        f"{backend_url.rstrip('/')}/agent/chat",
        json={"message": message, "history": history},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def normalize_history() -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for item in st.session_state.messages:
        result.append({"role": item["role"], "content": item["content"]})
    return result


def render_downloads(paths: List[str]) -> None:
    if not paths:
        return

    st.markdown("### Downloads")
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        mime = "application/octet-stream"
        suffix = path.suffix.lower()
        if suffix == ".pptx":
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif suffix == ".md":
            mime = "text/markdown"
        elif suffix == ".csv":
            mime = "text/csv"
        elif suffix == ".png":
            mime = "image/png"
        elif suffix == ".json":
            mime = "application/json"
        elif suffix == ".txt":
            mime = "text/plain"

        st.download_button(
            label=f"Download {path.name}",
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=f"download::{path}",
        )


def render_result(payload: Dict[str, Any]) -> None:
    st.markdown(payload.get("message", "No response message."))

    result = payload.get("result", {})
    action = payload.get("action")

    if action == "list_dashboards":
        dashboards = result.get("dashboards", [])
        if dashboards:
            st.dataframe(pd.DataFrame(dashboards), use_container_width=True)
    elif action == "list_views":
        views = result.get("views", [])
        if views:
            st.dataframe(pd.DataFrame(views), use_container_width=True)
    elif action == "list_datasources":
        sources = result.get("datasources", [])
        if sources:
            st.dataframe(pd.DataFrame(sources), use_container_width=True)
    elif action == "list_catalog":
        dashboards = result.get("dashboards", {}).get("dashboards", [])
        views = result.get("views", {}).get("views", [])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Dashboards")
            if dashboards:
                st.dataframe(pd.DataFrame(dashboards), use_container_width=True)
        with c2:
            st.markdown("#### Views")
            if views:
                st.dataframe(pd.DataFrame(views), use_container_width=True)
    else:
        with st.expander("Structured Result", expanded=False):
            st.json(result)

    render_downloads(payload.get("artifacts", []))


st.set_page_config(
    page_title="Tableau Agent Chat",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #f4efe4 0%, #f8f6f1 35%, #eef3ea 100%);
    }
    .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
    }
    .hero {
        padding: 1rem 1.25rem;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(18,52,86,0.94), rgba(37,89,65,0.9));
        color: #f7f3ea;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.14);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Connection")
    backend_url = st.text_input("Backend URL", value=DEFAULT_BACKEND_URL)
    st.caption("Streamlit UI runs on port 7779. Backend API runs on port 7778.")
    st.markdown("### Quick prompts")
    quick_prompts = [
        "Show me your dashboards and views",
        "Summarize workbook sample and generate a PPT",
        "Generate stock dashboard for AAPL over 3 months hourly",
        "Create a report for view Overview",
    ]
    for idx, prompt in enumerate(quick_prompts):
        if st.button(prompt, key=f"quick::{idx}"):
            st.session_state.pending_prompt = prompt

st.markdown(
    """
    <div class="hero">
      <h2 style="margin:0;">Tableau Agent Chat</h2>
      <p style="margin:0.35rem 0 0 0;">Ask for dashboards, views, stock dashboard generation, or PPT reports. The UI sends your request to the backend agent and returns downloadable files.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Ask me to list dashboards/views, generate a stock dashboard, or create a report and PowerPoint from a dashboard or view.",
            "payload": None,
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("payload"):
            render_result(msg["payload"])

prompt = st.session_state.pop("pending_prompt", None) or st.chat_input("Example: Show me your dashboards and then create a PPT for Executive Summary")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "payload": None})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking and calling the backend agent..."):
            try:
                history = normalize_history()[:-1]
                payload = call_backend(prompt, history, backend_url)
                st.markdown(payload.get("message", "Done."))
                render_result(payload)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": payload.get("message", "Done."),
                        "payload": payload,
                    }
                )
            except Exception as exc:
                error_text = f"Backend call failed: {exc}"
                st.error(error_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text, "payload": None}
                )
