"""REST API for Secondary School pastoral."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pastoral_bp = Blueprint("sec_pastoral", __name__, url_prefix="/api/pastoral")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


# ── Behaviour ───────────────────────────────────────────────────

@pastoral_bp.route("/behaviour", methods=["GET"])
@_token_required
def list_behaviour():
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (  # noqa: E501
        behaviour as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    args = request.args
    try:
        rows = data.list_incidents(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            incident_type=args.get("incident_type"),
            polarity=args.get("polarity"),
            severity=args.get("severity"),
            status=args.get("status"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/behaviour/<int:incident_id>", methods=["GET"])
@_token_required
def get_behaviour(incident_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (  # noqa: E501
        behaviour as data,
    )
    rec = data.get(incident_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pastoral_bp.route("/behaviour", methods=["POST"])
@_token_required
def create_behaviour():
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (  # noqa: E501
        behaviour as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    try:
        rec = data.log_incident(_body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pastoral_bp.route("/behaviour/<int:incident_id>", methods=["PUT"])
@_token_required
def update_behaviour(incident_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (  # noqa: E501
        behaviour as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    if data.get(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update(incident_id, _body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pastoral_bp.route("/behaviour/<int:incident_id>", methods=["DELETE"])
@_token_required
def delete_behaviour(incident_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (  # noqa: E501
        behaviour as data,
    )
    if not data.delete(incident_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": incident_id})


# ── Detentions ──────────────────────────────────────────────────

@pastoral_bp.route("/detentions", methods=["GET"])
@_token_required
def list_detentions():
    from education_system.secondarysch_system.modules.domain.pastoral.detentions import (  # noqa: E501
        detentions as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    args = request.args
    try:
        rows = data.list_detentions(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            status=args.get("status"),
            detention_type=args.get("detention_type"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
            supervisor=args.get("supervisor"),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/detentions/<int:detention_id>", methods=["GET"])
@_token_required
def get_detention(detention_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.detentions import (  # noqa: E501
        detentions as data,
    )
    rec = data.get(detention_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pastoral_bp.route("/detentions", methods=["POST"])
@_token_required
def create_detention():
    from education_system.secondarysch_system.modules.domain.pastoral.detentions import (  # noqa: E501
        detentions as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    try:
        rec = data.create(_body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pastoral_bp.route("/detentions/<int:detention_id>", methods=["PUT"])
@_token_required
def update_detention(detention_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.detentions import (  # noqa: E501
        detentions as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    if data.get(detention_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update(detention_id, _body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pastoral_bp.route("/detentions/<int:detention_id>", methods=["DELETE"])
@_token_required
def delete_detention(detention_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.detentions import (  # noqa: E501
        detentions as data,
    )
    if not data.delete(detention_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": detention_id})


# ── Safeguarding ────────────────────────────────────────────────

@pastoral_bp.route("/safeguarding", methods=["GET"])
@_token_required
def list_safeguarding():
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    args = request.args
    try:
        rows = data.list_concerns(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            category=args.get("category"),
            severity=args.get("severity"),
            status=args.get("status"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/safeguarding/<int:concern_id>", methods=["GET"])
@_token_required
def get_safeguarding(concern_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    rec = data.get(concern_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pastoral_bp.route("/safeguarding", methods=["POST"])
@_token_required
def create_safeguarding():
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    try:
        rec = data.raise_concern(_body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pastoral_bp.route("/safeguarding/<int:concern_id>", methods=["PUT"])
@_token_required
def update_safeguarding(concern_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    if data.get(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update(concern_id, _body())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pastoral_bp.route("/safeguarding/<int:concern_id>", methods=["DELETE"])
@_token_required
def delete_safeguarding(concern_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    if not data.delete(concern_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": concern_id})


@pastoral_bp.route("/safeguarding/<int:concern_id>/actions", methods=["GET"])
@_token_required
def list_safeguarding_actions(concern_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    if data.get(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_actions(concern_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/safeguarding/<int:concern_id>/actions", methods=["POST"])
@_token_required
def add_safeguarding_action(concern_id: int):
    from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (  # noqa: E501
        safeguarding as data,
    )
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (  # noqa: E501
        ValidationError,
    )
    payload = dict(_body())
    payload["concern_id"] = concern_id
    try:
        rec = data.add_action(payload)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201
