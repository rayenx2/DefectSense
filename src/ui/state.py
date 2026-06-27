"""
Session state management for DefectSense dashboard.
All keys and defaults are defined here to keep streamlit_app_v2.py clean.
"""
from __future__ import annotations

import time
from typing import Any

import requests
import streamlit as st

HISTORY_MAX = 50

_DEFAULTS: dict[str, Any] = {
    # API connectivity
    "api_online": False,
    "api_last_checked": 0.0,
    # Model info from /health
    "model_type": "unknown",
    "current_threshold": 13.0,
    "resize_dims": (224, 224),
    # Single-image analysis
    "analysis_result": None,
    "analysis_time": 0.0,
    "analysis_filename": "",
    "analysis_image_bytes": None,
    # Batch
    "batch_files": [],
    "batch_results": [],
    "batch_running": False,
    # History  (list of dicts, newest first)
    "history": [],
    # Session counter
    "session_analyses": 0,
}


def init_state() -> None:
    """Initialise all session state keys that are not yet set."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def append_history(entry: dict) -> None:
    """
    Push a new history entry to the front of the list.
    Evicts the oldest entry when the list exceeds HISTORY_MAX.
    """
    history: list = st.session_state.get("history", [])
    history.insert(0, entry)
    if len(history) > HISTORY_MAX:
        history = history[:HISTORY_MAX]
    st.session_state["history"] = history
    st.session_state["session_analyses"] = st.session_state.get("session_analyses", 0) + 1


def clear_history() -> None:
    """Remove all history entries and reset session counter."""
    st.session_state["history"] = []
    st.session_state["session_analyses"] = 0


def check_api_health(base_url: str, force: bool = False) -> dict:
    """
    Query GET /health and update session state.

    Results are cached for 10 seconds unless *force* is True.
    Returns the health payload dict (may be empty on failure).
    """
    now = time.time()
    last = st.session_state.get("api_last_checked", 0.0)
    if not force and (now - last) < 10:
        # Return cached
        return {
            "status": "healthy" if st.session_state["api_online"] else "offline",
            "model_type": st.session_state["model_type"],
            "threshold": st.session_state["current_threshold"],
            "resize_size": list(st.session_state["resize_dims"]),
        }

    try:
        resp = requests.get(f"{base_url}/health", timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["api_online"] = data.get("status") == "healthy"
            st.session_state["model_type"] = data.get("model_type", "unknown")
            st.session_state["current_threshold"] = float(data.get("threshold", 13.0))
            raw_resize = data.get("resize_size", [224, 224])
            if isinstance(raw_resize, (list, tuple)) and len(raw_resize) >= 2:
                st.session_state["resize_dims"] = (int(raw_resize[0]), int(raw_resize[1]))
            st.session_state["api_last_checked"] = now
            return data
        else:
            _mark_offline()
            return {}
    except requests.exceptions.RequestException:
        _mark_offline()
        return {}


def _mark_offline() -> None:
    st.session_state["api_online"] = False
    st.session_state["api_last_checked"] = time.time()
