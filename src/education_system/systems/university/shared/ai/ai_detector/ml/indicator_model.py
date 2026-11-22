"""A model over the AI-writing indicators, trained only on what people decided.

The indicators (``application/integrity/ai_indicators``) are read from every piece of
work. Whether a reading turned out to matter is known only from human
review:

* the reviewer recorded **no concern** → 0;
* the reading was referred into an integrity case that was **decided with an
  upheld outcome** → 1;
* referred, but the case found **no case to answer** (or was dismissed, or
  withdrawn on appeal) → 0;
* referred and still undecided → not used.

A logistic regression over :data:`FEATURES` (one fixed, ordered feature
space, so models from other institutions can be averaged — see
``features/federated_learning``) learns from those outcomes. Its estimate is
"how often readings like this one were confirmed by a person" — advisory
context for the reviewer, never a flag, a verdict or a reason on its own.

Models are kept as plain linear models in the raw feature space (scaling is
folded into the coefficients), saved with joblib to
``var/data/university/ai_models/<version>.joblib`` (owner-only) and listed in
``ai_detector_model_versions`` with their SHA-256, which is checked before a
model is loaded. Every training, import, activation and rollback is written
to the audit chain (``features/blockchain_audit``).

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path

FEATURES = ("artefacts", "stock_phrases", "sentence_variation", "paragraph_variation",
            "openers", "log_words")
#: What a feature is when the reading did not measure it (too few
#: sentences or paragraphs): a typical human value, so it pushes neither way.
NEUTRAL = {"artefacts": 0.0, "stock_phrases": 0.0, "sentence_variation": 0.6,
           "paragraph_variation": 0.5, "openers": 0.0}
MIN_LABELLED = 20
MIN_PER_CLASS = 5
FORMAT = "ai-indicator-linear-v1"
SOURCES = ("trained", "imported", "federated")
_CACHE: dict = {}


class ModelError(ValueError):
    """Training, loading or importing refused; the message is for the user."""


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _one(conn, sql, params=()) -> dict | None:
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure(conn) -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)


def models_dir() -> Path:
    from education_system.paths import UNIVERSITY_AI_MODELS_DIR
    return Path(UNIVERSITY_AI_MODELS_DIR)


def _audit(conn, event, payload, actor) -> None:
    from education_system.systems.university.shared.ai.ai_detector.features import (
        blockchain_audit,
    )
    blockchain_audit.record(conn, event, payload, actor or "system")


# ── features ────────────────────────────────────────────────────────────


def _reading(reading) -> dict | None:
    if reading is None:
        return None
    if isinstance(reading, (str, bytes)):
        try:
            reading = json.loads(reading)
        except ValueError:
            return None
    return reading if isinstance(reading, dict) else None


def features_from_reading(reading) -> list[float] | None:
    """The feature vector of an ``ai_indicators`` reading (dict or its JSON),
    or ``None`` when the reading had nothing to read (short text, code, or a
    score from the retired detector with no indicators)."""
    reading = _reading(reading)
    if not reading or reading.get("strength") is None:
        return None
    level = str(reading.get("level") or "")
    if level.startswith("not ") or "indicators" not in reading:
        return None
    values = {i.get("key"): i.get("value") for i in reading.get("indicators") or []}
    out = []
    for name in FEATURES:
        if name == "log_words":
            out.append(math.log(max(1, int(reading.get("words_checked") or 1))))
            continue
        value = values.get(name)
        out.append(float(NEUTRAL[name] if value is None else value))
    return out


# ── labelled data ───────────────────────────────────────────────────────


def _upheld() -> tuple:
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    return integrity_review.UPHELD


def label_of(row) -> int | None:
    """0 / 1 from a review (and the case it led to), ``None`` while open."""
    if row.get("decision") == "no_concern":
        return 0
    if row.get("decision") != "refer" or not row.get("case_id"):
        return None
    if row.get("stage") not in ("decided", "closed"):
        return None
    if row.get("status") == "dismissed" or row.get("outcome") in (None, "no_case"):
        return 0
    return 1 if row.get("outcome") in _upheld() else 0


def labelled_set(conn) -> list[dict]:
    """Every reviewed reading with a settled outcome: ``{"ai_result_id",
    "features", "label"}``."""
    ensure(conn)
    have_cases = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'integrity_cases'"
                              ).fetchone()
    case_cols = ("c.stage, c.outcome, c.status" if have_cases
                 else "NULL AS stage, NULL AS outcome, NULL AS status")
    join = "LEFT JOIN integrity_cases c ON c.id = v.case_id" if have_cases else ""
    rows = _dicts(conn.execute(
        f"SELECT r.id AS ai_result_id, r.detailed_results, v.decision, v.case_id, "  # nosec B608
        f"{case_cols} FROM ai_detector_results r JOIN integrity_ai_reviews v ON "
        f"v.ai_result_id = r.id {join} ORDER BY r.id"))
    out = []
    for row in rows:
        label = label_of(row)
        vector = features_from_reading(row["detailed_results"])
        if label is not None and vector is not None:
            out.append({"ai_result_id": row["ai_result_id"], "features": vector, "label": label})
    return out


def labelled_summary(conn) -> dict:
    data = labelled_set(conn)
    positives = sum(d["label"] for d in data)
    return {"labelled": len(data), "confirmed": positives, "not_confirmed": len(data) - positives,
            "needed": MIN_LABELLED, "needed_per_outcome": MIN_PER_CLASS,
            "enough": len(data) >= MIN_LABELLED and min(positives, len(data) - positives)
            >= MIN_PER_CLASS}


# ── the model object ────────────────────────────────────────────────────


def _linear(coef, intercept):
    """A fitted ``LogisticRegression`` with the given raw-space weights."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression()
    model.classes_ = np.array([0, 1])
    model.coef_ = np.array([list(map(float, coef))])
    model.intercept_ = np.array([float(intercept)])
    model.n_features_in_ = len(FEATURES)
    return model


def _fit(X, y):
    """Fit on standardised features, then fold the scaling into the
    coefficients so the model works on raw features."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    X = np.asarray(X, dtype=float)
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    fitted = LogisticRegression(class_weight="balanced", max_iter=1000)
    fitted.fit((X - mean) / scale, np.asarray(y))
    coef = fitted.coef_[0] / scale
    intercept = float(fitted.intercept_[0] - float(np.sum(fitted.coef_[0] * mean / scale)))
    return _linear(coef, intercept)


def evaluate(model, data) -> dict:
    """Metrics of ``model`` on labelled ``data`` (threshold 0.5)."""
    import numpy as np
    if not data:
        return {"evaluated_on": 0}
    X = np.array([d["features"] for d in data], dtype=float)
    y = np.array([d["label"] for d in data])
    proba = model.predict_proba(X)[:, 1]
    return _metrics(y, proba)


def _metrics(y, proba) -> dict:
    import numpy as np
    pred = (np.asarray(proba) >= 0.5).astype(int)
    y = np.asarray(y)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    out = {"evaluated_on": int(len(y)), "accuracy": round((tp + tn) / max(1, len(y)), 4),
           "precision": round(tp / (tp + fp), 4) if tp + fp else None,
           "recall": round(tp / (tp + fn), 4) if tp + fn else None,
           "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else None,
           "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}
    if 0 < int(y.sum()) < len(y):
        from sklearn.metrics import roc_auc_score
        out["auc"] = round(float(roc_auc_score(y, proba)), 4)
    p, r = out["precision"], out["recall"]
    out["f1"] = round(2 * p * r / (p + r), 4) if p and r else None
    return out


def _cross_validated(X, y) -> dict:
    """Out-of-fold metrics with stratified k-fold (k ≤ 5, ≥ 2 per fold)."""
    import numpy as np
    from sklearn.model_selection import StratifiedKFold
    y = np.asarray(y)
    folds = int(min(5, min(int(y.sum()), int(len(y) - y.sum()))))
    proba = np.zeros(len(y))
    for train, test in StratifiedKFold(n_splits=folds, shuffle=True,
                                       random_state=7).split(X, y):
        proba[test] = _fit(np.asarray(X)[train], y[train]).predict_proba(
            np.asarray(X)[test])[:, 1]
    metrics = _metrics(y, proba)
    metrics["method"] = f"{folds}-fold stratified cross-validation"
    return metrics


# ── versions on disk and in the table ───────────────────────────────────


def _new_version(conn, prefix) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version, n = f"{prefix}{stamp}", 1
    while conn.execute("SELECT 1 FROM ai_detector_model_versions WHERE version = ?",
                       (version,)).fetchone():
        n += 1
        version = f"{prefix}{stamp}_{n}"
    return version


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _save(model, version) -> tuple[str, str]:
    import joblib
    folder = models_dir()
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    path = folder / f"{version}.joblib"
    joblib.dump({"format": FORMAT, "version": version, "features": list(FEATURES),
                 "coef": [float(c) for c in model.coef_[0]],
                 "intercept": float(model.intercept_[0])}, path)
    os.chmod(path, 0o600)
    return str(path), _sha256(path)


def _register(conn, *, version, model, source, n, metrics, by, note=None) -> dict:
    path, digest = _save(model, version)
    conn.execute(
        "INSERT INTO ai_detector_model_versions (version, model_path, accuracy, precision_score, "
        "recall_score, f1_score, training_samples, is_active, created_at, source, trained_by, "
        "sha256, features, metrics, note) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
        (version, path, metrics.get("accuracy"), metrics.get("precision"), metrics.get("recall"),
         metrics.get("f1"), int(n), _now(), source, by, digest, json.dumps(list(FEATURES)),
         json.dumps(metrics), note))
    _audit(conn, f"model {source}", {"version": version, "n": int(n), "sha256": digest,
                                     "metrics": metrics}, by)
    return {"version": version, "path": path, "sha256": digest, "source": source,
            "training_samples": int(n), "metrics": metrics}


def version(conn, name) -> dict | None:
    ensure(conn)
    row = _one(conn, "SELECT * FROM ai_detector_model_versions WHERE version = ?", (name,))
    return _decode(row)


def active(conn) -> dict | None:
    ensure(conn)
    row = _one(conn, "SELECT * FROM ai_detector_model_versions WHERE is_active = 1 "
                     "ORDER BY COALESCE(activated_at, created_at) DESC LIMIT 1")
    return _decode(row)


def versions(conn) -> list[dict]:
    ensure(conn)
    return [_decode(r) for r in _dicts(conn.execute(
        "SELECT * FROM ai_detector_model_versions ORDER BY created_at DESC, id DESC"))]


def _decode(row) -> dict | None:
    if not row:
        return None
    try:
        row["metrics"] = json.loads(row.get("metrics") or "null")
    except ValueError:
        row["metrics"] = None
    row["is_active"] = bool(row.get("is_active"))
    row["usable"] = bool(row.get("features")) and bool(row.get("sha256"))
    return row


def load(row):
    """The model of a version row, after checking its file's SHA-256."""
    if not row or not row.get("usable"):
        raise ModelError("This version was made by the retired trainer and cannot be used")
    key = (row["model_path"], row["sha256"])
    if key in _CACHE:
        return _CACHE[key]
    if not os.path.isfile(row["model_path"]):
        raise ModelError(f"The model file of {row['version']} is missing")
    if _sha256(row["model_path"]) != row["sha256"]:
        raise ModelError(f"The model file of {row['version']} has changed since it was saved")
    import joblib
    data = joblib.load(row["model_path"])  # nosec B301 - our own file, hash checked above
    if data.get("format") != FORMAT or list(data.get("features") or []) != list(FEATURES):
        raise ModelError(f"{row['version']} is not an indicator model this version can read")
    model = _linear(data["coef"], data["intercept"])
    _CACHE.clear()
    _CACHE[key] = model
    return model


def cache_info() -> dict:
    return {"models_cached": len(_CACHE),
            "versions": [k[0].rsplit("/", 1)[-1] for k in _CACHE]}


def clear_cache() -> int:
    n = len(_CACHE)
    _CACHE.clear()
    return n


# ── training, activation, comparison ────────────────────────────────────


def train(conn, by, *, extra=(), note=None) -> dict:
    """Train a new (inactive) version on every settled human outcome, plus
    ``extra`` ``{"features", "label"}`` samples (a labelled text set the
    caller turned into readings). Refuses below :data:`MIN_LABELLED` or
    with fewer than :data:`MIN_PER_CLASS` of either outcome."""
    import numpy as np
    data = labelled_set(conn) + [dict(e) for e in extra]
    positives = sum(int(d["label"]) for d in data)
    negatives = len(data) - positives
    if len(data) < MIN_LABELLED or min(positives, negatives) < MIN_PER_CLASS:
        raise ModelError(
            f"Not enough reviewed readings to train: {len(data)} with a settled outcome "
            f"({positives} confirmed, {negatives} not). At least {MIN_LABELLED} are needed, "
            f"with {MIN_PER_CLASS} or more of each.")
    X = np.array([d["features"] for d in data], dtype=float)
    y = np.array([int(d["label"]) for d in data])
    metrics = _cross_validated(X, y)
    model = _fit(X, y)
    metrics["coefficients"] = dict(zip(FEATURES, (round(float(c), 4) for c in model.coef_[0])))
    return _register(conn, version=_new_version(conn, "m"), model=model, source="trained",
                     n=len(data), metrics=metrics, by=by, note=note)


def activate(conn, name, by, *, reason=None) -> dict:
    """Make ``name`` the model whose estimate reviewers see. An imported or
    federated version must have been evaluated on local outcomes first."""
    row = version(conn, name)
    if not row:
        raise ModelError(f"No model version {name}")
    load(row)
    metrics = row["metrics"] or {}
    if row.get("source") in ("imported", "federated") and not metrics.get("evaluated_on"):
        raise ModelError(f"{name} has not been evaluated on this university's reviewed "
                         "readings yet; evaluate it before using it")
    previous = active(conn)
    conn.execute("UPDATE ai_detector_model_versions SET is_active = 0")
    conn.execute("UPDATE ai_detector_model_versions SET is_active = 1, activated_at = ? "
                 "WHERE version = ?", (_now(), name))
    if reason is not None or previous:
        conn.execute("INSERT INTO ai_detector_model_rollbacks (from_version, to_version, reason, "
                     "rolled_back_by, rolled_back_at) VALUES (?, ?, ?, ?, ?)",
                     (previous["version"] if previous else None, name,
                      reason or "activated", by, _now()))
    _audit(conn, "model activated", {"version": name,
                                     "previous": previous["version"] if previous else None,
                                     "reason": reason}, by)
    return {"active_version": name, "previous_version": previous["version"] if previous else None}


def deactivate(conn, by, reason) -> dict:
    """Stop showing any model estimate."""
    previous = active(conn)
    conn.execute("UPDATE ai_detector_model_versions SET is_active = 0")
    _audit(conn, "model deactivated", {"previous": previous["version"] if previous else None,
                                       "reason": reason}, by)
    return {"previous_version": previous["version"] if previous else None}


def evaluate_version(conn, name, by=None) -> dict:
    """Evaluate a version on the current settled outcomes and store the
    result (this is what lets an imported/federated version be activated)."""
    row = version(conn, name)
    if not row:
        raise ModelError(f"No model version {name}")
    data = labelled_set(conn)
    if len(data) < MIN_LABELLED:
        raise ModelError(f"Only {len(data)} reviewed readings have a settled outcome; "
                         f"{MIN_LABELLED} are needed to evaluate a model")
    metrics = {**(row["metrics"] or {}), **evaluate(load(row), data),
               "method": "evaluated on this university's reviewed readings",
               "evaluated_at": _now()}
    conn.execute("UPDATE ai_detector_model_versions SET metrics = ?, accuracy = ?, "
                 "precision_score = ?, recall_score = ?, f1_score = ? WHERE version = ?",
                 (json.dumps(metrics), metrics.get("accuracy"), metrics.get("precision"),
                  metrics.get("recall"), metrics.get("f1"), name))
    _audit(conn, "model evaluated", {"version": name, "metrics": metrics}, by)
    return metrics


def compare(conn, a, b) -> dict:
    """Both versions on the same current settled outcomes."""
    data = labelled_set(conn)
    if not data:
        raise ModelError("No reviewed readings with a settled outcome to compare on")
    results = {name: evaluate(load(version(conn, name) or {}), data) for name in (a, b)}

    def score(m):
        return (m.get("auc") or 0, m.get("f1") or 0, -(m.get("false_positive_rate") or 1))
    better = a if score(results[a]) >= score(results[b]) else b
    return {"compared_on": len(data), "results": results, "recommended": better}


# ── estimates ───────────────────────────────────────────────────────────


def estimate(conn, reading) -> dict | None:
    """The active model's estimate for a reading: how often readings like
    this were confirmed by a person. ``None`` with no active model or
    nothing to read."""
    vector = features_from_reading(reading)
    if vector is None:
        return None
    try:
        row = active(conn)
        if not row:
            return None
        model = load(row)
    except ModelError:
        return None
    import numpy as np
    p = float(model.predict_proba(np.array([vector]))[0][1])
    return {"estimate": round(p, 4), "model_version": row["version"],
            "trained_on": row.get("training_samples"), "validation": row["metrics"],
            "meaning": "How often readings like this one were confirmed by a person after "
                       "review. Context for the reviewer, not evidence."}


def estimate_with(conn, reading, names) -> dict:
    """Each named version's estimate for one reading, side by side (to try
    a text on two versions before choosing one). ``{version: estimate or
    the reason there is none}``."""
    vector = features_from_reading(reading)
    if vector is None:
        raise ModelError("There is too little text (or it is code) for an estimate")
    import numpy as np
    out = {}
    for name in names:
        try:
            model = load(version(conn, name) or {})
            out[name] = round(float(model.predict_proba(np.array([vector]))[0][1]), 4)
        except ModelError as exc:
            out[name] = str(exc)
    return out


# ── weights as JSON (export / import) ───────────────────────────────────


def _payload_hash(payload) -> str:
    body = {k: v for k, v in payload.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def weights(conn, name=None) -> dict:
    row = version(conn, name) if name else active(conn)
    if not row:
        raise ModelError("No such model version" if name else "No model is active")
    model = load(row)
    payload = {"format": FORMAT, "version": row["version"], "features": list(FEATURES),
               "coef": [float(c) for c in model.coef_[0]],
               "intercept": float(model.intercept_[0]),
               "training_samples": row.get("training_samples"), "metrics": row["metrics"],
               "source": row.get("source"), "exported_at": _now()}
    payload["sha256"] = _payload_hash(payload)
    return payload


def export_weights(conn, name, path, by) -> dict:
    payload = weights(conn, name)
    target = Path(str(path))
    if target.is_dir() or not target.suffix:
        target = target / f"model_{payload['version']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _audit(conn, "model exported", {"version": payload["version"], "path": str(target),
                                    "sha256": payload["sha256"]}, by)
    return {"path": str(target), "version": payload["version"], "sha256": payload["sha256"],
            "bytes": target.stat().st_size}


def check_payload(payload, fmt=FORMAT) -> None:
    """Refuse anything that is not exactly an indicator model of ours."""
    if not isinstance(payload, dict) or payload.get("format") != fmt:
        raise ModelError("This file is not an AI-writing indicator model")
    if list(payload.get("features") or []) != list(FEATURES):
        raise ModelError("The model uses different features from this version")
    coef = payload.get("coef")
    if not isinstance(coef, list) or len(coef) != len(FEATURES):
        raise ModelError("The model's weights have the wrong shape")
    numbers = list(coef) + [payload.get("intercept")]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers):
        raise ModelError("The model's weights are not all finite numbers")
    if payload.get("sha256") != _payload_hash(payload):
        raise ModelError("The file's checksum does not match its contents")


def import_weights(conn, path, by, *, activate_now=False) -> dict:
    """Import exported weights as a new version, evaluated on local
    outcomes when there are enough of them."""
    try:
        payload = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelError(f"Could not read the model file: {exc}") from None
    check_payload(payload)
    model = _linear(payload["coef"], payload["intercept"])
    data = labelled_set(conn)
    metrics = evaluate(model, data) if len(data) >= MIN_LABELLED else {"evaluated_on": 0}
    metrics["imported_from"] = payload.get("version")
    out = _register(conn, version=_new_version(conn, "imp"), model=model, source="imported",
                    n=payload.get("training_samples") or 0, metrics=metrics, by=by,
                    note=f"Imported from {Path(str(path)).name}")
    if activate_now:
        activate(conn, out["version"], by, reason="imported")
    return out


def register_linear(conn, *, coef, intercept, source, n, by, note=None) -> dict:
    """A new version from raw weights (federated aggregation), evaluated on
    local outcomes when there are enough of them."""
    model = _linear(coef, intercept)
    data = labelled_set(conn)
    metrics = evaluate(model, data) if len(data) >= MIN_LABELLED else {"evaluated_on": 0}
    return _register(conn, version=_new_version(conn, "fed" if source == "federated" else "m"),
                     model=model, source=source, n=n, metrics=metrics, by=by, note=note)


def coefficients(row) -> tuple[list[float], float]:
    model = load(row)
    return [float(c) for c in model.coef_[0]], float(model.intercept_[0])
