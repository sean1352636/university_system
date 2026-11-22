"""Model management for the AI detector: train, list, activate, roll back,
compare, evaluate, export / import weights, and the model cache.

All of it works on the indicator model (``ml/indicator_model``), which
learns only from what people decided about readings (a reviewer's "no
concern", or a referral whose case was upheld or not). Its estimate is
advisory context shown to reviewers; it never flags work by itself.

Each method runs on its own short connection, records the signed-in person
and returns ``{"success": ...}`` with a message the screens can show.
Every change is written to the audit chain.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.ml import indicator_model as im


class ModelManagementMixin:
    """Mixin providing model and system management methods."""

    # ── plumbing ────────────────────────────────────────────────────────

    def _model_actor(self) -> str:
        user = getattr(self, "current_user", None) or {}
        return str(user.get("username") or "system")

    def _require_model_admin(self):
        """Training and switching models is for integrity officers."""
        from education_system.systems.university.application.integrity import access
        conn = self._safe_db_connect()
        try:
            who = access.from_user(conn, getattr(self, "current_user", None))
            if who is None or not access.is_officer(conn, who):
                raise PermissionError("Only an integrity officer can manage detection models")
        finally:
            conn.close()

    def _model_call(self, fn, *args, write=True, officer=True, **kwargs) -> Dict[str, Any]:
        try:
            if officer:
                self._require_model_admin()
            conn = self._safe_db_connect()
            try:
                result = fn(conn, *args, **kwargs)
                if write:
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return {"success": True, **(result if isinstance(result, dict) else
                                        {"result": result})}
        except (im.ModelError, PermissionError, ValueError) as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error(f"Model management failed: {exc}")
            return {"success": False, "error": f"That did not work: {exc}"}

    # ── training and versions ───────────────────────────────────────────

    def retrain_detection_model(self, data_source: str = 'reviews',
                                include_negative: bool = True,
                                min_samples: int = im.MIN_LABELLED,
                                labelled_texts: list = None,
                                activate: bool = False) -> Dict[str, Any]:
        """Train a new version on every reviewed reading with a settled
        outcome, plus ``labelled_texts`` (``[{"text", "label"}]``, a
        human-labelled set) when given. ``data_source``,
        ``include_negative`` and ``min_samples`` are kept for older callers
        (both outcomes are always used, and the minimum is fixed)."""
        import time
        started = time.time()

        def run(conn):
            extra = []
            if labelled_texts:
                from education_system.systems.university.application.integrity import ai_indicators
                for item in labelled_texts:
                    vector = im.features_from_reading(ai_indicators.assess(item.get("text", "")))
                    if vector is not None and item.get("label") in (0, 1, True, False):
                        extra.append({"features": vector, "label": int(item["label"])})
            out = im.train(conn, self._model_actor(), extra=extra)
            if activate:
                im.activate(conn, out["version"], self._model_actor(), reason="trained")
            return out
        out = self._model_call(run)
        if out.get("success"):
            out.update({"model_version": out["version"],
                        "training_time": round(time.time() - started, 2),
                        "data_source": "human review outcomes", "active": bool(activate)})
        return out

    def training_data_summary(self) -> Dict[str, Any]:
        """How many reviewed readings have a settled outcome, and whether
        that is enough to train."""
        return self._model_call(im.labelled_summary, write=False, officer=False)

    def list_model_versions(self) -> Dict[str, Any]:
        out = self._model_call(im.versions, write=False, officer=False)
        if not out.get("success"):
            return {"versions": [], "error": out.get("error")}
        return {"versions": [{"version": v["version"], "created_at": v["created_at"],
                              "accuracy": v.get("accuracy"), "is_active": v["is_active"],
                              "source": v.get("source"), "trained_by": v.get("trained_by"),
                              "training_samples": v.get("training_samples"),
                              "metrics": v.get("metrics"), "usable": v["usable"],
                              "note": v.get("note")}
                             for v in out["result"]]}

    def activate_model_version(self, version_id: str, reason: str = None) -> Dict[str, Any]:
        return self._model_call(im.activate, version_id, self._model_actor(),
                                reason=reason or "activated")

    def deactivate_model(self, reason: str = "") -> Dict[str, Any]:
        return self._model_call(im.deactivate, self._model_actor(), reason or "deactivated")

    def rollback_model_version(self, version_id: str, reason: str = None) -> Dict[str, Any]:
        """Make an earlier version active again (recorded with the reason)."""
        out = self._model_call(im.activate, version_id, self._model_actor(),
                               reason=f"rollback: {reason or 'no reason given'}")
        if out.get("success"):
            from datetime import datetime
            out["rollback_time"] = datetime.now().isoformat()
        return out

    def evaluate_model_version(self, version_id: str) -> Dict[str, Any]:
        """Evaluate a version on this university's reviewed readings (needed
        before an imported or federated version can be activated)."""
        return self._model_call(im.evaluate_version, version_id, self._model_actor())

    def compare_model_versions(self, version_a: str, version_b: str,
                               sample_size: int = None) -> Dict[str, Any]:
        """Both versions on the same current settled outcomes."""
        out = self._model_call(im.compare, version_a, version_b, write=False, officer=False)
        if out.get("success"):
            out.update({"version_a_metrics": out["results"].get(version_a, {}),
                        "version_b_metrics": out["results"].get(version_b, {}),
                        "recommended_version": out["recommended"],
                        "samples_tested": out["compared_on"]})
        return out

    def estimate_text_with_versions(self, text: str, versions: list) -> Dict[str, Any]:
        """Take a reading of ``text`` (not stored) and give each version's
        estimate for it — how often readings like it were confirmed by a
        person under that version. Context for choosing a version, not a
        judgement on the text."""
        from education_system.systems.university.application.integrity import ai_indicators
        reading = ai_indicators.assess(text)
        out = self._model_call(im.estimate_with, reading, [v for v in versions if v],
                               write=False, officer=False)
        if out.get("success"):
            out["level"] = reading.get("level")
            out["indicators"] = reading.get("indicators")
        return out

    def get_model_version(self) -> str:
        """The active version's name, or a plain statement that none is."""
        try:
            conn = self._safe_db_connect()
            try:
                row = im.active(conn)
            finally:
                conn.close()
        except Exception as exc:
            logger.debug(f"Active model unavailable: {exc}")
            return "no model active"
        if not row:
            return "no model active (indicators only)"
        return f"{row['version']} ({row.get('source') or 'trained'}, " \
               f"{row.get('training_samples') or 0} reviewed readings)"

    # ── weights ─────────────────────────────────────────────────────────

    def export_model_weights(self, version_id: str = None, output_path: str = None,
                             include_config: bool = True,
                             include_training_data: bool = False) -> Dict[str, Any]:
        """The version's weights as JSON (no student data). ``output_path``
        is a file or a folder (default: the models folder)."""
        target = output_path or os.path.join(str(im.models_dir()), "export")
        out = self._model_call(im.export_weights, version_id, target, self._model_actor())
        if out.get("success"):
            out.update({"export_path": out["path"], "version_id": out["version"],
                        "file_size": f"{out['bytes'] / 1024:.2f} KB",
                        "files_created": [out["path"]]})
        return out

    def import_model_weights(self, import_path: str, set_active: bool = False,
                             validate: bool = True) -> Dict[str, Any]:
        """Import exported weights as a new version (always validated; it is
        evaluated on local outcomes when there are enough)."""
        out = self._model_call(im.import_weights, import_path, self._model_actor(),
                               activate_now=set_active)
        if out.get("success"):
            out["version_id"] = out["version"]
            out["validation"] = {"is_valid": True, "compatibility": "compatible",
                                 "evaluated_on": out["metrics"].get("evaluated_on")}
        return out

    # ── cache ───────────────────────────────────────────────────────────

    def get_cache_statistics(self) -> Dict[str, Any]:
        info = im.cache_info()
        analysis = len(getattr(self, "_analysis_cache", {}) or {})
        return {"total_entries": info["models_cached"] + analysis,
                "models_cached": info["models_cached"], "analyses_cached": analysis,
                "cached_versions": info["versions"],
                "memory_usage": f"{self.get_cache_size()} bytes"}

    def get_cache_size(self) -> int:
        """Bytes of model files held in memory (their size on disk)."""
        size = 0
        for name in im.cache_info()["versions"]:
            path = im.models_dir() / name
            if path.is_file():
                size += path.stat().st_size
        return size

    def clear_analysis_cache(self, clear_all: bool = False, older_than_days: int = None,
                             student_id: str = None) -> Dict[str, Any]:
        cleared = im.clear_cache()
        cache = getattr(self, "_analysis_cache", None)
        if isinstance(cache, dict):
            if student_id:
                keys = [k for k in cache if student_id in str(k)]
            else:
                keys = list(cache)
            for key in keys:
                del cache[key]
            cleared += len(keys)
        logger.info(f"Cache cleared: {cleared} entries")
        return {"success": True, "entries_cleared": cleared,
                "memory_freed": "models are reloaded from disk when next needed"}

    # ── names the screens use ───────────────────────────────────────────

    def retrain_model(self, **kwargs) -> Dict[str, Any]:
        return self.retrain_detection_model(**kwargs)

    def export_weights(self, output_path: str = None, version_id: str = None) -> Dict[str, Any]:
        return self.export_model_weights(version_id=version_id, output_path=output_path)

    def import_weights(self, import_path: str, set_active: bool = False) -> Dict[str, Any]:
        return self.import_model_weights(import_path, set_active=set_active)

    def clear_cache(self) -> Dict[str, Any]:
        return self.clear_analysis_cache(clear_all=True)
