"""Batch jobs: every import or bulk run is a job with per-row results, so it
can be reviewed and undone - just that job, never a whole-database restore.

Undo, per kind:

* **students** - students the job created are withdrawn (through the
  registration lifecycle, records kept); fields it changed are put back and
  course transfers reversed, each with the undo reason.
* **marks** - marks it entered are removed, marks it changed get their old
  value back, and the module result is recalculated (refused where a board
  has since confirmed the result).
* **staff** - accounts it created are deactivated and their sign-in
  switched off.
* **actions** - not undoable here; apply the opposite bulk action. The
  exception is a module-enrolment import (mode ``enrolments``,
  ``batch_enrolments``): enrolments it made are withdrawn and withdrawals
  it made are re-enrolled.

Bookkeeping runs on its own connection (``db_path``) and commits as it
goes, so a crash mid-file still leaves an accurate record of what happened.
"""

from __future__ import annotations

import json
from contextlib import closing

from education_system.systems.university.infrastructure.database.schemas import (
    batch_jobs_schema as schema,
)


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(db_path, row_factory=False)
    schema.apply_to_connection(conn)
    return conn


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


class Job:
    """Records one run. Use as a context manager."""

    def __init__(self, kind, actor, *, source=None, mode=None, reason=None, db_path=None):
        self.conn = _connect(db_path)
        self.id = int(self.conn.execute(
            "INSERT INTO batch_jobs (kind, source, mode, actor, reason) VALUES (?, ?, ?, ?, ?)",
            (kind, source, mode, actor, reason)).lastrowid)
        self.conn.commit()

    def row(self, row_no, ref, outcome, message=None, undo=None):
        self.conn.execute("INSERT INTO batch_job_rows (job_id, row_no, ref, outcome, message, "
                          "undo_json) VALUES (?, ?, ?, ?, ?, ?)",
                          (self.id, row_no, ref, outcome, message,
                           json.dumps(undo) if undo else None))
        self.conn.commit()

    def finish(self):
        counts = dict(self.conn.execute(
            "SELECT outcome, COUNT(*) FROM batch_job_rows WHERE job_id = ? GROUP BY outcome",
            (self.id,)).fetchall())
        self.conn.execute(
            "UPDATE batch_jobs SET status = 'done', finished_at = datetime('now'), total = ?, "
            "succeeded = ?, skipped = ?, failed = ? WHERE id = ?",
            (sum(counts.values()), counts.get("created", 0) + counts.get("updated", 0),
             counts.get("skipped", 0) + counts.get("unchanged", 0), counts.get("failed", 0),
             self.id))
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.finish()
        finally:
            self.conn.close()


def jobs(conn, kind=None, limit=200) -> list[dict]:
    schema.apply_to_connection(conn)
    sql, args = "SELECT * FROM batch_jobs", []
    if kind:
        sql += " WHERE kind = ?"
        args.append(kind)
    return _dicts(conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, int(limit))))


def job(conn, job_id) -> dict:
    schema.apply_to_connection(conn)
    rows = _dicts(conn.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,)))
    if not rows:
        raise ValueError("No such job")
    out = rows[0]
    out["rows"] = _dicts(conn.execute("SELECT row_no, ref, outcome, message FROM batch_job_rows "
                                      "WHERE job_id = ? ORDER BY row_no", (job_id,)))
    return out


def error_report(conn, job_id, path) -> int:
    """Write the job's skipped and failed rows to a CSV."""
    import csv
    rows = [r for r in job(conn, job_id)["rows"] if r["outcome"] in ("failed", "skipped")]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_no", "ref", "outcome", "message"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ── undo ────────────────────────────────────────────────────────────────


def _undoable(conn, job_id, viewer):
    j = job(conn, job_id)
    if j["status"] != "done":
        raise ValueError(f"This job is {j['status']}")
    if j["kind"] == "actions" and j["mode"] != "enrolments":
        raise ValueError("Bulk actions cannot be undone here; apply the opposite action")
    needed = {"students": viewer.can_withdraw and viewer.can_update, "marks": viewer.can_mark,
              "staff": viewer.can_manage_users, "actions": viewer.can_update}[j["kind"]]
    if not needed:
        raise ValueError("You do not have permission to undo this job")
    return j


def undo(job_id, viewer, reason, *, db_path=None, auth_db_path=None) -> dict:
    """Reverse one job's rows. Returns ``{"undone", "failed": [(row, why)]}``."""
    if not (reason or "").strip():
        raise ValueError("Give a reason for undoing the job")
    with closing(_connect(db_path)) as conn:
        j = _undoable(conn, job_id, viewer)
        rows = conn.execute("SELECT id, row_no, ref, undo_json FROM batch_job_rows WHERE "
                            "job_id = ? AND undo_json IS NOT NULL ORDER BY row_no DESC",
                            (job_id,)).fetchall()
    from education_system.systems.university.application.batch import (
        enrolments as batch_enrolments,
        imports as batch_imports,
    )
    handler = {"students": batch_imports.undo_student_row, "marks": batch_imports.undo_mark_row,
               "staff": batch_imports.undo_staff_row,
               "actions": batch_enrolments.undo_enrolment_row}[j["kind"]]
    done, failed = 0, []
    for row_id, row_no, ref, data in rows:
        try:
            handler(json.loads(data), ref, viewer, reason.strip(), db_path=db_path,
                    auth_db_path=auth_db_path)
            done += 1
            outcome = ("undone", f"undone: {reason.strip()}", row_id)
        except Exception as exc:
            failed.append((row_no, str(exc)))
            outcome = None
        if outcome:
            with closing(_connect(db_path)) as conn:
                conn.execute("UPDATE batch_job_rows SET outcome = ?, message = ?, undo_json = NULL "
                             "WHERE id = ?", outcome)
                conn.commit()
    with closing(_connect(db_path)) as conn:
        if not failed:
            conn.execute("UPDATE batch_jobs SET status = 'undone', undone_by = ?, undone_at = "
                         "datetime('now'), undo_reason = ? WHERE id = ?",
                         (viewer.username, reason.strip(), job_id))
        conn.commit()
    return {"undone": done, "failed": failed}


# ── watched folders ─────────────────────────────────────────────────────


def add_watch(conn, viewer, kind, folder, reason, mode="create", mapping_id=None) -> int:
    from pathlib import Path
    schema.apply_to_connection(conn)
    if kind not in ("students", "marks"):
        raise ValueError("Watch folders import students or marks")
    if not (viewer.can_mark if kind == "marks" else viewer.can_update):
        raise ValueError("You do not have permission to schedule this import")
    if not Path(folder).is_dir():
        raise ValueError(f"{folder} is not a folder")
    if not (reason or "").strip():
        raise ValueError("Give the reason recorded on each imported change")
    return int(conn.execute(
        "INSERT INTO batch_watch_folders (owner, kind, folder, mode, mapping_id, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (viewer.username, kind, str(folder), mode, mapping_id, reason.strip())).lastrowid)


def watches(conn, viewer) -> list[dict]:
    schema.apply_to_connection(conn)
    if viewer.role in ("admin", "administrator", "superadmin"):
        return _dicts(conn.execute("SELECT * FROM batch_watch_folders ORDER BY id"))
    return _dicts(conn.execute("SELECT * FROM batch_watch_folders WHERE owner = ? ORDER BY id",
                               (viewer.username,)))


def _own_watch(conn, viewer, watch_id):
    row = conn.execute("SELECT owner FROM batch_watch_folders WHERE id = ?",
                       (watch_id,)).fetchone()
    if not row:
        raise ValueError("No such watched folder")
    if row[0] != viewer.username and viewer.role not in ("admin", "administrator", "superadmin"):
        raise ValueError("Only its owner (or an admin) can change this")


def set_watch_active(conn, viewer, watch_id, active):
    schema.apply_to_connection(conn)
    _own_watch(conn, viewer, watch_id)
    conn.execute("UPDATE batch_watch_folders SET active = ? WHERE id = ?",
                 (int(bool(active)), watch_id))


def remove_watch(conn, viewer, watch_id):
    schema.apply_to_connection(conn)
    _own_watch(conn, viewer, watch_id)
    conn.execute("DELETE FROM batch_watch_folders WHERE id = ?", (watch_id,))
