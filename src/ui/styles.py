"""
CSS injection module for DefectSense dark industrial theme.
Call inject_styles() once at the top of the Streamlit app.
"""
import streamlit as st


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── CSS Variables ─────────────────────────────────────────────────────────── */
:root {
  --bg-base:      #0d0f1a;
  --bg-surface:   #13162a;
  --bg-elevated:  #1a1e35;
  --bg-hover:     #222644;

  --accent:       #00d2ff;
  --accent-dim:   #007a99;
  --accent-glow:  rgba(0, 210, 255, 0.25);

  --anomaly:      #ff4444;
  --anomaly-dim:  #7a1a1a;
  --anomaly-glow: rgba(255, 68, 68, 0.30);
  --normal:       #00c853;
  --normal-dim:   #006b2d;
  --normal-glow:  rgba(0, 200, 83, 0.25);
  --warn:         #ffab00;
  --warn-dim:     #7a5000;

  --text-primary:   #e8eaf6;
  --text-secondary: #8892b0;
  --text-disabled:  #3d4666;

  --border:         rgba(0, 210, 255, 0.12);
  --border-strong:  rgba(0, 210, 255, 0.28);

  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-pill: 9999px;

  --shadow-sm: 0 2px 8px rgba(0,0,0,0.4);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.5);
}

/* ── Base & App Shell ───────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"] {
  background-color: var(--bg-base) !important;
  color: var(--text-primary) !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

[data-testid="stMain"] {
  background-color: var(--bg-base) !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
  background-color: var(--bg-surface) !important;
  border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * {
  color: var(--text-primary) !important;
}

[data-testid="stSidebarCollapseButton"] {
  color: var(--text-secondary) !important;
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
}

/* ── Typography ─────────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
  color: var(--text-primary) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em;
}

p, span, label, div {
  color: var(--text-primary);
  font-family: 'Inter', sans-serif !important;
}

/* ── Horizontal Rule ────────────────────────────────────────────────────────── */
hr {
  border-color: var(--border) !important;
  margin: 1rem 0 !important;
}

/* ── Buttons ────────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button,
button[kind="primary"],
button[kind="secondary"] {
  background: var(--bg-elevated) !important;
  color: var(--accent) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: var(--radius-md) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: 0.85rem !important;
  padding: 0.45rem 1.1rem !important;
  transition: background 0.18s, border-color 0.18s, box-shadow 0.18s !important;
  cursor: pointer !important;
}

[data-testid="stButton"] > button:hover {
  background: var(--bg-hover) !important;
  border-color: var(--accent) !important;
  box-shadow: 0 0 10px var(--accent-glow) !important;
}

[data-testid="stButton"] > button:active {
  transform: translateY(1px) !important;
}

/* Primary button variant */
[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, var(--accent-dim), var(--accent)) !important;
  color: var(--bg-base) !important;
  border-color: var(--accent) !important;
}

/* ── File Uploader ──────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
  background: var(--bg-surface) !important;
  border: 1.5px dashed var(--border-strong) !important;
  border-radius: var(--radius-lg) !important;
  transition: border-color 0.2s, background 0.2s !important;
}

[data-testid="stFileUploader"]:hover {
  border-color: var(--accent) !important;
  background: var(--bg-elevated) !important;
}

[data-testid="stFileUploaderDropzone"] {
  background: transparent !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important;
  background: transparent !important;
}

[data-testid="stTabs"] [role="tab"] {
  color: var(--text-secondary) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  padding: 0.6rem 1.2rem !important;
  transition: color 0.2s, border-color 0.2s !important;
}

[data-testid="stTabs"] [role="tab"]:hover {
  color: var(--text-primary) !important;
  border-bottom-color: var(--border-strong) !important;
}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
  background: transparent !important;
}

/* ── Sliders ────────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
  background: var(--accent) !important;
  border: 2px solid var(--bg-base) !important;
  box-shadow: 0 0 6px var(--accent-glow) !important;
}

[data-testid="stSlider"] > div > div > div {
  background: var(--border) !important;
}

[data-testid="stSlider"] > div > div > div > div {
  background: linear-gradient(90deg, var(--accent-dim), var(--accent)) !important;
}

/* ── Number Input ───────────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-primary) !important;
  font-family: 'Inter', sans-serif !important;
}

[data-testid="stNumberInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-glow) !important;
  outline: none !important;
}

/* ── Checkboxes ─────────────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label span {
  color: var(--text-primary) !important;
}

[data-testid="stCheckbox"] input:checked + div {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}

/* ── Dataframe / Table ──────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  overflow: hidden !important;
}

/* ── Expander ───────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
}

[data-testid="stExpander"] summary {
  color: var(--text-primary) !important;
  font-weight: 500 !important;
}

/* ── Alerts / Messages ──────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
  font-family: 'Inter', sans-serif !important;
}

[data-testid="stAlert"][data-baseweb="notification"][kind="error"] {
  background: rgba(255,68,68,0.12) !important;
  border-left: 3px solid var(--anomaly) !important;
}

[data-testid="stAlert"][data-baseweb="notification"][kind="success"] {
  background: rgba(0,200,83,0.12) !important;
  border-left: 3px solid var(--normal) !important;
}

[data-testid="stAlert"][data-baseweb="notification"][kind="warning"] {
  background: rgba(255,171,0,0.12) !important;
  border-left: 3px solid var(--warn) !important;
}

[data-testid="stAlert"][data-baseweb="notification"][kind="info"] {
  background: rgba(0,210,255,0.08) !important;
  border-left: 3px solid var(--accent) !important;
}

/* ── Progress Bar ───────────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
  background: linear-gradient(90deg, var(--accent-dim), var(--accent)) !important;
  border-radius: var(--radius-pill) !important;
}

[data-testid="stProgress"] > div {
  background: var(--bg-elevated) !important;
  border-radius: var(--radius-pill) !important;
}

/* ── Spinner ────────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {
  border-top-color: var(--accent) !important;
}

/* ── JSON viewer ────────────────────────────────────────────────────────────── */
[data-testid="stJson"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
}

/* ── Images ─────────────────────────────────────────────────────────────────── */
[data-testid="stImage"] img {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--border) !important;
}

/* ── Metric ─────────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  padding: 0.8rem 1rem !important;
}

[data-testid="stMetricLabel"] {
  color: var(--text-secondary) !important;
  font-size: 0.78rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}

[data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-size: 1.6rem !important;
  font-weight: 700 !important;
}

/* ── Custom Components (defectsense- prefix) ─────────────────────────────────── */

/* Header bar */
.ds-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 1rem 0 0.6rem 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}

.ds-logo {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, var(--accent-dim), var(--accent));
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.ds-title {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1;
}

.ds-subtitle {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 2px;
  letter-spacing: 0.02em;
}

/* Stats bar */
.ds-stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 1.2rem;
}

/* Stat card */
.ds-stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
  position: relative;
  overflow: hidden;
}

.ds-stat-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 3px; height: 100%;
  background: var(--accent);
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

.ds-stat-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.ds-stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

/* Status pill */
.ds-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  border: 1px solid;
}

.ds-pill-online {
  background: rgba(0,200,83,0.15);
  border-color: var(--normal);
  color: var(--normal);
}

.ds-pill-degraded {
  background: rgba(255,171,0,0.15);
  border-color: var(--warn);
  color: var(--warn);
}

.ds-pill-offline {
  background: rgba(255,68,68,0.15);
  border-color: var(--anomaly);
  color: var(--anomaly);
}

.ds-pill-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

/* Verdict banner */
.ds-verdict {
  width: 100%;
  padding: 1rem 1.4rem;
  border-radius: var(--radius-lg);
  margin-bottom: 1rem;
  border: 1.5px solid;
  display: flex;
  align-items: center;
  gap: 14px;
}

.ds-verdict-anomaly {
  background: var(--anomaly-dim);
  border-color: var(--anomaly);
}

.ds-verdict-normal {
  background: var(--normal-dim);
  border-color: var(--normal);
}

.ds-verdict-icon {
  font-size: 2rem;
  flex-shrink: 0;
}

.ds-verdict-title {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.ds-verdict-sub {
  font-size: 0.82rem;
  opacity: 0.85;
  margin-top: 2px;
}

/* Anomaly pulsing glow animation */
@media (prefers-reduced-motion: no-preference) {
  .ds-verdict-anomaly {
    animation: anomaly-pulse 2.4s ease-in-out infinite;
  }

  @keyframes anomaly-pulse {
    0%, 100% { box-shadow: 0 0 0 0 var(--anomaly-glow); }
    50%       { box-shadow: 0 0 18px 4px var(--anomaly-glow); }
  }
}

/* Score gauge */
.ds-gauge-wrap {
  margin: 0.8rem 0;
}

.ds-gauge-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.ds-gauge-track {
  width: 100%;
  height: 12px;
  background: var(--bg-elevated);
  border-radius: var(--radius-pill);
  position: relative;
  overflow: visible;
  border: 1px solid var(--border);
}

.ds-gauge-fill {
  height: 100%;
  border-radius: var(--radius-pill);
  transition: width 0.4s ease;
  position: relative;
}

.ds-gauge-marker {
  position: absolute;
  top: -4px;
  width: 2px;
  height: 20px;
  background: var(--warn);
  border-radius: 1px;
  transform: translateX(-50%);
  z-index: 2;
}

.ds-gauge-marker-label {
  position: absolute;
  top: 18px;
  transform: translateX(-50%);
  font-size: 0.68rem;
  color: var(--warn);
  white-space: nowrap;
}

/* Score badge */
.ds-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  font-size: 0.78rem;
  font-weight: 700;
  border: 1px solid;
}

.ds-badge-anomaly {
  background: rgba(255,68,68,0.15);
  border-color: var(--anomaly);
  color: var(--anomaly);
}

.ds-badge-normal {
  background: rgba(0,200,83,0.15);
  border-color: var(--normal);
  color: var(--normal);
}

/* Format tags row */
.ds-format-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0.4rem 0;
}

.ds-format-tag {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 500;
  padding: 2px 8px;
  font-family: 'Courier New', monospace;
}

/* Empty state */
.ds-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 1rem;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  text-align: center;
  min-height: 160px;
}

.ds-empty-icon {
  font-size: 2.2rem;
  margin-bottom: 0.6rem;
  opacity: 0.6;
}

.ds-empty-msg {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.ds-empty-sub {
  font-size: 0.8rem;
  color: var(--text-disabled);
  margin-top: 4px;
}

/* History item */
.ds-history-item {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.7rem 1rem;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ds-history-item:hover {
  border-color: var(--border-strong);
  background: var(--bg-elevated);
}

.ds-history-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ds-history-filename {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}

.ds-history-meta {
  font-size: 0.73rem;
  color: var(--text-secondary);
  margin-top: 2px;
}

.ds-history-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Upload zone override */
.ds-upload-zone {
  background: var(--bg-surface) !important;
  border: 1.5px dashed var(--border-strong) !important;
  border-radius: var(--radius-lg) !important;
  padding: 1.5rem !important;
}

/* Section header */
.ds-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.8rem;
}

.ds-section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

/* Metrics row */
.ds-metrics-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 1rem;
}

.ds-metric-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.65rem 0.9rem;
  text-align: center;
}

.ds-metric-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
}

.ds-metric-value {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2px;
}

/* Summary badges row */
.ds-summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0.6rem 0;
}

.ds-summary-badge {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 6px 14px;
  font-size: 0.82rem;
  font-weight: 600;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-dim); }

/* Utility */
.ds-muted { color: var(--text-secondary) !important; }
.ds-accent { color: var(--accent) !important; }
.ds-anomaly-color { color: var(--anomaly) !important; }
.ds-normal-color { color: var(--normal) !important; }
.ds-warn-color { color: var(--warn) !important; }
"""


def inject_styles() -> None:
    """Inject the complete DefectSense dark theme CSS into the current Streamlit page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
