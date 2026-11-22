"""Capability checks for the sixth-form REST routes.

Every flat route used to need only a valid token, so any signed-in
student or parent could list, edit or delete safeguarding concerns,
finance and student records. Each route module's ``_token_required``
now wraps its view in :func:`gate`, which runs after the token is
verified and:

1. resolves the caller's :class:`~access.Principal` (role, linked staff
   record, designations, per-user overrides);
2. finds the rule for the route in :data:`RULES` and checks the read or
   write capability — a route without a rule is refused, so a new route
   fails closed;
3. lets students through only on rules that name an ``owner`` path
   parameter, and only for their own student id;
4. binds the principal for the request so domain code calling
   ``access.current()`` sees the right user.
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass

from flask import g, jsonify, request

from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

logger = logging.getLogger(__name__)

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Rule:
    pattern: str            # regex searched in the mounted URL rule
    read: str               # capability for GET
    write: str              # capability for POST/PUT/PATCH/DELETE
    owner: str | None = None    # path param a student may match to self
    anyone: bool = False        # any signed-in user (term dates, feeds)


A = access
#: Route module (short name) -> ordered rules; first match wins.
RULES: dict[str, tuple[Rule, ...]] = {
    "academics_routes": (
        Rule(r"/(courses|subjects)", A.TEACHING, A.STUDENTS_MANAGE),
    ),
    "academic_year_routes": (
        Rule(r"/(import|webhooks)", A.GOVERNANCE, A.GOVERNANCE),
        Rule(r"", A.ACCOUNT, A.GOVERNANCE, anyone=True),
    ),
    "advanced_search_routes": (
        Rule(r"/advanced-search/", A.STUDENTS_VIEW, A.STUDENTS_VIEW),
    ),
    "assessment_routes": (
        Rule(r"/gradebook/students/<student_id>", A.ASSESSMENT, A.ASSESSMENT,
             owner="student_id"),
        Rule(r"/(predicted-grades|targets|reviews|gradebook)", A.ASSESSMENT,
             A.ASSESSMENT),
    ),
    "calendar_routes": (
        Rule(r"/portal/student/<student_id>", A.TEACHING, A.TEACHING,
             owner="student_id"),
        Rule(r"/(portal/parent|feed\.ics)", A.ACCOUNT, A.ACCOUNT, anyone=True),
        Rule(r"", A.TEACHING, A.TEACHING),
    ),
    "finance_routes": (
        Rule(r"/(fees|bursaries)", A.FINANCE, A.FINANCE),
    ),
    "governance_routes": (
        Rule(r"/policies", A.STAFF_DIRECTORY, A.GOVERNANCE),
        Rule(r"/risks", A.GOVERNANCE, A.GOVERNANCE),
    ),
    "onboarding_routes": (
        # Writes are checked again by the onboarding domain (admissions
        # or students.manage); sensitive tasks are masked there too.
        Rule(r"/onboarding/students/<student_id>", A.STUDENTS_VIEW,
             A.STUDENTS_MANAGE, owner="student_id"),
        Rule(r"/onboarding/reports", A.STUDENTS_VIEW, A.STUDENTS_VIEW),
        Rule(r"/onboarding/", A.STUDENTS_VIEW, A.STUDENTS_VIEW),
    ),
    "pastoral_routes": (
        # Any member of staff may REPORT a concern (KCSIE); only the
        # safeguarding team may read, change or archive one.
        Rule(r"/safeguarding/concerns$", A.SAFEGUARDING, A.TEACHING),
        Rule(r"/safeguarding/", A.SAFEGUARDING, A.SAFEGUARDING),
        Rule(r"/behaviour/", A.TEACHING, A.TEACHING),
    ),
    "progression_routes": (
        Rule(r"/(ucas|destinations)/?", A.CAREERS, A.CAREERS),
        Rule(r"/fe-referrals", A.STUDENTS_MANAGE, A.STUDENTS_MANAGE),
        Rule(r"/incoming-fe-applications", A.ADMISSIONS, A.ADMISSIONS),
        Rule(r"/linked-records/", A.STUDENTS_VIEW, A.STUDENTS_VIEW),
    ),
    "reports_routes": (
        Rule(r"", A.REPORTS, A.REPORTS),
    ),
    "staff_comms_routes": (
        Rule(r"/staff", A.STAFF_DIRECTORY, A.HR),
        Rule(r"/announcements", A.COMMS, A.COMMS),
    ),
    "student_services_routes": (
        Rule(r"/(admissions|enrolments)", A.ADMISSIONS, A.ADMISSIONS),
        Rule(r"/alumni", A.CAREERS, A.CAREERS),
    ),
    "students_routes": (
        Rule(r"/students/<student_id>", A.STUDENTS_VIEW, A.STUDENTS_MANAGE,
             owner="student_id"),
        Rule(r"/(students|identity)/", A.STUDENTS_VIEW, A.STUDENTS_MANAGE),
    ),
}


def _forbidden(message: str = "Forbidden"):
    return jsonify({"error": message, "status": 403}), 403


def _rule_for(module: str, url_rule: str) -> Rule | None:
    for rule in RULES.get(module.rsplit(".", 1)[-1], ()):
        if re.search(rule.pattern, url_rule):
            return rule
    return None


def decide(module: str, url_rule: str, method: str,
           p: access.Principal, view_kwargs: dict):
    """None to allow, or a Flask (response, status) to refuse."""
    rule = _rule_for(module, url_rule)
    if rule is None:
        logger.warning("No access rule for %s %s (%s) — refused",
                       method, url_rule, module)
        return _forbidden()
    if not p.username:
        return _forbidden()
    write = method.upper() not in _READ_METHODS
    capability = rule.write if write else rule.read
    if rule.anyone and not write:
        return None
    if p.is_staff:
        return None if p.can(capability) else _forbidden()
    if p.is_student and rule.owner and not write:
        own = view_kwargs.get(rule.owner)
        if p.student_id and own is not None and str(own) == p.student_id:
            return None
    return _forbidden()


def gate(view):
    """Wrap a route view with the capability check (inside token auth)."""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        p = access.from_request_user(g.get("current_user"))
        url_rule = request.url_rule.rule if request.url_rule else request.path
        denial = decide(view.__module__, url_rule, request.method, p, kwargs)
        if denial is not None:
            logger.info("Sixth-form API refused %s %s for %s (%s)",
                        request.method, url_rule, p.username or "?",
                        p.role or "no role")
            return denial
        token = access.bind_request(p)
        try:
            return view(*args, **kwargs)
        finally:
            access.unbind_request(token)

    return wrapper
