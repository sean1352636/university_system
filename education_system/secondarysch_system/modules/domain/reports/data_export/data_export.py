"""Bulk Data Export for the Secondary School System.

Where ``custom_export`` is a single-dataset, per-export-column tool,
this module is the "big red button": pick a *preset* (a curated list
of datasets), pick a folder, and write one file per dataset plus a
manifest. Optionally zip the lot.

What's stored
-------------
* ``data_export_presets`` — user-defined presets (name +
  description + the dataset keys they include).
* ``data_export_jobs``    — every export run, with status,
  destination folder, file/row totals and the per-dataset breakdown
  in ``files_json``.

Built-in presets are exposed as ``BUILTIN_PRESETS``; the registry
mixes built-ins (read-only) with user-defined ones (CRUD).

Each dataset key is delegated to ``custom_export`` so we get its
already-curated column lists / filters for free.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime as _dt
from pathlib import Path
from typing import Any

from education_system.secondarysch_system.core import paths
from education_system.secondarysch_system.modules.domain.reports.custom_export import (
    custom_export as _ce,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.DATA_EXPORT_DB

FORMATS: tuple[str, ...] = ("csv", "tsv", "json", "jsonl", "markdown")
DEFAULT_FORMAT: str = "csv"

JOB_STATUSES: tuple[str, ...] = (
    "pending", "running", "succeeded", "partial", "failed",
)


# ── Built-in presets ──────────────────────────────────────────────

# Each preset is (key, label, description, list of dataset keys).
_BUILTIN_PRESETS_RAW: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("full_backup", "Full Backup",
     "Every registered dataset. Best for full periodic snapshots.",
     ()),  # populated lazily — "everything"
    ("students_core", "Students (core)",
     "Students, enrolments, tutor-group assignments and parent contacts.",
     ("students", "enrolments", "tutor_groups", "parent_contacts")),
    ("academics", "Academics",
     "Courses, subjects, class groups, timetable and attendance.",
     ("courses", "subjects", "class_groups",
      "timetable", "attendance")),
    ("assessment", "Assessment",
     "Homework, gradebook, predicted grades, mock exams, exam "
     "entries and results.",
     ("homework", "gradebook", "predicted_grades", "mock_exams",
      "exam_entries", "exam_results")),
    ("pastoral", "Pastoral",
     "Behaviour, safeguarding and progress reviews.",
     ("behaviour", "safeguarding", "progress_reviews",
      "progress_targets")),
    ("ucas_careers", "UCAS & Careers",
     "UCAS applications, personal statements, references, offers, "
     "apprenticeships and careers.",
     ("ucas_applications", "personal_statements", "references",
      "offers", "apprenticeship_applications", "careers_aspirations")),
    ("finance", "Finance",
     "Fees, bursaries, trips, payments and receipts.",
     ("fees", "fee_payments", "bursary_applications",
      "bursary_disbursements", "trips", "trip_bookings",
      "trip_payments", "receipts")),
    ("staff", "Staff", "Staff directory.", ("staff",)),
)


# ── Types ─────────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class Preset:
    preset_id: int | None        # None for built-ins
    key: str
    name: str
    description: str
    datasets: list[str]
    is_builtin: bool
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class DatasetResult:
    dataset_key: str
    label: str
    file_path: str
    fmt: str
    row_count: int
    column_count: int
    bytes_written: int
    error: str | None = None


@dataclass
class ExportJob:
    job_id: int
    preset_key: str
    preset_name: str
    output_dir: str
    fmt: str
    status: str
    started_at: str
    finished_at: str | None
    files_total: int
    rows_total: int
    bytes_total: int
    zipped: bool
    archive_path: str | None
    run_by: str | None
    notes: str | None
    files: list[DatasetResult] = field(default_factory=list)


# ── DB plumbing ───────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_export_presets (
    preset_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    key           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT,
    datasets_json TEXT NOT NULL DEFAULT '[]',
    created_by    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS data_export_jobs (
    job_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    preset_key    TEXT NOT NULL,
    preset_name   TEXT NOT NULL,
    output_dir    TEXT NOT NULL,
    fmt           TEXT NOT NULL DEFAULT 'csv',
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    files_total   INTEGER NOT NULL DEFAULT 0,
    rows_total    INTEGER NOT NULL DEFAULT 0,
    bytes_total   INTEGER NOT NULL DEFAULT 0,
    zipped        INTEGER NOT NULL DEFAULT 0,
    archive_path  TEXT,
    run_by        TEXT,
    notes         TEXT,
    files_json    TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_de_jobs_started ON data_export_jobs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_de_jobs_status  ON data_export_jobs(status);
CREATE INDEX IF NOT EXISTS idx_de_jobs_preset  ON data_export_jobs(preset_key);
"""


def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Data-export schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Preset registry ───────────────────────────────────────────────

def _builtin_presets() -> list[Preset]:
    out: list[Preset] = []
    for key, name, desc, datasets in _BUILTIN_PRESETS_RAW:
        if key == "full_backup":
            ds = sorted(_ce.DATASETS().keys())
        else:
            ds = list(datasets)
        out.append(Preset(
            preset_id=None, key=key, name=name,
            description=desc, datasets=ds, is_builtin=True,
        ))
    return out


def _row_preset(r: sqlite3.Row) -> Preset:
    try:
        ds = json.loads(r["datasets_json"] or "[]")
    except (TypeError, ValueError):
        ds = []
    return Preset(
        preset_id=r["preset_id"], key=r["key"], name=r["name"],
        description=r["description"] or "",
        datasets=[str(x) for x in ds] if isinstance(ds, list) else [],
        is_builtin=False,
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def list_presets() -> list[Preset]:
    init_db()
    out: list[Preset] = _builtin_presets()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM data_export_presets ORDER BY LOWER(name)"
            ).fetchall()
    out.extend(_row_preset(r) for r in rows)
    return out


def get_preset(key_or_id: str | int) -> Preset | None:
    init_db()
    if isinstance(key_or_id, int):
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM data_export_presets WHERE preset_id = ?",
                (key_or_id,)).fetchone()
        return _row_preset(r) if r else None
    key = str(key_or_id).strip()
    for b in _builtin_presets():
        if b.key == key:
            return b
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM data_export_presets WHERE key = ?",
            (key,)).fetchone()
    return _row_preset(r) if r else None


def _validate_datasets(datasets: list[str]) -> list[str]:
    if not datasets:
        raise ValidationError("Pick at least one dataset")
    known = set(_ce.DATASETS().keys())
    bad = [d for d in datasets if d not in known]
    if bad:
        raise ValidationError(
            f"Unknown dataset(s): {', '.join(bad)}. "
            f"Try one of: {', '.join(sorted(known))}")
    seen: set[str] = set()
    out: list[str] = []
    for d in datasets:
        if d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def _validate_preset_key(key: str) -> str:
    s = (key or "").strip()
    if not s:
        raise ValidationError("Preset key is required")
    if not all(c.isalnum() or c in "_-" for c in s):
        raise ValidationError(
            "Preset key must contain only letters, digits, '_' or '-'")
    for b in _builtin_presets():
        if b.key == s:
            raise ValidationError(
                f"{s!r} is a built-in preset — pick another key")
    return s


def create_preset(payload: dict[str, Any]) -> Preset:
    init_db()
    key = _validate_preset_key(payload.get("key"))
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    desc = (payload.get("description") or "").strip()
    ds = _validate_datasets(payload.get("datasets") or [])
    by = (payload.get("created_by") or "").strip() or None
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO data_export_presets
                       (key, name, description, datasets_json,
                        created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (key, name, desc, json.dumps(ds), by),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A preset with key {key!r} already exists") from None
    out = get_preset(new_id)
    assert out is not None
    logger.info("Created data-export preset #%d (%s)", new_id, key)
    return out


def update_preset(preset_id: int, payload: dict[str, Any]) -> Preset:
    init_db()
    existing = get_preset(preset_id)
    if existing is None or existing.is_builtin:
        raise ValidationError(
            f"No editable preset #{preset_id}")
    new_key = payload.get("key", existing.key)
    if new_key != existing.key:
        new_key = _validate_preset_key(new_key)
    name = (payload.get("name", existing.name) or "").strip()
    if not name:
        raise ValidationError("Name is required")
    desc_raw = payload.get("description", existing.description)
    desc = (desc_raw or "").strip()
    ds_in = payload.get("datasets", existing.datasets)
    ds = _validate_datasets(list(ds_in))
    with _connect() as conn:
        try:
            conn.execute(
                """UPDATE data_export_presets
                      SET key=?, name=?, description=?, datasets_json=?,
                          updated_at=datetime('now')
                    WHERE preset_id=?""",
                (new_key, name, desc, json.dumps(ds), preset_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A preset with key {new_key!r} already exists") from None
    out = get_preset(preset_id)
    assert out is not None
    logger.info("Updated data-export preset #%d", preset_id)
    return out


def delete_preset(preset_id: int) -> bool:
    init_db()
    p = get_preset(preset_id)
    if p is None or p.is_builtin:
        return False
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM data_export_presets WHERE preset_id = ?",
            (preset_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted data-export preset #%d", preset_id)
        return True
    return False


# ── Run an export ─────────────────────────────────────────────────

def _validate_fmt(fmt: str) -> str:
    s = (fmt or DEFAULT_FORMAT).lower().strip()
    if s not in FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(FORMATS)}")
    return s


def _ext_for(fmt: str) -> str:
    return "md" if fmt == "markdown" else fmt


def _now_iso() -> str:
    return _dt.now().replace(microsecond=0).isoformat(sep=" ")


def _safe_filename(s: str) -> str:
    keep = "-_.()"
    return "".join(c if c.isalnum() or c in keep else "_" for c in s)


def run_export(
    preset_key_or_id: str | int,
    output_dir: str | Path,
    *,
    fmt: str = DEFAULT_FORMAT,
    zip_output: bool = False,
    run_by: str | None = None,
    notes: str | None = None,
) -> ExportJob:
    """Run the export. Always returns an ExportJob — check
    ``job.status`` and ``job.files[i].error`` to see what (if
    anything) failed."""
    init_db()
    preset = get_preset(preset_key_or_id)
    if preset is None:
        raise ValidationError(f"No preset {preset_key_or_id!r}")
    if not preset.datasets:
        raise ValidationError(
            f"Preset {preset.key!r} has no datasets")
    fmt = _validate_fmt(fmt)
    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    started = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO data_export_jobs
                   (preset_key, preset_name, output_dir, fmt,
                    status, started_at, zipped, run_by, notes,
                    files_json)
               VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, '[]')""",
            (preset.key, preset.name, str(out_dir), fmt, started,
             int(bool(zip_output)),
             (run_by or "").strip() or None,
             (notes or "").strip() or None),
        )
        conn.commit()
        job_id = cur.lastrowid

    results: list[DatasetResult] = []
    rows_total = 0
    bytes_total = 0
    failures = 0
    for key in preset.datasets:
        try:
            spec = _ce.get_dataset(key)
        except _ce.ValidationError as e:
            failures += 1
            results.append(DatasetResult(
                dataset_key=key, label=key, file_path="",
                fmt=fmt, row_count=0, column_count=0,
                bytes_written=0, error=str(e)))
            continue
        ext = _ext_for(fmt)
        fname = f"{_safe_filename(key)}.{ext}"
        fpath = out_dir / fname
        try:
            res = _ce.export(spec, fpath, fmt=fmt)
            results.append(DatasetResult(
                dataset_key=spec.key, label=spec.label,
                file_path=str(fpath), fmt=fmt,
                row_count=res.row_count,
                column_count=res.column_count,
                bytes_written=res.bytes_written,
            ))
            rows_total += res.row_count
            bytes_total += res.bytes_written
        except Exception as e:
            logger.exception("dataset %s export failed", key)
            failures += 1
            results.append(DatasetResult(
                dataset_key=key, label=getattr(spec, "label", key),
                file_path="", fmt=fmt,
                row_count=0, column_count=0,
                bytes_written=0, error=str(e)))

    archive_path: str | None = None
    if zip_output:
        try:
            archive_path = _make_archive(out_dir, job_id, preset.key)
        except Exception as e:
            logger.exception("zip step failed")
            failures += 1
            # Track the failure on a synthetic row.
            results.append(DatasetResult(
                dataset_key="__archive__", label="(zip archive)",
                file_path="", fmt="zip",
                row_count=0, column_count=0, bytes_written=0,
                error=str(e)))

    # Write a manifest alongside the data files (always — useful for
    # human review even if the job partially failed).
    manifest = {
        "job_id": job_id, "preset_key": preset.key,
        "preset_name": preset.name, "started_at": started,
        "finished_at": _now_iso(),
        "fmt": fmt,
        "files": [
            {"dataset": r.dataset_key, "file": Path(r.file_path).name
                if r.file_path else None, "rows": r.row_count,
             "bytes": r.bytes_written,
             "error": r.error}
            for r in results
        ],
        "totals": {"rows": rows_total, "bytes": bytes_total},
    }
    try:
        (out_dir / "_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    except Exception:
        logger.exception("manifest write failed")

    finished = _now_iso()
    successes = sum(1 for r in results if not r.error)
    if failures == 0:
        status = "succeeded"
    elif successes == 0:
        status = "failed"
    else:
        status = "partial"

    with _connect() as conn:
        conn.execute(
            """UPDATE data_export_jobs
                  SET status=?, finished_at=?, files_total=?,
                      rows_total=?, bytes_total=?,
                      archive_path=?, files_json=?
                WHERE job_id=?""",
            (status, finished, len(results), rows_total,
             bytes_total, archive_path,
             json.dumps([_dataset_result_to_dict(r) for r in results],
                         default=str),
             job_id),
        )
        conn.commit()

    out = get_job(job_id)
    assert out is not None
    logger.info(
        "Data-export job #%d %s — preset=%s files=%d rows=%d (%d byte(s))",
        job_id, status, preset.key, len(results),
        rows_total, bytes_total)
    return out


def _dataset_result_to_dict(r: DatasetResult) -> dict[str, Any]:
    return {
        "dataset_key": r.dataset_key, "label": r.label,
        "file_path": r.file_path, "fmt": r.fmt,
        "row_count": r.row_count, "column_count": r.column_count,
        "bytes_written": r.bytes_written, "error": r.error,
    }


def _dict_to_dataset_result(d: dict[str, Any]) -> DatasetResult:
    return DatasetResult(
        dataset_key=str(d.get("dataset_key", "")),
        label=str(d.get("label", d.get("dataset_key", ""))),
        file_path=str(d.get("file_path") or ""),
        fmt=str(d.get("fmt") or ""),
        row_count=int(d.get("row_count") or 0),
        column_count=int(d.get("column_count") or 0),
        bytes_written=int(d.get("bytes_written") or 0),
        error=d.get("error") or None,
    )


def _make_archive(out_dir: Path, job_id: int, preset_key: str) -> str:
    """Zip every file in ``out_dir`` (the manifest is added too once
    written). The archive is written next to ``out_dir`` so it
    isn't recursively included in subsequent runs."""
    parent = out_dir.parent
    name = (f"export_{preset_key}_{job_id}_"
             f"{_dt.now().strftime('%Y%m%d_%H%M%S')}.zip")
    archive = parent / name
    with zipfile.ZipFile(archive, "w",
                         compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out_dir.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(out_dir))
    return str(archive)


# ── Job listing ───────────────────────────────────────────────────

def _row_job(r: sqlite3.Row) -> ExportJob:
    try:
        files = json.loads(r["files_json"] or "[]")
    except (TypeError, ValueError):
        files = []
    return ExportJob(
        job_id=r["job_id"], preset_key=r["preset_key"],
        preset_name=r["preset_name"],
        output_dir=r["output_dir"], fmt=r["fmt"],
        status=r["status"],
        started_at=r["started_at"],
        finished_at=r["finished_at"],
        files_total=r["files_total"], rows_total=r["rows_total"],
        bytes_total=r["bytes_total"],
        zipped=bool(r["zipped"]),
        archive_path=r["archive_path"],
        run_by=r["run_by"], notes=r["notes"],
        files=[_dict_to_dataset_result(d)
                for d in files if isinstance(d, dict)],
    )


def get_job(job_id: int) -> ExportJob | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM data_export_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
    return _row_job(r) if r else None


def list_jobs(*, preset_key: str | None = None,
              status: str | None = None,
              limit: int = 200) -> list[ExportJob]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if preset_key:
        clauses.append("preset_key = ?")
        args.append(preset_key)
    if status:
        if status not in JOB_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(JOB_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM data_export_jobs {where} "
            f"ORDER BY started_at DESC, job_id DESC LIMIT {int(limit)}",
            args).fetchall()
    return [_row_job(r) for r in rows]


def delete_job(job_id: int, *,
               remove_files: bool = False) -> bool:
    """Remove a job row. If ``remove_files`` is set, also wipe the
    on-disk output_dir and archive — use carefully."""
    init_db()
    j = get_job(job_id)
    if j is None:
        return False
    if remove_files:
        try:
            if j.output_dir and Path(j.output_dir).exists():
                shutil.rmtree(j.output_dir)
        except Exception:
            logger.exception("failed to remove %s", j.output_dir)
        if j.archive_path:
            try:
                Path(j.archive_path).unlink(missing_ok=True)
            except Exception:
                logger.exception("failed to remove %s", j.archive_path)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM data_export_jobs WHERE job_id = ?",
            (job_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted data-export job #%d (files=%s)",
                    job_id, remove_files)
        return True
    return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class ExportOverview:
    total_jobs: int
    succeeded: int
    partial: int
    failed: int
    total_files_written: int
    total_rows_written: int
    total_bytes_written: int
    last_job: ExportJob | None
    builtin_preset_count: int
    user_preset_count: int


def overview() -> ExportOverview:
    init_db()
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM data_export_jobs"
            ).fetchone()["n"]
        rows = conn.execute(
            """SELECT status, COUNT(*) AS n,
                       COALESCE(SUM(files_total), 0) AS f,
                       COALESCE(SUM(rows_total),  0) AS r,
                       COALESCE(SUM(bytes_total), 0) AS b
                FROM data_export_jobs
                GROUP BY status"""
        ).fetchall()
        by_status = {row["status"]: row for row in rows}
        last_row = conn.execute(
            "SELECT * FROM data_export_jobs "
            "ORDER BY started_at DESC, job_id DESC LIMIT 1").fetchone()
        user_n = conn.execute(
            "SELECT COUNT(*) AS n FROM data_export_presets"
            ).fetchone()["n"]
    files = rows_w = bytes_w = 0
    for r in by_status.values():
        files += r["f"]
        rows_w += r["r"]
        bytes_w += r["b"]
    return ExportOverview(
        total_jobs=n,
        succeeded=by_status.get("succeeded", {"n": 0})["n"]
            if "succeeded" in by_status else 0,
        partial=by_status.get("partial", {"n": 0})["n"]
            if "partial" in by_status else 0,
        failed=by_status.get("failed", {"n": 0})["n"]
            if "failed" in by_status else 0,
        total_files_written=files,
        total_rows_written=rows_w,
        total_bytes_written=bytes_w,
        last_job=_row_job(last_row) if last_row else None,
        builtin_preset_count=len(_BUILTIN_PRESETS_RAW),
        user_preset_count=user_n,
    )


# ── Dataset registry helpers ──────────────────────────────────────

def available_datasets() -> list[tuple[str, str]]:
    """(key, label) for every dataset known to ``custom_export``."""
    return [(d.key, d.label) for d in _ce.list_datasets()]
