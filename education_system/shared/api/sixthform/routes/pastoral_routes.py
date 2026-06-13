"""REST API for Sixth Form Pastoral.

Exposes HTTP CRUD over the two most central pastoral submodules:

* safeguarding — concerns (with their chronological update notes) plus a
  read-only safeguarding summary dashboard.
* behaviour — behaviour-log entries plus a read-only behaviour summary.

Auth mirrors the other sixth-form route modules: a JWT bearer token
(validated by the university ``token_required`` if importable) or an
``X-Sixthform-Token`` header matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pastoral_bp = Blueprint("sf_pastoral", __name__, url_prefix="/api/sixthform/pastoral")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Safeguarding: concerns ─────────────────────────────────────────

@pastoral_bp.route("/safeguarding/concerns", methods=["GET"])
@_token_required
def list_concerns_route():
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    q = request.args
    open_only = (q.get("open_only", "").strip().lower()
                 in ("1", "true", "yes", "y", "on"))
    try:
        rows = data.list_concerns(
            student_id=q.get("student_id"),
            risk_level=q.get("risk_level"),
            status=q.get("status"),
            category=q.get("category"),
            reported_by_like=q.get("reported_by_like"),
            date_from=q.get("date_from"),
            date_to=q.get("date_to"),
            open_only=open_only,
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"concerns": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/safeguarding/concerns/<int:concern_id>", methods=["GET"])
@_token_required
def get_concern_route(concern_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    c = data.get_concern(concern_id)
    if c is None:
        return jsonify({"error": f"No concern {concern_id}"}), 404
    return jsonify(_dump(c))


@pastoral_bp.route("/safeguarding/concerns", methods=["POST"])
@_token_required
def create_concern_route():
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    try:
        c = data.create_concern(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(c)), 201


@pastoral_bp.route("/safeguarding/concerns/<int:concern_id>", methods=["PUT"])
@_token_required
def update_concern_route(concern_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    if data.get_concern(concern_id) is None:
        return jsonify({"error": f"No concern {concern_id}"}), 404
    try:
        c = data.update_concern(
            concern_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(c))


@pastoral_bp.route("/safeguarding/concerns/<int:concern_id>", methods=["DELETE"])
@_token_required
def delete_concern_route(concern_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    if not data.delete_concern(concern_id):
        return jsonify({"error": f"No concern {concern_id}"}), 404
    return jsonify({"deleted": concern_id})


# ── Safeguarding: chronological updates on a concern ───────────────

@pastoral_bp.route("/safeguarding/concerns/<int:concern_id>/updates",
                   methods=["GET"])
@_token_required
def list_updates_route(concern_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    if data.get_concern(concern_id) is None:
        return jsonify({"error": f"No concern {concern_id}"}), 404
    rows = data.list_updates(concern_id)
    return jsonify({"updates": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/safeguarding/concerns/<int:concern_id>/updates",
                   methods=["POST"])
@_token_required
def add_update_route(concern_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    try:
        u = data.add_update(
            concern_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(u)), 201


# ── Safeguarding: summary (read-only) ──────────────────────────────

@pastoral_bp.route("/safeguarding/summary", methods=["GET"])
@_token_required
def safeguarding_summary_route():
    from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
        safeguarding as data,
    )
    return jsonify(_dump(data.summary()))


# ── Behaviour: entries ─────────────────────────────────────────────

@pastoral_bp.route("/behaviour/entries", methods=["GET"])
@_token_required
def list_entries_route():
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    q = request.args
    fu = q.get("follow_up_required")
    follow_up_required = None
    if fu is not None:
        follow_up_required = fu.strip().lower() in ("1", "true", "yes", "y", "on")
    try:
        rows = data.list_entries(
            student_id=q.get("student_id"),
            entry_type=q.get("entry_type"),
            category=q.get("category"),
            severity=q.get("severity"),
            recorded_by_like=q.get("recorded_by_like"),
            date_from=q.get("date_from"),
            date_to=q.get("date_to"),
            follow_up_required=follow_up_required,
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"entries": _dump(rows), "count": len(rows)})


@pastoral_bp.route("/behaviour/entries/<int:entry_id>", methods=["GET"])
@_token_required
def get_entry_route(entry_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    e = data.get_entry(entry_id)
    if e is None:
        return jsonify({"error": f"No entry {entry_id}"}), 404
    return jsonify(_dump(e))


@pastoral_bp.route("/behaviour/entries", methods=["POST"])
@_token_required
def create_entry_route():
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    try:
        e = data.create_entry(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(e)), 201


@pastoral_bp.route("/behaviour/entries/<int:entry_id>", methods=["PUT"])
@_token_required
def update_entry_route(entry_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    if data.get_entry(entry_id) is None:
        return jsonify({"error": f"No entry {entry_id}"}), 404
    try:
        e = data.update_entry(
            entry_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(e))


@pastoral_bp.route("/behaviour/entries/<int:entry_id>", methods=["DELETE"])
@_token_required
def delete_entry_route(entry_id: int):
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    if not data.delete_entry(entry_id):
        return jsonify({"error": f"No entry {entry_id}"}), 404
    return jsonify({"deleted": entry_id})


# ── Behaviour: summary (read-only) ─────────────────────────────────

@pastoral_bp.route("/behaviour/summary", methods=["GET"])
@_token_required
def behaviour_summary_route():
    from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
        behaviour as data,
    )
    return jsonify(_dump(data.summary()))
