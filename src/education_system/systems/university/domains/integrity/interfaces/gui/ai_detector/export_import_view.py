"""Data management: exports, imports and housekeeping.

* **Exports** (the readings the person may see; files written owner-only):
  readings as JSON or CSV, a report (statistics and readings) as JSON or
  HTML, per-module counts by level as CSV, and the audit chain (integrity
  officers).
* **Imports** — readings from a CSV or JSON file whose rows give
  ``student_id``, ``module_code``, ``text`` and optionally
  ``assignment_id`` and ``title`` (real ids; a row naming an unknown
  student, module or assignment is reported and skipped); integrity
  settings (``ai_*`` keys) and students' recorded characteristics for the
  bias report (integrity officers).
* **Housekeeping** (integrity officers) — archive readings before a date
  to an owner-only file and remove their text, let SQLite re-plan its
  queries, and remove readings that repeat the same text for the same
  student (only ones nobody has reviewed).
"""

import csv
import hashlib
import json
import logging
import os
import threading
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _private(path):
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.debug("Could not restrict %s", path, exc_info=True)


def create_export_section(self, parent):
    box = ttk.LabelFrame(parent, text="Data", padding=10)
    box.pack(fill="x", padx=15, pady=(0, 10))
    row = ttk.Frame(box)
    row.pack(fill="x")
    ttk.Button(row, text="📤 Export readings", command=self.export_results).pack(side="left",
                                                                              padx=(0, 6))
    ttk.Button(row, text="📥 Import readings", command=self.import_data).pack(side="left",
                                                                            padx=(0, 6))
    ttk.Button(row, text="🗄 Database status", command=self.show_db_status).pack(side="left")


def create_data_export_import_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Data management", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                      pady=15)
    exports = ttk.LabelFrame(frame, text="Export", padding=10)
    exports.pack(fill="x", padx=15, pady=6)
    for label, command in (("Readings", self.export_results), ("Report", self.export_detailed_report),
                           ("Counts by module", self.export_analytics_data)):
        ttk.Button(exports, text=label, command=command).pack(side="left", padx=(0, 6))
    audit_btn = ttk.Button(exports, text="Audit chain", command=self.export_audit_log)
    audit_btn.pack(side="left")
    imports = ttk.LabelFrame(frame, text="Import", padding=10)
    imports.pack(fill="x", padx=15, pady=6)
    ttk.Button(imports, text="Readings (CSV / JSON)", command=self.import_submissions).pack(
        side="left", padx=(0, 6))
    student_btn = ttk.Button(imports, text="Students' characteristics",
                             command=self.import_student_data)
    student_btn.pack(side="left", padx=(0, 6))
    settings_btn = ttk.Button(imports, text="Settings", command=self.import_settings)
    settings_btn.pack(side="left")
    cleanup = ttk.LabelFrame(frame, text="Housekeeping", padding=10)
    cleanup.pack(fill="x", padx=15, pady=6)
    archive_btn = ttk.Button(cleanup, text="Archive old readings…", command=self.archive_old_data)
    archive_btn.pack(side="left", padx=(0, 6))
    optimise_btn = ttk.Button(cleanup, text="Optimise queries", command=self.optimize_database)
    optimise_btn.pack(side="left", padx=(0, 6))
    dup_btn = ttk.Button(cleanup, text="Remove repeated readings", command=self.clean_duplicates)
    dup_btn.pack(side="left")
    common.officer_only(self, audit_btn, student_btn, settings_btn, archive_btn, optimise_btn,
                        dup_btn)


# ── exports ─────────────────────────────────────────────────────────────


def _readings(self):
    data = common.call(self, self.detector.get_submission_history, limit=100000)
    if data is None:
        return None
    rows = []
    for s in data.get("submissions", []):
        rows.append({k: v for k, v in s.items() if k not in ("text_preview",)})
    return rows


def export_results(self):
    rows = _readings(self)
    if rows is None:
        return
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                        filetypes=[("JSON", "*.json"), ("CSV", "*.csv")])
    if not path:
        return
    if path.lower().endswith(".csv"):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            if rows:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"exported_at": datetime.now().isoformat(), "readings": rows,
                       "notice": common.NOTICE}, fh, indent=2, default=str)
    _private(path)
    messagebox.showinfo(common.TITLE, f"{len(rows)} reading(s) saved to {path}", parent=self.root)


def export_detailed_report(self):
    report = self.generate_comprehensive_report()
    if report.get("error"):
        messagebox.showerror(common.TITLE, report["error"], parent=self.root)
        return
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".html",
                                        filetypes=[("HTML", "*.html"), ("JSON", "*.json")])
    if not path:
        return
    if path.lower().endswith(".json"):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
    else:
        import html
        rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(s.get(k, '')))}</td>" for k in
                             ("result_id", "student_id", "course_code", "title", "level",
                              "ai_score", "analysis_date")) + "</tr>"
            for s in report.get("submission_history", {}).get("submissions", []))
        stats = "".join(f"<li>{html.escape(str(k))}: {html.escape(str(v))}</li>"
                        for k, v in report.get("statistics", {}).items())
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"<!doctype html><meta charset='utf-8'><title>AI-writing readings</title>"
                     f"<h1>AI-writing readings</h1><p><b>{html.escape(common.NOTICE)}</b></p>"
                     f"<p>Generated {html.escape(report['report_date'])}</p><ul>{stats}</ul>"
                     "<table border=1 cellpadding=4><tr><th>Reading</th><th>Student</th>"
                     "<th>Module</th><th>Title</th><th>Level</th><th>Strength</th><th>Taken</th>"
                     f"</tr>{rows}</table>")
    _private(path)
    messagebox.showinfo(common.TITLE, f"Report saved to {path}", parent=self.root)


def export_analytics_data(self):
    rows = _readings(self)
    if rows is None:
        return
    counts: dict = {}
    for r in rows:
        key = (r.get("course_code") or "—", r.get("level") or "taken before indicators")
        counts[key] = counts.get(key, 0) + 1
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                        filetypes=[("CSV", "*.csv")])
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["module", "level", "readings"])
        for (module, level), n in sorted(counts.items()):
            writer.writerow([module, level, n])
    _private(path)
    messagebox.showinfo(common.TITLE, f"Saved to {path}", parent=self.root)


def export_audit_log(self):
    """The audit chain (integrity officers)."""
    if common.call(self, self.detector.require_officer) is None:
        return
    blocks = self.get_audit_log_data()
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                        filetypes=[("JSON", "*.json"), ("CSV", "*.csv")])
    if not path:
        return
    if path.lower().endswith(".csv"):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["block", "when", "event", "who", "detail", "previous_hash", "hash"])
            for b in blocks:
                writer.writerow([b["index"], b["timestamp"], b["event"], b["actor"],
                                 json.dumps(b["payload"], default=str), b["previous_hash"],
                                 b["hash"]])
    else:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"exported_at": datetime.now().isoformat(),
                       "verified": common.call(self, self.detector.blockchain_audit.verify_chain),
                       "blocks": blocks}, fh, indent=2, default=str)
    _private(path)
    messagebox.showinfo(common.TITLE, f"{len(blocks)} block(s) saved to {path}", parent=self.root)


# ── imports ─────────────────────────────────────────────────────────────


def import_data(self):
    self.import_submissions()


def import_submissions(self):
    """Readings from CSV / JSON rows with real ids."""
    path = filedialog.askopenfilename(parent=self.root, filetypes=[("CSV or JSON",
                                                                    "*.csv *.json")])
    if not path:
        return
    try:
        if path.lower().endswith(".json"):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            records = data if isinstance(data, list) else (
                data.get("readings") or data.get("submissions") or [data])
        else:
            with open(path, newline="", encoding="utf-8") as fh:
                records = [self._format_csv_record(r) for r in csv.DictReader(fh)]
    except (OSError, ValueError) as exc:
        messagebox.showerror(common.TITLE, f"Could not read the file: {exc}", parent=self.root)
        return
    stats = {"total_records": len(records), "successful_imports": 0, "failed_imports": 0,
             "duplicate_skips": 0, "errors": []}
    self.update_status(f"Importing {len(records)} row(s)…")
    self.show_progress(True)

    def run():
        for record in records:
            if self._process_import_record(record, stats):
                stats["successful_imports"] += 1
            else:
                stats["failed_imports"] += 1
        ui(self.root, _import_done, self, stats)

    start_thread(self.root, run)


def _import_done(self, stats):
    self.show_progress(False)
    stats["errors"] = stats["errors"][:50]
    common.text_window(self, "Import", stats, 640, 460)
    self.update_status(f"Imported {stats['successful_imports']} reading(s)")


def _process_import_record(self, record, stats):
    """One row → one reading (real ids required)."""
    text = str(record.get("text") or record.get("content") or "").strip()
    student = record.get("student_id")
    module = record.get("module_code") or record.get("course_code")
    label = record.get("title") or f"row {stats['successful_imports'] + stats['failed_imports'] + 1}"
    if not text or not student or not module:
        stats["errors"].append(f"{label}: needs student_id, module_code and text")
        return False
    seen = self.__dict__.setdefault("_imported_hashes", set())
    digest = hashlib.sha256(f"{student}|{text}".encode("utf-8")).hexdigest()
    if digest in seen:
        stats["duplicate_skips"] += 1
        return False
    seen.add(digest)
    try:
        result = self.detector.analyze_text(text=text, title=record.get("title"),
                                            student_id=str(student), course_code=str(module),
                                            assignment_id=record.get("assignment_id") or None)
    except Exception as exc:
        stats["errors"].append(f"{label}: {exc}")
        return False
    if result.get("skipped"):
        stats["errors"].append(f"{label}: {result.get('reason')}")
        return False
    return True


def _format_csv_record(self, csv_record):
    """A CSV row with the usual column names mapped to the import fields."""
    names = {"student_id": ("student_id", "student", "student_number"),
             "module_code": ("module_code", "module", "course_code", "course"),
             "assignment_id": ("assignment_id", "assignment"),
             "title": ("title", "name", "file"),
             "text": ("text", "content", "submission", "essay")}
    found = {}
    lower = {str(k).strip().lower(): v for k, v in csv_record.items()}
    for field, options in names.items():
        for option in options:
            if lower.get(option):
                found[field] = lower[option]
                break
    return found


def import_student_data(self):
    """Students' recorded characteristics for the bias report (officers):
    CSV with ``student_id`` and any of the columns the demographics table
    holds; only existing students are updated."""
    if common.call(self, self.detector.require_officer) is None:
        return
    path = filedialog.askopenfilename(parent=self.root, filetypes=[("CSV", "*.csv")])
    if not path:
        return
    conn = common._connect()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(student_demographics)")]
        if "student_id" not in cols:
            raise ValueError("There is no characteristics table to import into")
        allowed = [c for c in cols if c != "student_id"]
        done, skipped = 0, []
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                sid = str(row.get("student_id") or "").strip()
                if not sid or not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                               (sid,)).fetchone():
                    skipped.append(sid or "(blank)")
                    continue
                values = {c: row[c] for c in allowed if row.get(c) not in (None, "")}
                if not values:
                    continue
                names = ", ".join(f'"{c}"' for c in values)
                marks = ", ".join("?" * len(values))
                updates = ", ".join(f'"{c}" = excluded."{c}"' for c in values)
                conn.execute(f'INSERT INTO student_demographics (student_id, {names}) VALUES '  # nosec B608
                             f'(?, {marks}) ON CONFLICT(student_id) DO UPDATE SET {updates}',
                             (sid, *values.values()))
                done += 1
        conn.commit()
    except (OSError, ValueError, Exception) as exc:
        conn.rollback()
        messagebox.showerror(common.TITLE, f"Not imported: {exc}", parent=self.root)
        return
    finally:
        conn.close()
    messagebox.showinfo(common.TITLE, f"{done} student(s) updated; {len(skipped)} row(s) "
                                      "skipped (unknown student).", parent=self.root)


def import_settings(self):
    """Integrity settings (``ai_*`` keys) from a JSON file (officers)."""
    path = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON", "*.json")])
    if not path:
        return
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    try:
        with open(path, encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError) as exc:
        messagebox.showerror(common.TITLE, f"Could not read the file: {exc}", parent=self.root)
        return
    conn = common._connect()
    try:
        who = integrity_access.from_user(conn, self.user)
        applied = []
        for key, value in (settings or {}).items():
            if str(key).startswith("ai_") and key in integrity_access.SETTINGS:
                integrity_access.set_setting(conn, who, key, value)
                applied.append(key)
        conn.commit()
    except (PermissionError, ValueError) as exc:
        conn.rollback()
        messagebox.showerror(common.TITLE, str(exc), parent=self.root)
        return
    finally:
        conn.close()
    messagebox.showinfo(common.TITLE, "Applied: " + (", ".join(applied) or "nothing (only ai_* "
                                                                          "settings are read)"),
                        parent=self.root)


# ── housekeeping ────────────────────────────────────────────────────────


def archive_old_data(self):
    """Save readings taken before a date to an owner-only archive file,
    then remove their text (not evidence in an open case)."""
    if common.call(self, self.detector.require_officer) is None:
        return
    cutoff = simpledialog.askstring(common.TITLE, "Archive readings taken before (YYYY-MM-DD):",
                                    parent=self.root)
    if not cutoff:
        return
    try:
        datetime.strptime(cutoff.strip(), "%Y-%m-%d")
    except ValueError:
        messagebox.showerror(common.TITLE, "Give the date as YYYY-MM-DD.", parent=self.root)
        return
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                        initialfile=f"ai_readings_before_{cutoff.strip()}.json")
    if not path:
        return
    count = common.call(self, _archive, self, cutoff.strip(), path)
    if count is not None:
        messagebox.showinfo(common.TITLE, f"{count[0]} reading(s) archived to {path}; text "
                                          f"removed from {count[1]}.", parent=self.root)


def _archive(self, cutoff, path):
    from education_system.systems.university.application.integrity import ai as integrity_ai
    conn = common._connect()
    try:
        cur = conn.execute("SELECT s.*, r.id AS result_id, r.ai_score, r.level, r.method, "
                           "r.detailed_results FROM ai_detector_submissions s LEFT JOIN "
                           "ai_detector_results r ON r.submission_id = s.id WHERE "
                           "s.submission_date < ? AND COALESCE(s.purged, 0) = 0", (cutoff,))
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"archived_at": datetime.now().isoformat(), "before": cutoff,
                       "readings": rows}, fh, default=str)
        _private(path)
        removed = integrity_ai.purge(conn, cutoff)
        conn.commit()
        return len(rows), removed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def optimize_database(self):
    """Let SQLite refresh its query statistics (no locking rebuild)."""
    if common.call(self, self.detector.require_officer) is None:
        return
    conn = common._connect()
    try:
        conn.execute("PRAGMA optimize")
        conn.execute("ANALYZE ai_detector_submissions")
        conn.execute("ANALYZE ai_detector_results")
        conn.commit()
    finally:
        conn.close()
    self.update_status("Query statistics refreshed")
    messagebox.showinfo(common.TITLE, "Query statistics refreshed.", parent=self.root)


def _duplicates(conn):
    """Older readings repeating the same text for the same student, nobody
    has reviewed and no alert has been acted on."""
    rows = conn.execute(
        "SELECT s.id, r.id, s.student_id, s.submission_text FROM ai_detector_submissions s "
        "JOIN ai_detector_results r ON r.submission_id = s.id WHERE COALESCE(s.purged, 0) = 0 "
        "AND NOT EXISTS (SELECT 1 FROM integrity_ai_reviews v WHERE v.ai_result_id = r.id) "
        "ORDER BY s.id DESC").fetchall()
    seen, repeats = set(), []
    for sub_id, result_id, student, text in rows:
        key = (student, hashlib.sha256(str(text or "").encode("utf-8")).hexdigest())
        if key in seen:
            repeats.append((sub_id, result_id))
        else:
            seen.add(key)
    return repeats


def clean_duplicates(self):
    if common.call(self, self.detector.require_officer) is None:
        return
    conn = common._connect()
    try:
        repeats = _duplicates(conn)
        if not repeats:
            messagebox.showinfo(common.TITLE, "No repeated readings.", parent=self.root)
            return
        if not messagebox.askyesno(common.TITLE, f"Remove {len(repeats)} older reading(s) that "
                                                 "repeat the same text for the same student? "
                                                 "Reviewed readings are kept.", parent=self.root):
            return
        for sub_id, result_id in repeats:
            conn.execute("DELETE FROM ai_detector_alerts WHERE ai_result_id = ? AND status = "
                         "'pending'", (result_id,))
            conn.execute("DELETE FROM ai_result_comments WHERE ai_result_id = ?", (result_id,))
            conn.execute("DELETE FROM ai_detector_results WHERE id = ?", (result_id,))
            if not conn.execute("SELECT 1 FROM ai_detector_results WHERE submission_id = ?",
                                (sub_id,)).fetchone():
                for table in ("ai_detector_metadata", "advanced_detection_results",
                              "ai_analysis_history"):
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?",
                                    (table,)).fetchone():
                        conn.execute(f'DELETE FROM "{table}" WHERE submission_id = ?',  # nosec B608
                                     (sub_id,))
                conn.execute("DELETE FROM ai_detector_submissions WHERE id = ?", (sub_id,))
        chain = getattr(self.detector, "blockchain_audit", None)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        messagebox.showerror(common.TITLE, f"Not removed: {exc}", parent=self.root)
        return
    finally:
        conn.close()
    if chain is not None:
        common.call(self, chain.record_event, "repeated_readings_removed",
                    {"readings": [r for _s, r in repeats]}, quiet=True)
    messagebox.showinfo(common.TITLE, f"Removed {len(repeats)} repeated reading(s).",
                        parent=self.root)
