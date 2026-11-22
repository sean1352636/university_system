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


# ── shared sign-in state ────────────────────────────────────────────────
#: auth.db tables holding a user's credentials or sessions, cleared on erasure.
_AUTH_PERSONAL_TABLES = ("sessions", "mfa_secrets", "mfa_recovery_codes", "password_history",
                         "password_reset_tokens", "security_questions", "trusted_devices",
                         "webauthn_credentials", "oauth_accounts", "email_verification_tokens")


def _auth_connect(db_path=None):
    """The central auth.db (patched in tests)."""
    from education_system.platform.identity.auth.db import connect
    return connect(db_path)


def set_student_login_active(username, active: bool, db_path=None) -> bool:
    """Enable or disable a student's shared sign-in; disabling also ends
    their sessions. Best-effort: returns False (and logs) on failure."""
    try:
        conn = _auth_connect(db_path)
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?",
                               (str(username),)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE users SET is_active = ?, updated_at = datetime('now') "
                         "WHERE id = ?", (int(bool(active)), row[0]))
            if not active:
                conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (row[0],))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception:
        logger.warning("Could not %s sign-in for %s", "enable" if active else "disable",
                       username, exc_info=True)
        return False


def erase_student_login(username, db_path=None) -> bool:
    """For an erased student: disable the shared sign-in, remove its name and
    email, and delete its credentials and sessions."""
    try:
        conn = _auth_connect(db_path)
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?",
                               (str(username),)).fetchone()
            if not row:
                return False
            for table in _AUTH_PERSONAL_TABLES:
                try:
                    conn.execute(f'DELETE FROM "{table}" WHERE user_id = ?', (row[0],))
                except Exception:
                    continue  # table absent in this auth.db
            conn.execute("UPDATE users SET is_active = 0, display_name = 'Erased', "
                         "email = NULL, updated_at = datetime('now') WHERE id = ?", (row[0],))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception:
        logger.warning("Could not erase sign-in for %s", username, exc_info=True)
        return False


def verify_staff_password(username, password, db_path=None) -> bool:
    """Re-check a signed-in member of staff's password against the shared
    sign-in (used before approving an erasure)."""
    if not username or not password:
        return False
    try:
        from education_system.platform.identity.auth.password_manager import verify_password
        conn = _auth_connect(db_path)
        try:
            row = conn.execute("SELECT password_hash, legacy_salt FROM users WHERE username = ? "
                               "AND is_active = 1", (str(username),)).fetchone()
        finally:
            conn.close()
        return bool(row) and verify_password(password, row[0], row[1])
    except Exception:
        logger.warning("Password re-check failed for %s", username, exc_info=True)
        return False


def sync_sign_in_for_status(student_id, status, db_path=None) -> None:
    """Withdrawn or closed students lose their sign-in; reinstated or resumed
    (Active) students get it back. Other statuses leave it as it is."""
    if status in ("Withdrawn", "Closed"):
        set_student_login_active(student_id, False, db_path)
    elif status == "Active":
        set_student_login_active(student_id, True, db_path)


def create_visa_record(student_id, email_address, first_name, nationality, passport_number,
                       visa_expiry_date, brp_number, module_codes, *, details=None) -> None:
    """The initial Student-route visa record for a new international
    student: ATAS flags for restricted modules and the right-to-study check
    reminder. Starts 'pending' until the in-person check is on file.

    ``details`` carries the rest of the visa profile when it was entered
    before the student existed (the full visa window opened from Create
    Student): passport/BRP expiry, visa type/number/start, sponsor licence,
    status, notes and the ATAS flag."""
    from education_system.systems.university.domains.governance.domain.compliance.international_compliance.services import (
        visa_service as vs,
    )
    details = dict(details or {})
    atas_codes = [c for c in (module_codes or []) if vs.is_atas_required_for_module(c)]
    vs.upsert_visa_record(vs.VisaRecord(
        student_id=student_id, nationality=nationality, passport_number=passport_number,
        passport_expiry=details.get("passport_expiry") or None,
        visa_type=details.get("visa_type") or "student_route",
        visa_number=details.get("visa_number") or None,
        visa_start_date=details.get("visa_start_date") or None,
        visa_expiry_date=visa_expiry_date, brp_number=brp_number,
        brp_expiry_date=details.get("brp_expiry_date") or None,
        sponsor_licence_ref=details.get("sponsor_licence_ref") or None,
        atas_required=bool(atas_codes) or bool(details.get("atas_required")),
        status=details.get("status") or "pending",
        notes=details.get("notes") or None,
    ))
    for code in atas_codes:
        vs.record_atas_clearance(
            student_id=student_id, module_code=code, certificate_number=None,
            issued_on=None, expires_on=None, status="pending",
            notes=f"Auto-flagged at enrolment for {code} (ATAS-restricted prefix)",
        )
    if email_address:
        vs.notify_right_to_study_required(student_id, email_address, first_name=first_name or "")
