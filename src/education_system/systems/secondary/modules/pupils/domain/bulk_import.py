"""Bulk Import: pupils in and out of the system in bulk, as undoable jobs.

Everything goes through the same rules as one-at-a-time screens (pupil and
contact validation, edit rights, audit, activity log):

* **Import** - :func:`read_file` reads a CSV or Excel (.xlsx) file and
  :func:`preview` checks every row *without writing anything*: errors, warnings
  (year group not matching date of birth, unknown columns) and likely duplicates
  (same legal name + date of birth already on file) are shown per row.
  :func:`run_import` then adds the ready rows (duplicates only if confirmed),
  their parent contacts, and optionally their logins + welcome e-mails. A row
  that fails at that point is reported and the rest carry on.
* **Bulk update** - one field (year group, form, SEN, FSM, EAL) set for many
  pupils at once; previewed first, recorded with before/after values.
* **Bulk delete** - for records created in error; needs a reason and typing
  DELETE in the screens. Each removal keeps a full copy in the pupil audit
  trail. Pupils who leave belong in Enrolment & Leavers, not here.
* **Undo** - an import job removes the pupils it added (and their logins) and
  an update job puts the old values back, *except* for pupils changed since -
  those are skipped and listed. Deletes can't be undone.
* **Export** - pupils to CSV in the import layout (so a file can go out and
  back in). Needs/notes columns only when asked for; cells that a spreadsheet
  would run as a formula are escaped.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MENU_LABEL = "Bulk Import"
MAX_ROWS = 2000
MAX_BYTES = 5 * 1024 * 1024
MAX_CONTACTS = 2

PUPIL_COLUMNS: tuple[str, ...] = (
    "upn", "legal_first_name", "middle_names", "legal_last_name", "preferred_name",
    "date_of_birth", "gender", "year_group", "form_group", "admission_date",
    "address_line1", "address_line2", "town", "postcode",
    "sen_status", "fsm_eligible", "eal", "notes",
)
CONTACT_FIELDS: tuple[str, ...] = ("name", "relationship", "email", "phone", "receives_email")
CONTACT_COLUMNS: tuple[str, ...] = tuple(
    f"contact{n}_{f}" for n in range(1, MAX_CONTACTS + 1) for f in CONTACT_FIELDS)
COLUMNS: tuple[str, ...] = PUPIL_COLUMNS + CONTACT_COLUMNS
REQUIRED: tuple[str, ...] = ("legal_first_name", "legal_last_name", "date_of_birth", "gender",
                             "year_group")
#: Needs, eligibility and notes: only exported when asked for.
SENSITIVE: frozenset[str] = frozenset({"sen_status", "fsm_eligible", "eal", "notes"})

#: Other spellings accepted in a header row (after lower-casing, spaces → _).
ALIASES: dict[str, str] = {
    "first_name": "legal_first_name", "forename": "legal_first_name",
    "firstname": "legal_first_name", "given_name": "legal_first_name",
    "last_name": "legal_last_name", "surname": "legal_last_name",
    "lastname": "legal_last_name", "family_name": "legal_last_name",
    "middle_name": "middle_names", "known_as": "preferred_name",
    "dob": "date_of_birth", "birth_date": "date_of_birth", "sex": "gender",
    "year": "year_group", "nc_year": "year_group", "form": "form_group",
    "tutor_group": "form_group", "reg_group": "form_group",
    "admission": "admission_date", "start_date": "admission_date",
    "date_of_admission": "admission_date", "address_1": "address_line1",
    "address1": "address_line1", "address_2": "address_line2", "address2": "address_line2",
    "post_code": "postcode", "sen": "sen_status", "send": "sen_status",
    "fsm": "fsm_eligible", "free_school_meals": "fsm_eligible",
    "english_additional_language": "eal",
}

#: Fields bulk update may set, with their labels.
UPDATE_FIELDS: dict[str, str] = {
    "year_group": "Year group", "form_group": "Form group", "sen_status": "SEN status",
    "fsm_eligible": "Free school meals", "eal": "English as an additional language",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bulk_jobs (
    job_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK (kind IN ('import', 'update', 'delete')),
    description TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    done        INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'done', 'undone', 'partly_undone')),
    undone_at   TEXT,
    undone_by   TEXT
);
-- No foreign key to pupils: the job record survives its pupils being removed.
CREATE TABLE IF NOT EXISTS bulk_job_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES bulk_jobs(job_id) ON DELETE CASCADE,
    line         INTEGER,
    pupil_id     INTEGER,
    admission_no TEXT,
    outcome      TEXT NOT NULL CHECK (outcome IN ('done', 'failed', 'undone', 'kept')),
    message      TEXT,
    detail       TEXT
);
CREATE INDEX IF NOT EXISTS ix_bulk_job_items ON bulk_job_items (job_id, item_id);
"""

database.register_schema("bulk_import", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not (actor.can_open(MENU_LABEL) and actor.can_edit_pupils):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account doesn't have access to Bulk Import.")


# ── Reading a file ──────────────────────────────────────────────────

def _header(name: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")
    return ALIASES.get(key, key)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass
class SourceFile:
    name: str
    columns: list[str]          # normalised, in file order
    ignored: list[str]          # headers we don't use
    rows: list[tuple[int, dict[str, str]]]   # (line number, values)


def read_file(path: str | Path) -> SourceFile:
    """Read a .csv or .xlsx file. Raises ValidationError for an unreadable,
    empty, oversized file or one missing required columns."""
    p = Path(path)
    if not p.is_file():
        raise ValidationError([f"File not found: {p.name}"])
    if p.stat().st_size > MAX_BYTES:
        raise ValidationError([f"The file is too big (over {MAX_BYTES // (1024 * 1024)} MB)"])
    if p.suffix.lower() in {".xlsx", ".xlsm"}:
        raw_rows = _read_xlsx(p)
    elif p.suffix.lower() in {".csv", ".txt"}:
        raw_rows = _read_csv(p)
    else:
        raise ValidationError(["Choose a .csv or .xlsx file"])
    while raw_rows and not any(_cell(c) for c in raw_rows[0][1]):
        raw_rows.pop(0)
    if not raw_rows:
        raise ValidationError(["The file is empty"])
    headers = [_header(h) for h in raw_rows[0][1]]
    seen: set[str] = set()
    problems = []
    for h in headers:
        if h and h in seen:
            problems.append(f"Column '{h}' appears twice")
        seen.add(h)
    missing = [c for c in REQUIRED if c not in seen]
    if missing:
        problems.append("Missing column(s): " + ", ".join(missing)
                        + " - see CSV format help for the layout")
    if problems:
        raise ValidationError(problems)
    rows = []
    for line, values in raw_rows[1:]:
        cells = [_cell(v) for v in values]
        if not any(cells):
            continue  # blank line
        rows.append((line, {h: (cells[i] if i < len(cells) else "")
                            for i, h in enumerate(headers) if h in COLUMNS}))
    if not rows:
        raise ValidationError(["The file has a header row but no pupils"])
    if len(rows) > MAX_ROWS:
        raise ValidationError([f"Too many rows ({len(rows)}); import at most {MAX_ROWS} "
                               "at a time"])
    ignored = [h for h in headers if h and h not in COLUMNS]
    return SourceFile(p.name, [h for h in headers if h in COLUMNS], ignored, rows)


def _read_csv(p: Path) -> list[tuple[int, list[Any]]]:
    data = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValidationError(["The file isn't readable text - save it as CSV (UTF-8)"])
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # type: ignore[assignment]
    reader = csv.reader(text.splitlines(), dialect)
    try:
        return [(reader.line_num, row) for row in reader]
    except csv.Error as e:
        raise ValidationError([f"The CSV couldn't be read: {e}"]) from e


def _read_xlsx(p: Path) -> list[tuple[int, list[Any]]]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 - corrupt / not really xlsx
        raise ValidationError([f"The Excel file couldn't be opened: {e}"]) from e
    try:
        ws = wb.worksheets[0]
        return [(i, list(row)) for i, row in enumerate(ws.iter_rows(values_only=True), 1)]
    finally:
        wb.close()


# ── Normalising cell values ─────────────────────────────────────────

_UK_DATE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$")
_YEAR_RE = re.compile(r"^(?:year|yr|y)?\s*(\d{1,2})$", re.I)
_GENDERS = {"f": "Female", "female": "Female", "girl": "Female",
            "m": "Male", "male": "Male", "boy": "Male",
            "non-binary": "Non-binary", "nonbinary": "Non-binary", "non binary": "Non-binary",
            "nb": "Non-binary", "enby": "Non-binary",
            "other": "Other", "o": "Other",
            "prefer not to say": "Prefer not to say", "not stated": "Prefer not to say",
            "not known": "Prefer not to say", "unknown": "Prefer not to say",
            "u": "Prefer not to say", "x": "Prefer not to say"}
_SEN = {"n": "N", "none": "N", "k": "K", "sen support": "K", "support": "K",
        "e": "E", "ehcp": "E", "ehc plan": "E", "ehc": "E"}


def normalise(key: str, value: str) -> str:
    """Spreadsheet spellings → what the pupil rules expect. Anything not
    recognised is passed through so the rules report it."""
    v = (value or "").strip()
    if not v:
        return ""
    if key in {"date_of_birth", "admission_date"}:
        m = _UK_DATE.match(v)
        if m:  # UK order: day/month/year
            try:
                return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except ValueError:
                return v
        return v[:10] if re.match(r"^\d{4}-\d{2}-\d{2}[ T]", v) else v
    if key == "year_group":
        m = _YEAR_RE.match(v)
        return m.group(1) if m else v
    if key == "gender":
        return _GENDERS.get(v.lower(), v)
    if key == "sen_status":
        return _SEN.get(v.lower(), v)
    return v


# ── Preview ──────────────────────────────────────────────────────────

READY, WARNING, DUPLICATE, ERROR = "ready", "warning", "duplicate", "error"
STATUS_LABELS = {READY: "Ready", WARNING: "Ready (check)", DUPLICATE: "Possible duplicate",
                 ERROR: "Error"}


@dataclass
class RowCheck:
    line: int
    pupil: dict[str, str]
    contacts: list[dict[str, Any]]
    status: str
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    existing: str | None = None   # admission no. of a likely duplicate

    @property
    def name(self) -> str:
        return " ".join(x for x in (self.pupil.get("legal_first_name"),
                                    self.pupil.get("legal_last_name")) if x) or "(no name)"

    @property
    def importable(self) -> bool:
        return self.status in {READY, WARNING}


@dataclass
class Preview:
    file_name: str
    ignored_columns: list[str]
    rows: list[RowCheck]

    def count(self, *statuses: str) -> int:
        return sum(1 for r in self.rows if r.status in statuses)


def _contacts_of(values: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    out, problems = [], []
    for n in range(1, MAX_CONTACTS + 1):
        raw = {f: values.get(f"contact{n}_{f}", "").strip() for f in CONTACT_FIELDS}
        if not any(raw.values()):
            continue
        data = {"full_name": raw["name"], "relationship": raw["relationship"].capitalize()
                if raw["relationship"].lower() != "social worker" else "Social worker",
                "email": raw["email"], "phone": raw["phone"], "priority": n,
                "receives_email": raw["receives_email"] or "yes"}
        try:
            out.append(C._validate(data))
        except C.ValidationError as e:
            problems += [f"Contact {n}: {p}" for p in e.problems]
    return out, problems


def preview(source: SourceFile, *, today: _dt.date | None = None) -> Preview:
    """Check every row against the pupil rules. Writes nothing."""
    today = today or _dt.date.today()
    with database.connect() as conn:
        upns = {r[0] for r in conn.execute("SELECT upn FROM pupils WHERE upn IS NOT NULL")}
        by_name = {(r[0].lower(), r[1].lower(), r[2]): r[3] for r in conn.execute(
            "SELECT legal_first_name, legal_last_name, date_of_birth, admission_no FROM pupils")}
    file_upns: dict[str, int] = {}
    file_names: dict[tuple, int] = {}
    checks = []
    for line, values in source.rows:
        pupil = {k: normalise(k, values.get(k, "")) for k in PUPIL_COLUMNS if k in values}
        problems: list[str] = []
        warnings: list[str] = []
        existing = None
        try:
            clean = P._validate(pupil, today=today)
        except P.ValidationError as e:
            problems += e.problems
            clean = None
        contacts, contact_problems = _contacts_of(values)
        problems += contact_problems
        if clean:
            upn = clean["upn"]
            if upn and upn in upns:
                problems.append(f"UPN {upn} is already recorded for another pupil")
            elif upn and upn in file_upns:
                problems.append(f"UPN {upn} is also on line {file_upns[upn]}")
            elif upn:
                file_upns[upn] = line
            key = (clean["legal_first_name"].lower(), clean["legal_last_name"].lower(),
                   clean["date_of_birth"])
            if key in file_names:
                problems.append(f"Same name and date of birth as line {file_names[key]}")
            else:
                file_names[key] = line
            existing = by_name.get(key)
            if clean["admission_date"] > today.isoformat():
                problems.append("Admission date can't be in the future - add them on or "
                                "after their start date")
            w = P.year_group_warning(clean["date_of_birth"], clean["year_group"], today)
            if w:
                warnings.append(w)
            if not values.get("admission_date"):
                warnings.append("No admission date: today's date will be used")
        if problems:
            status = ERROR
        elif existing:
            status = DUPLICATE
        elif warnings:
            status = WARNING
        else:
            status = READY
        checks.append(RowCheck(line, pupil, contacts, status, problems, warnings, existing))
    return Preview(source.name, source.ignored, checks)


# ── Jobs ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Job:
    job_id: int
    kind: str
    description: str
    created_by: str
    created_at: str
    done: int
    failed: int
    status: str
    undone_at: str | None
    undone_by: str | None

    @property
    def can_undo(self) -> bool:
        return self.kind in {"import", "update"} and self.status == "done" and self.done > 0


def _job_row(r) -> Job:
    return Job(*(r[k] for k in ("job_id", "kind", "description", "created_by", "created_at",
                                "done", "failed", "status", "undone_at", "undone_by")))


def _start_job(kind: str, description: str, actor: Principal) -> int:
    with database.connect() as conn:
        return int(conn.execute("INSERT INTO bulk_jobs (kind, description, created_by) "
                                "VALUES (?, ?, ?)",
                                (kind, description, actor.username)).lastrowid)


def _item(job_id: int, outcome: str, *, line: int | None = None, pupil: P.Pupil | None = None,
          message: str | None = None, detail: dict | None = None) -> None:
    with database.connect() as conn:
        conn.execute("INSERT INTO bulk_job_items (job_id, line, pupil_id, admission_no, outcome, "
                     "message, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (job_id, line, pupil.pupil_id if pupil else None,
                      pupil.admission_no if pupil else None, outcome, message,
                      json.dumps(detail, default=str) if detail else None))


def _finish_job(job_id: int, done: int, failed: int) -> None:
    with database.connect() as conn:
        conn.execute("UPDATE bulk_jobs SET done = ?, failed = ?, status = 'done' "
                     "WHERE job_id = ?", (done, failed, job_id))


def list_jobs(limit: int = 200) -> list[Job]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM bulk_jobs ORDER BY job_id DESC LIMIT ?",
                            (limit,)).fetchall()
    return [_job_row(r) for r in rows]


def get_job(job_id: int) -> Job | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM bulk_jobs WHERE job_id = ?", (int(job_id),)).fetchone()
    return _job_row(r) if r else None


def job_items(job_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM bulk_job_items WHERE job_id = ? ORDER BY item_id",
                            (int(job_id),)).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"]) if r["detail"] else {}}
            for r in rows]


Progress = Callable[[int, int], None]


# ── Import ───────────────────────────────────────────────────────────

@dataclass
class ImportResult:
    job_id: int
    created: list[P.Pupil]
    failed: list[tuple[int, str]]                  # (line, why)
    welcome_message_ids: list[int]
    login_errors: list[tuple[str, str]]            # (admission no., why)


def run_import(pv: Preview, *, actor: Principal, include_duplicates: bool = False,
               create_logins: bool = True, progress: Progress | None = None) -> ImportResult:
    """Add the importable rows (and, if confirmed, the possible duplicates).
    Welcome e-mails are saved, not delivered: deliver ``welcome_message_ids``
    next. Safe to call off the Tk thread (no Tk here)."""
    _require(actor, "bulk.import", pv.file_name)
    rows = [r for r in pv.rows if r.importable or (include_duplicates and
                                                    r.status == DUPLICATE)]
    if not rows:
        raise ValidationError(["Nothing to import - every row has an error or is a possible "
                               "duplicate"])
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    job_id = _start_job("import", f"Import {pv.file_name} ({len(rows)} rows)", actor)
    activity_log.record("bulk.import.start", target=f"job:{job_id}", principal=actor,
                        rows=len(rows), logins=create_logins)
    result = ImportResult(job_id, [], [], [], [])
    for i, row in enumerate(rows, 1):
        try:
            pupil = P.create_pupil(row.pupil, actor=actor,
                                   allow_duplicate=row.status == DUPLICATE)
        except P.DuplicatePupil as e:
            why = f"Possible duplicate of {e.existing.admission_no} (added since the preview)"
            result.failed.append((row.line, why))
            _item(job_id, "failed", line=row.line, message=why)
        except (P.ValidationError, P.PermissionDenied) as e:
            result.failed.append((row.line, str(e)))
            _item(job_id, "failed", line=row.line, message=str(e))
        except Exception as e:  # noqa: BLE001 - one bad row mustn't stop the rest
            result.failed.append((row.line, f"Unexpected error: {e}"))
            _item(job_id, "failed", line=row.line, message=type(e).__name__)
        else:
            contact_ids = []
            for contact in row.contacts:
                try:
                    contact_ids.append(C.add_contact(pupil.pupil_id, contact,
                                                     actor=actor).contact_id)
                except Exception as e:  # noqa: BLE001
                    result.failed.append((row.line, f"Pupil added but a contact wasn't: {e}"))
            if create_logins:
                try:
                    new = pupil_accounts.create_for_pupil(pupil.pupil_id, actor=actor)
                    if new.welcome_message_id:
                        result.welcome_message_ids.append(new.welcome_message_id)
                    elif new.welcome_error:
                        result.login_errors.append((pupil.admission_no,
                                                    f"welcome e-mail: {new.welcome_error}"))
                except Exception as e:  # noqa: BLE001 - "Create login" on the profile retries
                    result.login_errors.append((pupil.admission_no, str(e)))
            result.created.append(pupil)
            _item(job_id, "done", line=row.line, pupil=pupil,
                  detail={"contacts": contact_ids})
        if progress:
            progress(i, len(rows))
    _finish_job(job_id, len(result.created), len(result.failed))
    activity_log.record("bulk.import", target=f"job:{job_id}", principal=actor,
                        created=len(result.created), failed=len(result.failed) or None,
                        login_errors=len(result.login_errors) or None)
    return result


# ── Bulk update ──────────────────────────────────────────────────────

def resolve_refs(text: str) -> tuple[list[P.Pupil], list[str]]:
    """Admission numbers / UPNs (comma, space or line separated) → pupils,
    plus the references that matched nobody."""
    found, missing, seen = [], [], set()
    for ref in [r for r in re.split(r"[,;\s]+", text or "") if r]:
        p = P.find_by_reference(ref)
        if p is None:
            missing.append(ref)
        elif p.pupil_id not in seen:
            seen.add(p.pupil_id)
            found.append(p)
    return found, missing


@dataclass(frozen=True)
class UpdateCheck:
    pupil: P.Pupil
    before: Any
    after: Any
    problem: str | None

    @property
    def changes(self) -> bool:
        return self.problem is None and self.before != self.after


def preview_update(field_name: str, value: Any, pupils: list[P.Pupil]) -> list[UpdateCheck]:
    """What setting *field_name* to *value* would do to each pupil. Writes nothing."""
    if field_name not in UPDATE_FIELDS:
        raise ValidationError(["Choose a field: " + ", ".join(UPDATE_FIELDS.values())])
    value = normalise(field_name, "" if value is None else str(value))
    out = []
    for p in pupils:
        merged = {k: getattr(p, k) for k in P.EDITABLE_FIELDS}
        merged[field_name] = value
        try:
            after = P._validate(merged)[field_name]
            problem = None
        except P.ValidationError as e:
            after, problem = None, "; ".join(
                x for x in e.problems if UPDATE_FIELDS[field_name].split()[0].lower()
                in x.lower()) or "; ".join(e.problems)
        if problem is None and field_name == "form_group" and after:
            from education_system.systems.secondary.modules.curriculum.domain import form_groups
            try:
                form_groups.check_choice(p.year_group, after, p.form_group)
            except P.ValidationError as e:
                after, problem = None, "; ".join(e.problems)
        before = getattr(p, field_name)
        if isinstance(before, int) and isinstance(after, bool):
            before = bool(before)
        out.append(UpdateCheck(p, before, after, problem))
    return out


def run_update(field_name: str, value: Any, pupil_ids: list[int], *, actor: Principal,
               progress: Progress | None = None) -> tuple[int, list[tuple[str, str]]]:
    """Apply the change; returns (job_id, [(admission no., why not)]).
    No "your record changed" e-mails are sent for bulk changes."""
    _require(actor, "bulk.update", field_name)
    pupils = [p for p in (P.get_pupil(i) for i in dict.fromkeys(pupil_ids)) if p]
    checks = preview_update(field_name, value, pupils)
    todo = [c for c in checks if c.changes]
    if not todo:
        raise ValidationError(["Nothing would change"])
    label = UPDATE_FIELDS[field_name]
    job_id = _start_job("update", f"Set {label} = {_show(todo[0].after)} for "
                                  f"{len(todo)} pupil{'s' if len(todo) != 1 else ''}", actor)
    failed: list[tuple[str, str]] = [(c.pupil.admission_no, c.problem)
                                     for c in checks if c.problem]
    done = 0
    for i, c in enumerate(todo, 1):
        try:
            P.update_pupil(c.pupil.pupil_id, {field_name: c.after}, actor=actor)
        except Exception as e:  # noqa: BLE001
            failed.append((c.pupil.admission_no, str(e)))
            _item(job_id, "failed", pupil=c.pupil, message=str(e))
        else:
            done += 1
            _item(job_id, "done", pupil=c.pupil,
                  detail={"field": field_name, "from": c.before, "to": c.after})
        if progress:
            progress(i, len(todo))
    _finish_job(job_id, done, len(failed))
    activity_log.record("bulk.update", target=f"job:{job_id}", principal=actor,
                        field=field_name, updated=done, failed=len(failed) or None)
    return job_id, failed


def _show(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    return "(blank)" if v in (None, "") else str(v)


# ── Bulk delete ──────────────────────────────────────────────────────

def run_delete(pupil_ids: list[int], *, actor: Principal, reason: str,
               progress: Progress | None = None) -> tuple[int, list[tuple[str, str]]]:
    """Delete records created in error (each keeps a full copy in the pupil
    audit trail and loses its login). Can't be undone from here."""
    _require(actor, "bulk.delete", f"{len(pupil_ids)} pupils")
    reason = P._clean_text(reason, 300) or ""
    if not reason:
        raise ValidationError(["A reason is required"])
    ids = list(dict.fromkeys(pupil_ids))
    if not ids:
        raise ValidationError(["Choose the pupils to delete"])
    job_id = _start_job("delete", f"Delete {len(ids)} pupil record"
                                  f"{'s' if len(ids) != 1 else ''}: {reason}", actor)
    done, failed = 0, []
    for i, pid in enumerate(ids, 1):
        try:
            removed = P.delete_pupil(pid, actor=actor, reason=f"Bulk delete #{job_id}: {reason}")
        except Exception as e:  # noqa: BLE001
            failed.append((str(pid), str(e)))
            _item(job_id, "failed", message=f"pupil {pid}: {e}")
        else:
            done += 1
            _item(job_id, "done", pupil=removed)
        if progress:
            progress(i, len(ids))
    _finish_job(job_id, done, len(failed))
    activity_log.record("bulk.delete", target=f"job:{job_id}", principal=actor, deleted=done,
                        failed=len(failed) or None)
    return job_id, failed


# ── Undo ─────────────────────────────────────────────────────────────

def _changed_since_import(conn, pupil_id: int, contact_ids: list[int]) -> str | None:
    n = conn.execute("SELECT COUNT(*) FROM pupil_audit WHERE pupil_id = ? AND action != 'create'",
                     (pupil_id,)).fetchone()[0]
    if n:
        return "record changed since the import"
    now = {r[0] for r in conn.execute(
        "SELECT contact_id FROM pupil_contacts WHERE pupil_id = ?", (pupil_id,))}
    if now != set(contact_ids):
        return "contacts changed since the import"
    edited = conn.execute("SELECT COUNT(*) FROM pupil_contacts WHERE pupil_id = ? AND "
                          "updated_at != created_at", (pupil_id,)).fetchone()[0]
    if edited:
        return "contacts changed since the import"
    return None


def undo_job(job_id: int, *, actor: Principal) -> tuple[int, list[tuple[str, str]]]:
    """Undo an import or update job as far as is safe; returns (undone, kept)
    where *kept* lists (admission no., why it was left alone)."""
    _require(actor, "bulk.undo", f"job:{job_id}")
    job = get_job(job_id)
    if job is None:
        raise NotFound(f"No job {job_id}")
    if not job.can_undo:
        raise ValidationError(["This job can't be undone"
                               + (" (deletes can't be undone)" if job.kind == "delete"
                                  else f" (it is {job.status.replace('_', ' ')})")])
    undone, kept = 0, []
    for item in job_items(job_id):
        if item["outcome"] != "done" or item["pupil_id"] is None:
            continue
        pid, adm = item["pupil_id"], item["admission_no"]
        why = None
        current = P.get_pupil(pid)
        if current is None:
            why = "no longer on file"
        elif job.kind == "import":
            with database.connect() as conn:
                why = _changed_since_import(conn, pid, item["detail"].get("contacts", []))
        else:
            d = item["detail"]
            now = getattr(current, d["field"])
            if (bool(now) if isinstance(d["to"], bool) else now) != d["to"]:
                why = "changed again since"
        if why is None:
            try:
                if job.kind == "import":
                    P.delete_pupil(pid, actor=actor, reason=f"Undo bulk import #{job_id}")
                else:
                    d = item["detail"]
                    P.update_pupil(pid, {d["field"]: d["from"]}, actor=actor)
            except Exception as e:  # noqa: BLE001
                why = str(e)
        with database.connect() as conn:
            conn.execute("UPDATE bulk_job_items SET outcome = ?, message = ? WHERE item_id = ?",
                         ("kept" if why else "undone", why, item["item_id"]))
        if why:
            kept.append((adm, why))
        else:
            undone += 1
    with database.connect() as conn:
        conn.execute("UPDATE bulk_jobs SET status = ?, undone_at = datetime('now'), "
                     "undone_by = ? WHERE job_id = ?",
                     ("partly_undone" if kept else "undone", actor.username, job_id))
    activity_log.record("bulk.undo", target=f"job:{job_id}", principal=actor, undone=undone,
                        kept=len(kept) or None)
    return undone, kept


# ── Export / template ────────────────────────────────────────────────

EXPORT_EXTRA: tuple[str, ...] = ("admission_no", "roll_status", "leaving_date", "leaving_reason")


def _safe(value: Any) -> str:
    """Stop a spreadsheet running a cell as a formula."""
    text = "" if value is None else ("yes" if value is True else "no" if value is False
                                     else str(value))
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(path: str | Path, *, actor: Principal, roll_status: str | None = "on_roll",
               year_group: int | None = None, form_group: str | None = None,
               include_sensitive: bool = False, include_contacts: bool = True) -> int:
    """Write pupils to *path* in the import layout; returns how many."""
    _require(actor, "bulk.export", roll_status)
    pupils = P.list_pupils(roll_status=roll_status, year_group=year_group,
                           form_group=form_group or None)
    cols = ["admission_no"] + [c for c in PUPIL_COLUMNS
                               if include_sensitive or c not in SENSITIVE]
    cols += [c for c in EXPORT_EXTRA if c != "admission_no"]
    if include_contacts:
        cols += list(CONTACT_COLUMNS)
    contacts = {}
    if include_contacts:
        with database.connect() as conn:
            for r in conn.execute("SELECT * FROM pupil_contacts ORDER BY pupil_id, priority, "
                                  "contact_id"):
                contacts.setdefault(r["pupil_id"], []).append(r)
    p = Path(path)
    with p.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for pupil in pupils:
            row = {c: getattr(pupil, c, None) for c in cols if not c.startswith("contact")}
            for n, ct in enumerate(contacts.get(pupil.pupil_id, [])[:MAX_CONTACTS], 1):
                row.update({f"contact{n}_name": ct["full_name"],
                            f"contact{n}_relationship": ct["relationship"],
                            f"contact{n}_email": ct["email"], f"contact{n}_phone": ct["phone"],
                            f"contact{n}_receives_email": bool(ct["receives_email"])})
            w.writerow([_safe(row.get(c)) for c in cols])
    activity_log.record("bulk.export", principal=actor, rows=len(pupils),
                        status=roll_status or "all", year=year_group, form=form_group or None,
                        sensitive=include_sensitive, contacts=include_contacts)
    return len(pupils)


def write_template(path: str | Path) -> None:
    """An empty import file: the header row only."""
    with Path(path).open("w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerow(COLUMNS)


FORMAT_HELP = f"""CSV or Excel (.xlsx) file, one pupil per row, with a header row.

Required columns: {', '.join(REQUIRED)}
Optional: {', '.join(c for c in PUPIL_COLUMNS if c not in REQUIRED)}
Parent contacts (up to {MAX_CONTACTS}): contactN_name, contactN_relationship, contactN_email,
  contactN_phone, contactN_receives_email (N = 1 or 2)

• Dates: YYYY-MM-DD or DD/MM/YYYY. A blank admission date means today.
• Year group: 7-11 (also "Year 7", "Y7").  Gender: Female/Male/Non-binary/Other/Prefer not to say (or F/M).
• SEN status: N (none), K (SEN support), E (EHC plan).  FSM / EAL: yes or no.
• UPN optional; if given it must be a valid 13-character UPN not already used.
• Relationship: {', '.join(C.RELATIONSHIPS)}. A contact needs an e-mail or phone.
• Common header spellings work too (Forename, Surname, DOB, Form, Year…).
• Admission numbers, logins and school e-mail addresses are made automatically.

Nothing is saved until you have seen the preview and pressed Import. Rows with errors
are skipped; possible duplicates (same name and date of birth as a pupil already on
file) are skipped unless you tick them in. A whole import can be undone from Import
history, except for pupils changed since."""
