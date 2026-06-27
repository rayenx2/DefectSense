"""AI Optimization modules for DefectSense anomaly detection.

Modules:
    optimizer — Benchmark and optimize models (ONNX, PyTorch)
    registry  — Model version tracking and stage management
    compare   — A/B model comparison with statistical tests
"""

from . import compare, optimizer, registry

__all__ = ["optimizer", "registry", "compare"]
