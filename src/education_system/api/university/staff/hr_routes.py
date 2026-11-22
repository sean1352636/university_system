"""HR routes: staff, departments, instructors, leave, shifts, timesheets, appraisals.

Staff HR data (staff records, leave, timesheets, appraisals, shifts, HR
roles) is reached only through ``_hr_service``, which decides with
``domain/staff_hr/access.py`` what the caller may see and do. The caller is
the token's username (``sub``), never an id from the request: a member of
staff sees their own records, a line manager their reports', HR everyone's.
Departments and instructors are reference lists.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.api.university.staff import _hr_service as hr
from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

hr_bp = Blueprint("hr", __name__, url_prefix="/api/hr")


def _row_to_dict(row, exclude: set | None = None) -> dict:
    if row is None:
        return {}
    d = {k: row[k] for k in row.keys()}
    if exclude:
        for f in exclude:
            d.pop(f, None)
    return d


def _caller() -> dict:
    """The signed-in caller as Staff HR takes them (username = ``sub``)."""
    user = g.get("current_user") or {}
    return {"username": str(user.get("sub") or user.get("username") or "").strip(),
            "role": str(user.get("role") or "").lower(), "id": user.get("user_id")}


def _refused(exc: Exception):
    """A refusal as a response: PermissionError 403, a missing record 404,
    any other ValueError 400 (the message is fit to show)."""
    if isinstance(exc, PermissionError):
        status, error = 403, "Forbidden"
    elif "not found" in str(exc).lower():
        status, error = 404, "Not Found"
    else:
        status, error = 400, "Bad Request"
    return jsonify({"error": error, "message": str(exc), "status": status}), status


def _hr_gated(what, fn, *args, status=200, **kwargs):
    """``fn(caller, *args, **kwargs)`` from ``_hr_service`` as JSON; its
    access refusals as :func:`_refused`."""
    actor = _caller()
    try:
        result = fn(actor, *args, **kwargs)
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    log_activity("view" if request.method == "GET" else "update", what, user=actor["username"])
    if isinstance(result, list):
        result = {"items": result, "total": len(result)}
    return jsonify(result), status


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _paging() -> dict:
    page, per_page, _offset = get_pagination_params()
    return {"page": page, "per_page": per_page}


# ---- Staff ----

@hr_bp.route("/staff", methods=["GET"])
@token_required
def list_staff():
    return _hr_gated("staff", hr.list_staff, search=request.args.get("search"),
                     department=request.args.get("department"), **_paging())


@hr_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id: int):
    return _hr_gated("staff_member", hr.get_staff, staff_id)


@hr_bp.route("/my-team", methods=["GET"])
@token_required
def my_team():
    return _hr_gated("my_team", hr.my_team, deep=request.args.get("deep") in ("1", "true", "yes"))


@hr_bp.route("/roles", methods=["GET"])
@token_required
def list_hr_roles():
    return _hr_gated("hr_roles", hr.role_holders)


# ---- Departments ----

@hr_bp.route("/departments", methods=["GET"])
@token_required
def list_departments():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM departments WHERE is_active = 1 ORDER BY name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM departments WHERE is_active = 1"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "departments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hr_bp.route("/departments/<int:dept_id>", methods=["GET"])
@token_required
def get_department(dept_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM departments WHERE dept_id = ?", (dept_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Department {dept_id} not found")
    log_activity("view", "department", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Instructors ----

@hr_bp.route("/instructors", methods=["GET"])
@token_required
def list_instructors():
    department = request.args.get("department")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM instructors WHERE is_active = 1 AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_active = 1"]
        params: list = []
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM instructors" + where + " ORDER BY last_name, first_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM instructors" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "instructors", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Leave Requests ----

@hr_bp.route("/leave-requests", methods=["GET"])
@token_required
def list_leave_requests():
    return _hr_gated("leave_requests", hr.list_leave, person=request.args.get("user_id"),
                     status=request.args.get("status"), **_paging())


@hr_bp.route("/leave-requests", methods=["POST"])
@token_required
def create_leave_request():
    return _hr_gated("leave_request", hr.submit_leave, _body(), status=201)


@hr_bp.route("/leave-requests/<int:request_id>", methods=["PUT"])
@token_required
def update_leave_request(request_id: int):
    return _hr_gated("leave_request", hr.decide_leave, request_id, _body())


@hr_bp.route("/leave-balances", methods=["GET"])
@token_required
def leave_balances():
    return _hr_gated("leave_balances", hr.leave_balances, person=request.args.get("user_id"),
                     year=request.args.get("year"))


# ---- Shifts ----

@hr_bp.route("/shifts", methods=["GET"])
@token_required
def list_shifts():
    return _hr_gated("shifts", hr.list_shifts, person=request.args.get("staff_id"),
                     status=request.args.get("status"), **_paging())


@hr_bp.route("/shifts", methods=["POST"])
@token_required
def create_shift():
    return _hr_gated("shift", hr.create_shift, _body(), status=201)


# ---- Timesheets ----

@hr_bp.route("/timesheets", methods=["GET"])
@token_required
def list_timesheets():
    return _hr_gated("timesheets", hr.list_timesheets, person=request.args.get("user_id"),
                     status=request.args.get("status"), **_paging())


@hr_bp.route("/timesheets", methods=["POST"])
@token_required
def create_timesheet():
    return _hr_gated("timesheet", hr.create_timesheet, _body(), status=201)


@hr_bp.route("/timesheets/<int:timesheet_id>", methods=["PUT"])
@token_required
def update_timesheet(timesheet_id: int):
    return _hr_gated("timesheet", hr.update_timesheet, timesheet_id, _body())


# ---- Appraisals ----

@hr_bp.route("/appraisals", methods=["GET"])
@token_required
def list_appraisals():
    return _hr_gated("appraisals", hr.list_appraisals, person=request.args.get("user_id"),
                     status=request.args.get("status"), cycle_id=request.args.get("cycle_id"),
                     **_paging())
