"""
A/B Model Comparison for DefectSense anomaly detection.

Compares two model versions side-by-side: same test set, same threshold,
different models. Computes statistical significance and generates
a comparison report.
"""

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_TORCH_AVAILABLE = True
try:
    import torch
except ImportError:
    _TORCH_AVAILABLE = False


@dataclass
class ModelResult:
    """Results from evaluating one model on the test set."""

    name: str
    model_path: str
    scores: np.ndarray = field(default_factory=lambda: np.array([]))
    labels: np.ndarray = field(default_factory=lambda: np.array([]))
    latency_ms: float = 0.0
    fps: float = 0.0
    auroc: float = 0.0
    optimal_threshold: float = 0.0
    accuracy_at_opt: float = 0.0
    precision_at_opt: float = 0.0
    recall_at_opt: float = 0.0
    f1_at_opt: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class ComparisonReport:
    """Side-by-side comparison of two models."""

    model_a: ModelResult
    model_b: ModelResult
    auroc_delta: float = 0.0
    auroc_improvement_pct: float = 0.0
    fps_ratio: float = 0.0
    better_model: str = ""
    statistical_test: Dict = field(default_factory=dict)
    agreement_rate: float = 0.0
    disagreement_examples: int = 0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


# ── Metrics ──────────────────────────────────────────────────────

def compute_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Compute Area Under ROC curve."""
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(labels, scores))
    except ImportError:
        # Manual AUROC using sorting
        desc_score_indices = np.argsort(scores, kind="mergesort")[::-1]
        labels = labels[desc_score_indices]
        n_pos = np.sum(labels == 1)
        n_neg = len(labels) - n_pos
        if n_pos == 0 or n_neg == 0:
            return 0.5
        tpr = np.cumsum(labels == 1) / n_pos
        fpr = np.cumsum(labels == 0) / n_neg
        return float(np.trapz(tpr, fpr))


def find_optimal_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    metric: str = "f1",
) -> Tuple[float, float]:
    """Find threshold that maximizes F1 or Youden's J.

    Args:
        labels: Ground truth (0 or 1).
        scores: Anomaly scores (higher = more anomalous).
        metric: 'f1' or 'youden'.

    Returns:
        (threshold, best_metric_value)
    """
    if len(np.unique(scores)) < 2:
        return float(np.mean(scores)), 0.5

    thresholds = np.linspace(scores.min(), scores.max(), min(200, len(scores)))
    best_val = -1.0
    best_thresh = float(np.median(scores))

    for t in thresholds:
        preds = (scores >= t).astype(int)
        tp = np.sum((preds == 1) & (labels == 1))
        fp = np.sum((preds == 1) & (labels == 0))
        fn = np.sum((preds == 0) & (labels == 1))
        tn = np.sum((preds == 0) & (labels == 0))

        if metric == "f1":
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            val = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        else:  # Youden's J
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            val = tpr - fpr

        if val > best_val:
            best_val = val
            best_thresh = t

    return float(best_thresh), float(best_val)


def compute_metrics_at_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> Dict:
    """Compute precision, recall, F1, accuracy at given threshold."""
    preds = (scores >= threshold).astype(int)
    tp = int(np.sum((preds == 1) & (labels == 1)))
    fp = int(np.sum((preds == 1) & (labels == 0)))
    fn = int(np.sum((preds == 0) & (labels == 1)))
    tn = int(np.sum((preds == 0) & (labels == 0)))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(labels) if len(labels) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


# ── Statistical tests ────────────────────────────────────────────

def mcnemar_test(
    labels: np.ndarray,
    preds_a: np.ndarray,
    preds_b: np.ndarray,
) -> Dict:
    """McNemar's test for paired nominal data.

    Tests whether model A and model B have significantly different
    error rates on the same test set.

    Returns:
        Dict with statistic, p_value, significant (bool at alpha=0.05).
    """
    # Contingency table
    n_ab = int(np.sum((preds_a == 1) & (preds_b == 0)))  # A right, B wrong
    n_ba = int(np.sum((preds_a == 0) & (preds_b == 1)))  # A wrong, B right

    if n_ab + n_ba == 0:
        return {"test": "mcnemar", "statistic": 0.0, "p_value": 1.0,
                "significant": False, "note": "No discordant pairs"}

    # Continuity correction
    statistic = (abs(n_ab - n_ba) - 1) ** 2 / (n_ab + n_ba)

    # Chi-square p-value approximation (1 df)
    from scipy.stats import chi2
    p_value = 1.0 - chi2.cdf(statistic, 1)

    return {
        "test": "mcnemar",
        "statistic": round(float(statistic), 4),
        "p_value": round(float(p_value), 4),
        "significant": p_value < 0.05,
        "n_a_right_b_wrong": n_ab,
        "n_a_wrong_b_right": n_ba,
    }


# ── Evaluator ────────────────────────────────────────────────────

class ModelEvaluator:
    """Evaluates a single model on a test set for comparison."""

    def __init__(self, name: str, model_path: str, device: Optional[str] = None):
        self.name = name
        self.model_path = Path(model_path)
        if device is None:
            self.device = "cuda" if _TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
        else:
            self.device = device

    def evaluate(
        self,
        labels: np.ndarray,
        image_tensors: Optional[np.ndarray] = None,
        scores: Optional[np.ndarray] = None,
        threshold: Optional[float] = None,
    ) -> ModelResult:
        """Evaluate model performance.

        You can pass pre-computed scores OR image_tensors for inference.

        Args:
            labels: Ground truth (0=normal, 1=anomaly).
            image_tensors: Images for inference (if scores not provided).
            scores: Pre-computed anomaly scores (skips inference).
            threshold: Classification threshold. Auto-finds optimal if None.

        Returns:
            ModelResult with all metrics.
        """
        result = ModelResult(name=self.name, model_path=str(self.model_path))
        result.labels = labels

        if scores is not None:
            result.scores = scores
        elif image_tensors is not None and _TORCH_AVAILABLE:
            result.scores = self._run_inference(image_tensors)
        else:
            result.errors.append("No scores or image tensors provided for evaluation")
            return result

        # Compute AUROC
        try:
            result.auroc = round(compute_auroc(labels, result.scores), 4)
        except Exception as e:
            result.errors.append(f"AUROC computation failed: {e}")

        # Find optimal threshold
        try:
            result.optimal_threshold, _ = find_optimal_threshold(labels, result.scores, "f1")
            metrics = compute_metrics_at_threshold(labels, result.scores, result.optimal_threshold)
            result.accuracy_at_opt = metrics["accuracy"]
            result.precision_at_opt = metrics["precision"]
            result.recall_at_opt = metrics["recall"]
            result.f1_at_opt = metrics["f1"]
        except Exception as e:
            result.errors.append(f"Threshold optimization failed: {e}")

        return result

    def _run_inference(self, images: np.ndarray) -> np.ndarray:
        """Run inference using PyTorch model.

        Args:
            images: Numpy array of shape (N, C, H, W).

        Returns:
            1D array of anomaly scores.
        """
        if not _TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        model = torch.load(self.model_path, map_location=self.device, weights_only=False)

        # Handle stats-only dict
        if isinstance(model, dict) and "mean" in model:
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent / "DefectSense"))
                from defectsense.padim_lite import build_padim_from_stats
                model = build_padim_from_stats(model, device=self.device)
            except ImportError as e:
                raise RuntimeError(f"Cannot build PadimLite: {e}")

        if hasattr(model, "eval"):
            model.eval()

        scores = []
        batch = torch.from_numpy(images).float().to(self.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            if hasattr(model, "predict"):
                image_scores, _ = model.predict(batch)
            else:
                image_scores, _ = model(batch)
        elapsed = time.perf_counter() - t0

        self.result_latency_ms = round(elapsed * 1000, 2)
        self.result_fps = round(len(images) / elapsed, 1) if elapsed > 0 else 0.0

        if isinstance(image_scores, torch.Tensor):
            scores = image_scores.cpu().numpy()
        else:
            scores = np.array(image_scores)

        return scores.flatten()


# ── Comparator ───────────────────────────────────────────────────

def compare_models(
    model_a_path: str,
    model_b_path: str,
    labels: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    name_a: Optional[str] = None,
    name_b: Optional[str] = None,
    threshold_a: Optional[float] = None,
    threshold_b: Optional[float] = None,
) -> ComparisonReport:
    """Compare two anomaly detection models side by side.

    Args:
        model_a_path: Path to model A.
        model_b_path: Path to model B.
        labels: Ground truth labels (0=normal, 1=anomaly).
        scores_a: Anomaly scores from model A.
        scores_b: Anomaly scores from model B.
        name_a: Display name for model A.
        name_b: Display name for model B.
        threshold_a: Threshold for model A (auto if None).
        threshold_b: Threshold for model B (auto if None).

    Returns:
        ComparisonReport with full comparison data.
    """
    name_a = name_a or Path(model_a_path).stem
    name_b = name_b or Path(model_b_path).stem

    evaluator_a = ModelEvaluator(name_a, model_a_path)
    evaluator_b = ModelEvaluator(name_b, model_b_path)

    result_a = evaluator_a.evaluate(labels, scores=scores_a, threshold=threshold_a)
    result_b = evaluator_b.evaluate(labels, scores=scores_b, threshold=threshold_b)

    auroc_delta = round(result_b.auroc - result_a.auroc, 4)
    auroc_improvement = round((auroc_delta / result_a.auroc) * 100, 2) if result_a.auroc > 0 else 0.0

    # Determine better model
    if auroc_delta > 0.001:
        better = name_b
    elif auroc_delta < -0.001:
        better = name_a
    else:
        better = "tie"

    # McNemar test
    thresh_a = threshold_a if threshold_a is not None else result_a.optimal_threshold
    thresh_b = threshold_b if threshold_b is not None else result_b.optimal_threshold
    preds_a = (scores_a >= thresh_a).astype(int)
    preds_b = (scores_b >= thresh_b).astype(int)

    stat_test = {}
    try:
        stat_test = mcnemar_test(labels, preds_a, preds_b)
    except ImportError:
        stat_test = {"error": "scipy not available for McNemar test"}
    except Exception as e:
        stat_test = {"error": str(e)}

    # Agreement
    agreement = np.mean(preds_a == preds_b)
    disagreements = int(np.sum(preds_a != preds_b))

    fps_ratio = 0.0
    if hasattr(evaluator_a, "result_fps") and hasattr(evaluator_b, "result_fps"):
        if evaluator_a.result_fps > 0:
            fps_ratio = round(evaluator_b.result_fps / evaluator_a.result_fps, 2)

    return ComparisonReport(
        model_a=result_a,
        model_b=result_b,
        auroc_delta=auroc_delta,
        auroc_improvement_pct=auroc_improvement,
        fps_ratio=fps_ratio,
        better_model=better,
        statistical_test=stat_test,
        agreement_rate=round(float(agreement), 4),
        disagreement_examples=disagreements,
    )


def format_report(report: ComparisonReport) -> str:
    """Generate human-readable comparison report."""
    a, b = report.model_a, report.model_b
    lines = [
        "=" * 60,
        "  DefectSense — Model Comparison Report",
        "=" * 60,
        f"  Timestamp: {report.timestamp}",
        "",
        f"  Model A: {a.name} ({a.model_path})",
        f"  Model B: {b.name} ({b.model_path})",
        "",
        "-" * 60,
        "  METRICS",
        "-" * 60,
        f"  {'Metric':<25} {'Model A':>12} {'Model B':>12} {'Delta':>12}",
        f"  {'─'*25} {'─'*12} {'─'*12} {'─'*12}",
        f"  {'AUROC':<25} {a.auroc:>12.4f} {b.auroc:>12.4f} {report.auroc_delta:>+12.4f}",
        f"  {'Optimal Threshold':<25} {a.optimal_threshold:>12.4f} {b.optimal_threshold:>12.4f}",
        f"  {'Accuracy':<25} {a.accuracy_at_opt:>12.4f} {b.accuracy_at_opt:>12.4f}",
        f"  {'Precision':<25} {a.precision_at_opt:>12.4f} {b.precision_at_opt:>12.4f}",
        f"  {'Recall':<25} {a.recall_at_opt:>12.4f} {b.recall_at_opt:>12.4f}",
        f"  {'F1 Score':<25} {a.f1_at_opt:>12.4f} {b.f1_at_opt:>12.4f}",
        "",
        f"  AUROC Improvement: {report.auroc_improvement_pct:+.2f}%",
        "",
    ]

    if report.statistical_test and "error" not in report.statistical_test:
        st = report.statistical_test
        lines += [
            "-" * 60,
            "  STATISTICAL TEST (McNemar)",
            "-" * 60,
            f"  Statistic: {st.get('statistic', 'N/A')}",
            f"  p-value:   {st.get('p_value', 'N/A')}",
            f"  Significant at α=0.05: {'YES' if st.get('significant') else 'NO'}",
            f"  A right, B wrong: {st.get('n_a_right_b_wrong', 0)}",
            f"  A wrong, B right: {st.get('n_a_wrong_b_right', 0)}",
            "",
        ]

    lines += [
        f"  Prediction agreement: {report.agreement_rate:.2%}",
        f"  Disagreement count:  {report.disagreement_examples}",
        "",
        f"  Better model: {report.better_model.upper()}",
        "=" * 60,
    ]

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A/B Model Comparison for DefectSense")
    parser.add_argument("model_a", help="Path to model A (.pt, .pth, or .onnx)")
    parser.add_argument("model_b", help="Path to model B (.pt, .pth, or .onnx)")
    parser.add_argument("--labels", required=True, help="Path to JSON file with labels array")
    parser.add_argument("--scores-a", required=True, help="Path to JSON file with model A scores")
    parser.add_argument("--scores-b", required=True, help="Path to JSON file with model B scores")
    parser.add_argument("--name-a", help="Display name for model A")
    parser.add_argument("--name-b", help="Display name for model B")
    parser.add_argument("--threshold-a", type=float, help="Fixed threshold for model A")
    parser.add_argument("--threshold-b", type=float, help="Fixed threshold for model B")
    parser.add_argument("--output", "-o", help="Save report JSON to file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Load data
    with open(args.labels) as f:
        labels = np.array(json.load(f))
    with open(args.scores_a) as f:
        scores_a = np.array(json.load(f))
    with open(args.scores_b) as f:
        scores_b = np.array(json.load(f))

    # Compare
    report = compare_models(
        model_a_path=args.model_a,
        model_b_path=args.model_b,
        labels=labels,
        scores_a=scores_a,
        scores_b=scores_b,
        name_a=args.name_a,
        name_b=args.name_b,
        threshold_a=args.threshold_a,
        threshold_b=args.threshold_b,
    )

    if args.json:
        from dataclasses import asdict
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(format_report(report))

    if args.output:
        from dataclasses import asdict
        out = {"report": asdict(report), "text": format_report(report)}
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nReport saved: {args.output}")
