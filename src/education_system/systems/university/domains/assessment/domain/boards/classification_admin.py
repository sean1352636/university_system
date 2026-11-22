"""Classification rule sets for the Assessment Boards screens (own connections).

Thin, transaction-owning wrappers over
``application.assessment.classification_rules`` so the GUI and CLI never hold a
connection. Changing rule sets and bindings is for administrators (registry);
any staff member may read them and preview a student's classification.
"""

from __future__ import annotations

import json
from typing import Any

from education_system.systems.university.application.assessment import classification_rules
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

ADMIN_ROLES = frozenset({"admin", "administrator", "superadmin", "registrar"})
SCHEMES = tuple(classification_rules.TEMPLATES)


def _require_admin(role: str | None) -> None:
    if str(role or "").lower() not in ADMIN_ROLES:
        raise PermissionError("Only registry administrators can change classification rules")


def template(scheme: str) -> str:
    """The scheme's sector-norm starting point, as editable JSON."""
    if scheme not in classification_rules.TEMPLATES:
        raise ValueError(f"Scheme must be one of {', '.join(SCHEMES)}")
    return json.dumps(classification_rules.TEMPLATES[scheme], indent=2)


def rule_sets() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return classification_rules.list_rule_sets(conn)


def bindings() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return classification_rules.list_bindings(conn)


def show(rule_set_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        return classification_rules.rule_set(conn, rule_set_id)


def create(name: str, scheme: str, config_json: str, *, actor: str, role: str,
           notes: str = "") -> int:
    _require_admin(role)
    try:
        config = json.loads(config_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"The rules are not valid JSON: {exc.msg} (line {exc.lineno})") from None
    with transaction() as conn:
        return classification_rules.create_rule_set(conn, name, scheme, config, actor, notes)


def bind(rule_set_id: int, *, actor: str, role: str, version_id: int | None = None,
         programme_code: str | None = None) -> int:
    _require_admin(role)
    with transaction() as conn:
        return classification_rules.bind(conn, rule_set_id, actor, version_id=version_id,
                                         programme_code=programme_code or None)


def unbind(binding_id: int, *, role: str) -> bool:
    _require_admin(role)
    with transaction() as conn:
        return classification_rules.unbind(conn, binding_id)


def preview(student_id: str) -> dict[str, Any]:
    """The student's classification and exit award under their rules (read-only)."""
    with get_connection() as conn:
        result = classification_rules.classify(conn, student_id)
        result["exit_award"] = classification_rules.exit_award(conn, student_id)
        return result


__all__ = ["ADMIN_ROLES", "SCHEMES", "bind", "bindings", "create", "preview", "rule_sets",
           "show", "template", "unbind"]
