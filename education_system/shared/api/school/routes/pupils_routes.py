"""REST API for Secondary School pupils."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pupils_bp = Blueprint("sec_pupils", __name__, url_prefix="/api/pupils")


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


# --------------------------------------------------------------------------- #
# pupils submodule  (id type: str, e.g. "Y1234567")
# --------------------------------------------------------------------------- #

@pupils_bp.route("/pupils", methods=["GET"])
@_token_required
def list_pupils_route():
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
        list_pupils,
        search_pupils,
    )
    q = request.args.get("q")
    rows = search_pupils(q) if q else list_pupils()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupils_bp.route("/pupils/<pupil_id>", methods=["GET"])
@_token_required
def get_pupil_route(pupil_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
        get_pupil,
    )
    pupil = get_pupil(pupil_id)
    if pupil is None:
        return jsonify({"error": f"No pupil with id {pupil_id}"}), 404
    return jsonify(_dump(pupil))


@pupils_bp.route("/pupils", methods=["POST"])
@_token_required
def create_pupil_route():
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
        ValidationError,
        create_pupil,
    )
    data = request.get_json(silent=True) or {}
    try:
        pupil = create_pupil(data)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pupil)), 201


@pupils_bp.route("/pupils/<pupil_id>", methods=["PUT"])
@_token_required
def update_pupil_route(pupil_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
        ValidationError,
        update_pupil,
    )
    data = request.get_json(silent=True) or {}
    try:
        pupil = update_pupil(pupil_id, data)
    except ValidationError as e:
        msg = str(e)
        if msg.startswith("No pupil with id"):
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(pupil))


@pupils_bp.route("/pupils/<pupil_id>", methods=["DELETE"])
@_token_required
def delete_pupil_route(pupil_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
        delete_pupil,
    )
    if not delete_pupil(pupil_id):
        return jsonify({"error": f"No pupil with id {pupil_id}"}), 404
    return jsonify({"deleted": pupil_id})


# --------------------------------------------------------------------------- #
# admissions submodule  (id type: str, e.g. "A1234567")
# --------------------------------------------------------------------------- #

@pupils_bp.route("/admissions", methods=["GET"])
@_token_required
def list_applications_route():
    from education_system.secondarysch_system.modules.domain.pupils.admissions.admissions import (
        ValidationError,
        list_applications,
    )
    status = request.args.get("status")
    try:
        rows = list_applications(status)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupils_bp.route("/admissions/<application_id>", methods=["GET"])
@_token_required
def get_application_route(application_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.admissions.admissions import (
        get_application,
    )
    app = get_application(application_id)
    if app is None:
        return jsonify({"error": f"No application with id {application_id}"}), 404
    return jsonify(_dump(app))


@pupils_bp.route("/admissions", methods=["POST"])
@_token_required
def create_application_route():
    from education_system.secondarysch_system.modules.domain.pupils.admissions.admissions import (
        ValidationError,
        create_application,
    )
    data = request.get_json(silent=True) or {}
    try:
        app = create_application(data)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 201


@pupils_bp.route("/admissions/<application_id>", methods=["PUT"])
@_token_required
def update_application_route(application_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.admissions.admissions import (
        ValidationError,
        update_application,
    )
    data = request.get_json(silent=True) or {}
    try:
        app = update_application(application_id, data)
    except ValidationError as e:
        msg = str(e)
        if msg.startswith("No application with id"):
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(app))


@pupils_bp.route("/admissions/<application_id>", methods=["DELETE"])
@_token_required
def delete_application_route(application_id: str):
    from education_system.secondarysch_system.modules.domain.pupils.admissions.admissions import (
        delete_application,
    )
    if not delete_application(application_id):
        return jsonify({"error": f"No application with id {application_id}"}), 404
    return jsonify({"deleted": application_id})


# --------------------------------------------------------------------------- #
# enrolment submodule  (read-only aggregates / year-group roll)
# --------------------------------------------------------------------------- #

@pupils_bp.route("/enrolment/roll", methods=["GET"])
@_token_required
def enrolment_roll_route():
    from education_system.secondarysch_system.modules.domain.pupils.enrolment.enrolment import (
        roll_by_year,
    )
    grouped = roll_by_year()
    payload = {year: _dump(pupils) for year, pupils in grouped.items()}
    return jsonify({"roll": payload})


@pupils_bp.route("/enrolment/leavers", methods=["GET"])
@_token_required
def enrolment_leavers_route():
    from education_system.secondarysch_system.modules.domain.pupils.enrolment.enrolment import (
        leavers,
    )
    rows = leavers()
    return jsonify({"items": _dump(rows), "count": len(rows)})
