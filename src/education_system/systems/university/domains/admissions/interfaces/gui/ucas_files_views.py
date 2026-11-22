"""UCAS files tab for the UCAS Management window: import the applicant file
downloaded from UCAS and write the decisions file to upload back. All rules
are in ``application/statutory/ucas_files``; this screen never contacts UCAS.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.application.statutory import ucas_files

logger = logging.getLogger(__name__)

TITLE = "UCAS files"


def _current_user(widget) -> dict | None:
    cu = getattr(getattr(widget, "auth", None), "current_user", None)
    if isinstance(cu, dict):
        return cu
    try:
        from education_system.systems.university.infrastructure.auth.core_utils.global_auth import (  # noqa: E501
            get_current_user,
        )
        return get_current_user()
    except Exception:
        logger.debug("Could not resolve the current user", exc_info=True)
        return None


def _table(master, columns, height=8) -> ttk.Treeview:
    frame = ttk.Frame(master)
    frame.pack(fill=tk.BOTH, expand=True)
    view = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height)
    for key, heading, width in columns:
        view.heading(key, text=heading)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    bar.pack(side=tk.LEFT, fill=tk.Y)
    return view


def _fill(view, rows, columns) -> dict:
    view.delete(*view.get_children())
    return {view.insert("", tk.END, values=["" if r.get(c[0]) is None else r.get(c[0])
                                            for c in columns]): r for r in rows}


class UcasFilesTab:
    BATCHES = (("batch_id", "Batch", 60), ("filename", "File", 260), ("file_format", "Format", 60),
               ("imported_by", "By", 100), ("imported_at", "When", 150),
               ("rows_total", "Rows", 55), ("created", "New", 55), ("updated", "Updated", 65),
               ("linked", "Sixth-form links", 110), ("error_count", "Refused", 65))
    RECORDS = (("personal_id", "Personal ID", 100), ("course_code", "Course", 80),
               ("campus_code", "Campus", 60), ("entry_year", "Entry", 55),
               ("choice_number", "Choice", 55), ("ucas_status", "UCAS status", 120),
               ("ucas_decision", "UCAS decision", 100), ("application_id", "Application", 85),
               ("link_id", "Link", 55), ("updated_at", "Updated", 150))
    DECISIONS = (("personal_id", "Personal ID", 100), ("course_code", "Course", 90),
                 ("entry_year", "Entry", 60), ("decision", "Decision", 160),
                 ("decision_code", "Code", 50), ("decision_date", "Date", 95),
                 ("application_id", "Application", 85), ("state", "State", 260))

    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb, padding=8)
        nb.add(self.frame, text="UCAS Files")
        self.batch_rows: dict = {}
        self._build()

    def _run(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (PermissionError, ValueError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.frame)
        except Exception as exc:
            logger.exception("UCAS files action failed")
            messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self.frame)
        return None

    def _build(self) -> None:
        intro = ("Applicants who are not our own sixth formers reach us as a file downloaded "
                 "from UCAS. Import it here (CSV with a header row, or XML); each row opens or "
                 "updates an admissions application under its UCAS Personal ID. Required "
                 "columns: Personal ID, Course code, Entry year.")
        ttk.Label(self.frame, text=intro, wraplength=1250, justify=tk.LEFT).pack(anchor="w")

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=6)
        ttk.Button(bar, text="Import applicant file…", command=self._import).pack(side=tk.LEFT)
        ttk.Button(bar, text="Show accepted column names",
                   command=self._show_fields).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)

        imports = ttk.LabelFrame(self.frame, text="Import batches (select one to see its rows)",
                                 padding=6)
        imports.pack(fill=tk.BOTH, expand=True)
        self.batch_view = _table(imports, self.BATCHES, height=6)
        self.batch_view.bind("<<TreeviewSelect>>", lambda _e: self._load_records())
        self.batch_view.bind("<Double-1>", lambda _e: self._show_errors())
        self.record_view = _table(imports, self.RECORDS, height=7)

        dec = ttk.LabelFrame(self.frame, text="Decisions not yet sent to UCAS", padding=6)
        dec.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        dbar = ttk.Frame(dec)
        dbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(dbar, text="Write decisions file…",
                   command=self._export).pack(side=tk.LEFT)
        self.dec_status = tk.StringVar()
        ttk.Label(dbar, textvariable=self.dec_status).pack(side=tk.LEFT, padx=8)
        self.dec_view = _table(dec, self.DECISIONS, height=6)
        self.refresh(quiet=True)

    # ---------------------------------------------------------------- data
    def refresh(self, quiet: bool = False) -> None:
        user = _current_user(self.root)
        try:
            rows = ucas_files.batches(user)
            pending = ucas_files.pending_decisions(user)
        except PermissionError as exc:
            if not quiet:
                messagebox.showerror(TITLE, str(exc), parent=self.frame)
            self.dec_status.set(str(exc))
            return
        except Exception as exc:
            logger.exception("UCAS files refresh failed")
            if not quiet:
                messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self.frame)
            return
        for row in rows:
            try:
                row["error_count"] = len(json.loads(row.get("errors_json") or "[]"))
            except ValueError:
                row["error_count"] = "?"
        self.batch_rows = _fill(self.batch_view, rows, self.BATCHES)
        decisions = ([{**d, "state": "ready to send"} for d in pending["ready"]]
                     + [{**d, "state": "needs a C or U offer type before it can go"}
                        for d in pending["unclear"]])
        _fill(self.dec_view, decisions, self.DECISIONS)
        self.dec_status.set(f"{len(pending['ready'])} ready, {len(pending['unclear'])} "
                            "needing an offer type (conditional / unconditional).")

    def _selected_batch(self) -> dict | None:
        sel = self.batch_view.selection()
        return self.batch_rows.get(sel[0]) if sel else None

    def _load_records(self) -> None:
        batch = self._selected_batch()
        if not batch:
            return
        rows = self._run(ucas_files.records, _current_user(self.root), batch["batch_id"])
        if rows is not None:
            _fill(self.record_view, rows, self.RECORDS)

    def _show_errors(self) -> None:
        batch = self._selected_batch()
        if not batch:
            return
        try:
            errors = json.loads(batch.get("errors_json") or "[]")
        except ValueError:
            errors = []
        if not errors:
            messagebox.showinfo(TITLE, "No rows were refused in this batch.", parent=self.frame)
            return
        lines = [f"Line {e.get('line')}: {e.get('error')}" for e in errors[:30]]
        if len(errors) > 30:
            lines.append(f"... and {len(errors) - 30} more")
        messagebox.showinfo(TITLE, "\n".join(lines), parent=self.frame)

    # ------------------------------------------------------------- actions
    def _show_fields(self) -> None:
        lines = [f"{field}{' (required)' if field in ucas_files.REQUIRED else ''}: "
                 f"{', '.join(names)}" for field, names in ucas_files.FIELDS.items()]
        messagebox.showinfo(TITLE, "Header names accepted (case, spaces and punctuation "
                            "ignored):\n\n" + "\n".join(lines), parent=self.frame)

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.frame, title="UCAS applicant file",
            filetypes=[("UCAS files", "*.csv *.xml"), ("CSV", "*.csv"), ("XML", "*.xml")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig", newline="") as src:
                text = src.read()
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(TITLE, f"Could not read the file: {exc}", parent=self.frame)
            return
        fmt = "xml" if path.lower().endswith(".xml") or text.lstrip().startswith("<") else "csv"
        result = self._run(ucas_files.import_file, _current_user(self.root), text,
                           path.rsplit("/", 1)[-1], fmt)
        if result is None:
            return
        lines = [f"Batch {result['batch_id']}: {result['rows']} row(s) read.",
                 f"{result['created']} new application(s), {result['updated']} updated, "
                 f"{result['linked']} linked to our sixth formers' UCAS choices, "
                 f"{len(result['errors'])} refused."]
        lines += [f"Line {e['line']}: {e['error']}" for e in result["errors"][:15]]
        messagebox.showinfo(TITLE, "\n".join(lines), parent=self.frame)
        self.refresh()

    def _export(self) -> None:
        result = self._run(ucas_files.export_decisions, _current_user(self.root))
        if result is None:
            return
        unclear = len(result["unclear"])
        if not result["path"]:
            messagebox.showinfo(TITLE, "No decisions ready to send."
                                + (f" {unclear} need an offer type first." if unclear else ""),
                                parent=self.frame)
            return
        messagebox.showinfo(TITLE, f"{result['count']} decision(s) written to batch "
                            f"{result['batch_id']}. Upload this file to UCAS:\n{result['path']}"
                            + (f"\n\n{unclear} decision(s) still need an offer type."
                               if unclear else ""), parent=self.frame)
        self.refresh()
