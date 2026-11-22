"""Shared machinery for the authz-coverage contract.

Kept beside the test rather than in the app so the check cannot be weakened
by editing application code.
"""

from __future__ import annotations

import ast
import inspect
from typing import Iterable

from flask import Flask

from education_system.platform.delivery.api.registry import SYSTEMS
from education_system.platform.delivery.api.versioning import reprefix

#: Proves who the caller is. Necessary, never sufficient for an object route.
AUTHENTICATION = frozenset({"token_required", "shared_token_required"})

#: Proves the caller may touch *this* object, or holds a required capability.
#: Mirrors ``platform/delivery/api/security/decorators.py``.
AUTHORIZATION = frozenset({
    "require_staff", "staff_required", "authorize_object", "scoped_to",
    "deny_unless_owner_or_staff", "role_required", "system_required",
})

#: Route-local helpers that call an AUTHORIZATION gate internally. A route
#: using one of these is gated; add a name here only when the helper
#: unconditionally returns the gate's denial.
LOCAL_GATE_HELPERS = frozenset({
    "_deny_unless_manager", "_authorize_student_access",
    # Health / wellbeing / dental API (api/university/pastoral/_health_access.py
    # and the route modules): each returns a 403 unless the caller is the
    # health team, the student themselves, or holds break-glass access.
    "deny_unless_may_view_health", "deny_unless_health_team", "health_scope",
    "_deny_unless_patient_access", "_authorize_record",
    # Helpdesk links / time / followers / incidents / e-mail review
    # (api/university/pastoral/helpdesk_routes.py): runs a student_support
    # service that refuses (403) anyone not working / seeing that ticket,
    # not support staff, or not an administrator, as the service requires.
    "_support_gated",
    # Staff HR (api/university/staff/hr_routes.py, staff_hr_routes.py): runs an
    # _hr_service function that refuses (403) anyone who is not the person,
    # in their management line, an approver or HR, per staff_hr/access.py.
    "_hr_gated",
    # Financial aid / accessibility list scoping (api/university/finance/
    # financial_aid_routes.py, pastoral/accessibility_routes.py): staff must
    # hold the capability (require_staff), everyone else is pinned to their
    # own subject, and a caller with no subject is refused (403).
    "_pin_or_deny",
    # Mentorship (api/university/pastoral/mentorship_routes.py): 403 unless
    # the caller is staff or the relationship's mentor or mentee.
    "_deny_unless_participant",
    # Mobile devices / sessions (api/university/operations/mobility_routes.py):
    # 403 unless the row's INTEGER user_id is the caller's JWT user_id, or the
    # caller holds system_admin (require_staff).
    "_deny_unless_own_device",
    # Absence check-in / kiosk (api/university/academics/absence_routes.py):
    # 403 unless the caller holds a register-taking capability (require_staff).
    "_deny_unless_register_taker",
    # Announcements (api/university/operations/announcement_routes.py): 403
    # unless the caller is staff and created it, or is an administrator.
    "_deny_unless_editor",
    # Chat rooms (api/university/operations/chat_routes.py): 403 unless the
    # caller is a member of the room, by local id, and not banned from it.
    "_deny_unless_room_member",
    # Dashboard (api/university/operations/dashboard_routes.py): 403 unless it
    # is the caller's own student record or they hold a records role.
    "_deny_unless_self_or_records_staff",
    # Users (api/university/operations/user_routes.py): 403 unless it is the
    # caller's own local profile or they are an administrator or staff.
    "_deny_unless_self_or_reader",
    # Documents (api/university/learners/document_routes.py): 403 unless the
    # caller owns or uploaded it or is an administrator; the second admits
    # administrators only.
    "_deny_unless_document_reader", "_deny_unless_document_admin",
})

_SOURCE_CACHE: dict[str, ast.Module | None] = {}


def _module_tree(fn) -> ast.Module | None:
    module = inspect.getmodule(fn)
    path = getattr(module, "__file__", None)
    if not path:
        return None
    if path not in _SOURCE_CACHE:
        try:
            _SOURCE_CACHE[path] = ast.parse(open(path, encoding="utf-8").read())
        except (OSError, SyntaxError):
            _SOURCE_CACHE[path] = None
    return _SOURCE_CACHE[path]


def gate_names(fn) -> set[str]:
    """Decorator names on *fn*, plus calls made in its body.

    Read from source rather than from the wrapped function, because the
    decorators use functools.wraps and leave no runtime marker to inspect.
    """
    tree = _module_tree(fn)
    if tree is None:
        return set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn.__name__:
            found = set()
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                found.add(target.attr if isinstance(target, ast.Attribute)
                          else getattr(target, "id", ""))
            found |= {c.func.id for c in ast.walk(node)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            return found
    return set()


def build_app(system_key: str = "university") -> tuple[Flask, object]:
    """Mount one system exactly as the server does, via the registry."""
    mount = next(m for m in SYSTEMS if m.key == system_key)
    app = Flask(__name__)
    for blueprint in mount.load():
        app.register_blueprint(
            blueprint, url_prefix=reprefix(blueprint.url_prefix, system_key))
    return app, mount


def route_id(rule) -> str:
    """Stable identifier for a rule, used as the allow-list key."""
    methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
    return f"{methods} {rule}"


def object_scoped_rules(app: Flask) -> Iterable:
    """Rules carrying a path parameter, i.e. addressing a specific object."""
    for rule in app.url_map.iter_rules():
        if "static" in str(rule):
            continue
        if rule.arguments:
            yield rule


def is_authorized(app: Flask, rule) -> bool:
    names = gate_names(app.view_functions[rule.endpoint])
    return bool(names & AUTHORIZATION) or bool(names & LOCAL_GATE_HELPERS)


def is_authenticated(app: Flask, rule) -> bool:
    return bool(gate_names(app.view_functions[rule.endpoint]) & AUTHENTICATION)
