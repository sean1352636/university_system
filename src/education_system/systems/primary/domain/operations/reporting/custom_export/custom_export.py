"""Custom Export for the Primary School System.

A small, focused export engine: pick a dataset, optionally filter,
optionally choose columns, and write CSV / TSV / JSON / JSONL /
Markdown. Read-only — nothing here mutates state.

Datasets are registered in ``DATASETS``. Each entry knows:
* ``label``       — human name
* ``description`` — one-liner
* ``columns``     — ordered list of ``(key, header)`` tuples
* ``list_fn``     — callable returning an iterable of objects/dicts
* ``filter_keys`` — keyword arg names the ``list_fn`` accepts
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from education_system.systems.primary.domain.operations.reporting.custom_export import custom_export as data

logger = logging.getLogger(__name__)

FORMATS: tuple[str, ...] = (
    "csv", "tsv", "json", "jsonl", "markdown",
)
DEFAULT_FORMAT: str = "csv"


# ── Result types ──────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class DatasetSpec:
    key: str
    label: str
    description: str
    columns: list[tuple[str, str]]
    list_fn: Callable[..., Iterable[Any]]
    filter_keys: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    dataset_key: str
    fmt: str
    row_count: int
    column_count: int
    path: str | None        # None if written to a buffer
    bytes_written: int


# ── Cell helpers ──────────────────────────────────────────────────

def _get(row: Any, key: str) -> Any:
    """Pull a value by ``key`` from a dataclass / dict / dotted path
    on an object. Returns None if the path can't be resolved."""
    cur = row
    for part in key.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return ", ".join(_stringify(x) for x in v)
    return str(v)


def _json_safe(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json_safe(x) for x in v]
    return _stringify(v)


# ── Registry ──────────────────────────────────────────────────────


def _safe_register(R: dict[str, DatasetSpec], key: str,
                   build: Callable[[], DatasetSpec]) -> None:
    """Register a dataset, swallowing import / setup failures.

    Lets us list every dataset the primary system could provide while
    keeping the registry resilient to optional modules being absent or
    half-stubbed.
    """
    try:
        R[key] = build()
    except Exception:
        logger.exception("custom_export: failed to register dataset %r", key)


def _build_registry() -> dict[str, DatasetSpec]:
    R: dict[str, DatasetSpec] = {}

    def _pupils() -> DatasetSpec:
        from education_system.systems.primary.domain.learners.pupils import (
            pupils as pupils_mod,
        )
        return DatasetSpec(
            key="pupils", label="Pupils",
            description="Full pupil directory.",
            columns=[
                ("pupil_id", "Pupil ID"),
                ("first_name", "First name"),
                ("last_name", "Last name"),
                ("year_group", "Year"),
                ("class_name", "Class"),
                ("date_of_birth", "DOB"),
                ("email", "Email"),
                ("parent_name", "Parent"),
                ("parent_phone", "Parent phone"),
                ("send_status", "SEND"),
                ("medical_notes", "Medical notes"),
            ],
            list_fn=pupils_mod.list_pupils,
        )

    def _staff() -> DatasetSpec:
        from education_system.systems.primary.domain.staff import (
            staff as staff_mod,
        )
        return DatasetSpec(
            key="staff", label="Staff",
            description="Staff directory.",
            columns=[
                ("staff_id", "Staff ID"),
                ("first_name", "First name"),
                ("last_name", "Last name"),
                ("role", "Role"),
                ("department", "Department"),
                ("email", "Email"),
                ("is_active", "Active"),
                ("start_date", "Start"),
                ("end_date", "End"),
            ],
            list_fn=staff_mod.list_staff,
            filter_keys=["role", "department", "active_only"],
        )

    def _attendance() -> DatasetSpec:
        from education_system.systems.primary.domain.academics.attendance import (
            attendance as att_mod,
        )

        def _list(**kwargs: Any) -> list[Any]:
            return att_mod.list_records(
                pupil_id=kwargs.get("pupil_id"),
                date_from=kwargs.get("date_from"),
                date_to=kwargs.get("date_to"),
            )

        return DatasetSpec(
            key="attendance", label="Attendance records",
            description="Attendance marks (AM/PM sessions), optionally "
                        "for one pupil or a date range.",
            columns=[
                ("record_id", "#"),
                ("pupil_id", "Pupil"),
                ("date", "Date"),
                ("session", "Session"),
                ("mark", "Mark"),
                ("category", "Category"),
                ("notes", "Notes"),
            ],
            list_fn=_list,
            filter_keys=["pupil_id", "date_from", "date_to"],
        )

    def _behaviour() -> DatasetSpec:
        from education_system.systems.primary.domain.pastoral.behaviour import (
            behaviour as beh_mod,
        )
        return DatasetSpec(
            key="behaviour", label="Behaviour incidents",
            description="Behaviour incidents logged for pupils.",
            columns=[
                ("incident_id", "#"),
                ("pupil_id", "Pupil"),
                ("incident_date", "Date"),
                ("incident_type", "Type"),
                ("polarity", "Positive / negative"),
                ("severity", "Severity"),
                ("description", "Description"),
                ("action_taken", "Action"),
                ("raised_by", "Raised by"),
            ],
            list_fn=beh_mod.list_incidents,
            filter_keys=["pupil_id", "incident_type", "severity",
                         "date_from", "date_to"],
        )

    def _safeguarding() -> DatasetSpec:
        from education_system.systems.primary.domain.safeguarding import (
            safeguarding as sg_mod,
        )
        return DatasetSpec(
            key="safeguarding", label="Safeguarding concerns",
            description="Safeguarding concerns and follow-ups.",
            columns=[
                ("concern_id", "#"),
                ("pupil_id", "Pupil"),
                ("raised_date", "Raised"),
                ("category", "Category"),
                ("severity", "Severity"),
                ("status", "Status"),
                ("description", "Description"),
            ],
            list_fn=sg_mod.list_concerns,
            filter_keys=["pupil_id", "status", "severity"],
        )

    def _subjects() -> DatasetSpec:
        from education_system.systems.primary.domain.academics.subjects import (
            subjects as subj_mod,
        )
        return DatasetSpec(
            key="subjects", label="Subjects",
            description="Subjects catalogue.",
            columns=[
                ("subject_id", "#"),
                ("code", "Code"),
                ("name", "Name"),
                ("department", "Department"),
                ("is_core", "Core"),
                ("is_active", "Active"),
            ],
            list_fn=subj_mod.list_all,
            filter_keys=["active_only"],
        )

    def _homework() -> DatasetSpec:
        from education_system.systems.primary.domain.academics.homework import (
            homework as hw_mod,
        )
        return DatasetSpec(
            key="homework", label="Homework assignments",
            description="Homework / reading log assignments.",
            columns=[
                ("assignment_id", "#"),
                ("title", "Title"),
                ("year_group", "Year"),
                ("set_date", "Set"),
                ("due_date", "Due"),
            ],
            list_fn=hw_mod.list_assignments,
            filter_keys=["year_group"],
        )

    def _parent_contacts() -> DatasetSpec:
        from education_system.systems.primary.domain.operations.communications.parent_contacts import (
            parent_contacts as pc_mod,
        )
        return DatasetSpec(
            key="parent_contacts", label="Parent contacts",
            description="Parents and carers on each pupil's record.",
            columns=[
                ("contact_id", "#"),
                ("student_id", "Pupil"),
                ("relationship", "Relationship"),
                ("first_name", "First name"),
                ("last_name", "Last name"),
                ("email", "Email"),
                ("primary_phone", "Phone"),
                ("is_emergency_contact", "Emergency contact"),
                ("has_parental_responsibility", "Parental responsibility"),
            ],
            list_fn=pc_mod.list_contacts,
            filter_keys=["student_id"],
        )

    def _trips() -> DatasetSpec:
        from education_system.systems.primary.domain.finance.trips import (
            trips as trips_mod,
        )
        return DatasetSpec(
            key="trips", label="Trips",
            description="School trips header records.",
            columns=[
                ("trip_id", "#"),
                ("name", "Name"),
                ("start_date", "Date"),
                ("destination", "Destination"),
                ("year_group", "Year group"),
                ("cost_per_place", "Cost per place (£)"),
                ("status", "Status"),
            ],
            list_fn=trips_mod.list_trips,
        )

    def _send() -> DatasetSpec:
        from education_system.systems.primary.domain.pastoral.send import (
            send as send_mod,
        )
        return DatasetSpec(
            key="send", label="SEND records",
            description="Pupils on the SEND register.",
            columns=[
                ("send_id", "#"),
                ("pupil_id", "Pupil"),
                ("provision_stage", "Stage"),
                ("primary_need", "Primary need"),
                ("status", "Status"),
                ("next_review_date", "Next review"),
                ("notes", "Notes"),
            ],
            list_fn=send_mod.list_records,
            filter_keys=["year_group", "provision_stage"],
        )

    A = "education_system.systems.primary.domain."

    def _records(module: str, fn: str, *, pick: int | None = None):
        """A list_fn over ``module.fn``; ``pick`` takes that item from each
        (record, pupil) pair the primary list functions return."""
        def _list(**kwargs: Any) -> list[Any]:
            import importlib
            rows = getattr(importlib.import_module(A + module), fn)(**kwargs)
            if pick is None:
                return list(rows)
            return [r[pick] for r in rows if r[pick] is not None]
        return _list

    def _result(key, label, description, module, fn, columns, filters, pick=0):
        return lambda: DatasetSpec(
            key=key, label=label, description=description, columns=columns,
            list_fn=_records(module, fn, pick=pick), filter_keys=filters)

    _reading_levels = _result(
        "reading_levels", "Reading levels", "Each pupil's current reading band.",
        "assessment.reading_levels.reading_levels", "list_records",
        [("pupil_id", "Pupil"), ("band", "Band"), ("status", "Status"),
         ("last_assessed", "Last assessed"), ("book_title", "Book")],
        ["year_group", "band", "status"], pick=1)
    _phonics = _result(
        "phonics_screening", "Phonics screening check", "Year 1 / 2 phonics check scores.",
        "assessment.phonics_screening.phonics_screening", "list_results",
        [("result_id", "#"), ("pupil_id", "Pupil"), ("academic_year", "Year"),
         ("attempt", "Attempt"), ("score", "Score /40"), ("passed", "Passed"),
         ("assessed_on", "Assessed")],
        ["academic_year", "pupil_id", "year_group"])
    _mtc = _result(
        "mtc", "Multiplication tables check", "Year 4 MTC scores.",
        "assessment.mtc.mtc", "list_results",
        [("result_id", "#"), ("pupil_id", "Pupil"), ("academic_year", "Year"),
         ("score", "Score /25"), ("met_expected", "Met expected"),
         ("assessed_on", "Assessed")],
        ["academic_year", "pupil_id", "year_group"])
    _sats_cols = [("result_id", "#"), ("pupil_id", "Pupil"), ("academic_year", "Year"),
                  ("subject", "Subject"), ("scaled_score", "Scaled score"),
                  ("outcome", "Outcome"), ("assessed_on", "Assessed")]
    _ks1 = _result("ks1_sats", "KS1 SATs", "End of KS1 results.",
                   "assessment.ks1_sats.ks1_sats", "list_results", _sats_cols,
                   ["academic_year", "subject", "pupil_id", "year_group"])
    _ks2 = _result("ks2_sats", "KS2 SATs", "End of KS2 results.",
                   "assessment.ks2_sats.ks2_sats", "list_results", _sats_cols,
                   ["academic_year", "subject", "pupil_id", "year_group"])
    _progress = _result(
        "progress_reviews", "Progress reviews", "Pupil progress reviews.",
        "assessment.progress.progress", "list_reviews",
        [("review_id", "#"), ("student_id", "Pupil"), ("review_date", "Date"),
         ("period", "Period"), ("overall", "Overall"), ("risk_level", "Risk"),
         ("attendance_pct", "Attendance %"), ("status", "Status")],
        ["student_id", "period", "academic_year", "risk_level"], pick=None)
    _dinner = _result(
        "dinner_money", "Dinner money ledger", "Meals charged and top-ups paid.",
        "finance.dinner_money.dinner_money", "list_entries",
        [("entry_id", "#"), ("pupil_id", "Pupil"), ("entry_date", "Date"),
         ("kind", "Kind"), ("meal_type", "Meal"), ("amount_display", "Amount"),
         ("description", "Description")],
        ["pupil_id", "kind", "from_date", "to_date"])
    _pp = _result(
        "pupil_premium", "Pupil Premium", "Pupil Premium eligibility records.",
        "finance.pupil_premium.pupil_premium", "list_records",
        [("pp_id", "#"), ("pupil_id", "Pupil"), ("academic_year", "Year"),
         ("category", "Category"), ("status", "Status"),
         ("funding_amount", "Funding (£)"), ("eligibility_source", "Source")],
        ["year_group", "academic_year", "category", "status"], pick=None)
    _receipts = _result(
        "receipts", "Receipts", "Receipts issued for payments.",
        "finance.receipts.receipts", "list_receipts",
        [("receipt_number", "Receipt"), ("issued_date", "Date"),
         ("payer_name", "Payer"), ("student_id", "Pupil"), ("method", "Method"),
         ("total_amount", "Total (£)"), ("status", "Status")],
        ["student_id", "status", "date_from", "date_to"], pick=None)

    for key, builder in (
        ("pupils",          _pupils),
        ("staff",           _staff),
        ("attendance",      _attendance),
        ("behaviour",       _behaviour),
        ("safeguarding",    _safeguarding),
        ("subjects",        _subjects),
        ("homework",        _homework),
        ("parent_contacts", _parent_contacts),
        ("trips",           _trips),
        ("send",            _send),
        ("reading_levels",  _reading_levels),
        ("phonics_screening", _phonics),
        ("mtc",             _mtc),
        ("ks1_sats",        _ks1),
        ("ks2_sats",        _ks2),
        ("progress_reviews", _progress),
        ("dinner_money",    _dinner),
        ("pupil_premium",   _pp),
        ("receipts",        _receipts),
    ):
        _safe_register(R, key, builder)

    return R


_DATASETS_CACHE: dict[str, DatasetSpec] | None = None


def DATASETS() -> dict[str, DatasetSpec]:  # noqa: N802
    """Lazy-built registry — avoids importing every module at import
    time (matters when tests stub modules)."""
    global _DATASETS_CACHE
    if _DATASETS_CACHE is None:
        _DATASETS_CACHE = _build_registry()
    return _DATASETS_CACHE


def list_datasets() -> list[DatasetSpec]:
    return sorted(DATASETS().values(), key=lambda d: d.label.lower())


def get_dataset(key: str) -> DatasetSpec:
    reg = DATASETS()
    if key not in reg:
        raise ValidationError(
            f"Unknown dataset {key!r}. Try one of: "
            f"{', '.join(sorted(reg.keys()))}")
    return reg[key]


# ── Fetch + filter rows ───────────────────────────────────────────

def _apply_filters(spec: DatasetSpec,
                     filters: dict[str, Any]) -> list[Any]:
    """Call ``spec.list_fn(**filters_for_known_keys)`` and return
    rows. Unknown keys are ignored — a friendly behaviour for the
    quick-export CLI."""
    if not filters:
        return list(spec.list_fn())
    accepted = {k: v for k, v in filters.items()
                 if k in spec.filter_keys and v not in (None, "")}
    try:
        return list(spec.list_fn(**accepted))
    except TypeError:
        # list_fn signature changed; fall back to no-filter call.
        return list(spec.list_fn())


def fetch(spec_or_key: DatasetSpec | str,
            *,
            filters: dict[str, Any] | None = None,
            limit: int | None = None) -> list[Any]:
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    rows = _apply_filters(spec, filters or {})
    if limit is not None:
        rows = rows[:limit]
    return rows


def project(rows: list[Any],
             columns: list[tuple[str, str]]) -> list[list[str]]:
    """Return a 2-D table (no header row) of stringified cells."""
    return [[_stringify(_get(r, k)) for k, _ in columns]
            for r in rows]


def project_dicts(rows: list[Any],
                    columns: list[tuple[str, str]]) -> list[dict]:
    return [{label: _json_safe(_get(r, k)) for k, label in columns}
            for r in rows]


# ── Writers ──────────────────────────────────────────────────────

def _write_csv_like(rows: list[list[str]],
                      headers: list[str], *,
                      delimiter: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter,
                      quoting=csv.QUOTE_MINIMAL,
                      lineterminator="\n")
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _write_json(dicts: list[dict]) -> str:
    return json.dumps(dicts, indent=2, ensure_ascii=False) + "\n"


def _write_jsonl(dicts: list[dict]) -> str:
    return "\n".join(json.dumps(d, ensure_ascii=False)
                     for d in dicts) + "\n"


def _write_markdown(rows: list[list[str]],
                       headers: list[str]) -> str:
    def _esc(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ⏎ ")
    lines: list[str] = []
    lines.append("| " + " | ".join(_esc(h) for h in headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        lines.append("| " + " | ".join(_esc(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def render(
    spec_or_key: DatasetSpec | str,
    *,
    fmt: str = DEFAULT_FORMAT,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> str:
    """Return the rendered export as a string. Use ``export()`` to
    also write it to disk."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    body, _rows = _render_with_count(spec, fmt=fmt, columns=columns,
                                     filters=filters, limit=limit)
    return body


def _render_with_count(
    spec: DatasetSpec,
    *,
    fmt: str,
    columns: list[str] | None,
    filters: dict[str, Any] | None,
    limit: int | None,
) -> tuple[str, int]:
    """Render ``spec`` and return ``(body, data_rows)``. The row count is
    the number of records written, independent of how many text lines a
    record takes (a CSV cell may hold newlines)."""
    fmt = (fmt or DEFAULT_FORMAT).lower().strip()
    if fmt not in FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(FORMATS)}")
    cols = _resolve_columns(spec, columns)
    if not cols:
        raise ValidationError("No columns selected")
    rows_raw = fetch(spec, filters=filters, limit=limit)
    return _render_rows(fmt, cols, rows_raw), len(rows_raw)


def _render_rows(fmt: str, cols: list[tuple[str, str]],
                 rows_raw: list[Any]) -> str:
    if fmt == "csv":
        rows = project(rows_raw, cols)
        return _write_csv_like(rows, [h for _, h in cols],
                                  delimiter=",")
    if fmt == "tsv":
        rows = project(rows_raw, cols)
        return _write_csv_like(rows, [h for _, h in cols],
                                  delimiter="\t")
    if fmt == "json":
        return _write_json(project_dicts(rows_raw, cols))
    if fmt == "jsonl":
        return _write_jsonl(project_dicts(rows_raw, cols))
    if fmt == "markdown":
        rows = project(rows_raw, cols)
        return _write_markdown(rows, [h for _, h in cols])
    raise ValidationError(f"Unsupported format: {fmt}")


def export(
    spec_or_key: DatasetSpec | str,
    output_path: str | Path,
    *,
    fmt: str | None = None,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> ExportResult:
    """Write to a file. Format is auto-detected from extension when
    ``fmt`` is None."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    path = Path(output_path).expanduser()
    if fmt is None:
        suffix = path.suffix.lower().lstrip(".")
        fmt = suffix if suffix in FORMATS else DEFAULT_FORMAT
        if suffix == "md":
            fmt = "markdown"
    fmt = fmt.lower().strip()
    body, rows_n = _render_with_count(spec, fmt=fmt, columns=columns,
                                      filters=filters, limit=limit)
    path.parent.mkdir(parents=True, exist_ok=True)
    # bytes_written is the on-disk size, not the character count.
    written = path.write_bytes(body.encode("utf-8"))
    cols = _resolve_columns(spec, columns)
    logger.info(
        "Exported %s → %s (%s, %d row(s), %d byte(s))",
        spec.key, path, fmt, rows_n, written)
    return ExportResult(
        dataset_key=spec.key, fmt=fmt,
        row_count=rows_n, column_count=len(cols),
        path=str(path), bytes_written=written,
    )


def _resolve_columns(spec: DatasetSpec,
                       columns: list[str] | None
                       ) -> list[tuple[str, str]]:
    if not columns:
        return list(spec.columns)
    col_map = {k: h for k, h in spec.columns}
    out: list[tuple[str, str]] = []
    for c in columns:
        c = c.strip()
        if not c:
            continue
        if c in col_map:
            out.append((c, col_map[c]))
        else:
            # Allow free-form keys for advanced users.
            out.append((c, c))
    return out


def preview(
    spec_or_key: DatasetSpec | str,
    *,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 10,
) -> tuple[list[str], list[list[str]]]:
    """Return (headers, rows) for a small preview."""
    spec = (spec_or_key if isinstance(spec_or_key, DatasetSpec)
            else get_dataset(spec_or_key))
    cols = _resolve_columns(spec, columns)
    rows_raw = fetch(spec, filters=filters, limit=limit)
    return [h for _, h in cols], project(rows_raw, cols)
