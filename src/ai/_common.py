"""Shared helpers for the DefectSense AI optimization package.

Centralizes logging setup, project-path resolution, optional-dependency
probing and small numeric utilities used across optimizer/export/evaluation/
compare/registry modules. Keeps each public module DRY and within size limits.
"""

from __future__ import annotations

import importlib.util
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# This file lives at <project>/src/ai/_common.py
SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
MODELS_DIR = PROJECT_ROOT / "models"
OPTIMIZED_DIR = MODELS_DIR / "optimized"
REGISTRY_DIR = MODELS_DIR / "registry"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_size_mb(path: Path | str) -> float:
    """Return the size of ``path`` in megabytes (0.0 if it does not exist).

    For ONNX models with external weights (``*.onnx.data``) the companion
    file size is included so reported sizes reflect the full on-disk model.
    """
    p = Path(path)
    if not p.exists():
        return 0.0
    total = p.stat().st_size
    data_file = p.with_suffix(p.suffix + ".data")
    if data_file.exists():
        total += data_file.stat().st_size
    return total / (1024 * 1024)


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def get_logger(name: str = "defectsense.ai", level: int = logging.INFO) -> logging.Logger:
    """Return a configured module logger with a single stream handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


# --------------------------------------------------------------------------- #
# Optional dependency probing
# --------------------------------------------------------------------------- #
def has_module(module_name: str) -> bool:
    """Return True if ``module_name`` can be imported without importing it."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #
@contextmanager
def timed(logger: Optional[logging.Logger] = None, label: str = "step") -> Iterator[dict]:
    """Context manager measuring wall-clock time.

    Yields a mutable dict; on exit ``result["seconds"]`` holds the duration.

    Example:
        >>> with timed(label="export") as t:
        ...     do_work()
        >>> print(t["seconds"])
    """
    result: dict = {"seconds": 0.0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - start
        if logger is not None:
            logger.info("%s done in %.3fs", label, result["seconds"])
