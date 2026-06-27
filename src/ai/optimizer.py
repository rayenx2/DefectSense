"""
Model optimizer and benchmark tool for DefectSense anomaly detection.

Benchmarks ONNX and PyTorch models, applies ONNX Runtime optimizations,
and generates comparison reports. Builds on top of the existing
defectsense.export module.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Optional dependency handling ──────────────────────────────────
_ONNX_AVAILABLE = True
_ONNXRT_AVAILABLE = True
_TORCH_AVAILABLE = True

try:
    import onnx
except ImportError:
    _ONNX_AVAILABLE = False

try:
    import onnxruntime as ort
except ImportError:
    _ONNXRT_AVAILABLE = False

try:
    import torch
except ImportError:
    _TORCH_AVAILABLE = False


# ── Benchmark utilities ──────────────────────────────────────────

def _percentile(data: np.ndarray, p: float) -> float:
    """Compute percentile of numpy array."""
    return float(np.percentile(data, p))


def benchmark_onnx(
    model_path: str,
    input_shape: Tuple[int, int, int, int] = (1, 3, 224, 224),
    num_runs: int = 100,
    warmup_runs: int = 10,
    providers: Optional[List[str]] = None,
) -> Dict:
    """Benchmark ONNX model inference performance.

    Args:
        model_path: Path to .onnx model file.
        input_shape: Input tensor shape (B, C, H, W).
        num_runs: Number of inference runs for measurement.
        warmup_runs: Warmup runs (excluded from stats).
        providers: ONNX Runtime execution providers. Auto-detect if None.

    Returns:
        Dict with latency (ms) stats, throughput (fps), model size (MB).
    """
    if not _ONNXRT_AVAILABLE:
        return {"error": "onnxruntime not installed"}

    if providers is None:
        available = ort.get_available_providers()
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "CUDAExecutionProvider" in available
            else ["CPUExecutionProvider"]
        )

    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    session = ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)
    input_name = session.get_inputs()[0].name

    dummy = np.random.randn(*input_shape).astype(np.float32)

    # Warmup
    for _ in range(warmup_runs):
        session.run(None, {input_name: dummy})

    # Measure
    latencies = []
    for _ in range(num_runs):
        t0 = time.perf_counter()
        session.run(None, {input_name: dummy})
        latencies.append((time.perf_counter() - t0) * 1000)  # ms

    latencies = np.array(latencies)
    model_size_mb = os.path.getsize(model_path) / (1024 * 1024)

    return {
        "model_path": model_path,
        "model_size_mb": round(model_size_mb, 2),
        "provider": providers[0],
        "mean_ms": round(float(latencies.mean()), 2),
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "p99_ms": round(_percentile(latencies, 99), 2),
        "min_ms": round(float(latencies.min()), 2),
        "max_ms": round(float(latencies.max()), 2),
        "fps": round(1000.0 / float(latencies.mean()), 1),
        "num_runs": num_runs,
    }


def benchmark_pytorch(
    model_path: str,
    input_shape: Tuple[int, int, int, int] = (1, 3, 224, 224),
    num_runs: int = 100,
    warmup_runs: int = 10,
    device: Optional[str] = None,
) -> Dict:
    """Benchmark PyTorch model inference performance.

    Args:
        model_path: Path to .pt or .pth model file.
        input_shape: Input tensor shape (B, C, H, W).
        num_runs: Number of inference runs.
        warmup_runs: Warmup runs (excluded).
        device: 'cpu', 'cuda', or None (auto-detect).

    Returns:
        Dict with latency stats, throughput, model info.
    """
    if not _TORCH_AVAILABLE:
        return {"error": "torch not installed"}

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = torch.load(model_path, map_location=device, weights_only=False)

    # Handle stats-only dicts (PadimLite)
    if isinstance(model, dict) and "mean" in model:
        # Need to build PadimLite — use defectsense if available
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "DefectSense"))
            from defectsense.padim_lite import build_padim_from_stats
            model = build_padim_from_stats(model, device=device)
        except ImportError:
            return {"error": "Cannot build PadimLite from stats — defectsense not available"}

    if hasattr(model, "eval"):
        model.eval()

    dummy = torch.randn(*input_shape, device=device)

    # Warmup
    with torch.no_grad():
        for _ in range(warmup_runs):
            _ = model.predict(dummy) if hasattr(model, "predict") else model(dummy)

    # Measure
    latencies = []
    with torch.no_grad():
        for _ in range(num_runs):
            t0 = time.perf_counter()
            _ = model.predict(dummy) if hasattr(model, "predict") else model(dummy)
            latencies.append((time.perf_counter() - t0) * 1000)

    latencies = np.array(latencies)
    model_size_mb = os.path.getsize(model_path) / (1024 * 1024)

    return {
        "model_path": model_path,
        "model_size_mb": round(model_size_mb, 2),
        "device": device,
        "mean_ms": round(float(latencies.mean()), 2),
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "p99_ms": round(_percentile(latencies, 99), 2),
        "min_ms": round(float(latencies.min()), 2),
        "max_ms": round(float(latencies.max()), 2),
        "fps": round(1000.0 / float(latencies.mean()), 1),
        "num_runs": num_runs,
    }


# ── ONNX optimization ────────────────────────────────────────────

def optimize_onnx_graph(
    model_path: str,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Apply ONNX Runtime graph-level optimizations.

    Performs constant folding, node fusion, and extended optimizations
    using ONNX Runtime's graph optimization passes. Returns path to
    optimized model.

    Args:
        model_path: Path to input ONNX model.
        output_path: Output path. Defaults to adding '_opt' suffix.

    Returns:
        Path to optimized model, or None on failure.
    """
    if not _ONNXRT_AVAILABLE or not _ONNX_AVAILABLE:
        print("onnx/onnxruntime not installed — skipping graph optimization")
        return None

    if output_path is None:
        stem = Path(model_path).stem
        output_path = str(Path(model_path).with_name(f"{stem}_opt.onnx"))

    try:
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.optimized_model_filepath = output_path

        # Force optimization by creating session with dummy input
        session = ort.InferenceSession(model_path, sess_options=sess_options)
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        dummy_shape = tuple(1 if isinstance(d, str) or d is None else d for d in input_shape)
        dummy = np.random.randn(*dummy_shape).astype(np.float32)
        session.run(None, {input_name: dummy})

        if os.path.exists(output_path):
            orig_size = os.path.getsize(model_path) / 1024
            opt_size = os.path.getsize(output_path) / 1024
            print(f"Optimized ONNX: {orig_size:.1f}KB → {opt_size:.1f}KB → {output_path}")
            return output_path
        else:
            print("Optimization produced no output file")
            return None
    except Exception as e:
        print(f"ONNX graph optimization failed: {e}")
        return None


def quantize_onnx_dynamic(
    model_path: str,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Apply dynamic INT8 quantization to ONNX model.

    Args:
        model_path: Path to input ONNX model.
        output_path: Output path. Defaults to adding '_int8' suffix.

    Returns:
        Path to quantized model, or None on failure.
    """
    if not _ONNXRT_AVAILABLE:
        print("onnxruntime not installed — skipping quantization")
        return None

    if output_path is None:
        stem = Path(model_path).stem
        output_path = str(Path(model_path).with_name(f"{stem}_int8.onnx"))

    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(model_path, output_path, weight_type=QuantType.QInt8)

        if os.path.exists(output_path):
            orig_size = os.path.getsize(model_path) / 1024
            q_size = os.path.getsize(output_path) / 1024
            print(f"INT8 quantized: {orig_size:.1f}KB → {q_size:.1f}KB → {output_path}")
            return output_path
        return None
    except ImportError:
        print("onnxruntime.quantization not available")
        return None
    except Exception as e:
        print(f"INT8 quantization failed: {e}")
        return None


# ── Comparison runner ─────────────────────────────────────────────

def run_optimization_pipeline(
    model_dir: str,
    output_dir: Optional[str] = None,
    input_shape: Tuple[int, int, int, int] = (1, 3, 224, 224),
    num_benchmark_runs: int = 50,
) -> Dict:
    """Run full optimization pipeline: benchmark → optimize → compare.

    Scans model_dir for .onnx and .pt/.pth files, benchmarks each,
    applies optimizations, benchmarks again, and returns comparison.

    Args:
        model_dir: Directory containing model files.
        output_dir: Directory for optimized models. Defaults to model_dir/optimized.
        input_shape: Input tensor shape for benchmarking.
        num_benchmark_runs: Number of benchmark iterations.

    Returns:
        Dict with results per model file.
    """
    model_dir = Path(model_dir)
    if output_dir is None:
        output_dir = model_dir / "optimized"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {"models": [], "comparisons": [], "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # Find model files
    onnx_files = sorted(model_dir.glob("*.onnx"))
    pt_files = sorted(model_dir.glob("*.pt")) + sorted(model_dir.glob("*.pth"))

    for mod_path in onnx_files:
        entry = {"file": str(mod_path.name), "type": "onnx"}
        print(f"\n{'='*60}\nBenchmarking: {mod_path.name}\n{'='*60}")

        # Benchmark original
        try:
            orig = benchmark_onnx(str(mod_path), input_shape=input_shape, num_runs=num_benchmark_runs)
            entry["original"] = orig
            print(f"  Original: {orig['mean_ms']:.2f}ms mean, {orig['fps']:.1f} FPS ({orig['model_size_mb']:.1f}MB)")
        except Exception as e:
            entry["original"] = {"error": str(e)}
            print(f"  Original benchmark failed: {e}")
            results["models"].append(entry)
            continue

        # Optimize graph
        opt_path = optimize_onnx_graph(str(mod_path), str(output_dir / f"{mod_path.stem}_opt.onnx"))
        if opt_path:
            try:
                opt_bench = benchmark_onnx(opt_path, input_shape=input_shape, num_runs=num_benchmark_runs)
                entry["graph_optimized"] = opt_bench
                speedup = orig["mean_ms"] / opt_bench["mean_ms"] if opt_bench["mean_ms"] > 0 else 1.0
                entry["graph_speedup"] = round(speedup, 2)
                print(f"  Graph opt: {opt_bench['mean_ms']:.2f}ms mean ({speedup:.2f}x speedup)")
            except Exception as e:
                entry["graph_optimized"] = {"error": str(e)}

        # Dynamic quantization
        q_path = quantize_onnx_dynamic(str(mod_path), str(output_dir / f"{mod_path.stem}_int8.onnx"))
        if q_path:
            try:
                q_bench = benchmark_onnx(q_path, input_shape=input_shape, num_runs=num_benchmark_runs)
                entry["int8_quantized"] = q_bench
                size_reduction = (1 - q_bench["model_size_mb"] / orig["model_size_mb"]) * 100
                entry["int8_size_reduction_pct"] = round(size_reduction, 1)
                print(f"  INT8:       {q_bench['mean_ms']:.2f}ms mean, {q_bench['model_size_mb']:.1f}MB ({size_reduction:.1f}% smaller)")
            except Exception as e:
                entry["int8_quantized"] = {"error": str(e)}

        results["models"].append(entry)

    for mod_path in pt_files:
        entry = {"file": str(mod_path.name), "type": "pytorch"}
        print(f"\n{'='*60}\nBenchmarking: {mod_path.name}\n{'='*60}")

        try:
            orig = benchmark_pytorch(str(mod_path), input_shape=input_shape, num_runs=num_benchmark_runs)
            entry["original"] = orig
            print(f"  PyTorch: {orig['mean_ms']:.2f}ms mean, {orig['fps']:.1f} FPS on {orig['device']}")
        except Exception as e:
            entry["original"] = {"error": str(e)}
            print(f"  Benchmark failed: {e}")

        results["models"].append(entry)

    # Save report
    report_path = output_dir / "optimization_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")

    return results


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DefectSense Model Optimizer & Benchmark")
    parser.add_argument("--model-dir", default="../../models",
                        help="Directory with model files")
    parser.add_argument("--model", help="Single model file to benchmark")
    parser.add_argument("--output-dir", help="Output for optimized models")
    parser.add_argument("--runs", type=int, default=50,
                        help="Benchmark iterations")
    parser.add_argument("--format", choices=["onnx", "pytorch", "all"], default="all",
                        help="Model format to benchmark")
    parser.add_argument("--shape", nargs=4, type=int, default=[1, 3, 224, 224],
                        help="Input shape B C H W")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    shape = tuple(args.shape)

    if args.model:
        # Single model mode
        if args.model.endswith(".onnx") and args.format in ("onnx", "all"):
            result = benchmark_onnx(args.model, input_shape=shape, num_runs=args.runs)
        else:
            result = benchmark_pytorch(args.model, input_shape=shape, num_runs=args.runs)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            for k, v in result.items():
                print(f"  {k}: {v}")
    else:
        # Pipeline mode
        results = run_optimization_pipeline(
            model_dir=args.model_dir,
            output_dir=args.output_dir,
            input_shape=shape,
            num_benchmark_runs=args.runs,
        )
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print("\nOptimization pipeline complete.")
            for m in results["models"]:
                if "graph_speedup" in m:
                    print(f"  {m['file']}: {m['graph_speedup']}x speedup (graph opt)")
                if "int8_size_reduction_pct" in m:
                    print(f"  {m['file']}: {m['int8_size_reduction_pct']:.1f}% size reduction (INT8)")
