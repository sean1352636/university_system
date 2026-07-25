"""REST API for Nursery Designated Safeguarding Lead (DSL) register.

Exposes CRUD over the DSL register plus a summary and staff-choice lookup.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

dsl_bp = Blueprint("nsy_dsl", __name__, url_prefix="/api/dsl")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        out = dataclasses.asdict(obj)
        # include the computed training_status property when present
        ts = getattr(obj, "training_status", None)
        if ts is not None:
            out["training_status"] = ts
        return out
    return obj


@dsl_bp.route("", methods=["GET"])
@_token_required
def list_records():
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import list_records as _list
    rows = _list()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@dsl_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import summary as _summary
    return jsonify(_summary())


@dsl_bp.route("/staff-choices", methods=["GET"])
@_token_required
def staff_choices():
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import (
        list_staff_choices as _choices,
    )
    rows = _choices()
    items = [{"staff_id": sid, "label": label} for sid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@dsl_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import get_record as _get
    rec = _get(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@dsl_bp.route("", methods=["POST"])
@_token_required
def create_record():
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import (
        ValidationError,
        create_record as _create,
    )
    try:
        rec = _create(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@dsl_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import (
        ValidationError,
        get_record as _get,
        update_record as _update,
    )
    if _get(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = _update(record_id, request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@dsl_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.systems.nursery.domain.safeguarding.dsl.dsl import (
        delete_record as _delete,
    )
    if not _delete(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
