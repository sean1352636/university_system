"""Onboarding wizard helpers for Sixth Form User Management.

Drives the "pick a role template → preview permissions → create user →
issue one-time setup link → notify by email" flow. The user is created
in a *pending* state: their account exists, but a password is forced
on first login via the one-time token.

Schema-touching writes use the existing lifecycle helpers so audit
and extras flow through the standard path.
"""

from __future__ import annotations

import datetime
import logging
import secrets
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.governance.user_management import (
    lifecycle,
)
from education_system.systems.sixth_form.interfaces import user_accounts as _ua
from education_system.systems.sixth_form.interfaces.user_accounts import (
    DEFAULT_ROLE, SYSTEM_KEY, UserAccountError, UserRow,
)

logger = logging.getLogger(__name__)


# ── Role templates ────────────────────────────────────────────────────

@dataclass
class RoleTemplate:
    key: str
    label: str
    role: str
    description: str
    permissions_preview: list[str] = field(default_factory=list)
    default_department: str | None = None
    default_job_title: str | None = None


TEMPLATES: dict[str, RoleTemplate] = {
    "student": RoleTemplate(
        key="student",
        label="Student",
        role="student",
        description="Standard Year 12 / 13 student. Self-service "
                     "portal access only.",
        permissions_preview=[
            "View own profile, timetable, attendance",
            "Submit UCAS / progression info",
            "Read own gradebook and reports",
        ],
        default_job_title="Sixth-form student",
    ),
    "form_tutor": RoleTemplate(
        key="form_tutor",
        label="Form Tutor",
        role="teacher",
        description="Pastoral lead for a tutor group; sees their "
                     "students' data and writes pastoral notes.",
        permissions_preview=[
            "Read all students in assigned tutor group",
            "Record behaviour / attendance concerns",
            "Edit IEPs and tutor-group communications",
        ],
        default_department="Pastoral",
        default_job_title="Form Tutor",
    ),
    "subject_teacher": RoleTemplate(
        key="subject_teacher",
        label="Subject Teacher",
        role="teacher",
        description="Teaches A-Level / Level-3 classes. Manages "
                     "gradebook, attendance, lesson plans, homework.",
        permissions_preview=[
            "Manage gradebook for assigned classes",
            "Record attendance",
            "Set / mark homework and assignments",
        ],
        default_department="Academic",
        default_job_title="Teacher",
    ),
    "head_of_department": RoleTemplate(
        key="head_of_department",
        label="Head of Department",
        role="manager",
        description="Department lead — line-manages staff and "
                     "monitors departmental KPIs.",
        permissions_preview=[
            "Approve cover / leave for department staff",
            "Read all gradebooks across the department",
            "Run departmental reports",
        ],
        default_department="Academic",
        default_job_title="Head of Department",
    ),
    "exams_officer": RoleTemplate(
        key="exams_officer",
        label="Exams Officer",
        role="staff",
        description="Manages exam entries, room bookings, special "
                     "arrangements and results-day operations.",
        permissions_preview=[
            "Manage exam entries and timetables",
            "Approve access arrangements",
            "Run results-day workflow",
        ],
        default_department="Exams",
        default_job_title="Exams Officer",
    ),
    "admin": RoleTemplate(
        key="admin",
        label="Sixth-form Administrator",
        role="admin",
        description="Full administrative access to the sixth-form "
                     "system. Reserve for trusted staff only.",
        permissions_preview=[
            "Full user-management access",
            "Full read/write across every module",
            "System configuration and audit log",
        ],
        default_department="Administration",
        default_job_title="Administrator",
    ),
}


def list_templates() -> list[RoleTemplate]:
    return list(TEMPLATES.values())


def get_template(key: str) -> RoleTemplate:
    if key not in TEMPLATES:
        raise UserAccountError(f"Unknown template: {key!r}")
    return TEMPLATES[key]


# ── Schema ────────────────────────────────────────────────────────────

def _init_schema(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_pending_setups (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    template_key TEXT,
                    issued_by TEXT,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    consumed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_pending_setups_user
                ON user_pending_setups(user_id, status)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("user_pending_setups schema init failed")
        raise


# ── Token ─────────────────────────────────────────────────────────────

DEFAULT_TOKEN_TTL_HOURS = 48


def _issue_token(auth: Any, user_id: int, *,
                  template_key: str | None,
                  ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS) -> str:
    _init_schema(auth)
    token = secrets.token_urlsafe(24)
    now = datetime.datetime.now()
    issued_at = now.isoformat(timespec='seconds')
    expires_at = (now + datetime.timedelta(hours=ttl_hours)) \
        .isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_pending_setups
                (token, user_id, template_key, issued_by,
                 issued_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (token, user_id, template_key, actor,
                  issued_at, expires_at))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Could not record onboarding token")
        raise UserAccountError(f"Could not record token: {e}") from e
    return token


# ── Email ─────────────────────────────────────────────────────────────

def _send_welcome(email: str, *, username: str, display_name: str,
                   token: str, template: RoleTemplate) -> bool:
    try:
        from education_system.systems.university.infrastructure.utils.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email_service import failed — skipping welcome")
        return False
    if not email:
        return False
    subject = "Welcome to the Sixth Form — set up your account"
    body = (
        f"Hello {display_name or username},\n\n"
        f"An account has been created for you on the Sixth Form System.\n"
        f"  Username: {username}\n"
        f"  Role: {template.label}\n\n"
        f"To finish setting up your account, use the one-time setup "
        f"token below (valid for "
        f"{DEFAULT_TOKEN_TTL_HOURS} hours):\n\n"
        f"  {token}\n\n"
        f"If you weren't expecting this, ignore the email — the token "
        f"will expire automatically.\n"
    )
    try:
        send_email(email, subject, body)
        return True
    except Exception:
        logger.exception("Welcome email send failed for %s", email)
        return False


# ── Onboard ───────────────────────────────────────────────────────────

@dataclass
class OnboardResult:
    user: UserRow
    token: str
    email_sent: bool
    template: RoleTemplate


def onboard(
    auth: Any, *,
    template_key: str,
    username: str,
    display_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    line_manager_id: int | None = None,
    notes: str | None = None,
    initial_password: str | None = None,
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
) -> OnboardResult:
    """Run the full onboarding pipeline: create user with the chosen
    template, attach extras, issue a one-time setup token, and email
    the welcome message. Returns the new user + token so the caller
    can show / print it as a fallback when no email is on file.
    """
    template = get_template(template_key)
    # Initial password: random URL-safe value if not supplied — the
    # token is the real first-login mechanism.
    pwd = initial_password or secrets.token_urlsafe(18)
    department = department or template.default_department
    job_title = job_title or template.default_job_title

    user = lifecycle.create_user_full(
        auth, username=username, password=pwd,
        display_name=display_name, email=email,
        role=template.role, system_key=SYSTEM_KEY,
        phone=phone, department=department, job_title=job_title,
        line_manager_id=line_manager_id, notes=notes,
    )
    token = _issue_token(auth, user.id, template_key=template.key,
                          ttl_hours=ttl_hours)
    email_sent = _send_welcome(email or "", username=username,
                                display_name=display_name or username,
                                token=token, template=template)
    lifecycle._audit(auth, "user_onboard", user.id, {
        "template": template.key, "email_sent": email_sent,
        "token_ttl_hours": ttl_hours,
    })
    logger.info("Onboarded user_id=%d via template=%s "
                "(email_sent=%s)", user.id, template.key, email_sent)
    return OnboardResult(user=user, token=token,
                         email_sent=email_sent, template=template)


def consume_token(auth: Any, token: str) -> int | None:
    """Mark a token consumed and return its user_id. Returns ``None``
    if the token is missing, expired, or already consumed."""
    _init_schema(auth)
    now = datetime.datetime.now()
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT user_id, expires_at, status FROM user_pending_setups "
                "WHERE token = ?", (token,)).fetchone()
            if r is None:
                return None
            if r["status"] != 'Pending':
                return None
            if r["expires_at"]:
                try:
                    if datetime.datetime.fromisoformat(r["expires_at"]) < now:
                        return None
                except ValueError:
                    pass
            conn.execute(
                "UPDATE user_pending_setups SET status='Consumed', "
                "consumed_at=? WHERE token=?",
                (now.isoformat(timespec='seconds'), token))
            conn.commit()
            return r["user_id"]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("consume_token failed")
        return None


def revoke_token(auth: Any, token: str) -> bool:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "UPDATE user_pending_setups SET status='Revoked' "
                "WHERE token=? AND status='Pending'", (token,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("revoke_token failed")
        return False
