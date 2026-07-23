import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.db import (
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


def require(user, permission, raise_=False):
    if can(user, permission):
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
    except sqlite3.OperationalError:
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
