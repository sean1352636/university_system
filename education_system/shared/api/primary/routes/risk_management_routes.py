"""REST API for Primary Risk Management."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

risk_management_bp = Blueprint("pri_risk_management", __name__, url_prefix="/api/risk-management")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Risks ─────────────────────────────────────────────────────────

@risk_management_bp.route("", methods=["GET"])
@risk_management_bp.route("/", methods=["GET"])
@_token_required
def list_risks():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    q = request.args
    rows = data.list_risks(
        status=q.get("status"),
        category=q.get("category"),
        owner=q.get("owner"),
        open_only=q.get("open_only", "").lower() in ("1", "true", "yes"),
        review_due_only=q.get("review_due_only", "").lower() in ("1", "true", "yes"),
        min_score=int(q["min_score"]) if q.get("min_score") else None,
        search=q.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@risk_management_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    return jsonify(_dump(data.overview()))


@risk_management_bp.route("/heatmap", methods=["GET"])
@_token_required
def heatmap():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    grid = data.heatmap()
    return jsonify({"items": [
        {"likelihood": k[0], "impact": k[1], "count": v}
        for k, v in grid.items()
    ], "count": len(grid)})


@risk_management_bp.route("/<int:risk_id>", methods=["GET"])
@_token_required
def get_risk(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    row = data.get_risk(risk_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@risk_management_bp.route("/<int:risk_id>/view", methods=["GET"])
@_token_required
def view_risk(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    row = data.view_risk(risk_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@risk_management_bp.route("", methods=["POST"])
@risk_management_bp.route("/", methods=["POST"])
@_token_required
def create_risk():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    try:
        row = data.create_risk(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@risk_management_bp.route("/<int:risk_id>", methods=["PUT"])
@_token_required
def update_risk(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    if data.get_risk(risk_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_risk(risk_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@risk_management_bp.route("/<int:risk_id>", methods=["DELETE"])
@_token_required
def delete_risk(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    if not data.delete_risk(risk_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "risk_id": risk_id})


# ── Actions ───────────────────────────────────────────────────────

@risk_management_bp.route("/actions", methods=["GET"])
@_token_required
def list_actions():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    q = request.args
    rows = data.list_actions(
        risk_id=int(q["risk_id"]) if q.get("risk_id") else None,
        status=q.get("status"),
        open_only=q.get("open_only", "").lower() in ("1", "true", "yes"),
        overdue_only=q.get("overdue_only", "").lower() in ("1", "true", "yes"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@risk_management_bp.route("/actions/<int:action_id>", methods=["GET"])
@_token_required
def get_action(action_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    row = data.get_action(action_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@risk_management_bp.route("/<int:risk_id>/actions", methods=["POST"])
@_token_required
def add_action(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    try:
        row = data.add_action(risk_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@risk_management_bp.route("/actions/<int:action_id>", methods=["PUT"])
@_token_required
def update_action(action_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    if data.get_action(action_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_action(action_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@risk_management_bp.route("/actions/<int:action_id>", methods=["DELETE"])
@_token_required
def delete_action(action_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    if not data.delete_action(action_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "action_id": action_id})


# ── Reviews ───────────────────────────────────────────────────────

@risk_management_bp.route("/reviews", methods=["GET"])
@_token_required
def list_reviews():
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    q = request.args
    rows = data.list_reviews(
        risk_id=int(q["risk_id"]) if q.get("risk_id") else None,
        limit=int(q["limit"]) if q.get("limit") else 200,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@risk_management_bp.route("/reviews/<int:review_id>", methods=["GET"])
@_token_required
def get_review(review_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    row = data.get_review(review_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@risk_management_bp.route("/<int:risk_id>/reviews", methods=["POST"])
@_token_required
def add_review(risk_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    try:
        row = data.add_review(risk_id, _body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@risk_management_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review(review_id: int):
    from education_system.primarysch_system.modules.domain.risk_management import (
        risk_management as data,
    )
    if not data.delete_review(review_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "review_id": review_id})
