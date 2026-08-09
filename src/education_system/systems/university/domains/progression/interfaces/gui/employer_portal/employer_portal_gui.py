"""Tkinter GUI for the university employer portal."""
from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.progression.domain.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)

logger = logging.getLogger(__name__)


def _user_display_name(auth):
    if not auth:
        return ''
    return (auth.get('username') or auth.get('email') or
            auth.get('user_id') or auth.get('id') or '')


class EmployerPortalFrame(tk.Frame):
    """Notebook UI: Employers / Reviews / Sign-Off / Dashboard."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._svc = EmployerPortalService(db_path)
        self._auth = auth
        self._user_display = _user_display_name(auth) or 'Guest'
        self._build_ui()
        self._load_employers()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text=_t('gui.progression.employer_portal.employer_portal.labels.employer_portal', default="Employer Portal"),
            font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=10)

        role = (self._auth or {}).get('role') or ('—' if self._auth else 'not signed in')
        tk.Label(
            header,
            text=f"Signed in: {self._user_display}  ({role})",
            font=("Helvetica", 10), bg="#2c3e50", fg="#bdc3c7",
        ).pack(side="right", padx=20, pady=15)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)
        self._build_employers_tab()
        self._build_reviews_tab()
        self._build_signoff_tab()
        self._build_dashboard_tab()

    # -- Employers -----------------------------------------------------

    def _build_employers_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=_t('gui.progression.employer_portal.employer_portal.tabs.employers', default="Employers"))

        form = tk.LabelFrame(tab, text=_t('gui.progression.employer_portal.employer_portal.labels.register_employer', default="Register Employer"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)
        labels = ["Company", "Contact", "Email", "Phone", "Sector", "Size"]
        self._emp_vars: dict[str, tk.StringVar] = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(
                row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            if lbl == "Size":
                var.set("small")
                ttk.Combobox(form, textvariable=var,
                             values=["small", "medium", "large"], width=15).grid(
                    row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            else:
                tk.Entry(form, textvariable=var, width=18).grid(
                    row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            self._emp_vars[lbl] = var

        btns = tk.Frame(form, bg="#ecf0f1")
        btns.grid(row=2, column=0, columnspan=6, pady=5)
        tk.Button(btns, text=_t('gui.progression.employer_portal.employer_portal.buttons.add', default="Add"), command=self._add_employer).pack(side="left", padx=5)
        tk.Button(btns, text=_t('gui.progression.employer_portal.employer_portal.buttons.update', default="Update"), command=self._update_employer).pack(side="left", padx=5)
        tk.Button(btns, text=_t('gui.progression.employer_portal.employer_portal.buttons.refresh', default="Refresh"), command=self._load_employers).pack(side="left", padx=5)

        cols = ("id", "company", "contact", "email", "sector", "size", "active")
        self._emp_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._emp_tree.heading(c, text=c.title())
            self._emp_tree.column(c, width=110)
        self._emp_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_employer(self):
        try:
            v = self._emp_vars
            new_id = self._svc.register_employer(
                company_name=v["Company"].get().strip(),
                contact_name=v["Contact"].get().strip(),
                contact_email=v["Email"].get().strip(),
                contact_phone=v["Phone"].get().strip(),
                sector=v["Sector"].get().strip(),
                company_size=v["Size"].get().strip() or "small",
            )
            logger.info("Employer registered id=%s company=%r by user=%s",
                        new_id, v["Company"].get().strip(), self._user_display)
            messagebox.showinfo(_t('gui.progression.employer_portal.employer_portal.dialogs.success', default="Success"), _t('gui.progression.employer_portal.employer_portal.dialogs.employer_registered', default="Employer registered."))
            for var in v.values():
                var.set("" if var.get() != "small" else "small")
            self._load_employers()
        except EmployerPortalError as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def _update_employer(self):
        sel = self._emp_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.progression.employer_portal.employer_portal.dialogs.selection', default="Selection"), _t('gui.progression.employer_portal.employer_portal.dialogs.select_an_employer_to_update', default="Select an employer to update."))
            return
        row = self._emp_tree.item(sel[0], "values")
        emp_id = int(row[0])

        dlg = tk.Toplevel(self)
        dlg.title(_t('gui.progression.employer_portal.employer_portal.windows.update_employer', default="Update Employer"))
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        fields = [
            ("company_name", "Company", row[1]),
            ("contact_name", "Contact", row[2]),
            ("contact_email", "Email", row[3]),
            ("contact_phone", "Phone", ""),
            ("sector", "Sector", row[4]),
        ]
        upd_vars: dict[str, tk.StringVar] = {}
        for i, (key, label, current) in enumerate(fields):
            tk.Label(dlg, text=label + ":").grid(row=i, column=0, padx=5, pady=3, sticky="e")
            var = tk.StringVar(value=str(current or ""))
            tk.Entry(dlg, textvariable=var, width=28).grid(row=i, column=1, padx=5, pady=3)
            upd_vars[key] = var
        tk.Label(dlg, text=_t('gui.progression.employer_portal.employer_portal.labels.size', default="Size:")).grid(row=len(fields), column=0, padx=5, pady=3, sticky="e")
        size_var = tk.StringVar(value=str(row[5] or "small"))
        ttk.Combobox(dlg, textvariable=size_var, values=["small", "medium", "large"],
                     width=25).grid(row=len(fields), column=1, padx=5, pady=3)
        active_var = tk.BooleanVar(value=str(row[6]).lower() == "yes")
        tk.Checkbutton(dlg, text=_t('gui.progression.employer_portal.employer_portal.buttons.active', default="Active"), variable=active_var).grid(
            row=len(fields) + 1, column=1, padx=5, pady=3, sticky="w")

        def save():
            updates = {k: v.get().strip() for k, v in upd_vars.items() if v.get().strip()}
            updates["company_size"] = size_var.get().strip() or "small"
            updates["is_active"] = 1 if active_var.get() else 0
            try:
                self._svc.update_employer(emp_id, **updates)
                logger.info("Employer updated id=%s by user=%s", emp_id, self._user_display)
                messagebox.showinfo(_t('gui.progression.employer_portal.employer_portal.dialogs.success', default="Success"), _t('gui.progression.employer_portal.employer_portal.dialogs.employer_updated', default="Employer updated."), parent=dlg)
                dlg.destroy()
                self._load_employers()
            except EmployerPortalError as exc:
                messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc), parent=dlg)

        tk.Button(dlg, text=_t('gui.progression.employer_portal.employer_portal.buttons.save', default="Save"), command=save).grid(
            row=len(fields) + 2, column=0, columnspan=2, pady=10)

    def _load_employers(self):
        for row in self._emp_tree.get_children():
            self._emp_tree.delete(row)
        try:
            for e in self._svc.list_employers(active_only=False):
                self._emp_tree.insert("", "end", values=(
                    e["employer_id"], e["company_name"], e.get("contact_name", ""),
                    e.get("contact_email", ""), e.get("sector", ""),
                    e.get("company_size", ""),
                    "Yes" if e.get("is_active") else "No",
                ))
        except EmployerPortalError as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    # -- Reviews -------------------------------------------------------

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=_t('gui.progression.employer_portal.employer_portal.tabs.reviews', default="Reviews"))

        sched = tk.LabelFrame(tab, text=_t('gui.progression.employer_portal.employer_portal.labels.schedule_review', default="Schedule Review"), bg="#ecf0f1")
        sched.pack(fill="x", padx=10, pady=5)
        tk.Label(sched, text=_t('gui.progression.employer_portal.employer_portal.labels.placement_id_variant_2', default="Placement ID:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self._rev_pid = tk.StringVar()
        tk.Entry(sched, textvariable=self._rev_pid, width=8).grid(row=0, column=1, padx=5, pady=2)
        tk.Label(sched, text=_t('gui.progression.employer_portal.employer_portal.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):"), bg="#ecf0f1").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        self._rev_date = tk.StringVar()
        tk.Entry(sched, textvariable=self._rev_date, width=12).grid(row=0, column=3, padx=5, pady=2)
        tk.Label(sched, text=_t('gui.progression.employer_portal.employer_portal.labels.type', default="Type:"), bg="#ecf0f1").grid(row=0, column=4, padx=5, pady=2, sticky="e")
        self._rev_type = tk.StringVar(value=_t('gui.progression.employer_portal.employer_portal.values.monthly', default="monthly"))
        ttk.Combobox(sched, textvariable=self._rev_type,
                     values=["monthly", "tripartite", "midterm", "final"], width=12).grid(
            row=0, column=5, padx=5, pady=2)
        tk.Button(sched, text=_t('gui.progression.employer_portal.employer_portal.buttons.schedule', default="Schedule"), command=self._schedule_review).grid(row=0, column=6, padx=10)

        comp = tk.LabelFrame(tab, text=_t('gui.progression.employer_portal.employer_portal.labels.complete_review', default="Complete Review"), bg="#ecf0f1")
        comp.pack(fill="x", padx=10, pady=5)
        comp_labels = [
            "Review ID", "On Track (y/n)", "Competency Progress",
            "Hours Logged", "Employer Feedback", "Next Review Date",
        ]
        self._comp_vars: dict[str, tk.StringVar] = {}
        for i, lbl in enumerate(comp_labels):
            tk.Label(comp, text=lbl + ":", bg="#ecf0f1").grid(
                row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(comp, textvariable=var, width=20).grid(
                row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            self._comp_vars[lbl] = var
        tk.Button(comp, text=_t('gui.progression.employer_portal.employer_portal.buttons.complete', default="Complete"), command=self._complete_review).grid(
            row=2, column=5, padx=10, pady=5)

        tk.Button(tab, text=_t('gui.progression.employer_portal.employer_portal.buttons.refresh', default="Refresh"), command=self._load_reviews).pack(padx=10, pady=2, anchor="w")
        cols = ("id", "placement", "date", "type", "on_track", "hours",
                "emp", "stu", "sup", "status")
        self._rev_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._rev_tree.heading(c, text=c.title())
            self._rev_tree.column(c, width=80)
        self._rev_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _schedule_review(self):
        try:
            new_id = self._svc.schedule_review(
                placement_id=int(self._rev_pid.get()),
                review_date=self._rev_date.get().strip(),
                review_type=self._rev_type.get(),
            )
            logger.info("Review scheduled id=%s placement=%s date=%s type=%s by user=%s",
                        new_id, self._rev_pid.get(), self._rev_date.get(),
                        self._rev_type.get(), self._user_display)
            messagebox.showinfo(_t('gui.progression.employer_portal.employer_portal.dialogs.success', default="Success"), _t('gui.progression.employer_portal.employer_portal.dialogs.review_scheduled', default="Review scheduled."))
            self._load_reviews()
        except (EmployerPortalError, ValueError) as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def _complete_review(self):
        try:
            v = self._comp_vars
            self._svc.complete_review(
                review_id=int(v["Review ID"].get()),
                on_track=v["On Track (y/n)"].get().strip().lower().startswith("y"),
                competency_progress=v["Competency Progress"].get(),
                hours_logged=float(v["Hours Logged"].get() or 0),
                employer_feedback=v["Employer Feedback"].get(),
                next_review_date=v["Next Review Date"].get().strip() or None,
            )
            logger.info("Review completed review_id=%s by user=%s",
                        v["Review ID"].get(), self._user_display)
            messagebox.showinfo(_t('gui.progression.employer_portal.employer_portal.dialogs.success', default="Success"), _t('gui.progression.employer_portal.employer_portal.dialogs.review_completed', default="Review completed."))
            self._load_reviews()
        except (EmployerPortalError, ValueError) as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def _load_reviews(self):
        for row in self._rev_tree.get_children():
            self._rev_tree.delete(row)
        try:
            pid = self._rev_pid.get().strip()
            for r in self._svc.list_reviews(
                placement_id=int(pid) if pid else None,
            ):
                self._rev_tree.insert("", "end", values=(
                    r["review_id"], r["placement_id"], r.get("review_date", ""),
                    r.get("review_type", ""),
                    "Yes" if r.get("on_track") else ("No" if r.get("on_track") == 0 else "-"),
                    r.get("hours_logged") or 0,
                    "Y" if r.get("employer_signed") else "N",
                    "Y" if r.get("student_signed") else "N",
                    "Y" if r.get("supervisor_signed") else "N",
                    r.get("status", ""),
                ))
        except EmployerPortalError as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    # -- Sign-off ------------------------------------------------------

    def _build_signoff_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=_t('gui.progression.employer_portal.employer_portal.tabs.sign_off', default="Sign-Off"))

        form = tk.LabelFrame(tab, text=_t('gui.progression.employer_portal.employer_portal.labels.sign_off_review', default="Sign Off Review"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)
        tk.Label(form, text=_t('gui.progression.employer_portal.employer_portal.labels.review_id', default="Review ID:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._so_rid = tk.StringVar()
        tk.Entry(form, textvariable=self._so_rid, width=8).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(form, text=_t('gui.progression.employer_portal.employer_portal.labels.signer_type', default="Signer Type:"), bg="#ecf0f1").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self._so_type = tk.StringVar(value=_t('gui.progression.employer_portal.employer_portal.values.employer', default="employer"))
        ttk.Combobox(form, textvariable=self._so_type,
                     values=["employer", "student", "supervisor"], width=12).grid(
            row=0, column=3, padx=5, pady=5)
        tk.Label(form, text=_t('gui.progression.employer_portal.employer_portal.labels.signer_name', default="Signer Name:"), bg="#ecf0f1").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self._so_name = tk.StringVar(value=self._user_display if self._auth else "")
        tk.Entry(form, textvariable=self._so_name, width=20).grid(row=0, column=5, padx=5, pady=5)
        tk.Label(form, text=_t('gui.progression.employer_portal.employer_portal.labels.comments', default="Comments:"), bg="#ecf0f1").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self._so_comment = tk.StringVar()
        tk.Entry(form, textvariable=self._so_comment, width=50).grid(
            row=1, column=1, columnspan=4, padx=5, pady=5, sticky="w")
        tk.Button(form, text=_t('gui.progression.employer_portal.employer_portal.buttons.sign_off', default="Sign Off"), command=self._sign_off).grid(row=1, column=5, padx=10)

        tk.Button(tab, text=_t('gui.progression.employer_portal.employer_portal.buttons.show_overdue_reviews', default="Show Overdue Reviews"), command=self._show_overdue).pack(
            padx=10, pady=5, anchor="w")
        cols = ("id", "placement", "date", "type", "student", "company")
        self._overdue_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._overdue_tree.heading(c, text=c.title())
            self._overdue_tree.column(c, width=120)
        self._overdue_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _sign_off(self):
        try:
            self._svc.sign_off_review(
                review_id=int(self._so_rid.get()),
                signer_type=self._so_type.get(),
                signer_name=self._so_name.get().strip(),
                comments=self._so_comment.get().strip() or None,
            )
            logger.info("Review signed off review_id=%s signer_type=%s signer=%r logged_by=%s",
                        self._so_rid.get(), self._so_type.get(),
                        self._so_name.get().strip(), self._user_display)
            messagebox.showinfo(_t('gui.progression.employer_portal.employer_portal.dialogs.success', default="Success"), _t('gui.progression.employer_portal.employer_portal.dialogs.review_signed_off', default="Review signed off."))
        except (EmployerPortalError, ValueError) as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def _show_overdue(self):
        for row in self._overdue_tree.get_children():
            self._overdue_tree.delete(row)
        try:
            for r in self._svc.get_overdue_reviews():
                self._overdue_tree.insert("", "end", values=(
                    r["review_id"], r["placement_id"], r.get("review_date", ""),
                    r.get("review_type", ""), r.get("student_id", ""),
                    r.get("company", ""),
                ))
        except EmployerPortalError as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    # -- Dashboard -----------------------------------------------------

    def _build_dashboard_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=_t('gui.progression.employer_portal.employer_portal.tabs.dashboard', default="Dashboard"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)
        tk.Label(ctrl, text=_t('gui.progression.employer_portal.employer_portal.labels.employer_id', default="Employer ID:"), bg="#ecf0f1").pack(side="left", padx=5)
        self._dash_eid = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._dash_eid, width=8).pack(side="left", padx=5)
        tk.Button(ctrl, text=_t('gui.progression.employer_portal.employer_portal.buttons.load_employer_dashboard', default="Load Employer Dashboard"), command=self._load_dashboard).pack(
            side="left", padx=5)
        tk.Label(ctrl, text=_t('gui.progression.employer_portal.employer_portal.labels.placement_id', default="  Placement ID:"), bg="#ecf0f1").pack(side="left", padx=5)
        self._dash_pid = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._dash_pid, width=8).pack(side="left", padx=5)
        tk.Button(ctrl, text=_t('gui.progression.employer_portal.employer_portal.buttons.placement_progress', default="Placement Progress"), command=self._load_progress).pack(
            side="left", padx=5)

        self._dash_info = tk.Text(tab, height=20, width=80, state="disabled")
        self._dash_info.pack(fill="both", expand=True, padx=10, pady=10)

    def _set_dash(self, lines: list[str]):
        self._dash_info.config(state="normal")
        self._dash_info.delete("1.0", "end")
        self._dash_info.insert("end", "\n".join(lines))
        self._dash_info.config(state="disabled")

    def _load_dashboard(self):
        try:
            data = self._svc.get_employer_dashboard(int(self._dash_eid.get()))
            emp = data["employer"]
            lines = [
                f"Employer: {emp['company_name']} (ID {emp['employer_id']})",
                f"Contact: {emp.get('contact_name','')} <{emp.get('contact_email','')}>",
                f"Sector: {emp.get('sector','-')}  Size: {emp.get('company_size','-')}",
                "=" * 50,
                f"Total placements:  {data['total_placements']}",
                f"Active placements: {data['active_placements']}",
                "",
            ]
            for s in data["placements"]:
                rs = s.get("review_summary", {})
                lines.append(
                    f"  Placement #{s['placement_id']}  student={s.get('student_id')}  "
                    f"{s.get('title','')}  status={s.get('status','-')}"
                )
                lines.append(
                    f"    reviews: {rs.get('completed', 0) or 0}/{rs.get('total', 0) or 0}"
                    f"  on_track: {rs.get('on_track', 0) or 0}"
                    f"  hours: {rs.get('total_hours', 0) or 0}"
                )
            self._set_dash(lines)
        except (EmployerPortalError, ValueError) as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def _load_progress(self):
        try:
            data = self._svc.get_placement_progress(int(self._dash_pid.get()))
            p = data["placement"]
            lines = [
                f"Placement #{p['placement_id']} — {p.get('title','')} @ {p.get('company','')}",
                f"Student: {p.get('student_id','-')}  Supervisor: {p.get('supervisor_name','-')}",
                f"Dates: {p.get('start_date','-')} → {p.get('end_date','-')}",
                f"Completion: {data['completion_pct']}%",
                f"Total hours logged: {data['total_hours_logged']}",
                f"Reviews on file: {data['review_count']}",
                "=" * 50,
            ]
            for r in data["reviews"]:
                lines.append(
                    f"  {r.get('review_date','')} ({r.get('review_type','')}): "
                    f"{'on track' if r.get('on_track') else 'off track'}  "
                    f"hrs={r.get('hours_logged') or 0}  status={r.get('status','-')}"
                )
            self._set_dash(lines)
        except (EmployerPortalError, ValueError) as exc:
            messagebox.showerror(_t('gui.progression.employer_portal.employer_portal.dialogs.error', default="Error"), str(exc))

    def refresh(self):
        self._load_employers()
