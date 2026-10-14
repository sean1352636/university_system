"""Shared helpers for the student create/update flows.

Consolidates logic that had drifted across the three create paths (GUI single
create, GUI CSV bulk import, CLI create) plus the GUI update path:

* :func:`compute_age`             – age in whole years, with the day-of-month
                                    adjustment so it's never off by one;
* :func:`default_student_password`– the initial login password, one format
                                    everywhere;
* :func:`provision_student_login` – create the login in BOTH auth stores so a
                                    new student can actually sign in.

Front-end agnostic (no tkinter / no CLI I/O) so every path can share it.
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime

logger = logging.getLogger(__name__)


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def compute_age(dob, on=None) -> int:
    """Whole years from ``dob`` to ``on`` (default today).

    Includes the day-of-month adjustment so a birthday later in the year
    doesn't count yet — several hand-written copies omitted this and were off
    by one. ``dob`` / ``on`` may be a ``date``, ``datetime`` or
    ``"YYYY-MM-DD"`` string.
    """
    born = _to_date(dob)
    ref = _to_date(on) if on is not None else date.today()
    return ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))


def default_student_password(first_name, student_id) -> str:
    """Return an unpredictable bootstrap secret.

    The arguments remain for API compatibility only.  Callers must never show,
    email, log, or otherwise disclose this value; users activate their account
    through a separately issued single-use token.
    """
    del first_name, student_id
    return f"Aa1!{secrets.token_urlsafe(32)}"


def send_student_activation(email: str) -> bool:
    """Issue and email a hashed, expiring, single-use password setup token."""
    try:
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.delivery.api.auth import _send_password_reset_email

        result = PasswordResetService().request_reset(email)
        token = result.get("token")
        if not token:
            return False
        return bool(_send_password_reset_email(
            email=result["email"],
            username=result["username"],
            token=token,
            expires_at=result["expires_at"],
        ))
    except Exception as exc:
        logger.warning("Student activation delivery failed for %s: %s", email, exc)
        return False


def provision_student_login(auth, *, username, password, email,
                            first_name, last_name, role="student"):
    """Create the student's login in BOTH auth stores so the account works
    everywhere.

    * legacy ``student_records.db`` ``users`` / ``user_accounts`` rows (via the
      passed ``auth`` manager) — needed for chat-room membership and the legacy
      GUI/CLI screens;
    * the central ``auth.db`` shared-auth user — login, MFA and
      forgot-password all read from here.

    Best-effort and idempotent: returns ``{"legacy_ok": bool, "shared_ok":
    bool}`` and never raises. ``shared_ok`` is the one that gates whether the
    student can actually sign in.
    """
    legacy_ok = False
    if auth is not None:
        try:
            auth.create_user(
                username=username, password=password, email=email,
                first_name=first_name, last_name=last_name,
                role=role, student_id=username, password_reset_required=True,
            )
            legacy_ok = True
        except Exception as exc:
            logger.warning("Legacy user creation failed for %s: %s", username, exc)

    shared_ok = False
    try:
        from education_system.platform.identity.auth.core import UserAuth as _SharedUserAuth
        from education_system.platform.identity.auth.exceptions import AuthError as _SharedAuthError
        shared = _SharedUserAuth()
        try:
            shared.create_user(
                username=username, password=password,
                display_name=f"{first_name} {last_name}".strip(),
                email=email, systems=[("university", "student")],
            )
            shared_ok = True
        except _SharedAuthError as exc:
            # Existing username — the row is there, treat as success.
            shared_ok = "already exists" in str(exc).lower()
            if not shared_ok:
                raise
    except Exception as exc:
        logger.warning("Shared-auth creation failed for %s: %s", username, exc)

    if shared_ok:
        # Link the new login to the student's platform learner record, if
        # the student is registered on the platform yet. Never raises.
        from education_system.platform.cross_system import login_links
        login_links.try_sync_username(username)
    activation_sent = send_student_activation(email) if shared_ok else False
    return {
        "legacy_ok": legacy_ok,
        "shared_ok": shared_ok,
        "activation_sent": activation_sent,
    }
