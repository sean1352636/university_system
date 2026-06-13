"""Tkinter views for KS5 Destinations.

Single window with three tabs:

* **Records** — filterable table (checkpoint, destination type,
  student-id). Create / edit / delete a destination record. Double-
  click a row to edit. The "Missing" tab focuses on students with no
  capture at a chosen checkpoint.
* **Missing** — students who don't have a record at a chosen
  checkpoint (default LEAVING). Pick one and a save dialog opens
  pre-filled for that student.
* **Summary** — counts of records, students captured / missing at
  LEAVING, positive sustained-destination counts at LEAVING / +6 /
  +12, breakdowns by checkpoint, type and study level.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.sixthform_system.modules.domain.progression.destinations import (
    destinations as data,
)
from education_system.sixthform_system.modules.domain.progression.destinations.destinations import (
    CHECKPOINTS,
    CHECKPOINT_LABELS,
    CONFIRMED_VIA,
    DEFAULT_CHECKPOINT,
    DEFAULT_DESTINATION_TYPE,
    DESTINATION_TYPES,
    DestinationRecord,
    POSITIVE_TYPES,
    SALARY_BANDS,
    STUDY_LEVELS,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_TYPE_TAGS: dict[str, tuple[str, str]] = {
    "Higher Education":    ("#e6f0ff", "#1a3f8c"),
    "Further Education":   ("#e6f0ff", "#1a3f8c"),
    "Apprenticeship":      ("#e6f7e6", "#0d6b2a"),
    "Employment":          ("#e6f7e6", "#0d6b2a"),
    "Training":            ("#e6f7e6", "#0d6b2a"),
    "Gap Year":            ("#fff7e6", "#7a5800"),
    "NEET":                ("#ffd1d1", "#8c0d0d"),
    "Unknown":             ("#eeeeee", "#666666"),
}


def open_directory(parent=None) -> None:
    try:
        data.init_db()
    except Exception:
        logger.exception("Destinations init_db failed")
        messagebox.showerror(
            "Destinations",
            "Could not initialise the database. Check logs.")
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"KS5 Destinations — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    records_tab = RecordsTab(nb, win)
    MissingTab(nb, win, records_tab)
    SummaryTab(nb, records_tab)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ─────────────────────────────────────────────────────────────────
# Records tab
# ─────────────────────────────────────────────────────────────────

class RecordsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Records")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Checkpoint:").pack(side="left")
        self.f_cp = ttk.Combobox(
            bar, values=("",) + CHECKPOINTS,
            state="readonly", width=10)
        self.f_cp.current(0)
        self.f_cp.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + DESTINATION_TYPES,
            state="readonly", width=20)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New record",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "checkpoint", "type",
                "target", "level", "salary", "confirmed")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 90, "name": 160,
                   "checkpoint": 90, "type": 150, "target": 280,
                   "level": 90, "salary": 110, "confirmed": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c == "id" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for dtype, (bg, fg) in _TYPE_TAGS.items():
            self.tree.tag_configure(dtype, background=bg, foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit", self._edit),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_cp.current(0)
        self.f_type.current(0)
        self.f_student.delete(0, "end")
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_cp.get():
            f["checkpoint"] = self.f_cp.get()
        if self.f_type.get():
            f["destination_type"] = self.f_type.get()
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_records_with_detail(**self._filters())
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e))
            return
        except Exception as e:
            logger.exception("Records refresh failed")
            messagebox.showerror("Destinations",
                                   f"Could not load records: {e}")
            return
        for r in rows:
            d = r.record
            self.tree.insert(
                "", "end", iid=str(d.record_id),
                values=(d.record_id, d.student_id, r.student_name,
                          d.checkpoint, d.destination_type,
                          d.display_target(),
                          d.study_level or "—",
                          d.salary_band or "—",
                          d.confirmed_date or "—"),
                tags=(d.destination_type,),
            )
        self.count.configure(text=f"{len(rows)} record(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Destinations",
                                 "Select a record first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        if not student_data.list_students():
            messagebox.showinfo("Destinations",
                                 "Add at least one student first.")
            return
        RecordDialog(self.root, on_save=lambda _r: self.refresh())

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        rec = data.get_record(rid)
        if rec is None:
            self.refresh()
            return
        RecordDialog(self.root, record=rec,
                       on_save=lambda _r: self.refresh())

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno(
                "Destinations", f"Delete record #{rid}?"):
            return
        try:
            data.delete_record(rid)
        except Exception as e:
            logger.exception("delete_record failed")
            messagebox.showerror("Destinations",
                                   f"Delete failed: {e}")
            return
        self.refresh()

    def open_for(self, student_id: str, checkpoint: str) -> None:
        """Open the save dialog pre-filled for a (student, cp)."""
        rec = data.get_record_for(student_id, checkpoint)
        if rec is not None:
            RecordDialog(self.root, record=rec,
                           on_save=lambda _r: self.refresh())
        else:
            RecordDialog(self.root,
                           preset_student=student_id,
                           preset_checkpoint=checkpoint,
                           on_save=lambda _r: self.refresh())


# ─────────────────────────────────────────────────────────────────
# Record dialog
# ─────────────────────────────────────────────────────────────────

class RecordDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 record: DestinationRecord | None = None,
                 preset_student: str | None = None,
                 preset_checkpoint: str | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.record = record
        self.on_save = on_save
        self.title("Edit Destination" if record else "New Destination")
        self.geometry("760x800")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Student:").grid(
            row=row, column=0, sticky="w", pady=4)
        student_opts = _student_options()
        if record:
            ttk.Label(frm,
                       text=f"{record.student_id}").grid(
                row=row, column=1, sticky="w", pady=4)
            self._student_locked = record.student_id
        else:
            self._student_map = {lbl: sid for sid, lbl in student_opts}
            self.cb_student = ttk.Combobox(
                frm, values=[lbl for _sid, lbl in student_opts],
                state="readonly")
            if preset_student:
                current = next(
                    (lbl for sid, lbl in student_opts
                     if sid == preset_student), "")
                self.cb_student.set(current)
            self.cb_student.grid(row=row, column=1, sticky="ew", pady=4)
            self._student_locked = None
        row += 1

        ttk.Label(frm, text="Checkpoint:").grid(
            row=row, column=0, sticky="w", pady=4)
        if record:
            ttk.Label(frm,
                       text=f"{record.checkpoint}  "
                            f"({CHECKPOINT_LABELS[record.checkpoint]})").grid(
                row=row, column=1, sticky="w", pady=4)
            self._checkpoint_locked = record.checkpoint
        else:
            self.cb_cp = ttk.Combobox(
                frm, values=CHECKPOINTS, state="readonly")
            self.cb_cp.set(preset_checkpoint or DEFAULT_CHECKPOINT)
            self.cb_cp.grid(row=row, column=1, sticky="ew", pady=4)
            self._checkpoint_locked = None
        row += 1

        ttk.Label(frm, text="Destination type:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_type = ttk.Combobox(
            frm, values=DESTINATION_TYPES, state="readonly")
        self.cb_type.set(record.destination_type if record
                          else DEFAULT_DESTINATION_TYPE)
        self.cb_type.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        for label, attr, current in (
                ("Institution:",  "e_inst",
                 record.institution if record else ""),
                ("Course:",       "e_course",
                 record.course if record else ""),
                ("Employer:",     "e_employer",
                 record.employer if record else ""),
                ("Role:",         "e_role",
                 record.role if record else ""),
        ):
            ttk.Label(frm, text=label).grid(
                row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frm)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            if current:
                entry.insert(0, current)
            setattr(self, attr, entry)
            row += 1

        ttk.Label(frm, text="Study level:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_level = ttk.Combobox(
            frm, values=("",) + STUDY_LEVELS, state="readonly")
        self.cb_level.set(record.study_level if record
                            and record.study_level else "")
        self.cb_level.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Salary band:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_salary = ttk.Combobox(
            frm, values=("",) + SALARY_BANDS, state="readonly")
        self.cb_salary.set(record.salary_band if record
                            and record.salary_band else "")
        self.cb_salary.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Start date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_start = ttk.Entry(frm)
        self.e_start.grid(row=row, column=1, sticky="ew", pady=4)
        if record and record.start_date:
            self.e_start.insert(0, record.start_date)
        row += 1

        ttk.Label(frm, text="Confirmed via:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_via = ttk.Combobox(
            frm, values=("",) + CONFIRMED_VIA, state="readonly")
        self.cb_via.set(record.confirmed_via if record
                          and record.confirmed_via else "")
        self.cb_via.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Confirmed date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_confirmed = ttk.Entry(frm)
        self.e_confirmed.grid(row=row, column=1, sticky="ew", pady=4)
        if record and record.confirmed_date:
            self.e_confirmed.insert(0, record.confirmed_date)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=5, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if record and record.notes:
            self.t_notes.insert("1.0", record.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        sid = (self._student_locked
                or self._student_map.get(self.cb_student.get(), ""))
        cp = self._checkpoint_locked or self.cb_cp.get()
        return {
            "student_id":       sid,
            "checkpoint":       cp,
            "destination_type": self.cb_type.get(),
            "institution":      self.e_inst.get(),
            "course":           self.e_course.get(),
            "employer":         self.e_employer.get(),
            "role":             self.e_role.get(),
            "study_level":      self.cb_level.get(),
            "salary_band":      self.cb_salary.get(),
            "start_date":       self.e_start.get(),
            "confirmed_via":    self.cb_via.get(),
            "confirmed_date":   self.e_confirmed.get(),
            "notes":            self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            r = data.save_record(self._payload())
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Destination save failed")
            messagebox.showerror("Destinations",
                                   f"Save failed: {e}", parent=self)
            return
        self.on_save(r)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Missing tab
# ─────────────────────────────────────────────────────────────────

class MissingTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  records_tab: RecordsTab) -> None:
        self.root = root
        self.records_tab = records_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Missing")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Checkpoint:").pack(side="left")
        self.cb_cp = ttk.Combobox(
            bar, values=CHECKPOINTS, state="readonly", width=10)
        self.cb_cp.set(DEFAULT_CHECKPOINT)
        self.cb_cp.pack(side="left", padx=(2, 8))
        self.cb_cp.bind("<<ComboboxSelected>>",
                         lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Record selected…",
                    command=self._record_selected).pack(
            side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student_id", "name")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        self.tree.heading("student_id", text="Student id")
        self.tree.column("student_id", width=150, anchor="w")
        self.tree.heading("name", text="Name")
        self.tree.column("name", width=400, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._record_selected())

        self.count = ttk.Label(self.frame, text="")
        self.count.pack(anchor="e", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        cp = self.cb_cp.get() or DEFAULT_CHECKPOINT
        try:
            missing = data.students_missing_at(cp)
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e))
            return
        except Exception as e:
            logger.exception("Missing refresh failed")
            messagebox.showerror("Destinations",
                                   f"Could not load list: {e}")
            return
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        for sid in missing:
            self.tree.insert(
                "", "end", iid=sid,
                values=(sid, names.get(sid, "(unknown)")))
        self.count.configure(
            text=f"{len(missing)} student(s) missing at {cp}")

    def _record_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Destinations",
                                 "Select a student first.")
            return
        sid = sel[0]
        cp = self.cb_cp.get() or DEFAULT_CHECKPOINT
        self.records_tab.open_for(sid, cp)
        # Refresh both tabs after dialog closes.
        self.frame.after(100, self.refresh)


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook,
                  records_tab: RecordsTab) -> None:
        self.records_tab = records_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Button(top, text="Refresh",
                    command=self.refresh).pack(anchor="e")
        self.body = tk.Text(top, wrap="word", font=("Courier", 10),
                             height=30, state="disabled")
        self.body.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("Destinations summary failed")
            messagebox.showerror("Destinations",
                                   f"Summary failed: {e}")
            return
        lines: list[str] = []
        lines.append(
            f"Total records              : {s.total_records}")
        lines.append(
            f"Students captured @ LEAVING: {s.students_with_leaving}")
        lines.append(
            f"Students MISSING @ LEAVING : {s.students_missing_leaving}")
        lines.append("")
        lines.append("Positive sustained destinations:")
        lines.append(f"  @ LEAVING  : {s.positive_at_leaving}")
        lines.append(f"  @ +6  mth  : {s.positive_at_plus_6}")
        lines.append(f"  @ +12 mth  : {s.positive_at_plus_12}")
        lines.append("")
        lines.append("Records by checkpoint:")
        for cp, n in s.by_checkpoint.items():
            lines.append(
                f"  {cp:<10} {n:>4}  ({CHECKPOINT_LABELS[cp]})")
        lines.append("")
        lines.append("By destination type:")
        for d, n in s.by_destination_type.items():
            if n:
                lines.append(f"  {d:<22} {n:>4}")
        if any(n for n in s.by_level_at_leaving.values()):
            lines.append("")
            lines.append("Study level at LEAVING:")
            for lvl, n in s.by_level_at_leaving.items():
                if n:
                    lines.append(f"  {lvl:<14} {n:>4}")
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
