"""Tkinter dashboard for the Tier-4 / Student-Route sponsorship module.

A single Toplevel with four tabs:

* **Visa Record** — view/edit one student's visa profile, log right-to-
  study and ATAS, issue a CAS.
* **Engagement** — log a termly engagement check for the loaded student.
* **Changes** — list pending UKVI-reportable changes (overdue first),
  raise a new one, or mark one reported with a UKVI reference.
* **Expiry alerts** — system-wide list of visas/BRPs expiring soon, with
  a "send alert emails now" button.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domain.governance.compliance.international_compliance.services import visa_service as vs

logger = logging.getLogger(__name__)


_VISA_TYPES = ("student_route", "tier_4", "short_term_study", "graduate_route", "skilled_worker_dependant", "other")
_RTS_METHODS = ("In-person ID check", "IDVT (digital)", "Manual document scan")
_ENGAGEMENT_METHODS = ("Attendance ≥80%", "Tutor 1:1", "Submitted assessment", "Email reply", "Other")


class VisaComplianceGUI:
    def __init__(self, parent=None, student_id: str | None = None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Tier-4 / Student-Route Sponsorship")
        self.window.geometry("1200x780")
        self.window.minsize(1000, 700)

        try:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self.current_student_id = tk.StringVar(value=student_id or "")
        self._build_ui()
        if student_id:
            self._load_student()
        self._refresh_expiry_alerts()
        self._refresh_pending_coc()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Student ID:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.current_student_id, width=20).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Load", command=self._load_student).pack(side=tk.LEFT)
        ttk.Button(top, text="Save / Update Visa Record",
                   command=self._save_visa_record).pack(side=tk.LEFT, padx=12)
        ttk.Button(top, text="Issue Status Letter",
                   command=self._open_status_letter).pack(side=tk.LEFT)
        ttk.Button(top, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)

        nb = ttk.Notebook(self.window)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._build_visa_tab(nb)
        self._build_engagement_tab(nb)
        self._build_changes_tab(nb)
        self._build_alerts_tab(nb)

    def _build_visa_tab(self, nb):
        frame = ttk.Frame(nb, padding=10)
        nb.add(frame, text="Visa Record")

        self.visa_fields: dict[str, tk.Variable] = {}
        rows = [
            ("nationality", "Nationality"),
            ("passport_number", "Passport number"),
            ("passport_expiry", "Passport expiry (YYYY-MM-DD)"),
            ("visa_number", "Visa number"),
            ("visa_start_date", "Visa start (YYYY-MM-DD)"),
            ("visa_expiry_date", "Visa expiry (YYYY-MM-DD)"),
            ("brp_number", "BRP number"),
            ("brp_expiry_date", "BRP expiry (YYYY-MM-DD)"),
            ("sponsor_licence_ref", "Sponsor licence ref"),
        ]
        for r, (key, label) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky=tk.W, pady=3)
            v = tk.StringVar()
            ttk.Entry(frame, textvariable=v, width=36).grid(row=r, column=1, sticky=tk.W, padx=6)
            self.visa_fields[key] = v

        ttk.Label(frame, text="Visa type").grid(row=0, column=2, sticky=tk.W, padx=(40, 0))
        self.visa_fields["visa_type"] = tk.StringVar(value="student_route")
        ttk.Combobox(frame, textvariable=self.visa_fields["visa_type"], values=_VISA_TYPES,
                     state="readonly", width=24).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(frame, text="Status").grid(row=1, column=2, sticky=tk.W, padx=(40, 0))
        self.visa_fields["status"] = tk.StringVar(value="pending")
        ttk.Combobox(frame, textvariable=self.visa_fields["status"], values=vs.VISA_STATUSES,
                     state="readonly", width=24).grid(row=1, column=3, sticky=tk.W)

        self.visa_fields["atas_required"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="ATAS clearance required",
                        variable=self.visa_fields["atas_required"]).grid(row=2, column=2, columnspan=2, sticky=tk.W, padx=(40, 0))

        ttk.Label(frame, text="Notes").grid(row=3, column=2, sticky=tk.NW, padx=(40, 0))
        self.notes_text = tk.Text(frame, width=40, height=6)
        self.notes_text.grid(row=3, column=3, rowspan=4, sticky=tk.W)

        # Right-to-study quick log
        rts = ttk.LabelFrame(frame, text="Right-to-Study check", padding=8)
        rts.grid(row=len(rows), column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(14, 4))
        self.rts_method = tk.StringVar(value=_RTS_METHODS[0])
        self.rts_docs = tk.StringVar()
        ttk.Label(rts, text="Method").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(rts, textvariable=self.rts_method, values=_RTS_METHODS,
                     state="readonly", width=24).grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(rts, text="Documents seen").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Entry(rts, textvariable=self.rts_docs, width=42).grid(row=0, column=3, sticky=tk.W, padx=4)
        ttk.Button(rts, text="Record check", command=self._record_rts).grid(row=0, column=4, padx=8)
        self.rts_status_label = ttk.Label(rts, text="(none on file)")
        self.rts_status_label.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))

        # CAS issuance
        cas = ttk.LabelFrame(frame, text="Issue CAS", padding=8)
        cas.grid(row=len(rows) + 1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(8, 4))
        self.cas_fields = {
            "programme": tk.StringVar(),
            "course_start_date": tk.StringVar(),
            "course_end_date": tk.StringVar(),
            "tuition_fee_gbp": tk.StringVar(value="0"),
            "living_costs_gbp": tk.StringVar(value="0"),
        }
        for c, (key, label) in enumerate([
            ("programme", "Programme"),
            ("course_start_date", "Start (YYYY-MM-DD)"),
            ("course_end_date", "End (YYYY-MM-DD)"),
            ("tuition_fee_gbp", "Tuition £"),
            ("living_costs_gbp", "Living £"),
        ]):
            ttk.Label(cas, text=label).grid(row=0, column=c * 2, sticky=tk.W, padx=(4, 0))
            ttk.Entry(cas, textvariable=self.cas_fields[key], width=18).grid(row=0, column=c * 2 + 1, padx=2)
        ttk.Button(cas, text="Issue CAS", command=self._issue_cas).grid(row=0, column=10, padx=8)

        self.cas_list = ttk.Treeview(cas, columns=("cas", "issued", "programme", "fee", "status"),
                                     show="headings", height=4)
        for col, txt, w in [("cas", "CAS #", 160), ("issued", "Issued", 140),
                            ("programme", "Programme", 220), ("fee", "Tuition £", 90),
                            ("status", "Status", 80)]:
            self.cas_list.heading(col, text=txt)
            self.cas_list.column(col, width=w)
        self.cas_list.grid(row=1, column=0, columnspan=11, sticky=(tk.W, tk.E), pady=(8, 0))

    def _build_engagement_tab(self, nb):
        frame = ttk.Frame(nb, padding=10)
        nb.add(frame, text="Engagement")

        form = ttk.Frame(frame)
        form.pack(fill=tk.X)
        self.eng_term = tk.StringVar(value="Term 1")
        self.eng_method = tk.StringVar(value=_ENGAGEMENT_METHODS[0])
        self.eng_outcome = tk.StringVar(value="engaged")
        self.eng_evidence = tk.StringVar()
        ttk.Label(form, text="Term").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(form, textvariable=self.eng_term,
                     values=("Term 1", "Term 2", "Term 3", "Summer"),
                     state="readonly", width=12).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Method").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Combobox(form, textvariable=self.eng_method, values=_ENGAGEMENT_METHODS,
                     state="readonly", width=22).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Outcome").grid(row=0, column=4, sticky=tk.W, padx=(12, 0))
        ttk.Combobox(form, textvariable=self.eng_outcome,
                     values=("engaged", "partial", "missed"),
                     state="readonly", width=12).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Evidence").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Entry(form, textvariable=self.eng_evidence, width=70).grid(
            row=1, column=1, columnspan=4, sticky=(tk.W, tk.E), pady=(6, 0))
        ttk.Button(form, text="Log check", command=self._log_engagement).grid(
            row=1, column=5, padx=4, pady=(6, 0))
        ttk.Button(form, text="Pull from attendance",
                   command=self._pull_engagement_from_attendance).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        self.engagement_pull_status = ttk.Label(form, text="", foreground="#555555")
        self.engagement_pull_status.grid(row=2, column=2, columnspan=4, sticky=tk.W,
                                          pady=(8, 0), padx=(8, 0))

        ttk.Label(frame, text="History (most recent first — rows from attendance show source pipeline in Method)",
                  font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(14, 4))
        self.engagement_tree = ttk.Treeview(
            frame, columns=("date", "term", "method", "outcome", "evidence"),
            show="headings", height=10,
        )
        for col, txt, w in [("date", "Date", 110), ("term", "Term", 90),
                            ("method", "Method", 240), ("outcome", "Outcome", 100),
                            ("evidence", "Evidence", 560)]:
            self.engagement_tree.heading(col, text=txt)
            self.engagement_tree.column(col, width=w)
        self.engagement_tree.pack(fill=tk.BOTH, expand=True)

        risk_label_row = ttk.Frame(frame)
        risk_label_row.pack(fill=tk.X, pady=(14, 4))
        ttk.Label(risk_label_row,
                  text="At-risk international students (attendance < threshold, from the attendance pipeline)",
                  font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        self.atrisk_threshold = tk.DoubleVar(value=80.0)
        ttk.Label(risk_label_row, text="  Threshold %:").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Spinbox(risk_label_row, from_=50, to=100, increment=5,
                    textvariable=self.atrisk_threshold, width=6).pack(side=tk.LEFT)
        ttk.Button(risk_label_row, text="Refresh",
                   command=self._refresh_at_risk).pack(side=tk.LEFT, padx=6)
        ttk.Button(risk_label_row, text="Load selected into form",
                   command=self._load_selected_at_risk).pack(side=tk.LEFT)

        self.atrisk_tree = ttk.Treeview(
            frame, columns=("student", "name", "pct", "missed"),
            show="headings", height=8,
        )
        for col, txt, w in [("student", "Student", 110), ("name", "Name", 260),
                            ("pct", "Attendance %", 110), ("missed", "Missed sessions", 130)]:
            self.atrisk_tree.heading(col, text=txt)
            self.atrisk_tree.column(col, width=w)
        self.atrisk_tree.pack(fill=tk.BOTH, expand=False)
        self._refresh_at_risk()

    def _build_changes_tab(self, nb):
        frame = ttk.Frame(nb, padding=10)
        nb.add(frame, text="Changes (UKVI)")

        form = ttk.LabelFrame(frame, text="Raise a Change of Circumstance", padding=8)
        form.pack(fill=tk.X)
        self.coc_type = tk.StringVar(value=vs.COC_TYPES[0])
        self.coc_details = tk.StringVar()
        ttk.Label(form, text="Type").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(form, textvariable=self.coc_type, values=vs.COC_TYPES,
                     state="readonly", width=22).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Details").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Entry(form, textvariable=self.coc_details, width=70).grid(row=0, column=3, padx=4)
        ttk.Button(form, text="Log change", command=self._log_coc).grid(row=0, column=4, padx=6)

        ttk.Label(frame, text="Pending UKVI reports (overdue rows highlighted)",
                  font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(14, 4))
        self.coc_tree = ttk.Treeview(
            frame, columns=("id", "student", "type", "occurred", "due", "details"),
            show="headings", height=12,
        )
        for col, txt, w in [("id", "ID", 50), ("student", "Student", 120),
                            ("type", "Type", 160), ("occurred", "Occurred", 100),
                            ("due", "UKVI due", 100), ("details", "Details", 580)]:
            self.coc_tree.heading(col, text=txt)
            self.coc_tree.column(col, width=w)
        self.coc_tree.tag_configure("overdue", background="#ffe2e2")
        self.coc_tree.pack(fill=tk.BOTH, expand=True)

        action = ttk.Frame(frame)
        action.pack(fill=tk.X, pady=(8, 0))
        self.coc_ref = tk.StringVar()
        ttk.Label(action, text="UKVI report ref:").pack(side=tk.LEFT)
        ttk.Entry(action, textvariable=self.coc_ref, width=22).pack(side=tk.LEFT, padx=4)
        ttk.Button(action, text="Mark selected as reported",
                   command=self._mark_coc_reported).pack(side=tk.LEFT)
        ttk.Button(action, text="Refresh",
                   command=self._refresh_pending_coc).pack(side=tk.RIGHT)

    def _build_alerts_tab(self, nb):
        frame = ttk.Frame(nb, padding=10)
        nb.add(frame, text="Expiry alerts")

        ctrl = ttk.Frame(frame)
        ctrl.pack(fill=tk.X)
        self.alert_threshold = tk.IntVar(value=90)
        ttk.Label(ctrl, text="Threshold (days):").pack(side=tk.LEFT)
        ttk.Spinbox(ctrl, from_=7, to=365, increment=7,
                    textvariable=self.alert_threshold, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="Refresh", command=self._refresh_expiry_alerts).pack(side=tk.LEFT, padx=6)
        ttk.Button(ctrl, text="Send alert emails now",
                   command=self._send_alert_emails).pack(side=tk.LEFT)

        self.alerts_tree = ttk.Treeview(
            frame, columns=("student", "nationality", "visa", "visa_exp", "brp", "brp_exp", "status"),
            show="headings", height=18,
        )
        for col, txt, w in [("student", "Student", 100), ("nationality", "Nationality", 110),
                            ("visa", "Visa #", 130), ("visa_exp", "Visa expiry", 110),
                            ("brp", "BRP #", 130), ("brp_exp", "BRP expiry", 110),
                            ("status", "Status", 100)]:
            self.alerts_tree.heading(col, text=txt)
            self.alerts_tree.column(col, width=w)
        self.alerts_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _sid(self) -> str:
        return self.current_student_id.get().strip()

    def _load_student(self):
        sid = self._sid()
        if not sid:
            return
        rec = vs.get_visa_record(sid)
        for k, var in self.visa_fields.items():
            if k == "atas_required":
                var.set(bool(rec.get(k)) if rec else False)
            else:
                var.set((rec.get(k) if rec else "") or "")
        self.notes_text.delete("1.0", tk.END)
        if rec and rec.get("notes"):
            self.notes_text.insert("1.0", rec["notes"])

        self.rts_status_label.config(
            text=("Right-to-study: pass on file"
                  if vs.has_passing_right_to_study(sid)
                  else "Right-to-study: NO check on file"),
            foreground=("green" if vs.has_passing_right_to_study(sid) else "red"),
        )

        self.cas_list.delete(*self.cas_list.get_children())
        for c in vs.list_cas_for_student(sid):
            self.cas_list.insert("", tk.END, values=(
                c.get("cas_number", ""), c.get("issued_at", ""), c.get("programme", ""),
                c.get("tuition_fee_gbp", 0), c.get("status", ""),
            ))

        self.engagement_tree.delete(*self.engagement_tree.get_children())
        for e in vs.list_engagement_checks(sid):
            self.engagement_tree.insert("", tk.END, values=(
                e.get("check_date", ""), e.get("term", ""), e.get("method", ""),
                e.get("outcome", ""), e.get("evidence", "") or "",
            ))

    def _save_visa_record(self):
        sid = self._sid()
        if not sid:
            messagebox.showwarning("Missing", "Enter a student ID first.")
            return
        rec = vs.VisaRecord(
            student_id=sid,
            nationality=self.visa_fields["nationality"].get() or None,
            passport_number=self.visa_fields["passport_number"].get() or None,
            passport_expiry=self.visa_fields["passport_expiry"].get() or None,
            visa_type=self.visa_fields["visa_type"].get() or "student_route",
            visa_number=self.visa_fields["visa_number"].get() or None,
            visa_start_date=self.visa_fields["visa_start_date"].get() or None,
            visa_expiry_date=self.visa_fields["visa_expiry_date"].get() or None,
            brp_number=self.visa_fields["brp_number"].get() or None,
            brp_expiry_date=self.visa_fields["brp_expiry_date"].get() or None,
            sponsor_licence_ref=self.visa_fields["sponsor_licence_ref"].get() or None,
            atas_required=bool(self.visa_fields["atas_required"].get()),
            status=self.visa_fields["status"].get() or "pending",
            notes=self.notes_text.get("1.0", tk.END).strip() or None,
        )
        try:
            vs.upsert_visa_record(rec)
            messagebox.showinfo("Saved", f"Visa record saved for {sid}.")
        except Exception as exc:
            logger.exception("save visa")
            messagebox.showerror("Error", str(exc))

    def _record_rts(self):
        sid = self._sid()
        if not sid:
            return
        try:
            vs.record_right_to_study_check(
                sid,
                method=self.rts_method.get(),
                documents_seen=self.rts_docs.get().strip() or "(unspecified)",
                checked_by=self._user_id(),
            )
            self._load_student()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _open_status_letter(self):
        """Open the Status Letters GUI pre-filled for the loaded student.

        Defaults to a UKVI / Student Route letter type, which is the
        common reason a sponsor compliance officer drops in here."""
        sid = self._sid()
        if not sid:
            messagebox.showwarning(
                "Status Letter", "Load a student first."
            )
            return
        try:
            from education_system.systems.university.interfaces.gui.pastoral.student_app.documentation.documentation_gui import DocumentationGUI
            DocumentationGUI(
                parent=self.window,
                auth=self.auth,
                prefill_student_id=sid,
                prefill_letter_type="visa",
                prefill_purpose="UKVI / Student Route status letter requested via Visa Sponsorship dashboard",
            )
        except Exception as exc:
            logger.error("Failed to open Status Letters GUI: %s", exc)
            messagebox.showerror("Error", f"Could not open Status Letters: {exc}")

    def _issue_cas(self):
        sid = self._sid()
        if not sid:
            return
        try:
            tuition = float(self.cas_fields["tuition_fee_gbp"].get() or 0)
            living = float(self.cas_fields["living_costs_gbp"].get() or 0)
            cas = vs.issue_cas(
                student_id=sid,
                programme=self.cas_fields["programme"].get(),
                course_start_date=self.cas_fields["course_start_date"].get(),
                course_end_date=self.cas_fields["course_end_date"].get(),
                tuition_fee_gbp=tuition,
                living_costs_gbp=living,
                issued_by=self._user_id(),
            )
            email, first = self._student_contact(sid)
            if email:
                vs.notify_cas_issued(sid, email, cas, first_name=first)
            self._load_student()
            messagebox.showinfo("Issued", f"CAS {cas['cas_number']} issued.")
        except Exception as exc:
            logger.exception("issue cas")
            messagebox.showerror("Error", str(exc))

    def _pull_engagement_from_attendance(self):
        sid = self._sid()
        try:
            n = vs.import_attendance_engagement_events(student_id=sid or None)
        except Exception as exc:
            logger.exception("import attendance")
            messagebox.showerror("Error", str(exc))
            return
        scope = f"for {sid}" if sid else "across all students"
        self.engagement_pull_status.config(
            text=f"Imported {n} new event(s) from attendance {scope}.",
            foreground=("green" if n else "#555555"),
        )
        if sid:
            self._load_student()

    def _refresh_at_risk(self):
        try:
            rows = vs.get_attendance_at_risk(min_pct=float(self.atrisk_threshold.get() or 80))
        except Exception:
            logger.exception("at-risk")
            rows = []
        self.atrisk_tree.delete(*self.atrisk_tree.get_children())
        for r in rows:
            self.atrisk_tree.insert("", tk.END, values=(
                r["student_id"], r["name"],
                r["attendance_pct"], r["missed_sessions"],
            ))

    def _load_selected_at_risk(self):
        sel = self.atrisk_tree.selection()
        if not sel:
            messagebox.showinfo("Pick one", "Select a row first.")
            return
        sid = self.atrisk_tree.item(sel[0])["values"][0]
        self.current_student_id.set(str(sid))
        self._load_student()

    def _log_engagement(self):
        sid = self._sid()
        if not sid:
            return
        try:
            vs.record_engagement_check(
                student_id=sid,
                term=self.eng_term.get(),
                method=self.eng_method.get(),
                outcome=self.eng_outcome.get(),
                evidence=self.eng_evidence.get().strip() or None,
                recorded_by=self._user_id(),
            )
            self._load_student()
            self._refresh_pending_coc()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _log_coc(self):
        sid = self._sid()
        if not sid:
            return
        try:
            coc_id = vs.log_change_of_circumstance(
                student_id=sid,
                change_type=self.coc_type.get(),
                details=self.coc_details.get().strip() or None,
                recorded_by=self._user_id(),
            )
            email, first = self._student_contact(sid)
            if email:
                pending = [c for c in vs.list_pending_coc() if c["id"] == coc_id]
                if pending:
                    vs.notify_change_of_circumstance(sid, email, pending[0], first_name=first)
            self.coc_details.set("")
            self._refresh_pending_coc()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _mark_coc_reported(self):
        sel = self.coc_tree.selection()
        if not sel:
            messagebox.showinfo("Pick one", "Select a row first.")
            return
        ref = self.coc_ref.get().strip()
        if not ref:
            messagebox.showwarning("Missing ref", "Enter the UKVI report reference first.")
            return
        coc_id = int(self.coc_tree.item(sel[0])["values"][0])
        if vs.mark_coc_reported(coc_id, ref):
            self.coc_ref.set("")
            self._refresh_pending_coc()
        else:
            messagebox.showerror("Error", "No matching pending CoC row.")

    def _refresh_pending_coc(self):
        from datetime import date
        self.coc_tree.delete(*self.coc_tree.get_children())
        today = date.today().isoformat()
        for c in vs.list_pending_coc():
            tags = ("overdue",) if c.get("ukvi_report_due") and c["ukvi_report_due"] < today else ()
            self.coc_tree.insert("", tk.END, values=(
                c["id"], c["student_id"], c["change_type"],
                c["occurred_on"], c.get("ukvi_report_due", ""), c.get("details", "") or "",
            ), tags=tags)

    def _refresh_expiry_alerts(self):
        self.alerts_tree.delete(*self.alerts_tree.get_children())
        for v in vs.list_expiring_visas(within_days=int(self.alert_threshold.get() or 90)):
            self.alerts_tree.insert("", tk.END, values=(
                v["student_id"], v.get("nationality") or "",
                v.get("visa_number") or "", v.get("visa_expiry_date") or "",
                v.get("brp_number") or "", v.get("brp_expiry_date") or "",
                v.get("status") or "",
            ))

    def _send_alert_emails(self):
        try:
            n = vs.run_visa_expiry_alerts(threshold_days=int(self.alert_threshold.get() or 90))
            messagebox.showinfo("Alerts sent", f"Sent {n} visa-expiry email(s).")
        except Exception as exc:
            logger.exception("send alerts")
            messagebox.showerror("Error", str(exc))

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def _user_id(self):
        if self.auth and getattr(self.auth, "current_user", None):
            u = self.auth.current_user
            if isinstance(u, dict):
                return u.get("id") or u.get("user_id")
            return getattr(u, "id", None)
        return None

    def _student_contact(self, sid: str) -> tuple[str, str]:
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT email_address, first_name FROM students WHERE student_id = ?",
                    (sid,),
                ).fetchone()
            if not row:
                return "", ""
            if isinstance(row, tuple):
                return row[0] or "", row[1] or ""
            return row["email_address"] or "", row["first_name"] or ""
        except Exception:
            return "", ""
