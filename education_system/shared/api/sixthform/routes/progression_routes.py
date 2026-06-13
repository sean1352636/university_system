"""REST API for Sixth Form Progression.

Exposes CRUD over UCAS applications (and their nested choices) plus KS5
destination records, so any HTTP client can reach the progression domain
without importing the sixth-form Python package directly.

UCAS endpoints cover applications and their choices; destinations
endpoints cover the upsert-style destination records and the headline
summary. Auth mirrors the other sixth-form routes: a JWT bearer token
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

progression_bp = Blueprint(
    "sf_progression", __name__, url_prefix="/api/sixthform/progression")


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


# ── UCAS applications ─────────────────────────────────────────────

@progression_bp.route("/ucas/applications", methods=["GET"])
@_token_required
def list_ucas_applications():
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    cycle_year = request.args.get("cycle_year")
    cy = None
    if cycle_year:
        try:
            cy = int(cycle_year)
        except ValueError:
            return jsonify({"error": "cycle_year must be an integer"}), 400
    try:
        rows = data.list_applications(
            student_id=student_id, cycle_year=cy, status=status)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"applications": _dump(rows), "count": len(rows)})


@progression_bp.route("/ucas/applications/<int:application_id>", methods=["GET"])
@_token_required
def get_ucas_application(application_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    app = data.get_application(application_id)
    if app is None:
        return jsonify({"error": f"No application {application_id}"}), 404
    return jsonify(_dump(app))


@progression_bp.route("/ucas/applications", methods=["POST"])
@_token_required
def create_ucas_application():
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    try:
        app = data.create_application(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 201


@progression_bp.route("/ucas/applications/<int:application_id>", methods=["PUT"])
@_token_required
def update_ucas_application(application_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    if data.get_application(application_id) is None:
        return jsonify({"error": f"No application {application_id}"}), 404
    try:
        app = data.update_application(
            application_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app))


@progression_bp.route("/ucas/applications/<int:application_id>",
                      methods=["DELETE"])
@_token_required
def delete_ucas_application(application_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    if not data.delete_application(application_id):
        return jsonify({"error": f"No application {application_id}"}), 404
    return jsonify({"deleted": application_id})


# ── UCAS choices (nested under an application) ─────────────────────

@progression_bp.route("/ucas/applications/<int:application_id>/choices",
                      methods=["GET"])
@_token_required
def list_ucas_choices(application_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    if data.get_application(application_id) is None:
        return jsonify({"error": f"No application {application_id}"}), 404
    rows = data.list_choices(application_id)
    return jsonify({"choices": _dump(rows), "count": len(rows)})


@progression_bp.route("/ucas/applications/<int:application_id>/choices",
                      methods=["POST"])
@_token_required
def create_ucas_choice(application_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    try:
        choice = data.create_choice(
            application_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(choice)), 201


@progression_bp.route("/ucas/choices/<int:choice_id>", methods=["GET"])
@_token_required
def get_ucas_choice(choice_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    choice = data.get_choice(choice_id)
    if choice is None:
        return jsonify({"error": f"No choice {choice_id}"}), 404
    return jsonify(_dump(choice))


@progression_bp.route("/ucas/choices/<int:choice_id>", methods=["PUT"])
@_token_required
def update_ucas_choice(choice_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    if data.get_choice(choice_id) is None:
        return jsonify({"error": f"No choice {choice_id}"}), 404
    try:
        choice = data.update_choice(
            choice_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(choice))


@progression_bp.route("/ucas/choices/<int:choice_id>", methods=["DELETE"])
@_token_required
def delete_ucas_choice(choice_id: int):
    from education_system.sixthform_system.modules.domain.progression.ucas import (
        ucas as data,
    )
    if not data.delete_choice(choice_id):
        return jsonify({"error": f"No choice {choice_id}"}), 404
    return jsonify({"deleted": choice_id})


# ── Destination records ───────────────────────────────────────────

@progression_bp.route("/destinations", methods=["GET"])
@_token_required
def list_destinations():
    from education_system.sixthform_system.modules.domain.progression.destinations import (  # noqa: E501
        destinations as data,
    )
    checkpoint = request.args.get("checkpoint")
    destination_type = request.args.get("destination_type")
    student_id = request.args.get("student_id")
    try:
        rows = data.list_records(
            checkpoint=checkpoint,
            destination_type=destination_type,
            student_id=student_id,
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"records": _dump(rows), "count": len(rows)})


@progression_bp.route("/destinations/<int:record_id>", methods=["GET"])
@_token_required
def get_destination(record_id: int):
    from education_system.sixthform_system.modules.domain.progression.destinations import (  # noqa: E501
        destinations as data,
    )
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": f"No record {record_id}"}), 404
    return jsonify(_dump(rec))


@progression_bp.route("/destinations", methods=["POST"])
@_token_required
def save_destination():
    """Upsert keyed on (student_id, checkpoint)."""
    from education_system.sixthform_system.modules.domain.progression.destinations import (  # noqa: E501
        destinations as data,
    )
    try:
        rec = data.save_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@progression_bp.route("/destinations/<int:record_id>", methods=["DELETE"])
@_token_required
def delete_destination(record_id: int):
    from education_system.sixthform_system.modules.domain.progression.destinations import (  # noqa: E501
        destinations as data,
    )
    if not data.delete_record(record_id):
        return jsonify({"error": f"No record {record_id}"}), 404
    return jsonify({"deleted": record_id})


@progression_bp.route("/destinations/summary", methods=["GET"])
@_token_required
def destinations_summary():
    from education_system.sixthform_system.modules.domain.progression.destinations import (  # noqa: E501
        destinations as data,
    )
    return jsonify(_dump(data.summary()))
