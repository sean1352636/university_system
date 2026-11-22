"""Federated learning for the AI-writing indicator model, by file exchange.

Universities can improve the model together without sharing any student's
work: each trains on its own reviewed readings (``ml/indicator_model``) and
shares only the model's weights. Because every institution uses the same
fixed feature space (``indicator_model.FEATURES``), weights can be
averaged (FedAvg, weighted by how many reviewed readings each was trained
on).

* :func:`export_update` — the local model's weights, with differential-
  privacy noise added, to a JSON file the officer sends to partners.
* :func:`import_update` — a partner's file, checked (format, features,
  shape, finite numbers, checksum) and kept in ``ai_federated_updates``.
* :func:`aggregate` — a new, inactive model version from the weighted
  average of the local model and chosen imported updates. It is evaluated on
  this university's reviewed readings, and cannot be activated until it has
  been (``indicator_model.activate``).

**Privacy.** Output perturbation: independent Laplace noise with scale
``b = 2 / (n · ε)`` is added to every weight, where ``n`` is the number of
reviewed readings the model was trained on and ``ε`` (epsilon, default 1.0)
the privacy budget — smaller ε, more noise, more privacy. This is the
Chaudhuri–Monteleoni bound for L2-regularised logistic regression on
features of bounded norm; the indicator features are not norm-bounded, so
treat ε as indicative rather than a formal guarantee. Only weights leave the
university; no text, ids or readings.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.ml import indicator_model as im

UPDATE_FORMAT = "ai-indicator-federated-update-v1"
DEFAULT_EPSILON = 1.0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def institution_id(conn) -> str:
    im.ensure(conn)
    row = conn.execute("SELECT value FROM ai_detector_settings WHERE key = 'institution_id'"
                       ).fetchone()
    return row[0] if row else "local"


def set_institution_id(conn, value, by) -> None:
    value = str(value or "").strip()
    if not value:
        raise im.ModelError("Give this university's institution id")
    im.ensure(conn)
    conn.execute("INSERT INTO ai_detector_settings (key, value, updated_by, updated_at) VALUES "
                 "('institution_id', ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = "
                 "excluded.value, updated_by = excluded.updated_by, updated_at = "
                 "excluded.updated_at", (value, by, _now()))
    im._audit(conn, "federation institution set", {"institution_id": value}, by)


def _laplace(scale, rng) -> float:
    u = rng.random() - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


def export_update(conn, path, by, *, version=None, epsilon=DEFAULT_EPSILON,
                  seed=None) -> dict:
    """Write the (noised) weights of ``version`` (default: the active model)
    to ``path``. Returns where, the checksum and the noise scale used."""
    epsilon = float(epsilon)
    if not 0 < epsilon <= 10:
        raise im.ModelError("Epsilon must be above 0 and at most 10")
    row = im.version(conn, version) if version else im.active(conn)
    if not row:
        raise im.ModelError("No such model version" if version else
                            "No model is active: train or choose one first")
    coef, intercept = im.coefficients(row)
    n = int(row.get("training_samples") or 0)
    if n < im.MIN_LABELLED:
        raise im.ModelError(f"{row['version']} was trained on {n} readings; at least "
                            f"{im.MIN_LABELLED} are needed before its weights are shared")
    scale = 2.0 / (n * epsilon)
    rng = random.SystemRandom() if seed is None else random.Random(seed)
    payload = {"format": UPDATE_FORMAT, "institution_id": institution_id(conn),
               "model_version": row["version"], "features": list(im.FEATURES),
               "coef": [c + _laplace(scale, rng) for c in coef],
               "intercept": intercept + _laplace(scale, rng), "n_samples": n,
               "epsilon": epsilon, "noise": f"laplace(b=2/(n*epsilon)={scale:.6g})",
               "created_at": _now()}
    payload["sha256"] = im._payload_hash(payload)
    target = Path(str(path))
    if target.is_dir() or not target.suffix:
        target = target / f"federated_update_{payload['institution_id']}_{row['version']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cur = conn.execute(
        "INSERT INTO ai_federated_updates (direction, institution_id, model_version, features, "
        "coef, intercept, n_samples, epsilon, sha256, path, created_by, created_at) VALUES "
        "('exported', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (payload["institution_id"], row["version"], json.dumps(payload["features"]),
         json.dumps(payload["coef"]), payload["intercept"], n, epsilon, payload["sha256"],
         str(target), by, payload["created_at"]))
    im._audit(conn, "federated update exported", {"update_id": cur.lastrowid,
                                                  "version": row["version"],
                                                  "epsilon": epsilon,
                                                  "sha256": payload["sha256"]}, by)
    return {"update_id": cur.lastrowid, "path": str(target), "sha256": payload["sha256"],
            "noise_scale": scale, "epsilon": epsilon, "n_samples": n}


def import_update(conn, path, by) -> dict:
    """Check and keep a partner's update file."""
    try:
        payload = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise im.ModelError(f"Could not read the update file: {exc}") from None
    im.check_payload(payload, UPDATE_FORMAT)
    n = payload.get("n_samples")
    if not isinstance(n, int) or n < 1:
        raise im.ModelError("The update does not say how many readings it was trained on")
    im.ensure(conn)
    if conn.execute("SELECT 1 FROM ai_federated_updates WHERE sha256 = ? AND direction = "
                    "'imported'", (payload["sha256"],)).fetchone():
        raise im.ModelError("This update has already been imported")
    cur = conn.execute(
        "INSERT INTO ai_federated_updates (direction, institution_id, model_version, features, "
        "coef, intercept, n_samples, epsilon, sha256, path, created_by, created_at) VALUES "
        "('imported', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(payload.get("institution_id") or "unknown"), payload.get("model_version"),
         json.dumps(payload["features"]), json.dumps(payload["coef"]),
         float(payload["intercept"]), n, payload.get("epsilon"), payload["sha256"], str(path),
         by, _now()))
    im._audit(conn, "federated update imported", {"update_id": cur.lastrowid,
                                                  "from": payload.get("institution_id"),
                                                  "sha256": payload["sha256"]}, by)
    return {"update_id": cur.lastrowid, "institution_id": payload.get("institution_id"),
            "n_samples": n, "epsilon": payload.get("epsilon")}


def updates(conn, direction=None) -> list[dict]:
    im.ensure(conn)
    sql = "SELECT * FROM ai_federated_updates"
    params: list = []
    if direction:
        sql += " WHERE direction = ?"
        params.append(direction)
    rows = im._dicts(conn.execute(sql + " ORDER BY update_id DESC", params))
    for r in rows:
        r.pop("coef", None)
    return rows


def aggregate(conn, update_ids, by, *, include_local=True) -> dict:
    """FedAvg of the active local model (weighted by its training readings)
    and the chosen imported updates (weighted by theirs) into a new,
    inactive version. Returns the version and its local evaluation."""
    im.ensure(conn)
    parts = []
    if include_local:
        local = im.active(conn)
        if local:
            coef, intercept = im.coefficients(local)
            parts.append((coef, intercept, int(local.get("training_samples") or 0),
                          f"local {local['version']}"))
    for uid in update_ids or ():
        row = im._one(conn, "SELECT * FROM ai_federated_updates WHERE update_id = ? AND "
                            "direction = 'imported'", (int(uid),))
        if not row:
            raise im.ModelError(f"No imported update {uid}")
        parts.append((json.loads(row["coef"]), float(row["intercept"]), int(row["n_samples"]),
                      f"{row['institution_id']} update {uid}"))
    parts = [p for p in parts if p[2] > 0]
    if len(parts) < 2:
        raise im.ModelError("Choose at least one imported update (and have a local model, or "
                            "choose two updates) to aggregate")
    total = sum(p[2] for p in parts)
    coef = [sum(p[0][i] * p[2] for p in parts) / total for i in range(len(im.FEATURES))]
    intercept = sum(p[1] * p[2] for p in parts) / total
    out = im.register_linear(conn, coef=coef, intercept=intercept, source="federated", n=total,
                             by=by, note="FedAvg of " + ", ".join(p[3] for p in parts))
    for uid in update_ids or ():
        conn.execute("UPDATE ai_federated_updates SET used_in_version = ? WHERE update_id = ?",
                     (out["version"], int(uid)))
    return out


class FederatedLearning:
    """The detector's handle on federation (its own short connections)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.federation_config: Dict = {}

    def _actor(self) -> str:
        user = getattr(self.detector, "current_user", None) or {}
        return str(user.get("username") or "system")

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

    @property
    def institution_id(self) -> Optional[str]:
        try:
            value = self._run(institution_id)
        except Exception as exc:
            logger.debug(f"Federation id unavailable: {exc}")
            return None
        return None if value == "local" else value

    @property
    def model_updates(self) -> list:
        return self._run(updates)

    def initialize_federation(self, institution_id: str, federation_config: Dict = None):
        self.federation_config = dict(federation_config or {})
        self._run(set_institution_id, institution_id, self._actor(), write=True)

    def contribute_model_update(self, local_model_weights=None, privacy_budget: float = 1.0,
                                path: str = None, version: str = None) -> Dict:
        """Export the active (or given) model as a noised update file.
        ``local_model_weights`` is ignored (kept for older callers): the
        weights come from the stored model."""
        from education_system.paths import UNIVERSITY_AI_MODELS_DIR
        return self._run(export_update, path or (UNIVERSITY_AI_MODELS_DIR / "federated"),
                         self._actor(), version=version, epsilon=privacy_budget, write=True)

    def import_model_update(self, path: str) -> Dict:
        return self._run(import_update, path, self._actor(), write=True)

    def aggregate_model_updates(self, update_ids=None, include_local: bool = True) -> Dict:
        """Aggregate imported updates (all unused ones when ``update_ids`` is
        not given) with the local model into a new inactive version."""
        if update_ids is None or isinstance(update_ids, int):
            update_ids = [u["update_id"] for u in self._run(updates, "imported")
                          if not u.get("used_in_version")]
        return self._run(aggregate, update_ids, self._actor(), include_local=include_local,
                         write=True)
