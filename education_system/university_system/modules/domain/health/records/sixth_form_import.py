"""Map sixth-form medical records onto the university schema.

The two databases use very different shapes for medical data:

* **Sixth form** keeps four normalised tables — ``med_profiles``,
  ``med_conditions``, ``med_medications``, ``med_allergies`` —
  with one row per condition / medication / allergy.
* **University** keeps a single denormalised ``medical_info`` row
  per student (blood type, GP details, and free-text
  ``allergies`` / ``medications`` / ``conditions`` columns) plus
  a normalised ``medical_conditions`` table (one row per
  diagnosed condition).

When a Year 13 leaver is transferred, this module is the single
seam that copies their medical record across:

* Upserts one ``medical_info`` row for the university ``student_id``,
  carrying GP details, blood type, and a human-readable summary of
  allergies / medications / conditions in the corresponding free-text
  columns.
* Inserts one ``medical_conditions`` row per sixth-form condition,
  mapping severity directly (the vocabularies overlap) and the
  active flag onto a status of ``Active`` / ``Inactive``.

Medications and allergies do not have dedicated destination tables on
the university side, so they are flattened into the ``medical_info``
free-text columns where the GP, school nurse, or wellbeing team would
expect to read them.

All work happens in a single transaction. Failure does not block the
transfer — the caller logs and surfaces a warning, leaving the
university student record itself intact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)


@dataclass
class ImportSummary:
    """What ``import_from_sixth_form`` did, for logging and UI."""
    medical_info_written: bool
    conditions_written: int
    medications_written: int
    allergies_written: int
    profile_present: bool


def _format_allergies(allergies) -> str | None:
    if not allergies:
        return None
    lines: list[str] = []
    for a in allergies:
        flags = []
        if a.has_epipen:
            flags.append("EpiPen")
        flag_suffix = f"  [{', '.join(flags)}]" if flags else ""
        reaction = f" — {a.reaction}" if a.reaction else ""
        lines.append(
            f"- {a.allergen} ({a.severity}){reaction}{flag_suffix}")
    return "\n".join(lines)


def _format_medications(medications) -> str | None:
    if not medications:
        return None
    lines: list[str] = []
    for m in medications:
        bits: list[str] = []
        if m.dose:
            bits.append(m.dose)
        if m.frequency:
            bits.append(m.frequency)
        bits.append(m.route)
        if m.is_emergency:
            bits.append("EMERGENCY")
        meta = ", ".join(bits)
        dates = ""
        if m.start_date or m.end_date:
            dates = f"  [{m.start_date or '—'} → {m.end_date or '—'}]"
        prescriber = f"  Rx: {m.prescribed_by}" if m.prescribed_by else ""
        lines.append(f"- {m.name} ({meta}){dates}{prescriber}")
    return "\n".join(lines)


def _format_conditions(conditions) -> str | None:
    if not conditions:
        return None
    lines: list[str] = []
    for c in conditions:
        active = "Active" if c.active else "Inactive"
        diagnosed = f"  diagnosed {c.diagnosed_date}" if c.diagnosed_date else ""
        plan = f"  Care plan: {c.care_plan_ref}" if c.care_plan_ref else ""
        lines.append(
            f"- {c.name} ({c.severity}, {active}){diagnosed}{plan}")
    return "\n".join(lines)


def _combined_doctor_name(profile) -> str | None:
    bits = [profile.gp_name, profile.gp_practice]
    text = " — ".join(b for b in bits if b)
    return text or None


def import_from_sixth_form(
    uni_student_id: str,
    sf_student_id: str,
) -> ImportSummary:
    """Copy a sixth-form student's medical record onto the university
    schema for ``uni_student_id``.

    Reads via the sixth-form Python API (so the source-side
    validation / dataclasses are honoured), writes via the
    university's shared DB connection.

    Returns an :class:`ImportSummary` describing what was written.
    Raises only for unrecoverable database errors — if the sixth-form
    record is genuinely empty for a student, the function still
    succeeds, just with zero counts.
    """
    from education_system.sixthform_system.modules.domain.pastoral.medical_records import (
        medical_records as sf_med,
    )
    sf_med.init_db()

    profile      = sf_med.get_profile(sf_student_id)
    conditions   = sf_med.list_conditions(student_id=sf_student_id)
    medications  = sf_med.list_medications(student_id=sf_student_id)
    allergies    = sf_med.list_allergies(student_id=sf_student_id)

    logger.info(
        "Importing sixth-form medical record for sf=%s -> uni=%s "
        "(profile=%s, %d conditions, %d medications, %d allergies)",
        sf_student_id, uni_student_id, profile is not None,
        len(conditions), len(medications), len(allergies),
    )

    # If there's truly nothing to copy, short-circuit before opening
    # a transaction. The caller can still log "nothing imported"
    # without us writing an empty row.
    if (profile is None and not conditions
            and not medications and not allergies):
        logger.info(
            "Sixth-form medical record for %s is empty — nothing to import",
            sf_student_id)
        return ImportSummary(
            medical_info_written=False,
            conditions_written=0,
            medications_written=0,
            allergies_written=0,
            profile_present=False,
        )

    allergies_text   = _format_allergies(allergies)
    medications_text = _format_medications(medications)
    conditions_text  = _format_conditions(conditions)

    blood_type   = profile.blood_group if profile else None
    doctor_name  = _combined_doctor_name(profile) if profile else None
    doctor_phone = profile.gp_phone if profile else None

    conn = get_connection()
    try:
        cur = conn.cursor()

        # ── medical_info: upsert by student_id ─────────────────────
        cur.execute(
            "SELECT id FROM medical_info WHERE student_id = ?",
            (uni_student_id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """UPDATE medical_info SET
                       blood_type   = COALESCE(?, blood_type),
                       allergies    = ?,
                       medications  = ?,
                       conditions   = ?,
                       doctor_name  = COALESCE(?, doctor_name),
                       doctor_phone = COALESCE(?, doctor_phone),
                       last_updated = CURRENT_TIMESTAMP
                   WHERE student_id = ?""",
                (blood_type, allergies_text, medications_text,
                 conditions_text, doctor_name, doctor_phone,
                 uni_student_id),
            )
            logger.info(
                "Updated medical_info row for uni student %s",
                uni_student_id)
        else:
            cur.execute(
                """INSERT INTO medical_info
                       (student_id, blood_type, allergies, medications,
                        conditions, doctor_name, doctor_phone,
                        last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (uni_student_id, blood_type, allergies_text,
                 medications_text, conditions_text, doctor_name,
                 doctor_phone),
            )
            logger.info(
                "Inserted medical_info row for uni student %s",
                uni_student_id)

        # ── medical_conditions: one INSERT per sixth-form row ──────
        conditions_written = 0
        for c in conditions:
            status = "Active" if c.active else "Inactive"
            notes_bits = []
            if c.notes:
                notes_bits.append(c.notes)
            if c.care_plan_ref:
                notes_bits.append(f"Care plan ref: {c.care_plan_ref}")
            notes_bits.append(f"Imported from sixth-form record {sf_student_id}")
            notes = "\n".join(notes_bits)
            cur.execute(
                """INSERT INTO medical_conditions
                       (student_id, condition_name, severity,
                        diagnosed_date, status, provider, notes,
                        created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (uni_student_id, c.name, c.severity,
                 c.diagnosed_date, status,
                 "Imported from sixth form", notes),
            )
            conditions_written += 1

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception(
            "Medical-record import failed for sf=%s -> uni=%s",
            sf_student_id, uni_student_id)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

    summary = ImportSummary(
        medical_info_written=True,
        conditions_written=conditions_written,
        medications_written=len(medications),
        allergies_written=len(allergies),
        profile_present=profile is not None,
    )
    logger.info(
        "Sixth-form medical import complete: sf=%s -> uni=%s "
        "(conditions=%d, meds flattened=%d, allergies flattened=%d)",
        sf_student_id, uni_student_id,
        summary.conditions_written, summary.medications_written,
        summary.allergies_written,
    )
    return summary
