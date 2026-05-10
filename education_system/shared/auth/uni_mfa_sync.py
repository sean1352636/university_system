"""One-way sync from university ``mfa_methods`` → shared ``mfa_methods``.

Phase 5 of the option-3 MFA migration. The university ``MFAService``
keeps writing into its own database (``student_records.db``) — that's
unchanged for safety. This module reads those rows on demand and
mirrors them into the shared ``auth.db`` so the universal login (which
now drives the picker off shared ``mfa_methods``) sees them too.

The mirror is **idempotent and lazy**:
    - ``mirror_for_user(shared_user_id, username)`` is cheap when there
      are no university enrolments — it short-circuits if the uni DB
      can't be opened or has no matching account.
    - It uses ``ON CONFLICT(user_id, method_type) DO UPDATE`` so calling
      it repeatedly only refreshes ``method_identifier`` / ``is_primary``
      / ``is_enabled`` — no duplicate rows.

Called from ``UserAuth.login`` right before the MFA detection branch,
so a user who enrols email or SMS through the university wizard sees
their methods on their *next* login without any restart.
"""

from __future__ import annotations

import logging

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)


def mirror_for_user(shared_user_id: int, username: str,
                    auth_db_path: str | None = None) -> int:
    """Copy university MFA methods for *username* into shared.

    Returns the number of rows mirrored. Errors are swallowed (logged at
    debug) — this is a best-effort sync, never block the login.
    """
    try:
        from education_system.university_system.infrastructure.database.db import (
            get_connection,
        )
    except ImportError:
        return 0

    try:
        uconn = get_connection()
    except Exception as exc:
        logger.debug("uni MFA sync: could not open uni DB: %s", exc)
        return 0

    try:
        urow = uconn.execute(
            "SELECT id FROM user_accounts WHERE username = ?", (username,),
        ).fetchone()
        if not urow:
            return 0
        ua_id = urow[0] if isinstance(urow, tuple) else urow["id"]

        # Honour the university-side verification_disabled toggle by
        # treating it as 'don't sync'. ``set_verification_disabled`` on
        # the shared service is the canonical way to skip a challenge,
        # and we mirror it once below.
        srow = uconn.execute(
            "SELECT mfa_enabled, COALESCE(verification_disabled, 0) AS off "
            "FROM mfa_user_settings WHERE user_id = ?",
            (ua_id,),
        ).fetchone()
        uni_enabled = bool(srow and srow["mfa_enabled"])
        uni_off = bool(srow and srow["off"])

        if not uni_enabled:
            return 0

        rows = uconn.execute(
            "SELECT method_type, method_identifier, "
            "       COALESCE(is_primary, 0) AS is_primary, "
            "       COALESCE(is_enabled, 1) AS is_enabled "
            "FROM mfa_methods WHERE user_id = ? AND is_enabled = 1",
            (ua_id,),
        ).fetchall()
    finally:
        try:
            uconn.close()
        except Exception:
            pass

    if not rows:
        return 0

    sconn = connect(auth_db_path)
    try:
        mirrored = 0
        for r in rows:
            method_type = r["method_type"] if "method_type" in r.keys() else r[0]
            if method_type not in ("totp", "sms", "email"):
                continue
            ident = r["method_identifier"] if "method_identifier" in r.keys() else r[1]
            primary = r["is_primary"] if "is_primary" in r.keys() else r[2]
            sconn.execute(
                "INSERT INTO mfa_methods (user_id, method_type, "
                "                         method_identifier, is_primary, "
                "                         is_enabled, setup_completed_at) "
                "VALUES (?, ?, ?, ?, 1, datetime('now')) "
                "ON CONFLICT(user_id, method_type) DO UPDATE SET "
                "  method_identifier = excluded.method_identifier, "
                "  is_primary        = excluded.is_primary, "
                "  is_enabled        = 1",
                (shared_user_id, method_type, ident, 1 if primary else 0),
            )
            mirrored += 1

        # Mirror the uni-side verification_disabled flag.
        sconn.execute(
            "INSERT INTO mfa_user_settings (user_id, verification_disabled) "
            "VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "  verification_disabled = excluded.verification_disabled, "
            "  updated_at = datetime('now')",
            (shared_user_id, 1 if uni_off else 0),
        )
        sconn.commit()
        logger.debug("uni MFA sync: mirrored %d method(s) for user_id=%d",
                     mirrored, shared_user_id)
        return mirrored
    finally:
        try:
            sconn.close()
        except Exception:
            pass
