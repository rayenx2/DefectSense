"""Train a real PaDiM model on MVTec bottle/train/good and export to ONNX.

Produces models/padim_model.onnx compatible with fastapi_app_np.py:
  input  : float32 [N,3,224,224]  (ImageNet-normalized, as anodet.to_batch does)
  output_0: image_scores [N]
  output_1: score_map    [N,224,224]
"""
import logging
import os
from pathlib import Path

import torch
from torch.utils.data import DataLoader

import defectsense
from defectsense import Padim
from defectsense.export import ModelExporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("train_bottle")

DATA = "/home/rayen/data/mvtec/bottle/train/good"
OUT_DIR = Path("/home/rayen/portfolio/deep-learning/industrial-anomaly-detection/models")
STATS_PATH = OUT_DIR / "padim_bottle.pth"
ONNX_NAME = "padim_model.onnx"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info("Device: %s", device)

# 1) Dataset — defaults: resize=224, crop=224, ImageNet normalize (matches to_batch)
ds = anomavision.AnodetDataset(DATA)
logger.info("Training images: %d", len(ds))
dl = DataLoader(ds, batch_size=4, shuffle=False)

# 2) Fit PaDiM (resnet18, layers [0,1], feat_dim 50)
padim = Padim(backbone="resnet18", device=device, layer_indices=[0, 1], feat_dim=50)
logger.info("Fitting PaDiM ...")
padim.fit(dl)
logger.info("Fit complete.")

# 3) Save statistics (.pth) in FP32 for portable CPU ONNX export
OUT_DIR.mkdir(parents=True, exist_ok=True)
padim.save_statistics(str(STATS_PATH), half=False)
logger.info("Saved stats -> %s", STATS_PATH)

# 4) Export to ONNX
exporter = ModelExporter(model_path=STATS_PATH, output_dir=OUT_DIR, logger=logger, device="cpu")
exporter.export_onnx(
    input_shape=(1, 3, 224, 224),
    output_name=ONNX_NAME,
    opset_version=17,
    dynamic_batch=True,
)
logger.info("Exported ONNX -> %s", OUT_DIR / ONNX_NAME)
print("TRAIN_EXPORT_COMPLETE")
