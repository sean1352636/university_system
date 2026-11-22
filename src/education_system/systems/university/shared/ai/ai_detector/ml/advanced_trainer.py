"""The detector's trainer: the indicator model trained on human review
outcomes (``ml/indicator_model``).

The earlier "ensemble" labelled each text with its own heuristic score and
fitted a new TF-IDF vocabulary per text, so it learned nothing and could not
predict; it is replaced by one honest model. The class keeps the names the
detector and its screens call.
"""

from __future__ import annotations

from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.core.exceptions import AIDetectionError
from education_system.systems.university.shared.ai.ai_detector.ml import indicator_model as im


class AdvancedMLTrainer:
    """Trains and applies the indicator model for the detector."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def _run(self, fn, *args, write=False, **kwargs):
        conn = self.detector._safe_db_connect()
        try:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _actor(self) -> str:
        user = getattr(self.detector, "current_user", None) or {}
        return str(user.get("username") or "system")

    @property
    def models(self) -> Dict[str, Any]:
        """``{"indicator_model": <active version row>}`` or empty."""
        try:
            row = self._run(im.active)
        except Exception as exc:
            logger.debug(f"No active model: {exc}")
            return {}
        return {"indicator_model": row} if row else {}

    @property
    def feature_importance(self) -> Dict[str, float]:
        """The active model's weight on each indicator (raw scale)."""
        row = self.models.get("indicator_model")
        if not row:
            return {}
        coef, _intercept = im.coefficients(row)
        return dict(zip(im.FEATURES, coef))

    def train_ensemble_model(self, use_advanced_features: bool = True) -> Dict[str, Any]:
        """Train a new version on human review outcomes (inactive until an
        officer activates it)."""
        try:
            out = self._run(im.train, self._actor(), write=True)
        except im.ModelError as exc:
            raise AIDetectionError(str(exc)) from None
        return {"models_trained": ["indicator_model"], "version": out["version"],
                "model_scores": {"indicator_model": out["metrics"].get("accuracy")},
                "metrics": out["metrics"], "feature_importance":
                    out["metrics"].get("coefficients", {}), "active": False}

    def predict_ensemble(self, text: str) -> Dict[str, Any] | None:
        """The active model's estimate for ``text`` (via its indicators), or
        ``None`` with no active model or too little text."""
        from education_system.systems.university.application.integrity import ai_indicators
        reading = ai_indicators.assess(text)
        try:
            found = self._run(im.estimate, reading)
        except Exception as exc:
            logger.debug(f"Model estimate unavailable: {exc}")
            return None
        if not found:
            return None
        return {**found, "ensemble_score": found["estimate"], "confidence": None,
                "individual_predictions": {"indicator_model": found["estimate"]}}
