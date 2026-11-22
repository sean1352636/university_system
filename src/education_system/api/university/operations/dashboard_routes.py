"""Dashboards: the figures behind the GUI's role dashboards.

All of it comes from ``DashboardService``, which the GUI uses too, so there is
no second set of queries to drift. The view follows the caller's role, never a
request parameter. Parents and alumni have no dashboard in the GUI, so they get
a 403 rather than an empty one.

Routes (under ``/api/v1/university/dashboard``):

* ``GET /``                       the caller's own view
* ``GET /students/<student_id>``  that student, or an administrator / staff member
* ``GET /operations``             institution-wide figures, administrators only
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from education_system.api.university import _identity
from education_system.platform.delivery.api.kernel.problems import problem
from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    current_subject_id,
    require_staff,
    token_required,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.shared.analytics.dashboard.dashboard_service import (
    DashboardService,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

#: Instructors see their own teaching view, not any student's: nothing here
#: narrows a student's dashboard to the modules an instructor teaches.
_STUDENT_RECORD_ROLES = {"admin", "superadmin", "staff"}
#: Only administrators see this tab in the GUI. The figures include grade
#: distributions per instructor and institution-wide financial aid.
_OPERATIONS_CAPABILITY = "system_admin"


def _ticket_actor() -> dict:
    """The caller as the ticket service takes them, as the helpdesk routes do."""
    return {"username": _identity.username(), "role": _identity.service_role(),
            "id": _identity.shared_auth_id()}


def _student_view(student_id: str) -> dict:
    data = DashboardService.get_student_dashboard_data(student_id)
    data["financial_summary"] = DashboardService.get_student_financial_summary(student_id)
    return data


def _deny_unless_self_or_records_staff(student_id: str):
    """403 unless it is the caller's own record or they hold a records role."""
    if _identity.owns(student_id):
        return authorize_object(current_subject_id())
    return authorize_object(None, staff_roles=_STUDENT_RECORD_ROLES)


@dashboard_bp.route("", methods=["GET"])
@token_required
def my_dashboard():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    role = _identity.service_role()
    if role == "student":
        student_id = _identity.local_identity()[1]
        if not student_id:
            return problem(404, "You have no student record.")
        data = _student_view(student_id)
    elif role == "instructor":
        data = DashboardService.get_instructor_dashboard_data(_identity.username())
    elif role == "admin":
        data = DashboardService.get_admin_dashboard_data()
    elif role == "staff":
        # What may be seen is decided by the ticket service, per person.
        data = {"tickets": DashboardService.get_ticket_metrics(_ticket_actor())}
    else:
        return problem(403, "There is no dashboard for this role.")
    log_activity("view", "dashboard", user=_identity.username())
    return jsonify({"view": role, "data": data})


@dashboard_bp.route("/students/<student_id>", methods=["GET"])
@token_required
def student_dashboard(student_id: str):
    denied = _deny_unless_self_or_records_staff(student_id)
    if denied is not None:
        return denied
    log_activity("view", "dashboard_student", user=_identity.username())
    return jsonify({"view": "student", "student_id": student_id,
                    "data": _student_view(student_id)})


@dashboard_bp.route("/operations", methods=["GET"])
@token_required
def operations_dashboard():
    denied = require_staff(permission=_OPERATIONS_CAPABILITY)
    if denied is not None:
        return denied
    log_activity("view", "dashboard_operations", user=_identity.username())
    return jsonify({"view": "operations",
                    "data": DashboardService.get_operational_metrics(_ticket_actor())})
