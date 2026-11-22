"""DSA casework tab of the Disability & Accessibility portal.

Staff (disability services, the health team) get the case list and, for the
selected case, one sub-tab per part of the case: SFE application, needs
assessment, recommendations, non-medical help, equipment, exam access
arrangements and the adjustments linked to it. A student gets their own
case, read-only. Everything goes through ``domain/disability/dsa``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from education_system.systems.university.domains.student_support.domain.disability import (
    access,
    dsa,
)
from education_system.systems.university.domains.student_support.interfaces.gui.disability.forms import (
    ask_form,
    button_bar,
    fill_tree,
    make_tree,
    selected_id,
    show_error,
)

TITLE = "Disabled Students' Allowances"

CASE_COLUMNS = [("case_id", "#", 50), ("student_id", "Student", 90),
                ("student_name", "Name", 170), ("funding_body", "Body", 60),
                ("status_label", "Status", 260), ("updated_at", "Updated", 140)]
ASSESS_COLUMNS = [("id", "#", 40), ("assessment_date", "Date", 90),
                  ("assessment_time", "Time", 60), ("centre", "Centre", 180),
                  ("assessor", "Assessor", 150), ("mode", "Mode", 80),
                  ("attended_label", "Attended", 80)]
REC_COLUMNS = [("id", "#", 40), ("category_label", "Category", 150),
               ("recommendation", "Recommendation", 420), ("status", "Status", 90),
               ("accommodation_id", "Adjustment #", 90)]
NMH_COLUMNS = [("id", "#", 40), ("support_type", "Support", 170), ("worker_name", "Worker", 140),
               ("agency", "Agency", 120), ("band", "Band", 60),
               ("hours_allocated", "Allocated", 70), ("hours_used", "Used", 60),
               ("hours_remaining", "Remaining", 70), ("status", "Status", 70)]
LOG_COLUMNS = [("id", "#", 40), ("session_date", "Date", 90), ("hours", "Hours", 60),
               ("notes", "Notes", 360), ("logged_by", "Logged by", 110)]
EQUIP_COLUMNS = [("id", "#", 40), ("item", "Item", 220), ("supplier", "Supplier", 150),
                 ("status", "Status", 100), ("ordered_date", "Ordered", 90),
                 ("delivered_date", "Delivered", 90), ("training_date", "Training", 90)]
EXAM_COLUMNS = [("id", "#", 40), ("summary", "Arrangements", 440), ("valid_from", "From", 90),
                ("valid_to", "To", 90), ("status", "Status", 90),
                ("accommodation_id", "Adjustment #", 90)]
ADJ_COLUMNS = [("id", "#", 50), ("accommodation_type", "Type", 180),
               ("description", "Description", 360), ("status", "Status", 90),
               ("linked_label", "Linked to case", 100)]


class DsaPanel(ttk.Frame):
    """``DsaPanel(master, auth)`` — staff casework or a student's own case."""

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self.case = None
        try:
            self.staff = access.scope(auth) is None
        except PermissionError as exc:
            ttk.Label(self, text=str(exc), wraplength=900).pack(padx=20, pady=20)
            return
        self.manager = self.staff and access.may_manage(auth)
        self._build_top()
        self._build_detail()
        self.refresh()

    # ------------------------------------------------------------- layout
    def _build_top(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        self.stats_var = tk.StringVar()
        ttk.Label(top, textvariable=self.stats_var, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        self.closed_var = tk.BooleanVar(value=not self.staff)
        if self.staff:
            ttk.Checkbutton(top, text="Show closed cases", variable=self.closed_var,
                            command=self.refresh).pack(side=tk.RIGHT, padx=8)
            ttk.Button(top, text="Open DSA case…", command=self.open_case,
                       state="normal" if self.manager else "disabled").pack(side=tk.RIGHT)
        frame, self.cases = make_tree(self, CASE_COLUMNS, height=6)
        frame.pack(fill=tk.X, pady=(6, 4))
        self.cases.bind("<<TreeviewSelect>>", lambda _e: self.load_case())

    def _build_detail(self):
        self.book = ttk.Notebook(self)
        self.book.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.tabs = {}
        for key, label in (("sfe", "SFE application"), ("assess", "Needs assessment"),
                           ("recs", "Recommendations"), ("nmh", "Non-medical help"),
                           ("equip", "Equipment"), ("exam", "Exam arrangements"),
                           ("adj", "Adjustments")):
            tab = ttk.Frame(self.book, padding=6)
            self.book.add(tab, text=label)
            self.tabs[key] = tab
        self._sfe_tab()
        self._assess_tab()
        self._recs_tab()
        self._nmh_tab()
        self._equip_tab()
        self._exam_tab()
        self._adj_tab()

    def _sfe_tab(self):
        tab = self.tabs["sfe"]
        button_bar(tab, (("Move to next stage…", self.change_status),
                         ("Edit case…", self.edit_case)), self.manager)
        self.sfe_text = scrolledtext.ScrolledText(tab, height=10, wrap=tk.WORD, state="disabled")
        self.sfe_text.pack(fill=tk.BOTH, expand=True)

    def _assess_tab(self):
        tab = self.tabs["assess"]
        button_bar(tab, (("Book needs assessment…", self.book_assessment),
                         ("Mark attended", lambda: self.attendance(True)),
                         ("Mark did not attend", lambda: self.attendance(False))), self.manager)
        frame, self.assess = make_tree(tab, ASSESS_COLUMNS)
        frame.pack(fill=tk.BOTH, expand=True)

    def _recs_tab(self):
        tab = self.tabs["recs"]
        button_bar(tab, (("Add recommendation…", self.add_rec),
                         ("Set status…", self.rec_status),
                         ("Make reasonable adjustment…", self.rec_adjustment)), self.manager)
        frame, self.recs = make_tree(tab, REC_COLUMNS)
        frame.pack(fill=tk.BOTH, expand=True)

    def _nmh_tab(self):
        tab = self.tabs["nmh"]
        button_bar(tab, (("Add support…", self.add_nmh), ("Log hours…", self.log_hours),
                         ("End support", self.end_nmh)), self.manager)
        frame, self.nmh = make_tree(tab, NMH_COLUMNS, height=5)
        frame.pack(fill=tk.X)
        self.nmh.bind("<<TreeviewSelect>>", lambda _e: self._show_log())
        ttk.Label(tab, text="Hours used (selected support)").pack(anchor="w", pady=(6, 0))
        frame, self.nmh_log = make_tree(tab, LOG_COLUMNS, height=6)
        frame.pack(fill=tk.BOTH, expand=True)

    def _equip_tab(self):
        tab = self.tabs["equip"]
        button_bar(tab, (("Add equipment…", self.add_equipment),
                         ("Set status…", self.equipment_status)), self.manager)
        frame, self.equip = make_tree(tab, EQUIP_COLUMNS)
        frame.pack(fill=tk.BOTH, expand=True)

    def _exam_tab(self):
        tab = self.tabs["exam"]
        button_bar(tab, (("Recommend arrangements…", self.recommend_exam),
                         ("Apply to exams", self.apply_exam),
                         ("Withdraw…", self.withdraw_exam)), self.manager)
        ttk.Label(tab, text="Applying creates an approved adjustment that Exams reads; exams "
                            "staff see the arrangements, never the reason.",
                  foreground="#555555").pack(anchor="w")
        frame, self.exam = make_tree(tab, EXAM_COLUMNS)
        frame.pack(fill=tk.BOTH, expand=True)

    def _adj_tab(self):
        tab = self.tabs["adj"]
        button_bar(tab, (("Link to this case", lambda: self.link(True)),
                         ("Unlink", lambda: self.link(False))), self.manager)
        frame, self.adj = make_tree(tab, ADJ_COLUMNS)
        frame.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------- data
    def refresh(self):
        try:
            rows = dsa.list_cases(self.auth, include_closed=self.closed_var.get())
            if self.staff:
                stats = dsa.statistics(self.auth)
                self.stats_var.set(f"Open cases: {stats['open']}    Non-medical help over "
                                   f"allocation: {stats['nmh_over_allocation']}")
            else:
                self.stats_var.set("Your DSA case (read-only — disability services keep it "
                                   "up to date)" if rows else
                                   "You have no DSA case. Ask disability services about "
                                   "applying for Disabled Students' Allowances.")
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        fill_tree(self.cases, rows, CASE_COLUMNS, key="case_id")
        if rows:
            self.cases.selection_set(str(rows[0]["case_id"]))
        else:
            self.case = None
            self._render()

    def load_case(self):
        sel = self.cases.selection()
        if not sel:
            return
        try:
            self.case = dsa.case_detail(self.auth, int(sel[0]))
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        self._render()

    def _reload(self):
        if self.case:
            try:
                self.case = dsa.case_detail(self.auth, self.case["case_id"])
            except Exception as exc:
                show_error(self, TITLE, exc)
        self._render()

    def _render(self):
        c = self.case or {}
        self.sfe_text.config(state="normal")
        self.sfe_text.delete("1.0", tk.END)
        if c:
            lines = [f"Case #{c['case_id']} — student {c['student_id']}",
                     f"Funding body: {c['funding_body_label']}",
                     f"Funding body reference: {c.get('sfe_reference') or '—'}",
                     f"Status: {c['status_label']}", ""]
            for status, column in dsa.STATUS_DATE_COLUMN.items():
                lines.append(f"  {dsa.STATUS_LABELS[status]}: {c.get(column) or '—'}")
            lines += ["", f"Notes: {c.get('notes') or '—'}", "", "History:"]
            lines += [f"  {h['changed_at']}  {h.get('from_status') or '—'} → {h['to_status']}"
                      f"  ({h.get('changed_by') or ''}) {h.get('note') or ''}"
                      for h in c.get("history", [])]
            self.sfe_text.insert("1.0", "\n".join(lines))
        else:
            self.sfe_text.insert("1.0", "Select a case.")
        self.sfe_text.config(state="disabled")
        for row in c.get("assessments", []):
            row["attended_label"] = {1: "Yes", 0: "No"}.get(row.get("attended"), "—")
        fill_tree(self.assess, c.get("assessments", []), ASSESS_COLUMNS)
        for row in c.get("recommendations", []):
            row["category_label"] = dsa.CATEGORY_LABELS.get(row["category"], row["category"])
        fill_tree(self.recs, c.get("recommendations", []), REC_COLUMNS)
        fill_tree(self.nmh, c.get("nmh", []), NMH_COLUMNS)
        fill_tree(self.nmh_log, [], LOG_COLUMNS)
        fill_tree(self.equip, c.get("equipment", []), EQUIP_COLUMNS)
        for row in c.get("exam_arrangements", []):
            row["summary"] = dsa.arrangement_text(row)
        fill_tree(self.exam, c.get("exam_arrangements", []), EXAM_COLUMNS)
        for row in c.get("adjustments", []):
            row["linked_label"] = "Yes" if row.get("linked") else ""
        fill_tree(self.adj, c.get("adjustments", []), ADJ_COLUMNS)

    def _show_log(self):
        sel = self.nmh.selection()
        support = next((s for s in (self.case or {}).get("nmh", [])
                        if sel and str(s["id"]) == sel[0]), None)
        fill_tree(self.nmh_log, support["log"] if support else [], LOG_COLUMNS)

    def _need_case(self):
        if not self.case:
            messagebox.showinfo(TITLE, "Select a case first.", parent=self)
            return False
        return True

    def _do(self, fn, *args, **kwargs):
        try:
            result = fn(self.auth, *args, **kwargs)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return None
        self._reload()
        return result if result is not None else True

    # ------------------------------------------------------------- actions
    def open_case(self):
        data = ask_form(self, "Open DSA case", [
            ("student_id", "Student number", "entry", ""),
            ("funding_body", "Funding body", "combo", (list(dsa.FUNDING_BODIES), "SFE")),
            ("sfe_reference", "Funding body reference", "entry", ""),
            ("notes", "Notes", "text", "")])
        if not data:
            return
        try:
            dsa.open_case(self.auth, data["student_id"], funding_body=data["funding_body"],
                          sfe_reference=data["sfe_reference"], notes=data["notes"])
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        self.refresh()

    def change_status(self):
        if not self._need_case():
            return
        options = [dsa.STATUS_LABELS[s] for s in dsa.next_statuses(self.case["status"])]
        if not options:
            messagebox.showinfo(TITLE, "This case is closed.", parent=self)
            return
        data = ask_form(self, "Move to next stage", [
            ("status", "New stage", "combo", (options, options[0])),
            ("on_date", "Date (YYYY-MM-DD, blank = today)", "entry", ""),
            ("note", "Note", "entry", "")])
        if not data:
            return
        status = next((k for k, v in dsa.STATUS_LABELS.items() if v == data["status"]), None)
        self._do(dsa.set_status, self.case["case_id"], status, on_date=data["on_date"],
                 note=data["note"])
        self.refresh()

    def edit_case(self):
        if not self._need_case():
            return
        data = ask_form(self, "Edit DSA case", [
            ("funding_body", "Funding body", "combo",
             (list(dsa.FUNDING_BODIES), self.case["funding_body"])),
            ("sfe_reference", "Funding body reference", "entry",
             self.case.get("sfe_reference") or ""),
            ("notes", "Notes", "text", self.case.get("notes") or "")])
        if data:
            self._do(dsa.update_case, self.case["case_id"], **data)

    def book_assessment(self):
        if not self._need_case():
            return
        data = ask_form(self, "Book needs assessment", [
            ("assessment_date", "Date (YYYY-MM-DD)", "entry", ""),
            ("assessment_time", "Time (HH:MM)", "entry", ""),
            ("centre", "Assessment centre", "entry", ""),
            ("assessor", "Assessor", "entry", ""),
            ("mode", "Mode", "combo", (["in person", "remote (video)", "telephone"],
                                        "in person")),
            ("notes", "Notes", "text", "")])
        if data:
            self._do(dsa.book_assessment, self.case["case_id"], **data)

    def attendance(self, attended):
        if not self._need_case():
            return
        aid = selected_id(self.assess, self, TITLE, "an assessment")
        if aid:
            self._do(dsa.record_attendance, aid, attended)

    def add_rec(self):
        if not self._need_case():
            return
        labels = [dsa.CATEGORY_LABELS[c] for c in dsa.CATEGORIES]
        data = ask_form(self, "Add recommendation", [
            ("category", "Category", "combo", (labels, labels[0])),
            ("text", "Recommendation (as in the DSA2 / needs assessment report)", "text", "")])
        if data:
            category = next((k for k, v in dsa.CATEGORY_LABELS.items()
                             if v == data["category"]), data["category"])
            self._do(dsa.add_recommendation, self.case["case_id"], category, data["text"])

    def rec_status(self):
        rid = selected_id(self.recs, self, TITLE, "a recommendation")
        if not rid:
            return
        data = ask_form(self, "Recommendation status", [
            ("status", "Status", "combo", (list(dsa.RECOMMENDATION_STATUSES), "in_progress"))])
        if data:
            self._do(dsa.set_recommendation_status, rid, data["status"])

    def rec_adjustment(self):
        rid = selected_id(self.recs, self, TITLE, "a reasonable-adjustment recommendation")
        if not rid:
            return
        from education_system.systems.university.domains.student_support.domain.disability import (
            portal,
        )
        types = list(portal.ACCOMMODATION_TYPES)
        data = ask_form(self, "Make reasonable adjustment", [
            ("accommodation_type", "Type of adjustment", "combo", (types, types[0] if types
                                                                   else "")),
            ("description", "Description (blank = the recommendation)", "text", ""),
            ("start_date", "Start (YYYY-MM-DD, blank = today)", "entry", ""),
            ("end_date", "End (YYYY-MM-DD, optional)", "entry", "")])
        if data:
            if self._do(dsa.adjustment_from_recommendation, rid, data["accommodation_type"],
                        description=data["description"] or None,
                        start_date=data["start_date"], end_date=data["end_date"]):
                messagebox.showinfo(TITLE, "The adjustment is approved and now applies.",
                                    parent=self)

    def add_nmh(self):
        if not self._need_case():
            return
        data = ask_form(self, "Add non-medical help", [
            ("support_type", "Type of support", "combo", (list(dsa.NMH_TYPES),
                                                          dsa.NMH_TYPES[0])),
            ("worker_name", "Support worker", "entry", ""),
            ("agency", "Agency / provider", "entry", ""),
            ("band", "Band", "combo", (list(dsa.NMH_BANDS), "")),
            ("hours_allocated", "Hours allocated", "entry", ""),
            ("start_date", "Start (YYYY-MM-DD)", "entry", ""),
            ("end_date", "End (YYYY-MM-DD)", "entry", "")])
        if data:
            self._do(dsa.add_nmh_support, self.case["case_id"], **data)

    def log_hours(self):
        sid = selected_id(self.nmh, self, TITLE, "a support arrangement")
        if not sid:
            return
        data = ask_form(self, "Log hours used", [
            ("session_date", "Session date (YYYY-MM-DD)", "entry", ""),
            ("hours", "Hours", "entry", ""), ("notes", "Notes", "entry", "")])
        if not data:
            return
        result = self._do(dsa.log_hours, sid, **data)
        if isinstance(result, dict) and result.get("over"):
            messagebox.showwarning(TITLE, f"This support is now {-result['remaining']} hours "
                                          "over its allocation. Ask the funding body to "
                                          "approve more hours.", parent=self)

    def end_nmh(self):
        sid = selected_id(self.nmh, self, TITLE, "a support arrangement")
        if sid and messagebox.askyesno(TITLE, "End this support arrangement?", parent=self):
            self._do(dsa.end_nmh_support, sid)

    def add_equipment(self):
        if not self._need_case():
            return
        data = ask_form(self, "Add equipment", [
            ("item", "Item", "entry", ""), ("supplier", "Supplier", "entry", ""),
            ("notes", "Notes", "entry", "")])
        if data:
            self._do(dsa.add_equipment, self.case["case_id"], data["item"],
                     supplier=data["supplier"], notes=data["notes"])

    def equipment_status(self):
        eid = selected_id(self.equip, self, TITLE, "an item")
        if not eid:
            return
        data = ask_form(self, "Equipment status", [
            ("status", "Status", "combo", (list(dsa.EQUIPMENT_STATUSES), "ordered")),
            ("on_date", "Date (YYYY-MM-DD, blank = today)", "entry", "")])
        if data:
            self._do(dsa.set_equipment_status, eid, data["status"], on_date=data["on_date"])

    def recommend_exam(self):
        if not self._need_case():
            return
        data = ask_form(self, "Recommend exam access arrangements", [
            ("extra_percent", "Extra time (%)", "entry", "25"),
            ("separate_room", "Separate room", "check", False),
            ("rest_breaks", "Rest breaks", "check", False),
            ("reader", "Reader", "check", False), ("scribe", "Scribe", "check", False),
            ("assistive_technology", "Assistive technology", "entry", ""),
            ("other", "Other", "entry", ""),
            ("valid_from", "Valid from (YYYY-MM-DD)", "entry", ""),
            ("valid_to", "Valid to (YYYY-MM-DD)", "entry", "")])
        if data:
            self._do(dsa.recommend_exam_arrangements, self.case["case_id"], **data)

    def apply_exam(self):
        xid = selected_id(self.exam, self, TITLE, "arrangements")
        if xid and messagebox.askyesno(TITLE, "Apply these arrangements to the student's "
                                              "exams?", parent=self):
            self._do(dsa.apply_exam_arrangements, xid)

    def withdraw_exam(self):
        xid = selected_id(self.exam, self, TITLE, "arrangements")
        if not xid:
            return
        data = ask_form(self, "Withdraw arrangements", [("reason", "Reason", "entry", "")])
        if data:
            self._do(dsa.withdraw_exam_arrangements, xid, data["reason"])

    def link(self, linked):
        if not self._need_case():
            return
        aid = selected_id(self.adj, self, TITLE, "an adjustment")
        if aid:
            self._do(dsa.link_adjustment, self.case["case_id"], aid, linked=linked)
