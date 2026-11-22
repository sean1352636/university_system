"""SEN details for a pupil, beside the SEN status on the pupil record.

The pupil record holds the census SEN status (N none, K SEN support, E EHC
plan). This adds what the SENCO keeps and what moves on with the pupil to
the sixth form: the **primary and secondary area of need** (the DfE census
codes), the **EHC plan reference and issue date**, the **provision** in
place, **strategies** that help in class, and **exam access arrangements**.

Details are only kept for a pupil with SEN support or an EHC plan; the plan
reference only with an EHC plan. The SENCO (:data:`SEN_EDITORS`) changes
them, all staff read them, and every change is audited.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SEN_EDITORS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

#: DfE school census SEN type of need codes.
NEEDS: dict[str, str] = {
    "SPLD": "Specific learning difficulty",
    "MLD": "Moderate learning difficulty",
    "SLD": "Severe learning difficulty",
    "PMLD": "Profound and multiple learning difficulty",
    "SEMH": "Social, emotional and mental health",
    "SLCN": "Speech, language and communication needs",
    "HI": "Hearing impairment",
    "VI": "Visual impairment",
    "MSI": "Multi-sensory impairment",
    "PD": "Physical disability",
    "ASD": "Autistic spectrum disorder",
    "OTH": "Other difficulty or disability",
    "NSA": "SEN support but no specialist assessment of type of need",
}
FIELDS = ("primary_need", "secondary_need", "ehcp_reference", "ehcp_issued_on",
          "provision", "strategies", "exam_access", "notes")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_sen (
    pupil_id        INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    primary_need    TEXT,
    secondary_need  TEXT,
    ehcp_reference  TEXT,
    ehcp_issued_on  TEXT,
    provision       TEXT,
    strategies      TEXT,
    exam_access     TEXT,
    notes           TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT
);
CREATE TABLE IF NOT EXISTS pupil_sen_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id  INTEGER NOT NULL,
    action    TEXT NOT NULL CHECK (action IN ('save', 'clear')),
    fields    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("sen_details", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class SenDetails:
    pupil_id: int
    primary_need: str | None
    secondary_need: str | None
    ehcp_reference: str | None
    ehcp_issued_on: str | None
    provision: str | None
    strategies: str | None
    exam_access: str | None
    notes: str | None
    updated_at: str
    updated_by: str | None

    @property
    def primary_label(self) -> str:
        return NEEDS.get(self.primary_need or "", "")

    @property
    def secondary_label(self) -> str:
        return NEEDS.get(self.secondary_need or "", "")


def is_editor(actor: Principal) -> bool:
    return actor.role in SEN_EDITORS


def _pupil(pupil_id: int) -> P.Pupil:
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    return p


def get(pupil_id: int) -> SenDetails | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_sen WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    return SenDetails(**{k: r[k] for k in SenDetails.__dataclass_fields__}) if r else None


def _need(value: Any, label: str, problems: list[str]) -> str | None:
    v = (P._clean_text(value, 10) or "").upper()
    if not v:
        return None
    if v not in NEEDS:
        problems.append(f"{label} must be one of {', '.join(NEEDS)}")
        return None
    return v


def _clean(data: dict[str, Any], pupil: P.Pupil, current: SenDetails | None
           ) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update(data)
    if pupil.sen_status not in ("K", "E"):
        problems.append(f"{pupil.display_name} has no SEN status - set SEN support or "
                        "EHC plan on the pupil record first")
    out: dict[str, Any] = {
        "primary_need": _need(merged.get("primary_need"), "Primary need", problems),
        "secondary_need": _need(merged.get("secondary_need"), "Secondary need", problems),
    }
    if not out["primary_need"]:
        problems.append("Choose the primary area of need")
    if out["secondary_need"] and out["secondary_need"] == out["primary_need"]:
        problems.append("The secondary need can't be the same as the primary need")
    ref = P._clean_text(merged.get("ehcp_reference"), 40)
    issued = merged.get("ehcp_issued_on")
    out["ehcp_issued_on"] = None
    if issued not in (None, ""):
        try:
            d = _dt.date.fromisoformat(str(issued).strip())
            if d > _today():
                problems.append("The EHC plan issue date can't be in the future")
            out["ehcp_issued_on"] = d.isoformat()
        except ValueError:
            problems.append("EHC plan issued must be a date (YYYY-MM-DD)")
    if pupil.sen_status != "E" and (ref or out["ehcp_issued_on"]):
        problems.append("Only a pupil with an EHC plan has a plan reference or issue date")
    out["ehcp_reference"] = ref
    for k, limit in (("provision", 2000), ("strategies", 2000), ("exam_access", 500),
                     ("notes", 2000)):
        out[k] = P._clean_text(merged.get(k), limit)
    if problems:
        raise ValidationError(problems)
    return out


def save(pupil_id: int, data: dict[str, Any], *, actor: Principal) -> SenDetails:
    pupil = _pupil(pupil_id)
    if not is_editor(actor):
        activity_log.record("sen.save", target=pupil.admission_no, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the SENCO can change SEN details.")
    current = get(pupil.pupil_id)
    clean = _clean(data, pupil, current)
    changed = sorted(k for k in FIELDS if (getattr(current, k) if current else None)
                     != clean[k])
    if not changed:
        return current  # type: ignore[return-value]
    with database.connect() as conn:
        conn.execute(
            f"INSERT INTO pupil_sen (pupil_id, {', '.join(FIELDS)}, updated_by) VALUES "  # nosec B608 - FIELDS is fixed
            f"(?, {', '.join('?' * len(FIELDS))}, ?) ON CONFLICT (pupil_id) DO UPDATE SET "
            + ", ".join(f"{k} = excluded.{k}" for k in FIELDS)
            + ", updated_at = datetime('now'), updated_by = excluded.updated_by",
            (pupil.pupil_id, *(clean[k] for k in FIELDS), actor.username))
        conn.execute("INSERT INTO pupil_sen_audit (pupil_id, action, fields, actor) VALUES "
                     "(?, 'save', ?, ?)", (pupil.pupil_id, json.dumps(changed),
                                           actor.username or "unknown"))
    activity_log.record("sen.save", target=pupil.admission_no, principal=actor)
    return get(pupil.pupil_id)  # type: ignore[return-value]


def clear(pupil_id: int, *, actor: Principal) -> None:
    pupil = _pupil(pupil_id)
    if not is_editor(actor):
        activity_log.record("sen.clear", target=pupil.admission_no, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the SENCO can change SEN details.")
    with database.connect() as conn:
        if conn.execute("DELETE FROM pupil_sen WHERE pupil_id = ?",
                        (pupil.pupil_id,)).rowcount:
            conn.execute("INSERT INTO pupil_sen_audit (pupil_id, action, actor) VALUES "
                         "(?, 'clear', ?)", (pupil.pupil_id, actor.username or "unknown"))
    activity_log.record("sen.clear", target=pupil.admission_no, principal=actor)


def history(pupil_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "fields": json.loads(r["fields"] or "[]")}
                for r in conn.execute("SELECT * FROM pupil_sen_audit WHERE pupil_id = ? "
                                      "ORDER BY audit_id DESC", (int(pupil_id),))]


def register(*, year_group: int | None = None) -> list[tuple[P.Pupil, SenDetails | None]]:
    """Pupils on roll with SEN support or an EHC plan, with their details
    (None where the SENCO hasn't filled them in)."""
    pupils = [p for p in P.list_pupils(year_group=year_group) if p.sen_status in ("K", "E")]
    with database.connect() as conn:
        rows = {r["pupil_id"]: SenDetails(**{k: r[k] for k in SenDetails.__dataclass_fields__})
                for r in conn.execute("SELECT * FROM pupil_sen")}
    return [(p, rows.get(p.pupil_id)) for p in pupils]


def summary_line(pupil: P.Pupil) -> str:
    """One line for the profile: status, needs, plan."""
    if pupil.sen_status == "N":
        return P.SEN_STATUSES["N"]
    d = get(pupil.pupil_id)
    bits = [P.SEN_STATUSES.get(pupil.sen_status, pupil.sen_status)]
    if d and d.primary_need:
        bits.append(f"{d.primary_label} ({d.primary_need})"
                    + (f", also {d.secondary_label.lower()}" if d.secondary_need else ""))
    if d and d.ehcp_reference:
        bits.append(f"plan {d.ehcp_reference}")
    if d and d.exam_access:
        bits.append(f"exam access: {d.exam_access}")
    if d is None:
        bits.append("details not recorded")
    return " · ".join(bits)


def handover_block(pupil: P.Pupil) -> dict[str, Any] | None:
    """What moves on with the pupil (None for a pupil with no SEN)."""
    d = get(pupil.pupil_id)
    if pupil.sen_status == "N" and d is None:
        return None
    out: dict[str, Any] = {"sen_status": pupil.sen_status,
                           "sen_status_label": P.SEN_STATUSES.get(pupil.sen_status)}
    if d is not None:
        out.update({
            "primary_need": d.primary_need, "primary_need_label": d.primary_label or None,
            "secondary_need": d.secondary_need,
            "secondary_need_label": d.secondary_label or None,
            "ehcp_reference": d.ehcp_reference, "ehcp_issued_on": d.ehcp_issued_on,
            "provision": d.provision, "strategies": d.strategies,
            "exam_access": d.exam_access,
        })
    return out


# ── Used by the SEND register (modules.send.domain.send) ───────────

#: The four broad areas of need in the SEND Code of Practice, by census code.
AREAS: dict[str, str] = {
    "SLCN": "Communication and interaction", "ASD": "Communication and interaction",
    "SPLD": "Cognition and learning", "MLD": "Cognition and learning",
    "SLD": "Cognition and learning", "PMLD": "Cognition and learning",
    "SEMH": "Social, emotional and mental health",
    "HI": "Sensory and/or physical needs", "VI": "Sensory and/or physical needs",
    "MSI": "Sensory and/or physical needs", "PD": "Sensory and/or physical needs",
    "OTH": "Other", "NSA": "Other",
}


def area_of(code: str | None) -> str:
    """The broad area of need for a census code ("" when none)."""
    return AREAS.get((code or "").upper(), "")


def details_map() -> dict[int, SenDetails]:
    """Every pupil's SEN details, by pupil id (one read for a register)."""
    with database.connect() as conn:
        return {r["pupil_id"]: SenDetails(**{k: r[k] for k in SenDetails.__dataclass_fields__})
                for r in conn.execute("SELECT * FROM pupil_sen")}


def validate(pupil_id: int, data: dict[str, Any], *, sen_status: str | None = None
             ) -> list[str]:
    """The problems :func:`save` would find, as if the pupil's SEN status
    were *sen_status* (so a screen can check before changing the status)."""
    from dataclasses import replace
    pupil = _pupil(pupil_id)
    if sen_status:
        pupil = replace(pupil, sen_status=sen_status)
    try:
        _clean(data, pupil, get(pupil.pupil_id))
    except ValidationError as e:
        return list(e.problems)
    return []
