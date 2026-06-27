# DefectSense API Reference

FastAPI inference backend for DefectSense anomaly detection.

Two server variants exist:

| File | Port | Dependency | Use case |
|---|---|---|---|
| `src/fastapi_app_np.py` | 8080 | ONNX Runtime only | Production (no PyTorch required) |
| `src/fastapi_app.py` | 8000 | ONNX Runtime + PyTorch | Development / fallback |

Both expose the same endpoint surface. Interactive docs are at `/docs` (Swagger UI) and `/redoc` when either server is running.

---

## Model Loading

**`fastapi_app_np.py` (production):** On startup, reads the path from the `MODEL_PATH` environment variable (default: `padim_model.onnx`). If the file does not exist the server starts anyway and returns HTTP 503 on inference requests until a model is placed at the configured path.

**`fastapi_app.py` (dev):** Tries to load `padim_model.onnx` first. Falls back to `distributions/padim_model.pt` (PyTorch) if the ONNX file is not present. Raises a 500 error on startup if neither exists.

---

## Endpoints

### `GET /`

Returns service identity and endpoint listing.

**Response**

```json
{
  "message": "Anomaly Detection API",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "predict": "/predict",
    "batch_predict": "/predict-batch",
    "model_info": "/model-info",
    "config": "/config",
    "docs": "/docs",
    "redoc": "/redoc"
  }
}
```

---

### `GET /health`

Health probe. Returns the current server and model status.

**Response — model loaded**

```json
{
  "status": "healthy",
  "model_type": "onnx",
  "message": "Model loaded",
  "threshold": 24.0,
  "resize_size": [224, 224]
}
```

**Response — model not loaded (`fastapi_app_np.py`)**

```json
{
  "status": "unhealthy",
  "model_type": "none",
  "message": "Model not loaded yet",
  "threshold": 24.0,
  "resize_size": [224, 224]
}
```

`model_type` is `"onnx"` when an ONNX session is active, `"pytorch"` when a PyTorch model is loaded (`fastapi_app.py` only), or `"none"` when no model is loaded.

---

### `POST /predict`

Run anomaly detection on a single image.

**Request**

Content-Type: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file upload | yes | Image file. Accepted MIME types: `image/*`. |
| `include_visualizations` | bool query param | no | Default `true`. Set `false` to skip visualization generation and reduce latency. |

The server accepts any image format that Pillow can decode (JPEG, PNG, BMP, TIFF, WebP). The image is converted to RGB, then passed through the standard preprocessing pipeline (resize to `224×224`, ImageNet normalization).

**Response — 200 OK**

```json
{
  "anomaly_score": 18.42,
  "is_anomaly": true,
  "anomaly_map_base64": "",
  "boundary_image_base64": "<base64-encoded PNG>",
  "heatmap_image_base64": "<base64-encoded PNG>",
  "highlighted_image_base64": ""
}
```

| Field | Type | Description |
|---|---|---|
| `anomaly_score` | float | Scalar anomaly score for the image. Higher means more anomalous. |
| `is_anomaly` | bool | `true` if `anomaly_score >= threshold`. |
| `boundary_image_base64` | string | Original image with a colored border indicating normal/anomalous classification. Empty string if `include_visualizations=false`. |
| `heatmap_image_base64` | string | Heatmap overlay of the anomaly score map on the original image (alpha 0.5). Empty string if `include_visualizations=false`. |
| `highlighted_image_base64` | string | Currently empty in the production server (field reserved). |
| `anomaly_map_base64` | string | Currently empty in the production server (field reserved). |

All base64 fields encode PNG images resized to `224×224`. Decode with `base64.b64decode(value)` and load with any image library.

**Error responses**

| Status | Detail | Cause |
|---|---|---|
| 400 | `"File must be an image"` | Uploaded file MIME type does not start with `image/` |
| 500 | `"No model loaded."` | Model file missing (`fastapi_app.py`) |
| 503 | `"Model not loaded yet"` | Model file missing (`fastapi_app_np.py`) |
| 500 | `"Prediction failed: <detail>"` | Unexpected inference error |

**Example**

```bash
curl -X POST http://localhost:8080/predict \
  -F "file=@bottle_test.jpg" \
  -F "include_visualizations=true"
```

```python
import requests, base64
from PIL import Image
import io

with open("bottle_test.jpg", "rb") as f:
    resp = requests.post(
        "http://localhost:8080/predict",
        files={"file": f},
        params={"include_visualizations": True},
    )

data = resp.json()
print(data["anomaly_score"])    # e.g. 18.42
print(data["is_anomaly"])       # True

if data["heatmap_image_base64"]:
    img = Image.open(io.BytesIO(base64.b64decode(data["heatmap_image_base64"])))
    img.save("heatmap.png")
```

---

### `POST /predict-batch`

Run anomaly detection on multiple images in a single request.

**Request**

Content-Type: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | list of file uploads | yes | Up to 10 image files. |

Maximum 10 files per request. Batch inference does not generate visualizations (equivalent to `include_visualizations=false` for each image).

**Response — 200 OK**

```json
{
  "batch_results": [
    {
      "file_index": 0,
      "filename": "img1.jpg",
      "result": {
        "anomaly_score": 12.1,
        "is_anomaly": false,
        "anomaly_map_base64": "",
        "boundary_image_base64": "",
        "heatmap_image_base64": "",
        "highlighted_image_base64": ""
      }
    },
    {
      "file_index": 1,
      "filename": "img2.jpg",
      "error": "File must be an image"
    }
  ]
}
```

Individual file errors are returned inline in the `error` field — a single failing file does not abort the whole batch.

**Error responses**

| Status | Detail | Cause |
|---|---|---|
| 400 | `"Maximum 10 files per batch"` | More than 10 files submitted |

**Example**

```bash
curl -X POST http://localhost:8080/predict-batch \
  -F "files=@img1.jpg" \
  -F "files=@img2.jpg" \
  -F "files=@img3.jpg"
```

```python
import requests

files = [
    ("files", ("img1.jpg", open("img1.jpg", "rb"), "image/jpeg")),
    ("files", ("img2.jpg", open("img2.jpg", "rb"), "image/jpeg")),
]
resp = requests.post("http://localhost:8080/predict-batch", files=files)
for item in resp.json()["batch_results"]:
    if "error" in item:
        print(f"{item['filename']}: ERROR — {item['error']}")
    else:
        print(f"{item['filename']}: score={item['result']['anomaly_score']:.2f}, anomaly={item['result']['is_anomaly']}")
```

---

### `GET /model-info`

Returns metadata about the currently loaded model.

**Response — ONNX model**

```json
{
  "model_type": "onnx",
  "inputs": [["input", [1, 3, 224, 224], "tensor(float)"]],
  "outputs": [
    ["anomaly_score", [1], "tensor(float)"],
    ["score_maps", [1, 224, 224], "tensor(float)"]
  ],
  "threshold": 24.0
}
```

**Response — PyTorch model (`fastapi_app.py` only)**

```json
{
  "model_type": "pytorch",
  "device": "cpu",
  "threshold": 24.0
}
```

**Error responses**

| Status | Detail | Cause |
|---|---|---|
| 500 | `"No model loaded"` | No model available (`fastapi_app.py`) |
| 503 | `"Model not loaded yet"` | No model available (`fastapi_app_np.py`) |

---

### `POST /config`

Update the anomaly detection threshold and input resize dimensions at runtime without restarting the server.

**Request body (JSON)**

```json
{
  "threshold": 20.0,
  "resize_width": 224,
  "resize_height": 224
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `threshold` | float | `24.0` | Images with `anomaly_score >= threshold` are classified as anomalous. |
| `resize_width` | int | `224` | Width to resize input images before inference. |
| `resize_height` | int | `224` | Height to resize input images before inference. |

**Response — 200 OK**

```json
{
  "message": "Threshold updated to 20.0, Resize size set to (224, 224)"
}
```

**Example**

```bash
curl -X POST http://localhost:8080/config \
  -H "Content-Type: application/json" \
  -d '{"threshold": 20.0, "resize_width": 224, "resize_height": 224}'
```

---

## Default Values

| Parameter | Default | Notes |
|---|---|---|
| `ANOMALY_THRESHOLD` | `24.0` | Server-side default. The Streamlit dashboard defaults to `13.0`. Tune using `defectsense eval`. |
| `RESIZE_SIZE` | `(224, 224)` | Must match the dimensions used at training time. |
| Batch inference max | 10 files | Hard limit enforced by `/predict-batch`. |
| Single predict timeout | 30s | Enforced by the Streamlit client. |
| Batch predict timeout | 60s | Enforced by the Streamlit client. |
| Health probe interval | 30s | Docker `HEALTHCHECK` interval. |

---

## Environment Variables

| Variable | Used by | Description |
|---|---|---|
| `MODEL_PATH` | `fastapi_app_np.py` | Path to the ONNX model file. Default: `padim_model.onnx`. |

---

## Running the Server

```bash
# Production (ONNX-only)
MODEL_PATH=./models/padim_model.onnx \
  python -m uvicorn src.fastapi_app_np:app --host 0.0.0.0 --port 8080

# Development (ONNX + PyTorch fallback)
python -m uvicorn src.fastapi_app:app --host 0.0.0.0 --port 8000 --reload

# Via Docker Compose
docker compose up fastapi
```

---

## ONNX Model Contract

The ONNX model must expose exactly two outputs:

- Output 0: scalar anomaly score for each image in the batch — shape `(batch_size,)`
- Output 1: spatial score map per image — shape `(batch_size, H, W)`

The production server (`fastapi_app_np.py`) errors with HTTP 500 if fewer than two outputs are present.
