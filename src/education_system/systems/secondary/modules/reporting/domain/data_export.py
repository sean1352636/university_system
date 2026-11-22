"""Data Export: pick a dataset, its columns and filters, preview, export.

Read-only over the other areas' data (each dataset is loaded through its
owning module's public functions), so an export is always a copy of the
current records - never a second store.

Kept from the old Custom Export and Data Export screens:

* one dataset at a time with chosen columns, filters, a preview, a row
  limit, and the file formats CSV, TSV, JSON, JSON lines and Markdown
  (picked from the file name's extension or chosen);
* saved exports ("presets"), and packs that write several datasets to a
  folder in one go with a ``_manifest.json`` and an optional zip;
* a history of past export jobs (who, when, which dataset, format, how many
  rows - never the data itself).

New:

* **Datasets** are this system's: pupils, contacts, attendance summary,
  behaviour entries, detentions, suspension / exclusion cases, assessment
  marks (gradebook), assessment-point grades, target grades, the SEN
  register, form groups, teaching groups.
* **Filters**: year group, form, date range (where the dataset has dates).
* **Who.** The data manager (:data:`DATA_MANAGERS`) exports everything.
  Other staff export only datasets and columns that aren't sensitive
  (no contacts, SEN register or exclusion cases, no date of birth, UPN,
  address, FSM / EAL / SEN flags) and only for pupils in the teaching groups
  they teach or the forms they tutor.
* **Formula-safe.** Every text cell that a spreadsheet could run as a
  formula is escaped (``core.utilities.exports.safe_cell``).
* **Saved exports are per person**; each person sees and runs their own.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = RC.ValidationError
PermissionDenied = RC.PermissionDenied
NotFound = RC.NotFound

FORMATS: dict[str, str] = {"csv": ".csv", "tsv": ".tsv", "json": ".json", "jsonl": ".jsonl",
                           "markdown": ".md"}
DEFAULT_FORMAT = "csv"
FILTERS: dict[str, str] = {"year_group": "Year group", "form": "Form",
                           "date_from": "From date", "date_to": "To date"}
PREVIEW_ROWS = 20
MAX_NAME = 80

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_export_definitions (
    definition_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL COLLATE NOCASE,
    name           TEXT NOT NULL COLLATE NOCASE,
    dataset        TEXT NOT NULL,
    columns        TEXT NOT NULL,
    filters        TEXT,
    fmt            TEXT NOT NULL DEFAULT 'csv',
    row_limit      INTEGER,
    description    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (owner, name)
);
CREATE TABLE IF NOT EXISTS data_export_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    actor       TEXT NOT NULL,
    role        TEXT,
    dataset     TEXT NOT NULL,
    columns     INTEGER NOT NULL DEFAULT 0,
    filters     TEXT,
    fmt         TEXT,
    row_count   INTEGER NOT NULL DEFAULT 0,
    scope       TEXT,
    pack        TEXT,
    file_name   TEXT,
    status      TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'failed'))
);
CREATE INDEX IF NOT EXISTS ix_data_export_log_actor ON data_export_log (actor, at);
"""
database.register_schema("data_export", _SCHEMA)


# ── Datasets ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Column:
    key: str
    heading: str
    sensitive: bool = False


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    columns: tuple[Column, ...]
    loader: Callable[[dict[str, Any], set[int] | None], list[dict[str, Any]]]
    sensitive: bool = False
    dated: bool = False
    #: True when rows are groups rather than pupils (scope = the teacher's groups).
    groups: bool = False

    def column(self, key: str) -> Column | None:
        return next((c for c in self.columns if c.key == key), None)


def _c(spec: str) -> tuple[Column, ...]:
    """'key:Heading, key:Heading*' (a * marks a sensitive column)."""
    out = []
    for part in spec.split(","):
        k, h = part.strip().split(":", 1)
        out.append(Column(k.strip(), h.strip().rstrip("*"), h.strip().endswith("*")))
    return tuple(out)


def _yg(f: dict[str, Any]) -> int | None:
    return RC.int_or_none(f.get("year_group"))


def _in_scope(pid: int, scope: set[int] | None) -> bool:
    return scope is None or pid in scope


def _form_ok(form: str | None, f: dict[str, Any]) -> bool:
    want = (f.get("form") or "").strip().lower()
    return not want or (form or "").lower() == want


def _pupil_base(p: P.Pupil) -> dict[str, Any]:
    return {"admission_no": p.admission_no, "surname": p.legal_last_name,
            "first_name": p.legal_first_name, "preferred_name": p.preferred_name,
            "year": p.year_group, "form": p.form_group}


def _load_pupils(f, scope):
    return [{**_pupil_base(p), "upn": p.upn, "middle_names": p.middle_names,
             "dob": p.date_of_birth, "gender": p.gender, "admission_date": p.admission_date,
             "roll_status": p.roll_status_label, "leaving_date": p.leaving_date,
             "leaving_reason": p.leaving_reason, "address_line1": p.address_line1,
             "address_line2": p.address_line2, "town": p.town, "postcode": p.postcode,
             "sen_status": p.sen_status, "fsm": "Y" if p.fsm_eligible else "N",
             "eal": "Y" if p.eal else "N"}
            for p in P.list_pupils(year_group=_yg(f), form_group=f.get("form") or None)
            if _in_scope(p.pupil_id, scope)]


def _load_contacts(f, scope):
    out = []
    for p in P.list_pupils(year_group=_yg(f), form_group=f.get("form") or None):
        if not _in_scope(p.pupil_id, scope):
            continue
        for c in C.list_for_pupil(p.pupil_id):
            out.append({**_pupil_base(p), "contact": c.full_name,
                        "relationship": c.relationship, "priority": c.priority,
                        "email": c.email, "phone": c.phone,
                        "parental_responsibility": "Y" if c.parental_responsibility else "N",
                        "receives_email": "Y" if c.receives_email else "N"})
    return out


def _load_attendance(f, scope):
    rows = AT.summaries(f.get("date_from") or None, f.get("date_to") or None,
                        year_group=_yg(f), form=f.get("form") or None)
    return [{**_pupil_base(p), "possible": s.possible, "attended": s.attended,
             "authorised": s.authorised, "unauthorised": s.unauthorised, "late": s.late,
             "unmarked": s.unmarked, "attendance_pct": s.attendance_pct,
             "absence_pct": s.absence_pct, "band": s.band}
            for p, s in rows if _in_scope(p.pupil_id, scope)]


def _entry_base(pid: int, adm: str, name: str, year: int, form: str | None) -> dict[str, Any]:
    return {"admission_no": adm, "pupil": name, "year": year, "form": form}


def _load_behaviour(f, scope):
    return [{**_entry_base(e.pupil_id, e.admission_no, e.pupil_name, e.pupil_year,
                           e.form_group),
             "date": e.entry_date, "time": e.entry_time, "type": e.incident_type,
             "polarity": e.polarity, "points": e.points, "severity": e.severity,
             "subject": e.subject_code, "location": e.location, "raised_by": e.raised_by,
             "status": e.status, "description": e.description,
             "action_taken": e.action_taken}
            for e in BH.list_entries(year_group=_yg(f), form_group=f.get("form") or None,
                                     date_from=f.get("date_from") or None,
                                     date_to=f.get("date_to") or None)
            if _in_scope(e.pupil_id, scope)]


def _load_detentions(f, scope):
    return [{**_entry_base(d.pupil_id, d.admission_no, d.pupil_name, d.pupil_year,
                           d.form_group),
             "date": d.detention_date, "time": d.start_time, "type": d.detention_type,
             "minutes": d.duration_min, "location": d.location, "supervisor": d.supervisor,
             "reason": d.reason, "set_by": d.set_by, "status": d.status}
            for d in DT.list_detentions(year_group=_yg(f), form_group=f.get("form") or None,
                                        date_from=f.get("date_from") or None,
                                        date_to=f.get("date_to") or None)
            if _in_scope(d.pupil_id, scope)]


def _load_exclusions(f, scope):
    return [{**_entry_base(c.pupil_id, c.admission_no, c.pupil_name, c.pupil_year,
                           c.form_group),
             "type": c.case_type, "severity": c.severity, "start": c.start_date,
             "end": c.end_date, "days": c.days, "reason_category": c.reason_category,
             "reason": c.reason, "decision_maker": c.decision_maker, "status": c.status,
             "return_date": c.return_date}
            for c in EX.list_cases(year_group=_yg(f), date_from=f.get("date_from") or None,
                                   date_to=f.get("date_to") or None)
            if _in_scope(c.pupil_id, scope) and _form_ok(c.form_group, f)]


def _load_marks(f, scope):
    forms = _forms_of(f)
    return [{"admission_no": e.admission_no, "pupil": e.pupil_name, "year": e.pupil_year,
             "form": forms.get(e.pupil_id), "subject": e.subject_code,
             "assessment": e.assessment_name, "type": e.assessment_type, "term": e.term,
             "date": e.assessment_date, "group": e.group_code, "status": e.status,
             "marks": e.marks_awarded, "max_marks": e.max_marks, "pct": e.mark_pct,
             "grade": e.grade, "teacher": e.teacher}
            for e in GB.list_entries(year_group=_yg(f), date_from=f.get("date_from") or None,
                                     date_to=f.get("date_to") or None)
            if _in_scope(e.pupil_id, scope) and e.pupil_id in forms]


def _forms_of(f: dict[str, Any]) -> dict[int, str | None]:
    """pupil -> form for pupils passing the year / form filters (leavers kept)."""
    return {p.pupil_id: p.form_group for p in P.list_pupils(
        roll_status=None, year_group=_yg(f), form_group=f.get("form") or None)}


def _load_point_grades(f, scope):
    forms = _forms_of(f)
    out = []
    for pt in AP.list_points():
        for g in AP.grades(pt.point_id, year_group=_yg(f)):
            if _in_scope(g.pupil_id, scope) and g.pupil_id in forms:
                out.append({"admission_no": g.admission_no, "pupil": g.pupil_name,
                            "year": g.year_group, "form": g.form_group,
                            "point": pt.name, "school_year": pt.academic_year,
                            "subject": g.subject_code, "group": g.group_code,
                            "working_at": g.working_at, "predicted": g.predicted,
                            "attitude": g.attitude, "homework": g.homework})
    return out


def _load_targets(f, scope):
    return [{"admission_no": t.admission_no, "pupil": t.pupil_name, "year": t.pupil_year,
             "form": t.form_group, "subject": t.subject_code, "target": t.target_grade,
             "minimum": t.minimum_grade, "aspirational": t.aspirational_grade,
             "source": t.source, "set_by": t.set_by, "set_date": t.set_date}
            for t in TGR.list_targets(year_group=_yg(f), form_group=f.get("form") or None)
            if _in_scope(t.pupil_id, scope)]


def _load_sen(f, scope):
    return [{**_pupil_base(p), "sen_status": p.sen_status,
             "primary_need": d.primary_need if d else None,
             "secondary_need": d.secondary_need if d else None,
             "ehcp_reference": d.ehcp_reference if d else None,
             "ehcp_issued_on": d.ehcp_issued_on if d else None,
             "provision": d.provision if d else None, "strategies": d.strategies if d else None,
             "exam_access": d.exam_access if d else None}
            for p, d in SEN.register(year_group=_yg(f))
            if _in_scope(p.pupil_id, scope) and _form_ok(p.form_group, f)]


def _load_forms(f, scope):
    stats = FG.stats()
    out = []
    for fm in FG.list_forms(_yg(f)):
        if (scope is not None and fm.form_id not in scope) or not _form_ok(fm.name, f):
            continue
        st = stats.get(fm.form_id)
        out.append({"year": fm.year_group, "form": fm.name, "tutor": fm.tutor_name,
                    "co_tutor": fm.co_tutor_name, "room": fm.room, "capacity": fm.capacity,
                    "pupils": st.on_roll if st else None})
    return out


def _load_groups(f, scope):
    groups = [g for g in TG.list_groups(year_group=_yg(f))
              if scope is None or g.group_id in scope]
    out = []
    for gi in TG.info(groups):
        g = gi.group
        out.append({"code": g.code, "year": g.year_group, "subject": gi.subject.code,
                    "kind": g.kind, "set": g.set_number, "teacher": g.teacher_name,
                    "second_teacher": g.second_teacher, "room": g.room,
                    "pupils": gi.pupils, "lessons_per_week": gi.lessons,
                    "school_year": g.academic_year})
    return out


_PUPIL = ("admission_no:Admission no, surname:Surname, first_name:First name, "
          "preferred_name:Preferred name, year:Year, form:Form")
_ENTRY = "admission_no:Admission no, pupil:Pupil, year:Year, form:Form"

DATASETS: dict[str, Dataset] = {d.key: d for d in (
    Dataset("pupils", "Pupils", _c(
        _PUPIL + ", gender:Gender, admission_date:Admission date, roll_status:Roll status, "
        "upn:UPN*, middle_names:Middle names*, dob:Date of birth*, leaving_date:Leaving date*, "
        "leaving_reason:Leaving reason*, address_line1:Address 1*, address_line2:Address 2*, "
        "town:Town*, postcode:Postcode*, sen_status:SEN*, fsm:FSM*, eal:EAL*"), _load_pupils),
    Dataset("contacts", "Contacts", _c(
        _PUPIL + ", contact:Contact, relationship:Relationship, priority:Priority, "
        "email:E-mail, phone:Phone, parental_responsibility:Parental responsibility, "
        "receives_email:Receives e-mail"), _load_contacts, sensitive=True),
    Dataset("attendance", "Attendance summary", _c(
        _PUPIL + ", possible:Possible, attended:Attended, authorised:Authorised, "
        "unauthorised:Unauthorised, late:Late, unmarked:Unmarked, "
        "attendance_pct:Attendance %, absence_pct:Absence %, band:Band"),
        _load_attendance, dated=True),
    Dataset("behaviour", "Behaviour entries", _c(
        _ENTRY + ", date:Date, time:Time, type:Type, polarity:Polarity, points:Points, "
        "severity:Severity, subject:Subject, location:Location, raised_by:Raised by, "
        "status:Status, description:Description, action_taken:Action taken"),
        _load_behaviour, dated=True),
    Dataset("detentions", "Detentions", _c(
        _ENTRY + ", date:Date, time:Time, type:Type, minutes:Minutes, location:Location, "
        "supervisor:Supervisor, reason:Reason, set_by:Set by, status:Status"),
        _load_detentions, dated=True),
    Dataset("exclusions", "Suspension / exclusion cases", _c(
        _ENTRY + ", type:Type, severity:Severity, start:Start, end:End, days:Days, "
        "reason_category:Reason category, reason:Reason, decision_maker:Decision maker, "
        "status:Status, return_date:Return date"), _load_exclusions, sensitive=True,
        dated=True),
    Dataset("marks", "Assessment marks (gradebook)", _c(
        _ENTRY + ", subject:Subject, assessment:Assessment, type:Type, term:Term, date:Date, "
        "group:Group, status:Status, marks:Marks, max_marks:Max marks, pct:%, grade:Grade, "
        "teacher:Teacher"), _load_marks, dated=True),
    Dataset("point_grades", "Assessment-point grades", _c(
        _ENTRY + ", point:Assessment point, school_year:School year, subject:Subject, "
        "group:Group, working_at:Working at, predicted:Predicted, attitude:Attitude, "
        "homework:Homework"), _load_point_grades),
    Dataset("targets", "Target grades", _c(
        _ENTRY + ", subject:Subject, target:Target, minimum:Minimum, "
        "aspirational:Aspirational, source:Source, set_by:Set by, set_date:Set date"),
        _load_targets),
    Dataset("sen", "SEN register", _c(
        _PUPIL + ", sen_status:SEN status, primary_need:Primary need, "
        "secondary_need:Secondary need, ehcp_reference:EHC plan ref, "
        "ehcp_issued_on:EHC plan issued, provision:Provision, strategies:Strategies, "
        "exam_access:Exam access"), _load_sen, sensitive=True),
    Dataset("forms", "Form groups", _c(
        "year:Year, form:Form, tutor:Tutor, co_tutor:Co-tutor, room:Room, "
        "capacity:Capacity, pupils:Pupils"), _load_forms, groups=True),
    Dataset("groups", "Teaching groups", _c(
        "code:Code, year:Year, subject:Subject, kind:Kind, set:Set, teacher:Teacher, "
        "second_teacher:Second teacher, room:Room, pupils:Pupils, "
        "lessons_per_week:Lessons per week, school_year:School year"), _load_groups,
        groups=True),
)}

#: Built-in packs (the old presets): several datasets in one go.
PACKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "pupils_core": ("Pupils (core)", ("pupils", "contacts", "forms")),
    "curriculum": ("Curriculum", ("forms", "groups")),
    "assessment": ("Assessment", ("marks", "point_grades", "targets")),
    "pastoral": ("Pastoral", ("attendance", "behaviour", "detentions", "exclusions", "sen")),
    "full": ("Everything", tuple(DATASETS)),
}


def dataset(key: str) -> Dataset:
    d = DATASETS.get((key or "").strip())
    if d is None:
        raise ValidationError([f"Unknown dataset '{key}' - choose one of "
                               f"{', '.join(DATASETS)}"])
    return d


# ── Who may export what ──────────────────────────────────────────────

def can_export_all(actor: Principal) -> bool:
    return RC.is_data_manager(actor)


def datasets_for(actor: Principal) -> list[Dataset]:
    """The datasets *actor* may export."""
    if actor.role not in RC.STAFF_ROLES:
        return []
    return [d for d in DATASETS.values() if can_export_all(actor) or not d.sensitive]


def columns_for(actor: Principal, key: str) -> list[Column]:
    d = dataset(key)
    return [c for c in d.columns if can_export_all(actor) or not c.sensitive]


def _teacher_scope(actor: Principal, d: Dataset) -> tuple[set[int], str]:
    """Pupil ids (or group / form ids for group datasets) a teacher may export."""
    year = current_year()
    groups = TG.list_groups(academic_year=year, teacher=actor.username) \
        if actor.username else []
    forms = [a.form_id for a in FT.my_assignments(actor, academic_year=year)]
    if d.key == "groups":
        return {g.group_id for g in groups}, "own groups"
    if d.key == "forms":
        return set(forms), "own forms"
    pupils: set[int] = set()
    for g in groups:
        pupils |= {p.pupil_id for p in TG.members(g.group_id)}
    for fid in forms:
        pupils |= {p.pupil_id for p in FG.members(fid)}
    return pupils, "own groups"


def _check(actor: Principal, key: str, columns: list[str] | None
           ) -> tuple[Dataset, list[Column], set[int] | None, str]:
    RC.require_staff(actor, "data_export.run")
    d = dataset(key)
    allowed = {c.key for c in columns_for(actor, key)}
    if d.sensitive and not can_export_all(actor):
        activity_log.record("data_export.run", outcome="denied", principal=actor, dataset=key)
        raise PermissionDenied(f"{d.label} holds sensitive data: only the data manager can "
                               "export it.")
    cols = list(columns) if columns else [c.key for c in d.columns if c.key in allowed]
    problems = [f"Unknown column '{c}' for {d.label}" for c in cols if d.column(c) is None]
    if problems:
        raise ValidationError(problems)
    if not cols:
        raise ValidationError(["No columns selected"])
    blocked = [c for c in cols if c not in allowed]
    if blocked:
        activity_log.record("data_export.run", outcome="denied", principal=actor, dataset=key)
        raise PermissionDenied("Only the data manager can export "
                               + ", ".join(d.column(c).heading for c in blocked))  # type: ignore[union-attr]
    if can_export_all(actor):
        return d, [d.column(c) for c in cols], None, "everyone"  # type: ignore[misc]
    scope, label = _teacher_scope(actor, d)
    return d, [d.column(c) for c in cols], scope, label  # type: ignore[misc]


def clean_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    f = {k: v for k, v in (filters or {}).items() if k in FILTERS and v not in (None, "")}
    problems: list[str] = []
    if "year_group" in f:
        try:
            yg = RC.int_or_none(f["year_group"])
        except ValidationError:
            yg = None
        if yg not in P.YEAR_GROUPS:
            problems.append("Year group must be 7-11")
        f["year_group"] = yg
    for k in ("date_from", "date_to"):
        if k in f:
            d = RC.as_date(f[k], FILTERS[k], problems)
            f[k] = d.isoformat() if d else None
    if f.get("date_from") and f.get("date_to") and f["date_to"] < f["date_from"]:
        problems.append("The end date is before the start date")
    if "form" in f:
        f["form"] = str(f["form"]).strip()[:20]
    if problems:
        raise ValidationError(problems)
    return {k: v for k, v in f.items() if v not in (None, "")}


def rows(actor: Principal, key: str, columns: list[str] | None = None,
         filters: dict[str, Any] | None = None, limit: int | None = None
         ) -> tuple[list[Column], list[list[Any]], str]:
    """(columns, rows as lists, scope label) - what an export would write."""
    d, cols, scope, label = _check(actor, key, columns)
    f = clean_filters(filters)
    data = d.loader(f, scope)
    if limit is not None and limit >= 0:
        data = data[:limit]
    return cols, [[r.get(c.key) for c in cols] for r in data], label


def preview(actor: Principal, key: str, columns: list[str] | None = None,
            filters: dict[str, Any] | None = None, limit: int = PREVIEW_ROWS
            ) -> dict[str, Any]:
    cols, all_rows, label = rows(actor, key, columns, filters)
    activity_log.record("data_export.preview", principal=actor, dataset=key,
                        rows=len(all_rows))
    return {"columns": cols, "rows": all_rows[:limit], "total": len(all_rows), "scope": label}


# ── Writing ──────────────────────────────────────────────────────────

def format_for(path: str | Path, fmt: str | None = None) -> str:
    if fmt:
        if fmt not in FORMATS:
            raise ValidationError([f"Format must be one of {', '.join(FORMATS)}"])
        return fmt
    ext = Path(path).suffix.lower()
    return next((k for k, e in FORMATS.items() if e == ext), DEFAULT_FORMAT)


def _cell(v: Any) -> Any:
    return safe_cell(RC.show(v))


def render(cols: list[Column], data: list[list[Any]], fmt: str) -> str:
    """The text of an export in *fmt* (text cells formula-escaped)."""
    heads = [c.heading for c in cols]
    if fmt in ("csv", "tsv"):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="," if fmt == "csv" else "\t", lineterminator="\n")
        w.writerow([safe_cell(h) for h in heads])
        w.writerows([[_cell(v) for v in r] for r in data])
        return buf.getvalue()
    if fmt == "json":
        return json.dumps([{c.key: v for c, v in zip(cols, r)} for r in data], indent=1,
                          default=str)
    if fmt == "jsonl":
        return "".join(json.dumps({c.key: v for c, v in zip(cols, r)}, default=str) + "\n"
                       for r in data)
    if fmt == "markdown":
        def esc(v: Any) -> str:
            return str(_cell(v)).replace("|", "\\|").replace("\n", " ")
        lines = ["| " + " | ".join(esc(h) for h in heads) + " |",
                 "|" + "---|" * len(heads)]
        lines += ["| " + " | ".join(esc(v) for v in r) + " |" for r in data]
        return "\n".join(lines) + "\n"
    raise ValidationError([f"Format must be one of {', '.join(FORMATS)}"])


def _log(actor: Principal, key: str, ncols: int, filters: dict[str, Any], fmt: str, n: int,
         scope: str, *, pack: str | None = None, file_name: str | None = None,
         status: str = "ok") -> None:
    with database.connect() as conn:
        conn.execute("INSERT INTO data_export_log (actor, role, dataset, columns, filters, fmt, "
                     "row_count, scope, pack, file_name, status) VALUES "
                     "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (actor.username or "unknown", actor.role, key, ncols,
                      json.dumps(sorted(filters)) if filters else None, fmt, n, scope, pack,
                      file_name, status))
    activity_log.record("data_export.export", principal=actor, dataset=key, rows=n, fmt=fmt,
                        outcome="ok" if status == "ok" else "error")


def export(actor: Principal, key: str, path: str | Path, *, columns: list[str] | None = None,
           filters: dict[str, Any] | None = None, fmt: str | None = None,
           limit: int | None = None) -> int:
    """Write one dataset to *path*; returns the row count."""
    fmt = format_for(path, fmt)
    cols, data, scope = rows(actor, key, columns, filters, limit)
    Path(path).write_text(render(cols, data, fmt), encoding="utf-8")
    _log(actor, key, len(cols), clean_filters(filters), fmt, len(data), scope,
         file_name=Path(path).name)
    return len(data)


def run_pack(actor: Principal, datasets: list[str] | str, folder: str | Path, *,
             fmt: str = DEFAULT_FORMAT, filters: dict[str, Any] | None = None,
             zip_output: bool = False) -> dict[str, Any]:
    """The old Run export: several datasets to *folder* (one file each and a
    ``_manifest.json``), optionally zipped. Datasets the person may not
    export are listed as refused; the rest are still written."""
    RC.require_staff(actor, "data_export.run")
    pack = None
    if isinstance(datasets, str):
        if datasets not in PACKS:
            raise ValidationError([f"Unknown pack '{datasets}'"])
        pack = datasets
        datasets = list(PACKS[datasets][1])
    if not datasets:
        raise ValidationError(["Pick at least one dataset"])
    for k in datasets:
        dataset(k)
    fmt = format_for("x", fmt)
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    files, refused, total = [], [], 0
    for k in datasets:
        try:
            cols, data, scope = rows(actor, k, None, filters)
        except (PermissionDenied, ValidationError) as e:
            refused.append({"dataset": k, "why": RC.show(getattr(e, "problems", None) or e)})
            continue
        name = f"{k}{FORMATS[fmt]}"
        text = render(cols, data, fmt)
        (out / name).write_text(text, encoding="utf-8")
        _log(actor, k, len(cols), clean_filters(filters), fmt, len(data), scope, pack=pack,
             file_name=name)
        files.append({"dataset": k, "file": name, "rows": len(data), "columns": len(cols),
                      "bytes": len(text.encode("utf-8"))})
        total += len(data)
    manifest = {"pack": pack, "datasets": datasets, "format": fmt, "files": files,
                "refused": refused, "rows_total": total, "by": actor.username}
    (out / "_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    archive = None
    if zip_output:
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for f in [*(x["file"] for x in files), "_manifest.json"]:
                z.write(out / f, arcname=f)
    return {**manifest, "folder": str(out), "archive": str(archive) if archive else None}


# ── Saved exports (per person) ───────────────────────────────────────

@dataclass(frozen=True)
class Definition:
    definition_id: int
    owner: str
    name: str
    dataset: str
    columns: list[str]
    filters: dict[str, Any]
    fmt: str
    row_limit: int | None
    description: str | None
    created_at: str
    updated_at: str


def _def_row(r) -> Definition:
    return Definition(r["definition_id"], r["owner"], r["name"], r["dataset"],
                      json.loads(r["columns"]), json.loads(r["filters"] or "{}"), r["fmt"],
                      r["row_limit"], r["description"], r["created_at"], r["updated_at"])


def list_definitions(actor: Principal) -> list[Definition]:
    RC.require_staff(actor, "data_export.definitions")
    with database.connect() as conn:
        return [_def_row(r) for r in conn.execute(
            "SELECT * FROM data_export_definitions WHERE owner = ? ORDER BY name COLLATE "
            "NOCASE", (actor.username or "",))]


def get_definition(actor: Principal, definition_id: int) -> Definition:
    RC.require_staff(actor, "data_export.definitions")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM data_export_definitions WHERE definition_id = ? AND "
                         "owner = ?", (int(definition_id), actor.username or "")).fetchone()
    if r is None:
        raise NotFound(f"No saved export #{definition_id}")
    return _def_row(r)


def save_definition(actor: Principal, data: dict[str, Any], definition_id: int | None = None
                    ) -> Definition:
    """Save (or change) a named export: dataset, columns, filters, format,
    row limit. Checked as if it were run now."""
    RC.require_staff(actor, "data_export.definitions")
    problems: list[str] = []
    name = " ".join(str(data.get("name") or "").split())
    if not name:
        problems.append("Name is required")
    elif len(name) > MAX_NAME:
        problems.append(f"Name must be {MAX_NAME} characters or fewer")
    fmt = data.get("fmt") or DEFAULT_FORMAT
    if fmt not in FORMATS:
        problems.append(f"Format must be one of {', '.join(FORMATS)}")
    limit = data.get("row_limit")
    try:
        limit = RC.int_or_none(limit)
        if limit is not None and limit < 0:
            problems.append("Row limit must be 0 or more")
    except ValidationError:
        problems.append("Row limit must be a whole number")
        limit = None
    if problems:
        raise ValidationError(problems)
    _d, cols, _s, _l = _check(actor, str(data.get("dataset") or ""), data.get("columns"))
    filters = clean_filters(data.get("filters"))
    desc = (str(data.get("description") or "").strip()[:300]) or None
    vals = (name, _d.key, json.dumps([c.key for c in cols]), json.dumps(filters), fmt, limit,
            desc)
    try:
        with database.connect() as conn:
            if definition_id is None:
                definition_id = conn.execute(
                    "INSERT INTO data_export_definitions (name, dataset, columns, filters, fmt, "
                    "row_limit, description, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (*vals, actor.username or "")).lastrowid
            else:
                get_definition(actor, definition_id)
                conn.execute("UPDATE data_export_definitions SET name = ?, dataset = ?, "
                             "columns = ?, filters = ?, fmt = ?, row_limit = ?, description = ?, "
                             "updated_at = datetime('now') WHERE definition_id = ? AND "
                             "owner = ?", (*vals, int(definition_id), actor.username or ""))
    except database.IntegrityError as e:
        raise ValidationError([f"You already have a saved export called '{name}'"]) from e
    activity_log.record("data_export.save", target=definition_id, principal=actor,
                        dataset=_d.key)
    return get_definition(actor, int(definition_id))  # type: ignore[arg-type]


def delete_definition(actor: Principal, definition_id: int) -> bool:
    get_definition(actor, definition_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM data_export_definitions WHERE definition_id = ? AND owner = ?",
                     (int(definition_id), actor.username or ""))
    activity_log.record("data_export.delete", target=definition_id, principal=actor)
    return True


def run_definition(actor: Principal, definition_id: int, path: str | Path) -> int:
    d = get_definition(actor, definition_id)
    return export(actor, d.dataset, path, columns=d.columns, filters=d.filters,
                  fmt=format_for(path) if Path(path).suffix else d.fmt, limit=d.row_limit)


# ── The export log ───────────────────────────────────────────────────

def history(actor: Principal, *, everyone: bool = False, limit: int = 300
            ) -> list[dict[str, Any]]:
    """Past exports: the data manager sees everyone's (with *everyone*);
    other staff see their own."""
    RC.require_staff(actor, "data_export.history")
    sql, params = "SELECT * FROM data_export_log", []
    if not (everyone and can_export_all(actor)):
        sql += " WHERE actor = ?"
        params.append(actor.username or "")
    with database.connect() as conn:
        out = [dict(r) for r in conn.execute(sql + " ORDER BY log_id DESC LIMIT ?",
                                             (*params, int(limit)))]
    for r in out:
        r["filters"] = ", ".join(json.loads(r["filters"])) if r["filters"] else ""
    return out


def delete_log_entry(actor: Principal, log_id: int) -> bool:
    """The old Delete job (data manager only)."""
    RC.require_data_manager(actor, "data_export.history", "that")
    with database.connect() as conn:
        n = conn.execute("DELETE FROM data_export_log WHERE log_id = ?", (int(log_id),)).rowcount
    if not n:
        raise NotFound(f"No export #{log_id}")
    activity_log.record("data_export.log_delete", target=log_id, principal=actor)
    return True


def overview(actor: Principal) -> dict[str, Any]:
    """The old Overview: totals over the export log."""
    rows_ = history(actor, everyone=True, limit=100000)
    return {"exports": len(rows_), "succeeded": sum(1 for r in rows_ if r["status"] == "ok"),
            "failed": sum(1 for r in rows_ if r["status"] != "ok"),
            "rows": sum(r["row_count"] for r in rows_),
            "datasets": len({r["dataset"] for r in rows_}),
            "packs": len(PACKS), "saved": len(list_definitions(actor)),
            "last": rows_[0]["at"] if rows_ else None}


def safe_file_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "export"
