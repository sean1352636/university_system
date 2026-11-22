"""Nursery's side of the platform transition contract.

The nursery is the first phase, so nobody transfers *into* it through the
platform: children join through the nursery's own admissions. This adapter
answers the source side only — what the nursery may release about a child
leaving for Reception, and how it takes them off roll.

The export is keyed by :data:`handover.NURSERY_TO_PRIMARY`. It gathers
everything the nursery holds for those keys and leaves consent to
``handover.build_handover``: medical alerts and SEND detail are
*sensitive* there, so they reach the school only when the parent's
consent covers them. The daily observation log is deliberately not
exported — the spec carries the EYFS summary judgement, not the raw notes.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    ExportResult,
    PhaseAdapter,
)

logger = logging.getLogger(__name__)

SYSTEM_KEY = "nursery"


def _eyfs_profile(child_id: str) -> dict[str, Any] | None:
    """The child's EYFS profile summary — finalised if there is one."""
    try:
        from education_system.systems.nursery.domain.assessment.eyfs_profile import (
            eyfs_profile,
        )
        profiles = eyfs_profile.list_profiles(pupil_id=child_id)
    except Exception:
        logger.exception("Could not read the EYFS profile for child %s", child_id)
        return None
    if not profiles:
        return None
    finalised = [p for p in profiles if (p.status or "") == "finalised"]
    chosen = max(finalised or profiles,
                 key=lambda p: (p.assessment_date or "", p.profile_id))
    return {
        "assessment_date": chosen.assessment_date,
        "term": chosen.term,
        "status": chosen.status,
        "areas": {eyfs_profile.AREA_LABELS[area]: getattr(chosen, area)
                  for area in eyfs_profile.AREA_FIELDS if getattr(chosen, area)},
        "summary": chosen.summary,
    }


def _attendance_summary(child: Any) -> dict[str, Any]:
    """Sessions recorded by status, plus the funded-hours pattern."""
    from education_system.systems.nursery.infrastructure.database import connect, init_db

    counts: dict[str, int] = {}
    try:
        init_db()
        conn = connect()
        try:
            for row in conn.execute(
                    "SELECT status, COUNT(*) AS n FROM attendance_records "
                    "WHERE pupil_id = ? GROUP BY status", (child.pupil_id,)):
                counts[str(row["status"])] = int(row["n"])
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not summarise attendance for child %s",
                         child.pupil_id)
    return {
        "sessions_recorded": sum(counts.values()),
        "by_status": counts,
        "funded_hours": child.funded_hours,
        "room": child.room,
        "start_date": child.start_date,
    }


class NurseryAdapter(PhaseAdapter):
    """Source side only: nursery is where the journey starts."""

    system = SYSTEM_KEY

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        from education_system.systems.nursery.domain.learners.children import children

        child = children.get_child(local_student_id)
        if child is None:
            raise AdapterError(f"No nursery child {local_student_id} to export")

        guardian = {
            "name": child.parent_name, "phone": child.parent_phone,
            "email": child.parent_email,
            "relationship": child.parent_relationship or "Parent/Carer",
            "parental_responsibility": True,
        }
        has_guardian = any((child.parent_name, child.parent_phone,
                            child.parent_email))
        record: dict[str, Any] = {
            # The same identity and address the schools' Add Pupil asks for,
            # so Reception starts from the record the nursery already holds.
            "child_identity": {
                "first_name": child.first_name,
                "middle_names": child.middle_names,
                "last_name": child.last_name,
                "preferred_name": child.preferred_name,
                "date_of_birth": child.date_of_birth,
                "gender": child.gender,
                "upn": child.upn,
                "nursery_child_id": child.pupil_id,
                "address_line1": child.address_line1,
                "address_line2": child.address_line2,
                "town": child.town,
                "postcode": child.postcode,
            },
            "guardians": [guardian] if has_guardian else None,
            # The nursery records one contact per child; the parent is the
            # emergency contact until the school collects its own form.
            "emergency_contacts": ([{"name": child.parent_name or "Parent/Carer",
                                     "phone": child.parent_phone,
                                     "relationship": "Parent/Carer"}]
                                   if child.parent_phone else None),
            "eyfs_profile": _eyfs_profile(child.pupil_id),
            # Always present, even when empty: "nothing recorded" is itself
            # the answer a reception teacher needs, and an absent key would
            # read as missing. Still sensitive, so still consent-gated.
            "medical_alerts": {
                "allergies": (child.allergies or "").strip() or None,
                "medical_notes": (child.medical_notes or "").strip() or None,
            },
            "attendance_summary": _attendance_summary(child),
            # Sensitive on this boundary: present only when the nursery has
            # recorded something, and still consent-gated by build_handover.
            "send_support": ({"sen_status": child.sen_status,
                              "sen_label": child.sen_label}
                             if child.sen_status else None),
            "communication_needs": ({"eal": True} if child.eal else None),
        }
        logger.info("Exported nursery child %s for handover to %s",
                    child.pupil_id, destination_system or "(unspecified)")
        return ExportResult(record=record, local_student_id=child.pupil_id)

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """Take the child off roll (status ``left``). Never deletes: the
        EYFS record stays for safeguarding, audit and the leavers view."""
        from education_system.systems.nursery.domain.learners.children import children

        child = children.get_child(local_student_id)
        if child is None:
            logger.warning("close_enrolment: no nursery child %s", local_student_id)
            return
        if child.status == "left":
            logger.info("Nursery child %s has already left — not re-closing",
                        local_student_id)
            return
        children.set_status(local_student_id, "left",
                            left_date=details.get("end_date"),
                            exit_reason="Moved to school")
        logger.info("Nursery child %s taken off roll (%s)", local_student_id, reason)


ADAPTER = NurseryAdapter()


def register() -> NurseryAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "NurseryAdapter", "ADAPTER", "register"]
