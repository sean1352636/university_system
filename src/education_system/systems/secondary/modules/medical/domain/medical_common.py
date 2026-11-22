"""Shared helpers for the medical modules (:mod:`medical`,
:mod:`medical_incidents`): who may change things and the audit trail.

Field cleaning is the same as the SEND modules' (:mod:`send_common`)."""

from __future__ import annotations

import json
from typing import Any

from education_system.systems.secondary.modules.send.domain.send_common import (  # noqa: F401
    PUPIL_COLS,
    _blank,
    _bool,
    _choice,
    _date,
    _make,
    _name,
    _need_pupil,
    _number,
    _pupil,
    _text,
    add_months,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import MEDICAL_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

_SCHEMA = """
CREATE TABLE IF NOT EXISTS medical_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id   INTEGER,
    item       TEXT NOT NULL,
    item_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_audit_pupil ON medical_audit (pupil_id);
"""
database.register_schema("medical_audit", _SCHEMA)


def is_editor(actor: Principal) -> bool:
    return actor.role in MEDICAL_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"medical.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see medical information.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the school office / first aid lead can change "
                                     "medical records.")


def _audit(conn, actor: Principal, item: str, action: str, *, pupil_id: int | None,
           item_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO medical_audit (pupil_id, item, item_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (pupil_id, item, item_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(pupil_id: int | None = None, *, item: str | None = None,
            item_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM medical_audit", [], []
    for col, val in (("pupil_id", pupil_id), ("item", item), ("item_id", item_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "pupil_id": r["pupil_id"], "item": r["item"],
                 "item_id": r["item_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def family_letter(template: str, label: str, pupil: P.Pupil, values: dict[str, Any],
                  actor: Principal) -> dict[str, Any]:
    """E-mail *template* to the pupil's contacts with parental responsibility
    (saved in the outbox). Returns {'message_id', 'emails'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    to = [(x.email, x.full_name) for x in C.emailable_for_pupils([pupil.pupil_id]).get(
        pupil.pupil_id, []) if x.email and x.parental_responsibility]
    if not to:
        return {"message_id": None, "emails": 0}
    t = email_templates.load_template(template)
    letters = []
    for address, name in to:
        subject, body = t.render({"recipient_name": name, "pupil_name": pupil.display_name,
                                  "sender_name": BH._staff_name(actor), **values})
        letters.append((address, name, subject, body))
    mid = E.save_prepared(template, label, label, "(one letter per contact)", letters,
                          actor=actor)
    return {"message_id": mid, "emails": len(letters)}
