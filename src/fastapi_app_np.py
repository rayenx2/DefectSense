from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import onnxruntime as ort
from onnxruntime import SessionOptions, GraphOptimizationLevel
import multiprocessing
import numpy as np
from PIL import Image
import io
import base64
import cv2
import os
import json as _json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
import static.anodet as anodet


# ── Registry helpers ──────────────────────────────────────────────────────────

def _registry_path() -> str:
    model_path = os.getenv("MODEL_PATH", "padim_model.onnx")
    return os.path.join(os.path.dirname(os.path.abspath(model_path)), "model_registry.json")

def _load_reg() -> dict:
    p = _registry_path()
    if os.path.exists(p):
        with open(p) as f:
            return _json.load(f)
    return {"entries": {}, "history": [], "created_at": datetime.now().isoformat()}

def _save_reg(data: dict) -> None:
    p = _registry_path()
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        _json.dump(data, f, indent=2, default=str)
    os.replace(tmp, p)

def _seed_registry() -> None:
    """Register padim_model.onnx as production on first startup."""
    reg = _load_reg()
    if reg["entries"]:
        return
    model_path = os.getenv("MODEL_PATH", "padim_model.onnx")
    if not os.path.exists(model_path):
        return
    try:
        size_mb = round(os.path.getsize(model_path) / (1024 * 1024), 2)
        entry_id = "padim_model.onnx__initial"
        reg["entries"][entry_id] = {
            "id": entry_id,
            "filename": "padim_model.onnx",
            "file_size_mb": size_mb,
            "stage": "production",
            "registered_at": datetime.now().isoformat(),
            "metadata": {"backbone": "resnet18", "auroc": 0.850, "pixel_auroc": 0.956},
            "previous_stages": [],
            "version": 1,
        }
        reg["history"].append({
            "action": "register",
            "entry_id": entry_id,
            "filename": "padim_model.onnx",
            "stage": "production",
            "timestamp": datetime.now().isoformat(),
        })
        _save_reg(reg)
        print("Registry seeded with padim_model.onnx [production]")
    except Exception as e:
        print(f"Registry seed failed: {e}")


# Global variables
sess = None
ANOMALY_THRESHOLD = 24.0
RESIZE_SIZE = (224, 224)

async def load_model():
    global sess
    _seed_registry()
    model_path = os.getenv("MODEL_PATH", "padim_model.onnx")
    if not os.path.exists(model_path):
        print(f"WARNING: model file '{model_path}' not found — API starting without a model.")
        print("Place padim_model.onnx in the models/ folder to enable predictions.")
        return
    try:
        available_providers = ort.get_available_providers()
        use_gpu = "CUDAExecutionProvider" in available_providers

        sess_options = SessionOptions()
        sess_options.enable_mem_pattern = True
        sess_options.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_EXTENDED

        if not use_gpu:
            sess_options.enable_cpu_mem_arena = True
            sess_options.intra_op_num_threads = multiprocessing.cpu_count()

        providers = ["CUDAExecutionProvider"] if use_gpu else ["CPUExecutionProvider"]
        sess = ort.InferenceSession(model_path, providers=providers, sess_options=sess_options)
        print(f"ONNX model loaded from '{model_path}'.")
    except Exception as e:
        print(f"WARNING: failed to load model: {e} — API starting without a model.")

async def cleanup():
    global sess
    sess = None
    print("Model cleanup completed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await load_model()
    yield
    # Shutdown
    await cleanup()

app = FastAPI(title="Anomaly Detection API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React SPA — clean top-level URLs (/analyze, /batch, …)
# Static assets still served from /ui/ path to avoid collisions with API routes
_UI_DIR = os.path.join(os.path.dirname(__file__), "static", "ui")
_SPA_ROUTES = ["analyze", "batch", "history", "model", "bench", "registry", "about"]

def _spa():
    return FileResponse(os.path.join(_UI_DIR, "index.html"))

# Redirect legacy /ui paths → /analyze
@app.get("/ui", include_in_schema=False)
@app.get("/ui/", include_in_schema=False)
async def ui_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/analyze", status_code=301)

# Static assets (JS/CSS files) still live at /ui/<file>
@app.get("/ui/{path:path}", include_in_schema=False)
async def ui_static(path: str):
    file_path = os.path.join(_UI_DIR, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return _spa()

# Top-level SPA routes
for _route in _SPA_ROUTES:
    app.add_api_route(f"/{_route}", _spa, include_in_schema=False)
    app.add_api_route(f"/{_route}/", _spa, include_in_schema=False)

class PredictionResult(BaseModel):
    anomaly_score: float
    is_anomaly: bool
    anomaly_map_base64: Optional[str] = ""
    boundary_image_base64: Optional[str] = ""
    heatmap_image_base64: Optional[str] = ""
    highlighted_image_base64: Optional[str] = ""

class ConfigModel(BaseModel):
    threshold: float = ANOMALY_THRESHOLD
    resize_width: int = 224
    resize_height: int = 224

@app.get("/")
async def root():
    return {
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

@app.get("/health")
async def health_check():
    model_loaded = sess is not None
    return {
        "status": "healthy" if model_loaded else "unhealthy",
        "model_type": "onnx" if sess else "none",
        "message": "Model loaded" if model_loaded else "Model not loaded yet",
        "threshold": ANOMALY_THRESHOLD,
        "resize_size": RESIZE_SIZE
    }

@app.post("/config")
async def update_config(config: ConfigModel):
    global ANOMALY_THRESHOLD, RESIZE_SIZE
    ANOMALY_THRESHOLD = config.threshold
    RESIZE_SIZE = (config.resize_width, config.resize_height)
    return {
        "message": f"Threshold updated to {ANOMALY_THRESHOLD}, Resize size set to {RESIZE_SIZE}"
    }

def preprocess_image_from_upload(file_contents: bytes) -> np.ndarray:
    """Convert uploaded file to numpy array matching detect.py preprocessing"""
    # Read image using PIL and convert to RGB
    image_pil = Image.open(io.BytesIO(file_contents)).convert("RGB")

    # Convert PIL to numpy array (this matches how detect.py reads with cv2 then converts to RGB)
    image_np = np.array(image_pil)

    return image_np

def create_visualizations(image_np: np.ndarray, score_maps: np.ndarray, image_scores: np.ndarray) -> tuple:
    """Create visualization images using NumPy arrays (torch-free)."""
    try:
        print("Creating visualizations...")

        # Apply classification using NumPy
        score_map_classifications = anodet.classification(score_maps, ANOMALY_THRESHOLD)
        image_classifications = anodet.classification(image_scores, ANOMALY_THRESHOLD)

        # Prepare image array
        test_images = np.array([image_np])

        # Create visualizations
        boundary_images = anodet.visualization.framed_boundary_images(
            test_images,
            score_map_classifications,
            image_classifications,
            padding=40
        )

        heatmap_images = anodet.visualization.heatmap_images(
            test_images,
            score_maps,
            alpha=0.5
        )

        highlighted_images = anodet.visualization.highlighted_images(
            [image_np],
            score_map_classifications,
            color=(128, 0, 128)
        )

        print("All visualizations created successfully")

        return boundary_images[0], heatmap_images[0], highlighted_images[0]

    except Exception as e:
        print(f"Visualization error: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def numpy_to_base64(image_array: np.ndarray, resize_to: tuple[int, int] = None) -> str:
    """Convert numpy array to base64-encoded PNG, optionally resized"""
    if image_array is None:
        return ""

    try:
        # Ensure the array is in the right format (0-255 uint8)
        if image_array.dtype != np.uint8:
            # Handle different data ranges
            if image_array.max() <= 1.0:
                image_array = (image_array * 255).astype(np.uint8)
            else:
                image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        # Convert to PIL Image
        image = Image.fromarray(image_array)
        if resize_to is not None:
            image = image.resize(resize_to, Image.BILINEAR)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error converting to base64: {e}")
        return ""

@app.post("/predict", response_model=PredictionResult)
async def predict_anomaly(
    file: UploadFile = File(...),
    include_visualizations: bool = True
):
    if sess is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Read and preprocess image exactly like detect.py
        contents = await file.read()
        image_np = preprocess_image_from_upload(contents)

        print(f"Image shape: {image_np.shape}")
        print(f"Image dtype: {image_np.dtype}")

        if sess is not None:
            # ONNX inference - convert single image to batch
            batch = anodet.to_batch([image_np])
            input_numpy = batch

            input_name = sess.get_inputs()[0].name
            output_names = [output.name for output in sess.get_outputs()]

            if len(output_names) < 2:
                raise HTTPException(status_code=500, detail="Model must have at least 2 outputs")

            outputs = sess.run(output_names, {input_name: input_numpy})

            image_scores = np.array([outputs[0]])
            score_maps = np.array(outputs[1])


        print(f"Image scores: {image_scores}")
        print(f"Score maps shape: {score_maps.shape}")

        # Get single values
        anomaly_score = float(image_scores[0])
        is_anomaly = anomaly_score >= ANOMALY_THRESHOLD

        # Create anomaly map (normalized score map)
        # score_map_np = score_maps[0]
        # score_map_normalized = score_map_np.copy()

        # if score_map_np.max() - score_map_np.min() > 0:
        #     score_map_normalized = (score_map_np - score_map_np.min()) / (score_map_np.max() - score_map_np.min())
        # else:
        #     score_map_normalized = np.zeros_like(score_map_np)

        # anomaly_map_base64 = numpy_to_base64(score_map_normalized,RESIZE_SIZE)

        # Initialize visualization base64 strings
        boundary_image_base64 = ""
        heatmap_image_base64 = ""
        highlighted_image_base64 = ""

        if include_visualizations:
            print("Creating visualizations...")
            boundary_image, heatmap_image, highlighted_image = create_visualizations(
                image_np, score_maps, image_scores
            )

            if boundary_image is not None:
                boundary_image_base64 = numpy_to_base64(boundary_image,RESIZE_SIZE)
                print("✓ Boundary image created")
            else:
                print("❗ Boundary image is None")

            if heatmap_image is not None:
                heatmap_image_base64 = numpy_to_base64(heatmap_image,RESIZE_SIZE)
                print("✓ Heatmap image created")
            else:
                print("❗ Heatmap image is None")

            # if highlighted_image is not None:
            #     highlighted_image_base64 = numpy_to_base64(highlighted_image,RESIZE_SIZE)
            #     print("✓ Highlighted image created")
            # else:
            #     print("❗ Highlighted image is None")

        return PredictionResult(
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            # anomaly_map_base64=anomaly_map_base64,
            boundary_image_base64=boundary_image_base64,
            heatmap_image_base64=heatmap_image_base64,
            # highlighted_image_base64=highlighted_image_base64
        )

    except Exception as e:
        print(f"Prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/predict-batch")
async def predict_batch(files: list[UploadFile] = File(...)):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch")

    results = []
    for i, file in enumerate(files):
        try:
            result = await predict_anomaly(file, include_visualizations=False)
            results.append({
                "file_index": i,
                "filename": file.filename,
                "result": result
            })
        except Exception as e:
            results.append({
                "file_index": i,
                "filename": file.filename,
                "error": str(e)
            })

    return {"batch_results": results}

@app.get("/model-info")
async def get_model_info():
    """Get information about the loaded model"""
    if sess is not None:
        inputs = [(inp.name, inp.shape, inp.type) for inp in sess.get_inputs()]
        outputs = [(out.name, out.shape, out.type) for out in sess.get_outputs()]
        return {
            "model_type": "onnx",
            "inputs": inputs,
            "outputs": outputs,
            "threshold": ANOMALY_THRESHOLD
        }

    else:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

# ── Registry endpoints ────────────────────────────────────────────────────────

@app.get("/registry")
async def list_registry():
    reg = _load_reg()
    entries = sorted(reg["entries"].values(), key=lambda e: e["version"])
    return {"entries": entries, "created_at": reg.get("created_at")}

@app.get("/registry/history")
async def registry_history():
    reg = _load_reg()
    return {"history": reg["history"][-20:][::-1]}

class PromoteRequest(BaseModel):
    filename: str
    target_stage: str

@app.post("/registry/promote")
async def promote_model(req: PromoteRequest):
    valid = ("staging", "production", "archived")
    if req.target_stage not in valid:
        raise HTTPException(400, f"Invalid stage. Use one of {valid}")
    reg = _load_reg()
    entry_id, entry = None, None
    for eid, e in reg["entries"].items():
        if e["filename"] == req.filename:
            entry_id, entry = eid, e
            break
    if entry is None:
        raise HTTPException(404, f"Model '{req.filename}' not found")
    old_stage = entry["stage"]
    if old_stage == req.target_stage:
        return {"message": f"Already at '{req.target_stage}'", "entry": entry}
    entry["previous_stages"].append({"stage": old_stage, "moved_at": datetime.now().isoformat()})
    if req.target_stage == "production":
        for eid, e in reg["entries"].items():
            if e["stage"] == "production" and eid != entry_id:
                e["stage"] = "archived"
                e["previous_stages"].append({"stage": "production", "moved_at": datetime.now().isoformat(), "reason": "superseded"})
    entry["stage"] = req.target_stage
    reg["history"].append({"action": "promote", "entry_id": entry_id, "filename": req.filename, "from_stage": old_stage, "to_stage": req.target_stage, "timestamp": datetime.now().isoformat()})
    _save_reg(reg)
    return {"message": f"Promoted '{req.filename}': {old_stage} → {req.target_stage}", "entry": entry}

@app.post("/registry/rollback")
async def rollback_registry():
    reg = _load_reg()
    prod_id, prod = None, None
    for eid, e in reg["entries"].items():
        if e["stage"] == "production":
            prod_id, prod = eid, e
            break
    if prod is None:
        raise HTTPException(404, "No production model to rollback from")
    archived = [e for e in reg["entries"].values() if e["stage"] == "archived"]
    if not archived:
        raise HTTPException(404, "No archived models to rollback to")
    archived.sort(key=lambda e: e["previous_stages"][-1]["moved_at"] if e["previous_stages"] else "", reverse=True)
    restored = archived[0]
    prod["stage"] = "archived"
    restored["stage"] = "production"
    restored["previous_stages"].append({"stage": "archived", "moved_at": datetime.now().isoformat(), "reason": "rollback"})
    reg["history"].append({"action": "rollback", "rolled_back_id": prod_id, "restored_id": restored["id"], "stage": "production", "timestamp": datetime.now().isoformat()})
    _save_reg(reg)
    return {"message": f"Rollback: '{restored['filename']}' restored to production", "entry": restored}

@app.get("/registry/export")
async def export_registry():
    reg = _load_reg()
    return JSONResponse(content=reg, headers={"Content-Disposition": "attachment; filename=model_registry.json"})


if __name__ == "__main__":
    uvicorn.run("fastapi_app_np:app", host="0.0.0.0", port=8080, reload=False)
# run that from the Docker image,  see docker\Dockerfile.np



