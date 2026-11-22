"""Learner logins: create an FE learner's shared login when they are added.

Secondary, sixth form and university create a learner's login on add; this
is the same for FE. The username is the learner's student ID, which is how
FE sign-in finds the learner (``CollegeSession._find_student``). The
password is a random temporary one, shown to the admin once and e-mailed
to the learner with the ``learner_login`` template.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

from education_system.systems.fe_college.config import COLLEGE_NAME
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    student_repository as repo,
)

logger = logging.getLogger(__name__)

SYSTEM_KEY = "fe_college"
LEARNER_ROLE = "student"

# No 0/O, 1/l/I: the password gets read out and typed in by hand.
_PASSWORD_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


class AccountError(Exception):
    """The shared login database refused to create the account."""


@dataclass(frozen=True)
class NewLogin:
    """A login just created for a learner. ``password`` is shown once."""

    username: str
    password: str
    email: str
    welcome_detail: str


def has_login(student_id: str) -> bool:
    """Whether a shared account already uses this learner's student ID."""
    return _user_exists(student_id)


def create_login(student_id: str, *, send_welcome: bool = True) -> NewLogin:
    """Create the learner's shared login and e-mail them the details.

    Refused if an account with their student ID already exists: an existing
    login is never changed from here. A failure to send the welcome e-mail
    does not undo the account; it is reported in ``welcome_detail``.
    """
    learner = repo.get(student_id)
    if learner is None:
        raise ValidationError(f"No learner with ID {student_id}")
    username = learner.student_id
    if _user_exists(username):
        raise ValidationError(f"{learner.full_name} already has a login ({username})")

    password = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(12))
    try:
        from education_system.platform.identity.auth.core import UserAuth

        UserAuth().provision_user(
            username, password, display_name=learner.full_name,
            email=learner.email.strip() or None,
            systems=[(SYSTEM_KEY, LEARNER_ROLE)],
        )
    except Exception as exc:
        logger.exception("Creating a login for FE learner %s failed", student_id)
        raise AccountError(f"The login could not be created: {exc}") from exc
    logger.info("FE learner login %s created", username)

    try:
        from education_system.platform.cross_system import login_links

        login_links.try_sync_username(username)
    except Exception:
        logger.debug("Login link sync skipped for %s", username, exc_info=True)

    if not send_welcome:
        detail = "No welcome e-mail was sent."
    elif not learner.email.strip():
        detail = "No e-mail address on the record, so no welcome e-mail was sent."
    else:
        detail = _send_welcome(learner, username, password)
    return NewLogin(username=username, password=password, email=learner.email,
                    welcome_detail=detail)


def _user_exists(username: str) -> bool:
    if not (username or "").strip():
        return False
    from education_system.platform.identity.auth.db import connect

    conn = connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM users WHERE lower(username) = lower(?)", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def _send_welcome(learner, username: str, password: str) -> str:
    from education_system.systems.fe_college.services import email_templates

    try:
        result = email_templates.compose_from_template(
            "learner_login",
            {"first_name": learner.preferred_name or learner.first_name,
             "username": username, "password": password, "college_name": COLLEGE_NAME},
            to_name=learner.full_name, to_address=learner.email.strip(),
            student_id=learner.student_id, send_now=True,
        )
    except Exception as exc:
        logger.warning("Welcome e-mail for %s failed", username, exc_info=True)
        return f"The welcome e-mail could not be sent: {exc}"
    if not result.ok:
        return (f"The welcome e-mail to {learner.email} was saved but delivery failed: "
                f"{result.detail}")
    if result.delivered:
        return f"Welcome e-mail sent to {learner.email}."
    return f"Welcome e-mail to {learner.email} is recorded in the Email centre."
