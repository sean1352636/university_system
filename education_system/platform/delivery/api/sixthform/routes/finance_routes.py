"""REST API for Sixth Form Finance.

Exposes CRUD over the two most central finance submodules:

* fees       — fee items + payments against them
* bursaries  — bursary applications + disbursements

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

finance_bp = Blueprint("sf_finance", __name__, url_prefix="/api/sixthform/finance")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


# ── fees ────────────────────────────────────────────────────────────

@finance_bp.route("/fees", methods=["GET"])
@_token_required
def list_fee_items():
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    kwargs = {}
    for key in ("student_id", "category", "academic_year", "stored_status"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    try:
        rows = data.list_items(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"fees": _dump(rows), "count": len(rows)})


@finance_bp.route("/fees/<int:fee_id>", methods=["GET"])
@_token_required
def get_fee_item(fee_id: int):
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    item = data.get_item(fee_id)
    if item is None:
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    return jsonify(_dump(item))


@finance_bp.route("/fees", methods=["POST"])
@_token_required
def create_fee_item():
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    try:
        item = data.create_item(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(item)), 201


@finance_bp.route("/fees/<int:fee_id>", methods=["PUT"])
@_token_required
def update_fee_item(fee_id: int):
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    if data.get_item(fee_id) is None:
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    try:
        item = data.update_item(fee_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(item))


@finance_bp.route("/fees/<int:fee_id>", methods=["DELETE"])
@_token_required
def delete_fee_item(fee_id: int):
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    if not data.delete_item(fee_id):
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    return jsonify({"deleted": fee_id})


@finance_bp.route("/fees/<int:fee_id>/payments", methods=["GET"])
@_token_required
def list_fee_payments(fee_id: int):
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    try:
        rows = data.list_payments(fee_id=fee_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"payments": _dump(rows), "count": len(rows)})


@finance_bp.route("/fees/<int:fee_id>/payments", methods=["POST"])
@_token_required
def create_fee_payment(fee_id: int):
    from education_system.systems.sixth_form.domain.finance.fees import fees as data
    try:
        pay = data.create_payment(fee_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pay)), 201


# ── bursaries ───────────────────────────────────────────────────────

@finance_bp.route("/bursaries", methods=["GET"])
@_token_required
def list_bursary_applications():
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    kwargs = {}
    for key in ("student_id", "bursary_type", "status", "academic_year",
                "assessed_by"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    try:
        rows = data.list_applications(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"applications": _dump(rows), "count": len(rows)})


@finance_bp.route("/bursaries/<int:application_id>", methods=["GET"])
@_token_required
def get_bursary_application(application_id: int):
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    app = data.get_application(application_id)
    if app is None:
        return jsonify({"error": f"No application #{application_id}"}), 404
    return jsonify(_dump(app))


@finance_bp.route("/bursaries", methods=["POST"])
@_token_required
def create_bursary_application():
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    try:
        app = data.create_application(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 201


@finance_bp.route("/bursaries/<int:application_id>", methods=["PUT"])
@_token_required
def update_bursary_application(application_id: int):
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    if data.get_application(application_id) is None:
        return jsonify({"error": f"No application #{application_id}"}), 404
    try:
        app = data.update_application(
            application_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app))


@finance_bp.route("/bursaries/<int:application_id>", methods=["DELETE"])
@_token_required
def delete_bursary_application(application_id: int):
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    if not data.delete_application(application_id):
        return jsonify({"error": f"No application #{application_id}"}), 404
    return jsonify({"deleted": application_id})


@finance_bp.route("/bursaries/<int:application_id>/disbursements",
                  methods=["GET"])
@_token_required
def list_bursary_disbursements(application_id: int):
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as data,
    )
    try:
        rows = data.list_disbursements(application_id=application_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"disbursements": _dump(rows), "count": len(rows)})
