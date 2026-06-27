"""
Reusable HTML component generators for the DefectSense dashboard.

All functions return an HTML string (or call st.markdown internally).
No Streamlit state is read here — pure presentation layer.
"""
from __future__ import annotations

import streamlit as st


# ── Verdict Banner ────────────────────────────────────────────────────────────

def render_verdict_banner(score: float, threshold: float, is_anomaly: bool) -> None:
    """Full-width verdict banner. Anomaly variant has CSS pulsing glow."""
    if is_anomaly:
        cls = "ds-verdict ds-verdict-anomaly"
        icon = "&#9888;"  # warning sign
        label = "ANOMALY DETECTED"
        color = "var(--anomaly)"
    else:
        cls = "ds-verdict ds-verdict-normal"
        icon = "&#10003;"  # check mark
        label = "NORMAL"
        color = "var(--normal)"

    direction = ">=" if is_anomaly else "<"
    html = f"""
<div class="{cls}">
  <div class="ds-verdict-icon">{icon}</div>
  <div>
    <div class="ds-verdict-title" style="color:{color}">{label}</div>
    <div class="ds-verdict-sub">
      Score <strong>{score:.3f}</strong> {direction} threshold <strong>{threshold:.1f}</strong>
    </div>
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── Score Gauge ───────────────────────────────────────────────────────────────

def render_score_gauge(score: float, threshold: float, max_score: float = 50.0) -> None:
    """Horizontal bar gauge showing score relative to threshold."""
    effective_max = max(max_score, score * 1.15, threshold * 1.3)
    fill_pct = min(100.0, (score / effective_max) * 100)
    threshold_pct = min(100.0, (threshold / effective_max) * 100)

    # Color: anomaly red if over threshold, warning amber if within 10%, normal green otherwise
    if score >= threshold:
        fill_color = "var(--anomaly)"
    elif score >= threshold * 0.9:
        fill_color = "var(--warn)"
    else:
        fill_color = "var(--normal)"

    html = f"""
<div class="ds-gauge-wrap">
  <div class="ds-gauge-labels">
    <span>0</span>
    <span style="color:var(--text-primary);font-weight:600;">Score: {score:.3f}</span>
    <span>{effective_max:.0f}</span>
  </div>
  <div class="ds-gauge-track">
    <div class="ds-gauge-fill"
         style="width:{fill_pct:.1f}%;background:{fill_color};
                box-shadow:0 0 8px {fill_color}44;">
    </div>
    <div class="ds-gauge-marker" style="left:{threshold_pct:.1f}%">
      <span class="ds-gauge-marker-label">T={threshold:.1f}</span>
    </div>
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── Stat Card ─────────────────────────────────────────────────────────────────

def render_stat_card(label: str, value: str, color: str | None = None) -> str:
    """Return HTML for a single metric card (no st.markdown call)."""
    accent = color or "var(--accent)"
    return f"""
<div class="ds-stat-card" style="--card-accent:{accent}">
  <div class="ds-stat-label">{label}</div>
  <div class="ds-stat-value" style="color:{accent}">{value}</div>
</div>
"""


# ── Status Pill ───────────────────────────────────────────────────────────────

def render_status_pill(status_label: str, status_type: str) -> str:
    """
    Return HTML pill for online / degraded / offline states.
    status_type: 'online' | 'degraded' | 'offline'
    """
    cls_map = {
        "online": "ds-pill-online",
        "degraded": "ds-pill-degraded",
        "offline": "ds-pill-offline",
    }
    cls = cls_map.get(status_type, "ds-pill-offline")
    return f"""
<span class="ds-pill {cls}">
  <span class="ds-pill-dot"></span>
  {status_label}
</span>
"""


# ── Score Badge ───────────────────────────────────────────────────────────────

def render_score_badge(score: float, threshold: float) -> str:
    """Return HTML for a compact anomaly/normal badge with score."""
    is_anomaly = score >= threshold
    cls = "ds-badge ds-badge-anomaly" if is_anomaly else "ds-badge ds-badge-normal"
    label = f"ANOMALY {score:.2f}" if is_anomaly else f"NORMAL {score:.2f}"
    return f'<span class="{cls}">{label}</span>'


# ── Branding Header ───────────────────────────────────────────────────────────

def render_header(api_online: bool, model_type: str) -> None:
    """Render the top DefectSense branding bar."""
    pill_type = "online" if api_online else "offline"
    pill_label = "API ONLINE" if api_online else "API OFFLINE"
    pill_html = render_status_pill(pill_label, pill_type)
    model_badge = f'<span class="ds-format-tag">{model_type.upper()}</span>' if model_type and model_type != "unknown" else ""
    html = f"""
<div class="ds-header">
  <div class="ds-logo">&#9889;</div>
  <div>
    <div class="ds-title">DefectSense</div>
    <div class="ds-subtitle">Industrial Anomaly Detection &bull; PaDiM</div>
  </div>
  <div style="margin-left:auto;display:flex;align-items:center;gap:8px;">
    {model_badge}
    {pill_html}
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── Format Tags ───────────────────────────────────────────────────────────────

def render_format_tags() -> None:
    """Render a row of supported image format badges."""
    formats = ["JPG", "JPEG", "PNG", "BMP", "TIFF"]
    tags = "".join(f'<span class="ds-format-tag">.{f.lower()}</span>' for f in formats)
    html = f'<div class="ds-format-tags">{tags}</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── Empty State ───────────────────────────────────────────────────────────────

_ICONS = {
    "upload": "&#8679;",
    "search": "&#128269;",
    "history": "&#128337;",
    "batch": "&#128193;",
    "model": "&#129302;",
    "info": "&#8505;",
}


def render_empty_state(message: str, subtext: str = "", icon_type: str = "search") -> None:
    """Render a centred placeholder for empty content areas."""
    icon = _ICONS.get(icon_type, "&#8505;")
    sub_html = f'<div class="ds-empty-sub">{subtext}</div>' if subtext else ""
    html = f"""
<div class="ds-empty">
  <div class="ds-empty-icon">{icon}</div>
  <div class="ds-empty-msg">{message}</div>
  {sub_html}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── History Item ──────────────────────────────────────────────────────────────

def render_history_item(entry: dict) -> None:
    """Render a single analysis history card."""
    filename = entry.get("filename", "unknown")
    score = entry.get("score", 0.0)
    threshold = entry.get("threshold", 13.0)
    is_anomaly = entry.get("is_anomaly", False)
    timestamp = entry.get("timestamp", "")
    latency = entry.get("latency", 0.0)

    badge_html = render_score_badge(score, threshold)
    status_icon = "&#9888;" if is_anomaly else "&#10003;"
    status_color = "var(--anomaly)" if is_anomaly else "var(--normal)"

    html = f"""
<div class="ds-history-item">
  <div class="ds-history-left">
    <span style="font-size:1.2rem;color:{status_color}">{status_icon}</span>
    <div>
      <div class="ds-history-filename">{filename}</div>
      <div class="ds-history-meta">{timestamp} &bull; {latency:.2f}s latency</div>
    </div>
  </div>
  <div class="ds-history-right">
    {badge_html}
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── Stats Bar (4-card row) ────────────────────────────────────────────────────

def render_stats_bar(
    api_online: bool,
    model_type: str,
    threshold: float,
    session_analyses: int,
) -> None:
    """Render the four-card statistics bar beneath the header."""
    status_val = "ONLINE" if api_online else "OFFLINE"
    status_color = "var(--normal)" if api_online else "var(--anomaly)"
    cards_html = (
        render_stat_card("Model Status", status_val, status_color)
        + render_stat_card("Model Type", model_type.upper() if model_type else "N/A")
        + render_stat_card("Threshold", f"{threshold:.1f}", "var(--warn)")
        + render_stat_card("Session Analyses", str(session_analyses))
    )
    html = f'<div class="ds-stats-bar">{cards_html}</div>'
    st.markdown(html, unsafe_allow_html=True)
