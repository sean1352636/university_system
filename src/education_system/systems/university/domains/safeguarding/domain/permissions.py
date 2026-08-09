import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
from education_system.systems.university.infrastructure.database.db import (
    sqlite3 as _db_errors,
)
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.infrastructure.db import (
    _connect,
)

_ROLE_PERMISSIONS = {
    "student": {"view_own", "submit"},
    "staff": {"view_own", "submit", "view_case", "add_note", "add_action"},
    "instructor": {"view_own", "submit", "view_case", "add_note", "add_action"},
    "dsl": {
        "view_own",
        "submit",
        "view_case",
        "add_note",
        "add_action",
        "assign",
        "close",
        "export",
        "merge_split",
    },
    "safeguarding": {
        "view_own",
        "submit",
        "view_case",
        "add_note",
        "add_action",
        "assign",
        "close",
        "export",
        "merge_split",
    },
    "admin": {"*"},  # all permissions
    "superadmin": {"*"},
}


def can(user, permission):
    role = (user or {}).get("role", "").lower()
    perms = _ROLE_PERMISSIONS.get(role)
    if not perms:
        return False
    if "*" in perms:
        return True
    return permission in perms


def require(
    user,
    permission,
    raise_=False,
    *,
    purpose="safeguarding_casework",
    subject_id=None,
    fields=("case_summary",),
):
    role_allowed = can(user, permission)
    sensitive_allowed = role_allowed
    if permission in {"view_case", "export", "add_note", "add_action"}:
        from education_system.platform.governance.security.sensitive_access import (
            authorize_sensitive_fields,
        )

        requested_fields = ("*",) if permission == "export" else fields
        decision = authorize_sensitive_fields(
            actor_id=str((user or {}).get("id") or (user or {}).get("username") or "?"),
            actor_role=str((user or {}).get("role") or ""),
            domain="safeguarding",
            subject_id=str(subject_id) if subject_id is not None else None,
            fields=requested_fields,
            purpose=purpose,
        )
        sensitive_allowed = decision.allowed
    if role_allowed and sensitive_allowed:
        audit_log(
            actor=(user or {}).get("username", "?"),
            actor_role=(user or {}).get("role", "?"),
            action="permission_allowed",
            case_id=subject_id,
            details=f"permission={permission};purpose={purpose};fields={list(fields)}",
        )
        return True
    audit_log(
        actor=(user or {}).get("username", "?"),
        actor_role=(user or {}).get("role", "?"),
        action="permission_denied",
        details=f"permission={permission}",
    )
    if raise_:
        raise PermissionError(f"Role lacks permission: {permission}")
    return False


def audit_log(actor="?", action="?", case_id=None, details="", actor_role=None):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO safeguarding_audit_log"
            "(ts, actor, actor_role, action, case_id, details) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), actor, actor_role, action, case_id, details),
        )
        conn.commit()
        conn.close()
    except _db_errors.OperationalError:
        # init_db hasn't run yet — drop on the floor rather than crash callers
        pass


def list_audit_log(case_id=None, limit=200):
    conn = _connect()
    cur = conn.cursor()
    if case_id is None:
        cur.execute(
            "SELECT id, ts, actor, actor_role, action, case_id, details "
            "FROM safeguarding_audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    else:
        cur.execute(
            "SELECT id, ts, actor, actor_role, action, case_id, details "
            "FROM safeguarding_audit_log WHERE case_id=? "
            "ORDER BY id DESC LIMIT ?",
            (case_id, limit),
        )
    rows = cur.fetchall()
    conn.close()
    return rows


__all__ = ["_ROLE_PERMISSIONS", "can", "require", "audit_log", "list_audit_log"]
