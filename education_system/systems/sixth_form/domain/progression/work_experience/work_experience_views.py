"""Tkinter views for Work Experience & Placements.

Single window with three tabs:

* **Placements** — filterable table of placements, create / edit /
  log-hours / delete actions. Double-click to edit.
* **Employers** — employer directory with full CRUD.
* **Summary** — counts by status, by sector, consent / risk pending,
  upcoming starts, total hours.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from education_system.platform import branding
from education_system.systems.sixth_form.domain.progression.work_experience import (
    work_experience as data,
)
from education_system.systems.sixth_form.domain.progression.work_experience.work_experience import (
    DEFAULT_PLACEMENT_STATUS,
    DEFAULT_SECTOR,
    Employer,
    PLACEMENT_STATUSES,
    Placement,
    SECTORS,
    ValidationError,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS: dict[str, tuple[str, str]] = {
    "Planned":     ("#fff7e6", "#7a5800"),
    "In Progress": ("#e6f0ff", "#1a3f8c"),
    "Completed":   ("#e6f7e6", "#0d6b2a"),
    "Cancelled":   ("#eeeeee", "#666666"),
}


def open_directory(parent=None) -> None:
    try:
        data.init_db()
    except Exception:
        logger.exception("Work-experience init_db failed")
        messagebox.showerror(
            "Work Experience",
            "Could not initialise the database. Check logs.")
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Work Experience — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    employers_tab = EmployersTab(nb, win)
    placements_tab = PlacementsTab(nb, win, employers_tab)
    employers_tab.set_refresh_callback(placements_tab.refresh)
    SummaryTab(nb, placements_tab, employers_tab)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _employer_options() -> list[tuple[int, str]]:
    return [(e.employer_id, f"{e.name} ({e.sector})")
            for e in data.list_employers()]


# ─────────────────────────────────────────────────────────────────
# Placements tab
# ─────────────────────────────────────────────────────────────────

class PlacementsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  employers_tab: EmployersTab) -> None:
        self.root = root
        self.employers_tab = employers_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Placements")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + PLACEMENT_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        self.v_consent = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Consent pending",
                         variable=self.v_consent,
                         command=self.refresh).pack(side="left", padx=4)
        self.v_risk = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Risk-assessment pending",
                         variable=self.v_risk,
                         command=self.refresh).pack(side="left", padx=4)

        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New placement",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "employer", "role",
                "start", "end", "hours", "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 80, "name": 130,
                   "employer": 180, "role": 130,
                   "start": 90, "end": 90,
                   "hours": 90, "status": 100, "flags": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "hours", "flags")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg, foreground=fg)
        self.tree.tag_configure("flagged", background="#fff0d6",
                                  foreground="#7a5800")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",  self._edit),
                ("Log hours",    self._log_hours),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_status.current(0)
        self.f_student.delete(0, "end")
        self.v_consent.set(False)
        self.v_risk.set(False)
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.v_consent.get():
            f["consent_pending"] = True
        if self.v_risk.get():
            f["risk_pending"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_placements_with_detail(**self._filters())
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e))
            return
        except Exception as e:
            logger.exception("Placements refresh failed")
            messagebox.showerror(
                "Work Experience", f"Could not load placements: {e}")
            return
        for r in rows:
            p = r.placement
            flags = []
            if not p.parental_consent and p.status != "Cancelled":
                flags.append("CONS")
            if not p.risk_assessment_done and p.status != "Cancelled":
                flags.append("RISK")
            hours_str = (f"{p.hours_completed:.0f}/{p.hours_required:.0f}"
                          if p.hours_required
                          else f"{p.hours_completed:.0f}/—")
            tags = [p.status]
            if flags:
                tags.append("flagged")
            self.tree.insert(
                "", "end", iid=str(p.placement_id),
                values=(p.placement_id, p.student_id, r.student_name,
                          r.employer_name, p.role or "—",
                          p.start_date, p.end_date, hours_str,
                          p.status, ",".join(flags)),
                tags=tuple(tags),
            )
        self.count.configure(text=f"{len(rows)} placement(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Work Experience",
                                 "Select a placement first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        if not data.list_employers():
            messagebox.showinfo(
                "Work Experience",
                "Add at least one employer first (Employers tab).")
            return
        PlacementDialog(self.root, on_save=lambda _p: self.refresh())

    def _edit(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        p = data.get_placement(pid)
        if p is None:
            self.refresh()
            return
        PlacementDialog(self.root, placement=p,
                          on_save=lambda _p: self.refresh())

    def _delete(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        if not messagebox.askyesno(
                "Work Experience", f"Delete placement #{pid}?"):
            return
        try:
            data.delete_placement(pid)
        except Exception as e:
            logger.exception("delete_placement failed")
            messagebox.showerror("Work Experience",
                                  f"Delete failed: {e}")
            return
        self.refresh()

    def _log_hours(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        p = data.get_placement(pid)
        if p is None:
            self.refresh()
            return
        raw = simpledialog.askstring(
            "Log hours",
            f"Hours to add for placement #{pid} "
            f"(current {p.hours_completed:.1f}):",
            parent=self.root,
        )
        if raw is None or not raw.strip():
            return
        try:
            out = data.log_hours(pid, float(raw))
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e))
            return
        except ValueError:
            messagebox.showwarning("Work Experience",
                                     "Hours must be a number.")
            return
        except Exception as e:
            logger.exception("log_hours failed")
            messagebox.showerror("Work Experience",
                                   f"Log-hours failed: {e}")
            return
        self.refresh()
        messagebox.showinfo(
            "Work Experience",
            f"Logged. Total now {out.hours_completed:.1f}"
            f" / {out.hours_required or '—'}.")


# ─────────────────────────────────────────────────────────────────
# Placement dialog
# ─────────────────────────────────────────────────────────────────

class PlacementDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 placement: Placement | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.placement = placement
        self.on_save = on_save
        self.title("Edit Placement" if placement else "New Placement")
        self.geometry("760x780")
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
        if placement:
            ttk.Label(frm, text=placement.student_id).grid(
                row=row, column=1, sticky="w", pady=4)
        else:
            self._student_map = {lbl: sid for sid, lbl in student_opts}
            self.cb_student = ttk.Combobox(
                frm, values=[lbl for _sid, lbl in student_opts],
                state="readonly")
            self.cb_student.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Employer:").grid(
            row=row, column=0, sticky="w", pady=4)
        emp_opts = _employer_options()
        self._employer_map = {lbl: eid for eid, lbl in emp_opts}
        self.cb_employer = ttk.Combobox(
            frm, values=[lbl for _eid, lbl in emp_opts],
            state="readonly")
        if placement:
            current_label = next(
                (lbl for eid, lbl in emp_opts
                 if eid == placement.employer_id), "")
            self.cb_employer.set(current_label)
        self.cb_employer.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Start date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_start = ttk.Entry(frm)
        self.e_start.grid(row=row, column=1, sticky="ew", pady=4)
        self.e_start.insert(0, placement.start_date if placement
                              else _dt.date.today().isoformat())
        row += 1

        ttk.Label(frm, text="End date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_end = ttk.Entry(frm)
        self.e_end.grid(row=row, column=1, sticky="ew", pady=4)
        if placement:
            self.e_end.insert(0, placement.end_date)
        row += 1

        ttk.Label(frm, text="Role / job title:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_role = ttk.Entry(frm)
        self.e_role.grid(row=row, column=1, sticky="ew", pady=4)
        if placement and placement.role:
            self.e_role.insert(0, placement.role)
        row += 1

        ttk.Label(frm, text="Hours required:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_hours_req = ttk.Entry(frm)
        self.e_hours_req.grid(row=row, column=1, sticky="ew", pady=4)
        if placement and placement.hours_required is not None:
            self.e_hours_req.insert(0, str(placement.hours_required))
        row += 1

        ttk.Label(frm, text="Hours completed:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_hours_done = ttk.Entry(frm)
        self.e_hours_done.grid(row=row, column=1, sticky="ew", pady=4)
        self.e_hours_done.insert(
            0, str(placement.hours_completed) if placement else "0")
        row += 1

        ttk.Label(frm, text="Status:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_status = ttk.Combobox(
            frm, values=PLACEMENT_STATUSES, state="readonly")
        self.cb_status.set(placement.status if placement
                            else DEFAULT_PLACEMENT_STATUS)
        self.cb_status.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        self.v_risk = tk.BooleanVar(
            value=bool(placement.risk_assessment_done)
            if placement else False)
        ttk.Checkbutton(frm, text="Risk assessment completed",
                         variable=self.v_risk).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        self.v_consent = tk.BooleanVar(
            value=bool(placement.parental_consent)
            if placement else False)
        ttk.Checkbutton(frm, text="Parental consent received",
                         variable=self.v_consent).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Supervisor name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_sup_name = ttk.Entry(frm)
        self.e_sup_name.grid(row=row, column=1, sticky="ew", pady=4)
        if placement and placement.supervisor_name:
            self.e_sup_name.insert(0, placement.supervisor_name)
        row += 1

        ttk.Label(frm, text="Supervisor email:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_sup_email = ttk.Entry(frm)
        self.e_sup_email.grid(row=row, column=1, sticky="ew", pady=4)
        if placement and placement.supervisor_email:
            self.e_sup_email.insert(0, placement.supervisor_email)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=6, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if placement and placement.notes:
            self.t_notes.insert("1.0", placement.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        if self.placement is not None:
            sid = self.placement.student_id
        else:
            sid = self._student_map.get(self.cb_student.get(), "")
        emp_id = self._employer_map.get(self.cb_employer.get())
        return {
            "student_id":            sid,
            "employer_id":           emp_id,
            "start_date":            self.e_start.get(),
            "end_date":              self.e_end.get(),
            "role":                  self.e_role.get(),
            "hours_required":        self.e_hours_req.get().strip() or None,
            "hours_completed":       self.e_hours_done.get().strip() or 0,
            "status":                self.cb_status.get(),
            "risk_assessment_done":  self.v_risk.get(),
            "parental_consent":      self.v_consent.get(),
            "supervisor_name":       self.e_sup_name.get(),
            "supervisor_email":      self.e_sup_email.get(),
            "notes":                 self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._payload()
            if self.placement is None:
                p = data.create_placement(payload)
            else:
                p = data.update_placement(
                    self.placement.placement_id, payload)
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Placement save failed")
            messagebox.showerror("Work Experience",
                                   f"Save failed: {e}", parent=self)
            return
        self.on_save(p)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Employers tab
# ─────────────────────────────────────────────────────────────────

class EmployersTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self._refresh_callback = None
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Employers")
        self._build()
        self.refresh()

    def set_refresh_callback(self, cb) -> None:
        self._refresh_callback = cb

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Sector:").pack(side="left")
        self.f_sector = ttk.Combobox(
            bar, values=("",) + SECTORS,
            state="readonly", width=18)
        self.f_sector.current(0)
        self.f_sector.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=22)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New employer",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "sector", "contact",
                "email", "phone")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", selectmode="browse")
        widths = {"id": 50, "name": 260, "sector": 140,
                   "contact": 160, "email": 220, "phone": 140}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c == "id" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
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
        self.f_sector.current(0)
        self.f_name.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            kw: dict[str, Any] = {}
            if self.f_sector.get():
                kw["sector"] = self.f_sector.get()
            if self.f_name.get().strip():
                kw["name_like"] = self.f_name.get().strip()
            rows = data.list_employers(**kw)
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e))
            return
        except Exception as e:
            logger.exception("Employers refresh failed")
            messagebox.showerror(
                "Work Experience",
                f"Could not load employers: {e}")
            return
        for e in rows:
            self.tree.insert(
                "", "end", iid=str(e.employer_id),
                values=(e.employer_id, e.name, e.sector,
                          e.contact_name or "—",
                          e.contact_email or "—",
                          e.contact_phone or "—"),
            )
        self.count.configure(text=f"{len(rows)} employer(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Work Experience",
                                 "Select an employer first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        EmployerDialog(self.root, on_save=self._after_save)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        e = data.get_employer(eid)
        if e is None:
            self.refresh()
            return
        EmployerDialog(self.root, employer=e, on_save=self._after_save)

    def _after_save(self, _e) -> None:
        self.refresh()
        if self._refresh_callback is not None:
            self._refresh_callback()

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        if not messagebox.askyesno(
                "Work Experience", f"Delete employer #{eid}?"):
            return
        try:
            data.delete_employer(eid)
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e))
            return
        except Exception as e:
            logger.exception("delete_employer failed")
            messagebox.showerror("Work Experience",
                                   f"Delete failed: {e}")
            return
        self._after_save(None)


class EmployerDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 employer: Employer | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.employer = employer
        self.on_save = on_save
        self.title("Edit Employer" if employer else "New Employer")
        self.geometry("640x600")
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

        ttk.Label(frm, text="Name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(frm)
        self.e_name.grid(row=row, column=1, sticky="ew", pady=4)
        if employer:
            self.e_name.insert(0, employer.name)
        row += 1

        ttk.Label(frm, text="Sector:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_sector = ttk.Combobox(
            frm, values=SECTORS, state="readonly")
        self.cb_sector.set(employer.sector if employer
                            else DEFAULT_SECTOR)
        self.cb_sector.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Contact name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_contact = ttk.Entry(frm)
        self.e_contact.grid(row=row, column=1, sticky="ew", pady=4)
        if employer and employer.contact_name:
            self.e_contact.insert(0, employer.contact_name)
        row += 1

        ttk.Label(frm, text="Contact email:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_email = ttk.Entry(frm)
        self.e_email.grid(row=row, column=1, sticky="ew", pady=4)
        if employer and employer.contact_email:
            self.e_email.insert(0, employer.contact_email)
        row += 1

        ttk.Label(frm, text="Contact phone:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_phone = ttk.Entry(frm)
        self.e_phone.grid(row=row, column=1, sticky="ew", pady=4)
        if employer and employer.contact_phone:
            self.e_phone.insert(0, employer.contact_phone)
        row += 1

        ttk.Label(frm, text="Address:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_addr = tk.Text(frm, height=4, wrap="word")
        self.t_addr.grid(row=row, column=1, sticky="ew", pady=4)
        if employer and employer.address:
            self.t_addr.insert("1.0", employer.address)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=5, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if employer and employer.notes:
            self.t_notes.insert("1.0", employer.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        return {
            "name":          self.e_name.get(),
            "sector":        self.cb_sector.get(),
            "contact_name":  self.e_contact.get(),
            "contact_email": self.e_email.get(),
            "contact_phone": self.e_phone.get(),
            "address":       self.t_addr.get("1.0", "end").strip(),
            "notes":         self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._payload()
            if self.employer is None:
                e = data.create_employer(payload)
            else:
                e = data.update_employer(self.employer.employer_id, payload)
        except ValidationError as e:
            messagebox.showwarning("Work Experience", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Employer save failed")
            messagebox.showerror("Work Experience",
                                   f"Save failed: {e}", parent=self)
            return
        self.on_save(e)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook,
                  placements_tab: PlacementsTab,
                  employers_tab: EmployersTab) -> None:
        self.placements_tab = placements_tab
        self.employers_tab = employers_tab
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
            logger.exception("Work-experience summary failed")
            messagebox.showerror("Work Experience",
                                   f"Summary failed: {e}")
            return
        lines: list[str] = []
        lines.append(f"Total employers          : {s.total_employers}")
        lines.append(f"Total placements         : {s.total_placements}")
        lines.append(f"Students with placement  : {s.students_with_placement}")
        lines.append(
            f"Total hours completed    : {s.total_hours_completed:.1f}")
        lines.append(f"Parental consent pending : {s.consent_pending}")
        lines.append(f"Risk-assessment pending  : {s.risk_pending}")
        lines.append(
            f"Upcoming starts (30 d)   : {s.upcoming_start}")
        lines.append("")
        lines.append("By status:")
        for st, n in s.by_status.items():
            lines.append(f"  {st:<14} {n:>4}")
        lines.append("")
        lines.append("By sector:")
        for sect, n in s.by_sector.items():
            if n:
                lines.append(f"  {sect:<22} {n:>4}")
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
