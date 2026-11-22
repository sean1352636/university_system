"""Staff HR routes: staff records and leave.

The staff record is ``staff_profiles`` with its login (``users``); leave is
``leave_requests`` — both through ``_hr_service`` and ``access.py``, exactly
as ``hr_routes``: the caller (the token's ``sub``) sees their own records,
a line manager their reports', HR everyone's; only HR adds or changes staff
records, and pay is never part of one.
"""

from __future__ import annotations

import logging

from flask import Blueprint, request

from education_system.api.university.staff import _hr_service as hr
from education_system.api.university.staff.hr_routes import _body, _hr_gated, _paging
from education_system.platform.delivery.api.university.auth import token_required

logger = logging.getLogger(__name__)

staff_hr_bp = Blueprint("staff_hr", __name__, url_prefix="/api/staff-hr")


# ---- staff ----

@staff_hr_bp.route("/staff", methods=["GET"])
@token_required
def list_staff():
    return _hr_gated("staff_records", hr.list_staff, search=request.args.get("search"),
                     department=request.args.get("department"), **_paging())


@staff_hr_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id: int):
    return _hr_gated("staff_records", hr.get_staff, staff_id)


@staff_hr_bp.route("/staff", methods=["POST"])
@token_required
def create_staff():
    return _hr_gated("staff_records", hr.create_staff, _body(), status=201)


@staff_hr_bp.route("/staff/<int:staff_id>", methods=["PUT"])
@token_required
def update_staff(staff_id: int):
    return _hr_gated("staff_records", hr.update_staff, staff_id, _body())


# ---- leave-requests ----

@staff_hr_bp.route("/leave-requests", methods=["GET"])
@token_required
def list_leave_requests():
    return _hr_gated("leave_requests", hr.list_leave, person=request.args.get("staff_id"),
                     status=request.args.get("status"),
                     leave_type=request.args.get("leave_type"), **_paging())


@staff_hr_bp.route("/leave-requests/<int:request_id>", methods=["GET"])
@token_required
def get_leave_request(request_id: int):
    return _hr_gated("leave_requests", hr.get_leave, request_id)


@staff_hr_bp.route("/leave-requests", methods=["POST"])
@token_required
def create_leave_request():
    return _hr_gated("leave_requests", hr.submit_leave, _body(), status=201)
