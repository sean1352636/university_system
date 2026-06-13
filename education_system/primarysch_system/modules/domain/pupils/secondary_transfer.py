"""Transfer primary pupils into the secondary school system."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

from education_system.primarysch_system.modules.domain.pupils import pupils as primary_pupils
from education_system.primarysch_system.modules.domain.pupils.leavers import leavers
from education_system.primarysch_system.modules.domain.pupils.pupils import ValidationError
from education_system.secondarysch_system.modules.domain.pupils.pupils import (
    pupils as secondary_pupils,
)
from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.db import connect as auth_connect
from education_system.shared.auth.schema import initialise_auth_db

logger = logging.getLogger(__name__)

SECONDARY_SYSTEM_KEY = "school"
SECONDARY_ROLE = "student"
DEFAULT_DESTINATION = "Secondary School System"


@dataclass(frozen=True)
class SecondaryTransferResult:
    source_pupil_id: str
    secondary_pupil_id: str
    secondary_email: str
    password: str
    leaver_id: str
    auth_user_id: int


def _generate_password() -> str:
    return f"Sec-{secrets.token_urlsafe(9)}1!"


def _delete_auth_user(user_id: int) -> None:
    conn = auth_connect()
    try:
        for table in (
            "user_systems",
            "sessions",
            "password_history",
            "mfa_secrets",
            "mfa_recovery_codes",
        ):
            try:
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            except Exception:
                logger.debug("Rollback skipped auth table %s", table, exc_info=True)
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def _ensure_not_already_leaver(pupil_id: str) -> None:
    leavers.init_db()
    with leavers._connect() as conn:
        row = conn.execute(
            "SELECT leaver_id FROM leavers WHERE pupil_id = ?",
            (pupil_id,),
        ).fetchone()
    if row:
        raise ValidationError(
            f"Pupil {pupil_id} is already a leaver ({row['leaver_id']})"
        )


def move_to_secondary_school(
    pupil_id: str,
    *,
    form_group: str | None = None,
    destination_school: str | None = None,
    notes: str | None = None,
) -> SecondaryTransferResult:
    """Move a primary pupil to secondary and create their login.

    The new login username is the generated secondary-school email address.
    The generated password is returned once so the caller can show it to the
    operator.
    """
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")

    pupil = primary_pupils.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    _ensure_not_already_leaver(pupil_id)

    secondary = None
    auth_user_id: int | None = None
    leaver = None
    password = _generate_password()

    try:
        secondary = secondary_pupils.create_pupil(
            {
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "year_group": "7",
                "form_group": form_group or "",
                "date_of_birth": pupil.date_of_birth or "",
                "phone": "",
                "parent_name": pupil.parent_name or "",
                "parent_phone": pupil.parent_phone or "",
                "send_status": pupil.send_status or "",
            }
        )

        initialise_auth_db()
        auth = UserAuth()
        auth_user_id = auth.create_user(
            username=secondary.email,
            password=password,
            display_name=secondary.full_name,
            email=secondary.email,
            systems=[(SECONDARY_SYSTEM_KEY, SECONDARY_ROLE)],
        )

        leaver = leavers.create_leaver(
            {
                "pupil_id": pupil.pupil_id,
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth or "",
                "year_left": pupil.year_group,
                "destination_school": (
                    destination_school or DEFAULT_DESTINATION
                ),
                "current_email": secondary.email,
                "parent_phone": pupil.parent_phone or "",
                "reason": "Moved to secondary school",
                "status": "active",
                "notes": notes or "",
            }
        )

        primary_pupils.delete_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Secondary transfer failed for pupil %s", pupil_id)
        if leaver is not None:
            try:
                leavers.delete_leaver(leaver.leaver_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete leaver %s",
                    leaver.leaver_id,
                    exc_info=True,
                )
        if auth_user_id is not None:
            try:
                _delete_auth_user(auth_user_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete auth user %s",
                    auth_user_id,
                    exc_info=True,
                )
        if secondary is not None:
            try:
                secondary_pupils.delete_pupil(secondary.pupil_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete secondary pupil %s",
                    secondary.pupil_id,
                    exc_info=True,
                )
        raise

    assert secondary is not None
    assert leaver is not None
    assert auth_user_id is not None
    logger.info(
        "Moved primary pupil %s to secondary pupil %s and auth user %s",
        pupil.pupil_id,
        secondary.pupil_id,
        auth_user_id,
    )
    # Link the canonical journey across both phases, record the transition
    # and publish a durable progression event (best-effort; never raises).
    try:
        from education_system.shared.cross_system import progression
        progression.announce_progression(
            source_system="primary",
            source_module="primarysch_system.pupils.secondary_transfer",
            first_name=pupil.first_name, last_name=pupil.last_name,
            date_of_birth=pupil.date_of_birth,
            source_student_id=pupil.pupil_id,
            target_student_id=secondary.pupil_id,
            year_group=secondary.year_group)
    except Exception:
        logger.debug("Cross-system progression announce skipped for "
                     "pupil %s", pupil.pupil_id, exc_info=True)
    return SecondaryTransferResult(
        source_pupil_id=pupil.pupil_id,
        secondary_pupil_id=secondary.pupil_id,
        secondary_email=secondary.email,
        password=password,
        leaver_id=leaver.leaver_id,
        auth_user_id=auth_user_id,
    )
