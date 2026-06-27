"""
DefectSense v2 — Industrial Anomaly Detection Dashboard
========================================================
Run: streamlit run src/streamlit_app_v2.py --server.port 8501 -- --port 8080

The legacy src/streamlit_app.py remains untouched.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import sys
import time
from datetime import datetime
from typing import Any

import requests
import streamlit as st
from PIL import Image

# ── Support module import (graceful fallback if run from wrong cwd) ───────────
try:
    from ui.styles import inject_styles
    from ui.state import init_state, append_history, clear_history, check_api_health
    from ui.components import (
        render_header,
        render_stats_bar,
        render_verdict_banner,
        render_score_gauge,
        render_format_tags,
        render_empty_state,
        render_history_item,
        render_status_pill,
        render_score_badge,
        render_stat_card,
    )
    _MODULES_OK = True
except ImportError:
    _MODULES_OK = False


# ── Fallback stubs (if ui/ package not found) ─────────────────────────────────

if not _MODULES_OK:
    def inject_styles() -> None:  # type: ignore[misc]
        st.markdown("<style>body{background:#0d0f1a;color:#e8eaf6}</style>",
                    unsafe_allow_html=True)

    def init_state() -> None:  # type: ignore[misc]
        for key, val in {
            "api_online": False,
            "model_type": "unknown",
            "current_threshold": 13.0,
            "resize_dims": (224, 224),
            "analysis_result": None,
            "analysis_time": 0.0,
            "analysis_filename": "",
            "analysis_image_bytes": None,
            "batch_files": [],
            "batch_results": [],
            "batch_running": False,
            "history": [],
            "session_analyses": 0,
        }.items():
            if key not in st.session_state:
                st.session_state[key] = val

    def append_history(entry: dict) -> None:  # type: ignore[misc]
        h = st.session_state.get("history", [])
        h.insert(0, entry)
        st.session_state["history"] = h[:50]
        st.session_state["session_analyses"] = st.session_state.get("session_analyses", 0) + 1

    def clear_history() -> None:  # type: ignore[misc]
        st.session_state["history"] = []
        st.session_state["session_analyses"] = 0

    def check_api_health(base_url: str, force: bool = False) -> dict:  # type: ignore[misc]
        try:
            r = requests.get(f"{base_url}/health", timeout=4)
            if r.status_code == 200:
                d = r.json()
                st.session_state["api_online"] = d.get("status") == "healthy"
                st.session_state["model_type"] = d.get("model_type", "unknown")
                st.session_state["current_threshold"] = float(d.get("threshold", 13.0))
                return d
        except Exception:
            pass
        st.session_state["api_online"] = False
        return {}

    def render_header(api_online: bool, model_type: str) -> None:  # type: ignore[misc]
        status = "ONLINE" if api_online else "OFFLINE"
        st.markdown(f"## DefectSense  |  API {status}", unsafe_allow_html=True)

    def render_stats_bar(*_args: Any) -> None:  # type: ignore[misc]
        pass

    def render_verdict_banner(score: float, threshold: float, is_anomaly: bool) -> None:  # type: ignore[misc]
        label = "ANOMALY DETECTED" if is_anomaly else "NORMAL"
        st.markdown(f"**{label}** — score {score:.3f} (threshold {threshold:.1f})")

    def render_score_gauge(score: float, threshold: float, max_score: float = 50.0) -> None:  # type: ignore[misc]
        st.progress(min(1.0, score / max(max_score, threshold * 1.3)))

    def render_format_tags() -> None:  # type: ignore[misc]
        st.caption("Supported: JPG JPEG PNG BMP TIFF")

    def render_empty_state(msg: str, subtext: str = "", icon_type: str = "search") -> None:  # type: ignore[misc]
        st.info(f"{msg}  {subtext}")

    def render_history_item(entry: dict) -> None:  # type: ignore[misc]
        st.text(f"{entry.get('filename')} | {entry.get('score', 0):.3f}")

    def render_status_pill(label: str, status_type: str) -> str:  # type: ignore[misc]
        return f"[{label}]"

    def render_score_badge(score: float, threshold: float) -> str:  # type: ignore[misc]
        label = "ANOMALY" if score >= threshold else "NORMAL"
        return f"{label} {score:.2f}"

    def render_stat_card(label: str, value: str, color: str | None = None) -> str:  # type: ignore[misc]
        return f"**{label}**: {value}  "


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="localhost")
    return parser.parse_known_args(sys.argv[1:])[0]


# ── Image helpers ─────────────────────────────────────────────────────────────

def _b64_to_pil(b64str: str) -> Image.Image | None:
    if not b64str:
        return None
    try:
        raw = base64.b64decode(b64str)
        return Image.open(io.BytesIO(raw))
    except Exception:
        return None


def _bytes_to_pil(data: bytes) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


# ── API calls ─────────────────────────────────────────────────────────────────

def _api_predict(base_url: str, filename: str, data: bytes, mime: str) -> tuple[dict | None, str]:
    """
    POST /predict — returns (result_dict, error_message).
    On success error_message is "".
    """
    try:
        files = {"file": (filename, data, mime)}
        resp = requests.post(f"{base_url}/predict", files=files, timeout=30)
        if resp.status_code == 200:
            return resp.json(), ""
        err = resp.json().get("detail", f"HTTP {resp.status_code}")
        return None, err
    except requests.exceptions.Timeout:
        return None, "Request timed out (30s)"
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to backend"
    except Exception as exc:
        return None, str(exc)


def _api_predict_batch(base_url: str, files_data: list[tuple[str, bytes, str]]) -> tuple[dict | None, str]:
    """
    POST /predict-batch — send up to 10 files at once.
    Returns (response_dict, error_message).
    """
    try:
        multi = [("files", (name, data, mime)) for name, data, mime in files_data]
        resp = requests.post(f"{base_url}/predict-batch", files=multi, timeout=60)
        if resp.status_code == 200:
            return resp.json(), ""
        err = resp.json().get("detail", f"HTTP {resp.status_code}")
        return None, err
    except requests.exceptions.Timeout:
        return None, "Batch request timed out (60s)"
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to backend"
    except Exception as exc:
        return None, str(exc)


def _api_model_info(base_url: str) -> tuple[dict | None, str]:
    try:
        resp = requests.get(f"{base_url}/model-info", timeout=6)
        if resp.status_code == 200:
            return resp.json(), ""
        return None, f"HTTP {resp.status_code}"
    except Exception as exc:
        return None, str(exc)


def _api_update_config(base_url: str, threshold: float, w: int, h: int) -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"{base_url}/config",
            json={"threshold": threshold, "resize_width": w, "resize_height": h},
            timeout=6,
        )
        if resp.status_code == 200:
            return True, resp.json().get("message", "Config updated")
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(base_url: str) -> None:
    with st.sidebar:
        st.markdown("### Configuration")

        # Connectivity
        with st.expander("Backend Connection", expanded=True):
            st.caption(f"Endpoint: `{base_url}`")
            col_a, col_b = st.columns([3, 1])
            with col_b:
                if st.button("Ping", key="btn_ping"):
                    check_api_health(base_url, force=True)
                    st.rerun()
            api_online: bool = st.session_state.get("api_online", False)
            pill = render_status_pill(
                "API ONLINE" if api_online else "API OFFLINE",
                "online" if api_online else "offline",
            )
            st.markdown(pill, unsafe_allow_html=True)

        st.markdown("---")

        # Threshold
        st.markdown("**Detection Threshold**")
        saved_thr = float(st.session_state.get("current_threshold", 13.0))
        new_threshold = st.slider(
            "Anomaly threshold",
            min_value=0.1,
            max_value=50.0,
            value=saved_thr,
            step=0.1,
            key="sidebar_threshold",
            label_visibility="collapsed",
        )

        # Resize
        st.markdown("**Preprocessing**")
        saved_dims = st.session_state.get("resize_dims", (224, 224))
        c1, c2 = st.columns(2)
        with c1:
            rw = st.number_input("Width", 32, 1024, int(saved_dims[0]), step=8, key="resize_w")
        with c2:
            rh = st.number_input("Height", 32, 1024, int(saved_dims[1]), step=8, key="resize_h")

        if st.button("Apply Config", key="btn_apply_config"):
            if not api_online:
                st.error("Backend offline — cannot update config")
            else:
                ok, msg = _api_update_config(base_url, new_threshold, int(rw), int(rh))
                if ok:
                    st.session_state["current_threshold"] = new_threshold
                    st.session_state["resize_dims"] = (int(rw), int(rh))
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(f"Config update failed: {msg}")

        st.markdown("---")

        # Model info expander
        with st.expander("Model Info", expanded=False):
            mtype = st.session_state.get("model_type", "unknown")
            thr = st.session_state.get("current_threshold", 13.0)
            dims = st.session_state.get("resize_dims", (224, 224))
            st.markdown(
                f"**Type:** `{mtype}`  \n"
                f"**Threshold:** `{thr}`  \n"
                f"**Input size:** `{dims[0]}x{dims[1]}`  \n"
                f"**Backend:** `{base_url}`",
            )


# ── Tab 0 — Analysis ──────────────────────────────────────────────────────────

def _tab_analysis(base_url: str) -> None:
    api_online: bool = st.session_state.get("api_online", False)
    threshold: float = float(st.session_state.get("current_threshold", 13.0))

    left, right = st.columns([1, 1], gap="large")

    # ── Left: Upload + preview ────────────────────────────────────────────────
    with left:
        st.markdown('<div class="ds-section-title">Upload Image</div>', unsafe_allow_html=True)
        render_format_tags()

        uploaded = st.file_uploader(
            "Drag & drop or click to browse",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            key="analysis_uploader",
            label_visibility="collapsed",
        )

        if uploaded is not None:
            img_bytes = uploaded.getvalue()
            st.session_state["analysis_image_bytes"] = img_bytes
            st.session_state["analysis_filename"] = uploaded.name
            pil_img = _bytes_to_pil(img_bytes)
            if pil_img:
                st.image(pil_img, caption=f"Preview — {uploaded.name}", use_container_width=True)

            # Analyze button
            st.markdown("")
            btn_disabled = not api_online
            if st.button(
                "Analyze Image",
                key="btn_analyze",
                disabled=btn_disabled,
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Running inference..."):
                    t0 = time.time()
                    result, err = _api_predict(
                        base_url,
                        uploaded.name,
                        img_bytes,
                        uploaded.type or "image/jpeg",
                    )
                    elapsed = time.time() - t0

                if err:
                    st.error(f"Inference failed: {err}")
                else:
                    st.session_state["analysis_result"] = result
                    st.session_state["analysis_time"] = elapsed
                    # Push to history
                    append_history(
                        {
                            "filename": uploaded.name,
                            "score": result.get("anomaly_score", 0.0),
                            "threshold": threshold,
                            "is_anomaly": result.get("is_anomaly", False),
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "latency": elapsed,
                        }
                    )
                    st.rerun()

            if btn_disabled:
                st.warning("Backend offline — analysis unavailable")
        else:
            render_empty_state(
                "No image selected",
                "Upload a JPG, PNG, BMP or TIFF file to begin",
                "upload",
            )

    # ── Right: Results ────────────────────────────────────────────────────────
    with right:
        st.markdown('<div class="ds-section-title">Analysis Results</div>', unsafe_allow_html=True)

        result = st.session_state.get("analysis_result")
        if result is None:
            render_empty_state(
                "Awaiting analysis",
                "Upload an image and press Analyze",
                "search",
            )
            return

        score: float = float(result.get("anomaly_score", 0.0))
        is_anomaly: bool = bool(result.get("is_anomaly", False))
        elapsed: float = float(st.session_state.get("analysis_time", 0.0))

        # Verdict banner
        render_verdict_banner(score, threshold, is_anomaly)

        # Metrics row
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Anomaly Score", f"{score:.3f}")
        with m2:
            st.metric("Classification", "ANOMALY" if is_anomaly else "NORMAL")
        with m3:
            st.metric("Latency", f"{elapsed:.2f}s")

        # Score gauge
        st.markdown("**Score Gauge**")
        render_score_gauge(score, threshold)

        # Visualisations
        heatmap_b64: str = result.get("heatmap_image_base64", "") or ""
        boundary_b64: str = result.get("boundary_image_base64", "") or ""

        has_any_viz = bool(heatmap_b64 or boundary_b64)

        if has_any_viz:
            viz_tabs = st.tabs(["Heatmap", "Boundary", "Side-by-Side"])
            with viz_tabs[0]:
                hm_img = _b64_to_pil(heatmap_b64)
                if hm_img:
                    st.image(hm_img, caption="Anomaly Heatmap Overlay", use_container_width=True)
                else:
                    st.info("Heatmap not available")

            with viz_tabs[1]:
                bd_img = _b64_to_pil(boundary_b64)
                if bd_img:
                    st.image(bd_img, caption="Boundary Visualisation", use_container_width=True)
                else:
                    st.info("Boundary visualisation not available")

            with viz_tabs[2]:
                orig_bytes = st.session_state.get("analysis_image_bytes")
                c1, c2 = st.columns(2)
                with c1:
                    if orig_bytes:
                        st.image(_bytes_to_pil(orig_bytes), caption="Original", use_container_width=True)
                    else:
                        st.caption("Original not available")
                with c2:
                    hm_img2 = _b64_to_pil(heatmap_b64)
                    bd_img2 = _b64_to_pil(boundary_b64)
                    display = hm_img2 or bd_img2
                    if display:
                        lbl = "Heatmap" if hm_img2 else "Boundary"
                        st.image(display, caption=lbl, use_container_width=True)
                    else:
                        st.caption("Visualisation not available")
        else:
            st.info("No visualisation data returned by the backend (include_visualizations may be disabled).")

        # Download button for raw JSON
        json_str = json.dumps(
            {k: v for k, v in result.items() if not k.endswith("_base64")},
            indent=2,
        )
        st.download_button(
            "Download Result JSON",
            data=json_str,
            file_name=f"defectsense_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )


# ── Tab 1 — Batch ─────────────────────────────────────────────────────────────

def _tab_batch(base_url: str) -> None:
    api_online: bool = st.session_state.get("api_online", False)
    threshold: float = float(st.session_state.get("current_threshold", 13.0))

    st.markdown('<div class="ds-section-title">Batch Analysis</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload up to 10 images",
        type=["jpg", "jpeg", "png", "bmp", "tiff"],
        accept_multiple_files=True,
        key="batch_uploader",
    )

    if uploaded_files:
        capped = uploaded_files[:10]
        if len(uploaded_files) > 10:
            st.warning(f"Max 10 files — using first 10 of {len(uploaded_files)} selected.")
        st.caption(f"Queue: {len(capped)} file(s) ready")

        run_disabled = not api_online
        if st.button(
            f"Run Batch ({len(capped)} files)",
            key="btn_batch_run",
            disabled=run_disabled,
            type="primary",
        ):
            if not api_online:
                st.error("Backend offline")
            else:
                files_data = [
                    (f.name, f.getvalue(), f.type or "image/jpeg") for f in capped
                ]
                progress_bar = st.progress(0, text="Preparing batch...")

                # Submit batch
                progress_bar.progress(0.1, text="Submitting to backend...")
                t0 = time.time()
                raw, err = _api_predict_batch(base_url, files_data)
                elapsed = time.time() - t0

                if err:
                    progress_bar.empty()
                    st.error(f"Batch failed: {err}")
                    return

                progress_bar.progress(0.9, text="Processing results...")
                batch_entries = raw.get("batch_results", [])  # type: ignore[union-attr]

                results_list = []
                for entry in batch_entries:
                    res = entry.get("result", {})
                    if isinstance(res, dict):
                        score = float(res.get("anomaly_score", 0.0))
                        is_anom = bool(res.get("is_anomaly", False))
                    else:
                        score = 0.0
                        is_anom = False
                    results_list.append(
                        {
                            "filename": entry.get("filename", "unknown"),
                            "score": score,
                            "is_anomaly": is_anom,
                            "classification": "ANOMALY" if is_anom else "NORMAL",
                            "latency": round(elapsed / max(len(batch_entries), 1), 3),
                            "error": entry.get("error", ""),
                        }
                    )
                    # Push each to history
                    append_history(
                        {
                            "filename": entry.get("filename", "unknown"),
                            "score": score,
                            "threshold": threshold,
                            "is_anomaly": is_anom,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "latency": round(elapsed / max(len(batch_entries), 1), 3),
                        }
                    )

                st.session_state["batch_results"] = results_list
                progress_bar.progress(1.0, text="Done!")
                time.sleep(0.3)
                progress_bar.empty()
                st.rerun()

        if run_disabled:
            st.warning("Backend offline — batch unavailable")

    # Results
    batch_results: list = st.session_state.get("batch_results", [])
    if not batch_results:
        render_empty_state(
            "No batch results yet",
            "Upload files and press Run Batch",
            "batch",
        )
        return

    # Summary badges
    total = len(batch_results)
    n_anom = sum(1 for r in batch_results if r.get("is_anomaly"))
    n_norm = total - n_anom
    pct = int(100 * total / total) if total else 0

    st.markdown(
        f"""
<div class="ds-summary-row">
  <div class="ds-summary-badge">Total: {total}</div>
  <div class="ds-summary-badge" style="color:var(--normal)">Normal: {n_norm}</div>
  <div class="ds-summary-badge" style="color:var(--anomaly)">Anomaly: {n_anom}</div>
  <div class="ds-summary-badge">Complete: {pct}%</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Dataframe
    import pandas as pd  # local import to avoid top-level overhead
    df = pd.DataFrame(
        [
            {
                "File": r["filename"],
                "Score": round(r["score"], 4),
                "Class": r["classification"],
                "Latency (s)": r["latency"],
                "Error": r["error"] or "",
            }
            for r in batch_results
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export buttons
    ex1, ex2, ex3 = st.columns([1, 1, 2])
    with ex1:
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        st.download_button(
            "Export CSV",
            data=csv_buf.getvalue(),
            file_name=f"defectsense_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    with ex2:
        st.download_button(
            "Export JSON",
            data=json.dumps(batch_results, indent=2),
            file_name=f"defectsense_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
    with ex3:
        if st.button("Clear Batch Results", key="btn_clear_batch"):
            st.session_state["batch_results"] = []
            st.rerun()


# ── Tab 2 — History ───────────────────────────────────────────────────────────

def _tab_history() -> None:
    history: list = st.session_state.get("history", [])

    hdr_col, btn_col = st.columns([3, 1])
    with hdr_col:
        st.markdown(
            f'<div class="ds-section-title">History — {len(history)} entries</div>',
            unsafe_allow_html=True,
        )
    with btn_col:
        if st.button("Clear All", key="btn_clear_history"):
            clear_history()
            st.rerun()

    if not history:
        render_empty_state(
            "No analysis history",
            "Completed analyses will appear here",
            "history",
        )
        return

    for entry in history:
        render_history_item(entry)


# ── Tab 3 — Model Info ────────────────────────────────────────────────────────

def _tab_model_info(base_url: str) -> None:
    api_online: bool = st.session_state.get("api_online", False)

    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.markdown('<div class="ds-section-title">Model Information</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button("Refresh", key="btn_refresh_model"):
            check_api_health(base_url, force=True)
            st.rerun()

    if not api_online:
        render_empty_state(
            "Backend offline",
            "Start the FastAPI server to view model info",
            "model",
        )
        return

    # Health-based cards
    mtype = st.session_state.get("model_type", "unknown")
    thr = st.session_state.get("current_threshold", 13.0)
    dims = st.session_state.get("resize_dims", (224, 224))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Model Type", mtype.upper())
    with c2:
        st.metric("Threshold", f"{thr:.1f}")
    with c3:
        st.metric("Backend", f"{base_url.replace('http://', '')}")

    st.markdown("---")

    # Detailed model-info endpoint
    model_data, err = _api_model_info(base_url)
    if err:
        st.warning(f"Could not load /model-info: {err}")
        return

    # Input/output specs
    if "inputs" in (model_data or {}):
        st.markdown("**Input Specifications**")
        import pandas as pd

        inp_rows = [
            {"Name": i[0], "Shape": str(i[1]), "Type": i[2]}
            for i in (model_data.get("inputs") or [])
        ]
        if inp_rows:
            st.dataframe(pd.DataFrame(inp_rows), use_container_width=True, hide_index=True)

    if "outputs" in (model_data or {}):
        st.markdown("**Output Specifications**")
        import pandas as pd

        out_rows = [
            {"Name": o[0], "Shape": str(o[1]), "Type": o[2]}
            for o in (model_data.get("outputs") or [])
        ]
        if out_rows:
            st.dataframe(pd.DataFrame(out_rows), use_container_width=True, hide_index=True)

    # Raw JSON
    if model_data:
        with st.expander("Raw /model-info JSON", expanded=False):
            st.json(model_data)


# ── Tab 4 — Benchmark ─────────────────────────────────────────────────────────

def _tab_benchmark() -> None:
    """Display model optimization benchmark results from the optimizer module."""
    import json
    import os
    from pathlib import Path

    st.markdown('<div class="ds-section-title">Model Benchmark &amp; Optimization</div>', unsafe_allow_html=True)

    # Locate models directory
    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    report_path = models_dir / "optimized" / "optimization_report.json"

    col_info, col_btn = st.columns([3, 1])
    with col_info:
        if report_path.exists():
            st.caption(f"Report: `{report_path}`")
        else:
            st.caption("No benchmark report found. Models dir: `" + str(models_dir) + "`")
    with col_btn:
        if st.button("Scan Models", key="btn_scan_models"):
            model_files = list(models_dir.glob("*.onnx")) + list(models_dir.glob("*.pt")) + list(models_dir.glob("*.pth"))
            if not model_files:
                st.warning("No model files (.onnx/.pt/.pth) found in models/")
            else:
                st.info(f"Found {len(model_files)} model file(s). Run `python src/ai/optimizer.py` for benchmarks.")

    # Display last report if available
    if report_path.exists():
        try:
            with open(report_path) as f:
                data = json.load(f)

            st.markdown(f"**Last run:** `{data.get('timestamp', 'unknown')}`")

            for m in data.get("models", []):
                fname = m.get("file", "?")
                mtype = m.get("type", "?").upper()
                orig = m.get("original", {})

                st.markdown(f"### {fname} ({mtype})")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Latency (mean)", f"{orig.get('mean_ms', '—')}ms")
                with c2:
                    st.metric("Throughput", f"{orig.get('fps', '—')} FPS")
                with c3:
                    st.metric("Size", f"{orig.get('model_size_mb', '—')} MB")

                # Show optimizations if applied
                if "graph_optimized" in m:
                    go = m["graph_optimized"]
                    st.caption(
                        f"⏵ Graph optimized: {go.get('mean_ms', '—')}ms / {go.get('fps', '—')} FPS "
                        f"(speedup: {m.get('graph_speedup', 1.0)}×)"
                    )
                if "int8_quantized" in m:
                    iq = m["int8_quantized"]
                    st.caption(
                        f"⏵ INT8 quantized: {iq.get('model_size_mb', '—')} MB "
                        f"(reduction: {m.get('int8_size_reduction_pct', 0)}%)"
                    )
                st.markdown("---")

            with st.expander("Raw Benchmark JSON", expanded=False):
                st.json(data)
        except Exception as e:
            st.error(f"Failed to parse report: {e}")
    else:
        render_empty_state(
            "No benchmarks yet",
            "Run `python src/ai/optimizer.py` to generate the optimization report",
            "model",
        )


# ── Tab 5 — Registry ──────────────────────────────────────────────────────────

def _tab_registry() -> None:
    """Model registry viewer — list, promote, rollback registered models."""
    import json
    from pathlib import Path

    st.markdown('<div class="ds-section-title">Model Registry</div>', unsafe_allow_html=True)

    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    reg_path = models_dir / "model_registry.json"

    # Initialize registry entries in session
    if "registry_data" not in st.session_state:
        st.session_state["registry_data"] = None

    if not reg_path.exists():
        render_empty_state(
            "No registry found",
            f"Run `python src/ai/registry.py register <model_file>` to create the registry",
            "model",
        )
        # Quick-register button for existing models
        if st.button("Auto-register models/ files", key="btn_auto_reg"):
            model_files = list(models_dir.glob("*.onnx")) + list(models_dir.glob("*.pt")) + list(models_dir.glob("*.pth"))
            if model_files:
                sys.path.insert(0, str(project_root / "src"))
                try:
                    from ai.registry import ModelRegistry
                    reg = ModelRegistry(str(models_dir))
                    for mf in model_files:
                        try:
                            reg.register(mf.name)
                        except Exception:
                            pass
                    st.success(f"Registered {len(model_files)} model(s)")
                    st.rerun()
                except ImportError as e:
                    st.error(f"Cannot import registry module: {e}")
            else:
                st.warning("No model files found")
        return

    # Load registry data
    try:
        with open(reg_path) as f:
            data = json.load(f)
        st.session_state["registry_data"] = data
    except Exception as e:
        st.error(f"Failed to read registry: {e}")
        return

    entries = data.get("entries", {})
    if not entries:
        st.info("Registry is empty — register models to populate")
        return

    # Count by stage
    stages_count = {}
    for e in entries.values():
        s = e.get("stage", "unknown")
        stages_count[s] = stages_count.get(s, 0) + 1

    # Stage summary badges
    cols = st.columns(len(stages_count) if stages_count else 1)
    for i, (stage, count) in enumerate(sorted(stages_count.items())):
        with cols[i]:
            color = {"production": "green", "staging": "orange", "archived": "gray"}.get(stage, "blue")
            st.markdown(
                f'<div style="background:var(--ds-bg-elevated);padding:12px;border-radius:8px;'
                f'text-align:center;border-left:3px solid var(--ds-teal-pure);">'
                f'<div style="font-size:0.7rem;text-transform:uppercase;color:var(--ds-text-secondary);">'
                f'{stage}</div><div style="font-size:1.5rem;font-weight:700;">{count}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Model list
    for eid, entry in sorted(entries.items(), key=lambda x: x[1].get("version", 0)):
        stage = entry.get("stage", "unknown")
        badge_color = {"production": "#00c853", "staging": "#00d2ff", "archived": "#8892b0"}.get(stage, "#8892b0")

        with st.expander(
            f"v{entry.get('version', '?')} — {entry.get('filename', '?')} "
            f"[{stage.upper()}] ({entry.get('file_size_mb', 0):.1f}MB)",
            expanded=(stage == "production"),
        ):
            c1, c2 = st.columns(2)
            with c1:
                st.caption(f"Registered: {entry.get('registered_at', '?')[:19]}")
                meta = entry.get("metadata", {})
                if meta:
                    for k, v in meta.items():
                        st.caption(f"  {k}: `{v}`")
            with c2:
                st.caption(f"ID: `{eid[:24]}...`")
                prev = entry.get("previous_stages", [])
                if prev:
                    st.caption(f"Previous stages: {', '.join(p['stage'] for p in prev)}")

            # Action buttons
            btn_c1, btn_c2, btn_c3 = st.columns(3)
            with btn_c1:
                if stage != "production" and st.button("Promote → Production", key=f"prom_{eid}"):
                    sys.path.insert(0, str(project_root / "src"))
                    try:
                        from ai.registry import ModelRegistry
                        reg = ModelRegistry(str(models_dir))
                        reg.promote(entry["filename"], "production")
                        st.rerun()
                    except ImportError as e:
                        st.error(str(e))
            with btn_c2:
                if stage == "production" and st.button("Archive", key=f"arch_{eid}"):
                    sys.path.insert(0, str(project_root / "src"))
                    try:
                        from ai.registry import ModelRegistry
                        reg = ModelRegistry(str(models_dir))
                        reg.archive(entry["filename"])
                        st.rerun()
                    except ImportError as e:
                        st.error(str(e))
            with btn_c3:
                if stage == "archived" and st.button("Restore → Staging", key=f"rest_{eid}"):
                    sys.path.insert(0, str(project_root / "src"))
                    try:
                        from ai.registry import ModelRegistry
                        reg = ModelRegistry(str(models_dir))
                        reg.promote(entry["filename"], "staging")
                        st.rerun()
                    except ImportError as e:
                        st.error(str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Page config — must be first Streamlit call
    st.set_page_config(
        page_title="DefectSense — Industrial Anomaly Detection",
        page_icon="&#9889;",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 2. Parse CLI args
    args = _parse_args()
    base_url = f"http://{args.host}:{args.port}"

    # 3. Inject dark industrial CSS
    inject_styles()

    # 4. Initialise session state
    init_state()

    # 5. Health probe (cached — runs at most every 10 s)
    check_api_health(base_url)

    api_online: bool = st.session_state.get("api_online", False)
    model_type: str = st.session_state.get("model_type", "unknown")
    threshold: float = float(st.session_state.get("current_threshold", 13.0))
    session_analyses: int = int(st.session_state.get("session_analyses", 0))

    # 6. Header bar
    render_header(api_online, model_type)

    # 7. Stats bar
    render_stats_bar(api_online, model_type, threshold, session_analyses)

    # 8. Sidebar
    _render_sidebar(base_url)

    # 9. Main tabs
    tab_labels = ["Analysis", "Batch", "History", "Model Info", "Benchmark", "Registry"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _tab_analysis(base_url)

    with tabs[1]:
        _tab_batch(base_url)

    with tabs[2]:
        _tab_history()

    with tabs[3]:
        _tab_model_info(base_url)

    with tabs[4]:
        _tab_benchmark()

    with tabs[5]:
        _tab_registry()

    # Footer
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;color:var(--text-disabled);font-size:0.78rem;padding-bottom:1rem;">'
        "DefectSense v2 &bull; Industrial Anomaly Detection &bull; PaDiM"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
