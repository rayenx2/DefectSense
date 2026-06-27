"""
Model registry for DefectSense — version tracking and stage management.

Tracks model versions, stages (staging → production → archived),
and provides rollback capability. Uses a JSON registry file.
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ModelRegistry:
    """Lightweight model version registry for DefectSense.

    Tracks model metadata, stage transitions, and version history
    in a JSON file. Supports staging → production → archived workflow.

    Usage:
        reg = ModelRegistry("./models")
        reg.register("padim_v2.onnx", {"backbone": "resnet18", "auroc": 0.95})
        reg.promote("padim_v2.onnx", "production")
        current = reg.get_current("production")
        reg.rollback("production")  # revert to previous production model
    """

    STAGES = ("staging", "production", "archived")

    def __init__(self, registry_dir: str):
        """Initialize registry in given directory.

        Args:
            registry_dir: Directory where registry.json and models live.
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.registry_dir / "model_registry.json"
        self._data = self._load()

    # ── IO ──────────────────────────────────────────────────────

    def _load(self) -> Dict:
        """Load registry from disk or return empty default."""
        if self.registry_path.exists():
            with open(self.registry_path, "r") as f:
                return json.load(f)
        return {"entries": {}, "history": [], "created_at": datetime.now().isoformat()}

    def _save(self) -> None:
        """Persist registry to disk atomically."""
        tmp = self.registry_path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2, default=str)
        tmp.replace(self.registry_path)

    # ── CRUD ────────────────────────────────────────────────────

    def register(
        self,
        model_filename: str,
        metadata: Optional[Dict] = None,
        stage: str = "staging",
    ) -> Dict:
        """Register a new model version.

        Args:
            model_filename: Name of model file in registry_dir.
            metadata: Arbitrary key-value metadata (backbone, accuracy, etc.).
            stage: Initial stage (one of 'staging', 'production', 'archived').

        Returns:
            The created entry dict.

        Raises:
            ValueError: If stage is invalid or file doesn't exist.
        """
        if stage not in self.STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Use one of {self.STAGES}")

        model_path = self.registry_dir / model_filename
        if not model_path.exists():
            raise ValueError(f"Model file not found: {model_path}")

        entry_id = f"{model_filename}__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        entry = {
            "id": entry_id,
            "filename": model_filename,
            "file_size_mb": round(os.path.getsize(model_path) / (1024 * 1024), 2),
            "stage": stage,
            "registered_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "previous_stages": [],
            "version": len(self._data["entries"]) + 1,
        }

        self._data["entries"][entry_id] = entry
        self._data["history"].append({
            "action": "register",
            "entry_id": entry_id,
            "filename": model_filename,
            "stage": stage,
            "timestamp": entry["registered_at"],
        })
        self._save()
        return entry

    def promote(self, model_filename: str, target_stage: str) -> Optional[Dict]:
        """Promote a model to a new stage.

        If promoting to 'production', the current production model
        is moved to 'archived'.

        Args:
            model_filename: The model filename (must be registered).
            target_stage: Target stage to promote to.

        Returns:
            Updated entry, or None if not found.
        """
        if target_stage not in self.STAGES:
            raise ValueError(f"Invalid stage '{target_stage}'")

        entry_id, entry = self._find_by_filename(model_filename)
        if entry is None:
            print(f"Model '{model_filename}' not found in registry")
            return None

        if entry["stage"] == target_stage:
            print(f"Model already at stage '{target_stage}'")
            return entry

        old_stage = entry["stage"]
        entry["previous_stages"].append({
            "stage": old_stage,
            "moved_at": datetime.now().isoformat(),
        })

        # Archive current production model if promoting to production
        if target_stage == "production":
            for eid, e in self._data["entries"].items():
                if e["stage"] == "production" and eid != entry_id:
                    e["stage"] = "archived"
                    e["previous_stages"].append({
                        "stage": "production",
                        "moved_at": datetime.now().isoformat(),
                        "reason": "superseded",
                    })

        entry["stage"] = target_stage
        self._data["history"].append({
            "action": "promote",
            "entry_id": entry_id,
            "from_stage": old_stage,
            "to_stage": target_stage,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()
        print(f"Promoted '{model_filename}': {old_stage} → {target_stage}")
        return entry

    def get_current(self, stage: str = "production") -> Optional[Dict]:
        """Get the current model at a given stage.

        Args:
            stage: Stage to query.

        Returns:
            Entry dict of the current model, or None.
        """
        for entry in self._data["entries"].values():
            if entry["stage"] == stage:
                return entry
        return None

    def rollback(self, stage: str = "production") -> Optional[Dict]:
        """Rollback to the previous model at the given stage.

        Archival model is promoted back to the target stage.

        Args:
            stage: Stage to rollback (typically 'production').

        Returns:
            The restored entry, or None if no previous model found.
        """
        current = self.get_current(stage)
        if current is None:
            print(f"No current model at stage '{stage}'")
            return None

        if not current["previous_stages"]:
            print("No previous stage to rollback to")
            return None

        # Find the previously archived model
        prev_stage_info = current["previous_stages"][-1]
        candidates = [
            e for e in self._data["entries"].values()
            if e["stage"] == "archived"
        ]
        # Sort by most recently archived
        candidates.sort(
            key=lambda e: e["previous_stages"][-1]["moved_at"]
            if e["previous_stages"] else "",
            reverse=True,
        )

        if not candidates:
            print("No archived models to rollback to")
            return None

        restored = candidates[0]
        current["stage"] = "archived"
        restored["stage"] = stage
        restored["previous_stages"].append({
            "stage": "archived",
            "moved_at": datetime.now().isoformat(),
            "reason": "rollback",
        })

        self._data["history"].append({
            "action": "rollback",
            "rolled_back_id": current["id"],
            "restored_id": restored["id"],
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()
        print(f"Rollback: '{restored['filename']}' restored to {stage}")
        return restored

    def list_models(self, stage: Optional[str] = None) -> List[Dict]:
        """List registered models, optionally filtered by stage.

        Args:
            stage: Filter by stage, or None for all.

        Returns:
            List of entry dicts sorted by version.
        """
        entries = list(self._data["entries"].values())
        if stage:
            entries = [e for e in entries if e["stage"] == stage]
        return sorted(entries, key=lambda e: e["version"])

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recent registry actions.

        Args:
            limit: Max number of history entries.

        Returns:
            List of history dicts (newest first).
        """
        return self._data["history"][-limit:][::-1]

    def archive(self, model_filename: str) -> Optional[Dict]:
        """Archive a model (move to archived stage).

        Args:
            model_filename: The model filename.

        Returns:
            Updated entry, or None if not found.
        """
        return self.promote(model_filename, "archived")

    def delete(self, model_filename: str) -> bool:
        """Remove a model from the registry (does NOT delete the file).

        Args:
            model_filename: The model filename.

        Returns:
            True if deleted, False if not found.
        """
        entry_id, entry = self._find_by_filename(model_filename)
        if entry is None:
            return False

        del self._data["entries"][entry_id]
        self._data["history"].append({
            "action": "delete",
            "entry_id": entry_id,
            "filename": model_filename,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()
        return True

    # ── Helpers ─────────────────────────────────────────────────

    def _find_by_filename(self, filename: str) -> tuple:
        """Find (entry_id, entry) by model filename."""
        for eid, entry in self._data["entries"].items():
            if entry["filename"] == filename:
                return eid, entry
        return None, None

    def summary(self) -> str:
        """Generate human-readable summary of registry state."""
        lines = ["Model Registry Summary", "=" * 40]
        for stage in self.STAGES:
            items = self.list_models(stage)
            count = len(items)
            lines.append(f"\n{stage.upper()} ({count}):")
            for item in items:
                meta = ", ".join(f"{k}={v}" for k, v in item["metadata"].items())
                lines.append(
                    f"  v{item['version']} — {item['filename']} "
                    f"({item['file_size_mb']:.1f}MB)"
                )
                if meta:
                    lines.append(f"          {meta}")
        return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DefectSense Model Registry")
    sub = parser.add_subparsers(dest="command")

    # register
    reg_parser = sub.add_parser("register", help="Register a new model")
    reg_parser.add_argument("model", help="Model filename")
    reg_parser.add_argument("--dir", default="./models", help="Registry directory")
    reg_parser.add_argument("--stage", default="staging",
                            choices=["staging", "production", "archived"])
    reg_parser.add_argument("--meta", nargs="*", help="Key=value metadata pairs")

    # promote
    prom_parser = sub.add_parser("promote", help="Promote model to new stage")
    prom_parser.add_argument("model", help="Model filename")
    prom_parser.add_argument("--dir", default="./models", help="Registry directory")
    prom_parser.add_argument("--stage", default="production",
                             choices=["staging", "production", "archived"])

    # list
    list_parser = sub.add_parser("list", help="List registered models")
    list_parser.add_argument("--dir", default="./models", help="Registry directory")
    list_parser.add_argument("--stage", help="Filter by stage")

    # rollback
    rb_parser = sub.add_parser("rollback", help="Rollback to previous model")
    rb_parser.add_argument("--dir", default="./models", help="Registry directory")
    rb_parser.add_argument("--stage", default="production", help="Stage to rollback")

    # summary
    sum_parser = sub.add_parser("summary", help="Print registry summary")
    sum_parser.add_argument("--dir", default="./models", help="Registry directory")

    args = parser.parse_args()

    if args.command == "register":
        reg = ModelRegistry(args.dir)
        meta = {}
        if args.meta:
            for pair in args.meta:
                k, v = pair.split("=", 1)
                meta[k] = v
        reg.register(args.model, metadata=meta, stage=args.stage)
        print(f"Registered: {args.model} [{args.stage}]")

    elif args.command == "promote":
        reg = ModelRegistry(args.dir)
        reg.promote(args.model, args.stage)

    elif args.command == "list":
        reg = ModelRegistry(args.dir)
        models = reg.list_models(args.stage)
        for m in models:
            print(f"  v{m['version']} — {m['filename']} [{m['stage']}] "
                  f"({m['file_size_mb']:.1f}MB)")
        if not models:
            print("  (no models registered)")

    elif args.command == "rollback":
        reg = ModelRegistry(args.dir)
        reg.rollback(args.stage)

    elif args.command == "summary":
        reg = ModelRegistry(args.dir)
        print(reg.summary())

    else:
        parser.print_help()
