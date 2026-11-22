"""Who may call the health, counselling, wellbeing and dental API routes.

Health data is UK GDPR special-category data. The policy itself lives in
``domains/health/application/health/access`` (shared with the GUI and CLI);
this module adapts it to the API's signed-in caller (``g.current_user``) and
turns a refusal into the usual ``({"error": ...}, 403)`` response, so a route
can do::

    denial = deny_unless_may_view_health(row["student_id"], "appointment",
                                         record_id=appointment_id)
    if denial is not None:
        return denial

In short:

* the health team (``access.CLINICAL_ROLES``) and administrators see every
  student; for counselling and wellbeing data that area's own practitioners
  (``access.AREA_ROLES``) count as the team too (``area="counselling"`` /
  ``area="wellbeing"``; ``pastoral=True`` means ``area="wellbeing"``);
* a student sees only their own data — the student number resolved from the
  username in ``users``, never the token's numeric id;
* everybody else (lecturers, generic staff, parents, alumni) sees nothing,
  unless they have opened that student's record with break-glass access.

Every successful look at a student's data is written to the immutable audit
log first; if that write fails the request is refused (fail closed).
"""

from __future__ import annotations

import logging

from flask import g, jsonify

from education_system.systems.university.domains.health.application.health import access

logger = logging.getLogger(__name__)

#: Wellbeing staff — part of the team for ``pastoral=True`` areas only. The
#: per-area lists live in ``access.AREA_ROLES`` (shared with the GUI and CLI).
PASTORAL_ROLES = access.AREA_ROLES["wellbeing"]


def _area(pastoral: bool, area: str | None) -> str | None:
    return area if area is not None else ("wellbeing" if pastoral else None)


def _forbidden(message: str):
    return jsonify({"error": "Forbidden", "message": message, "status": 403}), 403


def health_caller() -> access.HealthUser | None:
    """The signed-in caller as the health policy sees them."""
    user = g.get("current_user") or {}
    username = str(user.get("sub") or user.get("username") or "").strip()
    if not username:
        return None
    role = str(user.get("role") or "").lower()
    student_id = None
    if role in ("student", "alumni"):
        from education_system.systems.university.infrastructure.auth.session_user import (
            resolve_local_identity,
        )
        _local_id, student_id = resolve_local_identity(username)
    return access.from_user({"username": username, "role": role,
                             "id": user.get("user_id"), "student_id": student_id})


def is_health_team(who: access.HealthUser | None = None, *, pastoral: bool = False,
                   area: str | None = None) -> bool:
    who = who if who is not None else health_caller()
    if who is None:
        return False
    area = _area(pastoral, area)
    return who.is_clinician or (area is not None and who.role in access.AREA_ROLES[area])


def health_scope(*, pastoral: bool = False, area: str | None = None):
    """``(scope, denial)`` for a list route.

    ``scope`` is ``None`` when the caller may list every student, or the one
    student number they are confined to. ``denial`` is a 403 response for
    anyone else.
    """
    who = health_caller()
    area = _area(pastoral, area)
    try:
        if area is not None:
            return access.scope_area(who, area), None
        return access.scope(who), None
    except PermissionError as exc:
        return None, _forbidden(str(exc))


def deny_unless_health_team(what: str = "do this", *, pastoral: bool = False,
                            area: str | None = None):
    """403 unless the caller is on the health team (or that ``area``'s team)."""
    who = health_caller()
    if is_health_team(who, pastoral=pastoral, area=area):
        return None
    return _forbidden(f"Only the health team can {what}")


def deny_unless_may_view_health(student_id, area: str, *, record_id=None,
                                pastoral: bool = False, team_area: str | None = None):
    """403 unless the caller may see ``student_id``'s data; audits the view.
    ``area`` names the audit entry; ``team_area`` widens the team as in
    :func:`is_health_team`."""
    who = health_caller()
    allowed = is_health_team(who, pastoral=pastoral, area=team_area) or (
        student_id is not None and access.may_view(who, student_id))
    if not allowed:
        return _forbidden("You cannot see this student's health information")
    return audit_health_view(area, student_id=student_id, record_id=record_id, who=who)


def audit_health_view(area: str, *, student_id=None, record_id=None, who=None):
    """Record a view in the immutable audit log; 403 if that fails (fail closed)."""
    who = who if who is not None else health_caller()
    if who is None:
        return _forbidden("Sign in to use the health services")
    try:
        access.record_view(who, area, student_id=student_id, record_id=record_id)
    except PermissionError as exc:
        logger.warning("health view refused, audit write failed: %s", exc)
        return _forbidden(str(exc))
    return None


def own_student_id() -> str | None:
    """The caller's own student number, if they are a student."""
    who = health_caller()
    return who.student_id if who is not None and who.is_student else None


def unseal(rows, table: str | None = None) -> list[dict]:
    """Rows as dicts with every sealed value readable (``table`` is for the reader)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.unseal_rows(rows)


def seal(table: str, values: dict) -> dict:
    """``values`` as they should be stored in ``table`` (sealed columns sealed)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.seal_values(table, values)
