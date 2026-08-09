"""REST API for Nursery 2-Year-Old Progress Check.

Exposes CRUD over the statutory EYFS two-year-old progress check records.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

progress_check_2yr_bp = Blueprint(
    "nsy_progress_check_2yr", __name__, url_prefix="/api/progress-check-2yr"
)


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
        return dataclasses.asdict(obj)
    return obj


@progress_check_2yr_bp.route("", methods=["GET"])
@progress_check_2yr_bp.route("/", methods=["GET"])
@_token_required
def list_checks():
    from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
        list_checks as _list,
    )

    pupil_id = request.args.get("pupil_id") or None
    rows = _list(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@progress_check_2yr_bp.route("/<check_id>", methods=["GET"])
@_token_required
def get_check(check_id):
    from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
        get_check as _get,
    )

    row = _get(check_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@progress_check_2yr_bp.route("", methods=["POST"])
@progress_check_2yr_bp.route("/", methods=["POST"])
@_token_required
def create_check():
    from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
        create_check as _create,
        ValidationError,
    )

    try:
        row = _create(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@progress_check_2yr_bp.route("/<check_id>", methods=["PUT"])
@_token_required
def update_check(check_id):
    from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
        get_check as _get,
        update_check as _update,
        ValidationError,
    )

    if _get(check_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = _update(check_id, request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@progress_check_2yr_bp.route("/<check_id>", methods=["DELETE"])
@_token_required
def delete_check(check_id):
    from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
        delete_check as _delete,
    )

    if not _delete(check_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "check_id": check_id})
