# DefectSense Dashboard — User Guide

The DefectSense Streamlit dashboard (`src/streamlit_app_v2.py`) is the primary user-facing interface for running anomaly detection, reviewing results, and managing model versions. It communicates exclusively with the FastAPI backend via HTTP.

---

## Starting the Dashboard

The dashboard requires the FastAPI backend to be running before it can perform any inference. Start both in order:

**With Docker Compose (recommended):**

```bash
docker compose up --build
```

- FastAPI: `http://localhost:8080`
- Dashboard: `http://localhost:8501`

**Manually:**

```bash
# Terminal 1 — backend
MODEL_PATH=./models/padim_model.onnx \
  python -m uvicorn src.fastapi_app_np:app --host 0.0.0.0 --port 8080

# Terminal 2 — dashboard
streamlit run src/streamlit_app_v2.py --server.port 8501 -- --host localhost --port 8080
```

**Dashboard CLI arguments** (passed after `--`):

| Argument | Default | Description |
|---|---|---|
| `--host` | `localhost` | Hostname of the FastAPI backend |
| `--port` | `8080` | Port of the FastAPI backend |

---

## Layout Overview

The dashboard has a persistent sidebar and six tabs in the main content area:

```
┌────────────────┬──────────────────────────────────────────────────────┐
│   Sidebar      │  [Analysis] [Batch] [History] [Model Info]           │
│                │  [Benchmark] [Registry]                               │
│ Configuration  │                                                       │
│ ─────────────  │  (tab content here)                                  │
│ Backend conn.  │                                                       │
│ Threshold      │                                                       │
│ Preprocessing  │                                                       │
│ Model Info     │                                                       │
└────────────────┴──────────────────────────────────────────────────────┘
```

---

## Sidebar

### Backend Connection

Displays the configured backend URL and a "Ping" button. The button calls `GET /health` and shows either "API ONLINE" or "API OFFLINE".

- If the API is offline, all inference buttons are disabled.
- The health check also runs automatically on page load and refreshes every 10 seconds.

### Detection Threshold

A slider from `0.1` to `50.0` (step `0.1`). This is the anomaly score cutoff — images scoring at or above the threshold are classified as anomalous.

The default threshold after server start is `24.0`. The slider starts at the value last reported by `GET /health`.

### Preprocessing

Width and height fields for input resize dimensions (32–1024 px, step 8). Must match the dimensions used at training time. Default: `224 × 224`.

### Apply Config

Sends a `POST /config` request with the current threshold and resize dimensions. The sidebar shows a success message or an error if the backend is unreachable.

### Model Info expander

Shows the model type, current threshold, input dimensions, and backend URL as read from session state.

---

## Tab 1: Analysis

Single-image anomaly detection.

### Upload and analyze

1. Click "Drag & drop or click to browse" or drag an image file onto the upload widget. Accepted formats: JPG, JPEG, PNG, BMP, TIFF.
2. A preview of the uploaded image appears.
3. Click **Analyze Image**. The button is disabled when the API is offline.
4. Results appear in the right column.

### Result display

**Verdict banner:** Shows "ANOMALY DETECTED" or "NORMAL" in color, with the exact score and threshold.

**Score gauge:** A progress bar scaled to `min(score / max_score, 1.0)` where `max_score = max(50.0, threshold × 1.3)`.

**Inference time:** Displayed in milliseconds, measured client-side from POST to response.

**Visualization tabs:** Three sub-tabs appear when the backend returns visualization data:

- **Heatmap** — anomaly score map overlaid on the original image (alpha 0.5). Bright regions indicate detected anomalies.
- **Boundary** — original image with a colored border frame. Green border = normal, red/colored border = anomaly.
- **Side-by-Side** — original image and heatmap displayed next to each other for direct comparison.

If `include_visualizations` is disabled on the backend, the tabs show "Heatmap not available" / "Boundary visualisation not available".

**Download Result JSON:** Exports the raw inference result (score, is_anomaly) as a timestamped JSON file. Base64 image fields are excluded from the download.

Every analysis is automatically appended to the History tab (up to 50 entries per session).

---

## Tab 2: Batch

Analyze up to 10 images in a single request.

### Workflow

1. Click the upload widget and select multiple image files (JPG, JPEG, PNG, BMP, TIFF).
2. If more than 10 files are selected, only the first 10 are used. A warning is shown.
3. Click **Run Batch (N files)**. A progress bar shows submission and processing stages.
4. Results are displayed in a table and appended to History.

### Results table

| Column | Description |
|---|---|
| File | Original filename |
| Score | Anomaly score (4 decimal places) |
| Class | `NORMAL` or `ANOMALY` |
| Latency (s) | Estimated per-image time (total elapsed / batch size) |
| Error | Any per-file error message. Empty if successful. |

Individual file errors do not stop the batch — they appear in the Error column.

### Export options

After a batch run, three export buttons appear:

- **Download CSV** — table as a `.csv` file.
- **Download JSON** — full batch result as `.json`.
- A third option for custom formats (if configured).

---

## Tab 3: History

Session-level log of all analyses (single and batch). Holds up to 50 entries per session.

Each history item shows:

- Filename
- Anomaly score
- Classification (NORMAL / ANOMALY)
- Timestamp (HH:MM:SS)
- Inference latency

A **Clear History** button removes all entries from the current session. History is not persisted across page reloads.

---

## Tab 4: Model Info

Calls `GET /model-info` and displays the raw response.

**ONNX model:** Shows model type, input tensor names/shapes/dtypes, output tensor names/shapes/dtypes, and the active threshold.

**PyTorch model** (when using `fastapi_app.py`): Shows model type, device, and threshold.

If no model is loaded the tab shows the HTTP error detail.

---

## Tab 5: Benchmark

Runs a local benchmarking sequence using `src/ai/optimizer.py`. Measures inference latency and throughput for the loaded model across multiple configurations.

Results are displayed as a table and, optionally, comparison charts. The benchmark tab does not call the FastAPI `/predict` endpoint — it benchmarks the ONNX Runtime session directly from the dashboard process.

---

## Tab 6: Registry

Displays and manages the model version registry stored at `models/model_registry.json` (populated by `src/ai/registry.py`).

### What it shows

- Stage summary badges: count of models in `staging`, `production`, and `archived` stages.
- One expandable entry per registered model, showing:
  - Version number, filename, stage, file size
  - Registration timestamp
  - Metadata (backbone, AUROC, or any key/value passed at registration)
  - Registry entry ID

### Stage actions

Each model entry has action buttons depending on its current stage:

| Button | Visible when | Effect |
|---|---|---|
| Promote → Production | stage is not `production` | Moves model to `production` stage |
| Archive | stage is `production` | Moves model to `archived` stage |
| Restore → Staging | stage is `archived` | Moves model back to `staging` stage |

Stage transitions are written immediately to `models/model_registry.json` and the page refreshes.

### Registering new models

If `models/model_registry.json` does not exist, the Registry tab shows a "Initialize Registry" button. Click it to scan the `models/` directory for `.onnx`, `.pt`, and `.pth` files and register them all at the `staging` stage.

### Programmatic registration

```python
from ai.registry import ModelRegistry

reg = ModelRegistry("./models")

# Register a new model (optional metadata dict)
reg.register("padim_v2.onnx", {"backbone": "resnet18", "auroc": 0.95})

# Promote to production
reg.promote("padim_v2.onnx", "production")

# Get the current production model entry
current = reg.get_current("production")

# Roll back to the previous production model
reg.rollback("production")
```

---

## Session State Reference

These keys are maintained in `st.session_state` throughout a session:

| Key | Type | Description |
|---|---|---|
| `api_online` | bool | Whether `GET /health` returned `status: healthy` |
| `model_type` | str | Model type string from `/health` (`onnx`, `pytorch`, `unknown`) |
| `current_threshold` | float | Threshold last confirmed by the backend |
| `resize_dims` | tuple | `(width, height)` last confirmed by the backend |
| `analysis_result` | dict or None | Last single-image inference result |
| `analysis_time` | float | Elapsed seconds for the last single inference |
| `analysis_filename` | str | Filename of the last uploaded image |
| `analysis_image_bytes` | bytes or None | Raw bytes of the last uploaded image |
| `batch_results` | list | Results from the last batch run |
| `history` | list | All inference entries this session (max 50) |
| `session_analyses` | int | Total analyses run this session |

---

## Troubleshooting

**"API OFFLINE" despite the backend running**

Verify the `--host` and `--port` arguments match the actual backend address. If running both services in Docker Compose, use `--host fastapi --port 8080` (service name, not `localhost`).

**"Analyze Image" button is disabled**

The button only activates when `api_online` is `true`. Click "Ping" in the sidebar to force a health check.

**Visualization tabs show "not available"**

The backend returns empty base64 strings when `include_visualizations` is `false` (e.g. in batch mode or if an exception occurred in visualization generation). For single-image analysis this should not happen unless the backend logs show a visualization error.

**Scores are always low / nothing is detected**

The default threshold of `24.0` may be too high for a model trained with `--threshold 13.0`. Adjust the threshold slider in the sidebar and click "Apply Config". Use `defectsense eval` to inspect the score distribution for your dataset before choosing a production threshold.

**"Config update failed"**

The `POST /config` endpoint returns an error if the backend is restarting or the model is not yet loaded. Wait a moment and try again.

**Batch request timed out**

The Streamlit client enforces a 60-second timeout on batch requests. For large images or a slow CPU backend, reduce the batch size or disable visualizations.
