"""Health Portal screens for the features that only the health CLI had.

Vital signs, insurance (and insurer verifications), health advisories,
disease surveillance and outbreak investigations, risk assessment, quality
assurance, data retention, backup and recovery, record templates, the
student health dashboard, the drug interaction table and personal metrics.

Each screen is a panel in the style of ``clinical_panels`` (``Panel(parent,
auth, get_connection=None)``) and is backed by the same domain services the
CLI uses — the non-interactive helpers next to each CLI function (for
example ``services/vitals.record_vitals`` beside ``record_vital_signs``), or
the application modules (``application/health/retention``, ``prescribing``,
``personal_metrics``, ``integrations``, ``diary``). Nothing here writes SQL
of its own except the read-only summary on the dashboard.

Access follows ``application/health/access`` through ``access_ui``: every
list is scoped (the health team sees whoever they filter on, a student only
themselves, anyone else is refused or offered break-glass) and every view is
audited, refused when the audit entry cannot be written. Writes are audited
by the domain helpers in the same transaction, and are limited to the health
team wherever the CLI limits them.
"""

from __future__ import annotations

import contextlib
import io
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext

from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import (
    messagebox, simpledialog,
)
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import (
    access_ui,
)
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.clinical_panels import (
    _ClinicalPanelBase,
)

logger = logging.getLogger(__name__)


def _must(done, message):
    """``done`` when truthy; otherwise a ``ValueError`` (rolls the write back
    and is shown to the user)."""
    if not done:
        raise ValueError(message)
    return done


def _selection(tree):
    """The first value (the id column) of the selected row, or ``None``."""
    chosen = tree.selection() if tree is not None else ()
    if not chosen:
        return None
    values = tree.item(chosen[0], "values")
    return values[0] if values else None


class _ParityPanel(_ClinicalPanelBase):
    """``_ClinicalPanelBase`` plus a transaction helper and the signed-in
    person as ``access.HealthUser``."""

    @property
    def who(self):
        return access_ui.who(self.auth)

    @property
    def username(self):
        person = self.who
        return person.username if person else None

    def _run(self, fn, *, commit=False):
        """``fn(conn)`` on a fresh connection; commits when asked, rolls
        back on any error (and re-raises)."""
        conn = self._conn()
        try:
            result = fn(conn)
            if commit:
                conn.commit()
            return result
        except Exception:
            try:
                conn.rollback()
            except Exception:
                logger.debug("rollback failed", exc_info=True)
            raise
        finally:
            conn.close()

    def _write(self, fn, success=None):
        """Run a write; show the domain's own message on a refusal."""
        try:
            result = self._run(fn, commit=True)
        except (PermissionError, ValueError, LookupError) as exc:
            self._err(str(exc))
            return None
        except Exception as exc:
            logger.exception("%s: write failed", self.title)
            self._err(f"Nothing was saved: {exc}")
            return None
        if success:
            self._info(success(result) if callable(success) else success)
        return result

    def _audit_view(self, student_id=None) -> bool:
        return access_ui.record_view(self.parent, self.auth, self.title, student_id=student_id)

    def _bar(self, parent=None):
        bar = ttk.Frame(parent or self.parent)
        bar.pack(fill=tk.X, padx=10, pady=(0, 6))
        return bar

    def _text_box(self, parent=None, height=12):
        box = scrolledtext.ScrolledText(parent or self.parent, height=height, wrap="word",
                                        font=("Consolas", 10))
        box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        return box

    @staticmethod
    def _show_text(box, text):
        box.configure(state="normal")
        box.delete("1.0", tk.END)
        box.insert("1.0", text)
        box.configure(state="disabled")


# --------------------------------------------------------------------------
# Vital signs
# --------------------------------------------------------------------------
class VitalSignsPanel(_ParityPanel):
    title = "Vital Signs"

    def build(self):
        from education_system.systems.university.domains.health.domain.health.services import vitals
        self.vitals = vitals
        self._header()
        if access_ui.is_clinician(self.auth):
            form = ttk.LabelFrame(self.parent, text="Record vital signs", padding=10)
            form.pack(fill=tk.X, padx=10, pady=(0, 6))
            left, right = ttk.Frame(form), ttk.Frame(form)
            left.pack(side=tk.LEFT, anchor="n")
            right.pack(side=tk.LEFT, anchor="n", padx=(20, 0))
            self._build_form(left, [
                {"key": "student_id", "label": "Student ID:"},
                {"key": "measurement_date", "label": "Date (YYYY-MM-DD):", "kind": "date"},
                {"key": "systolic", "label": "BP systolic (mmHg):", "width": 10},
                {"key": "diastolic", "label": "BP diastolic (mmHg):", "width": 10},
            ])
            self._build_form(right, [
                {"key": "heart_rate", "label": "Heart rate (bpm):", "width": 10},
                {"key": "temperature", "label": "Temperature (°F):", "width": 10},
                {"key": "weight", "label": "Weight (lb):", "width": 10},
                {"key": "height", "label": "Height (in):", "width": 10},
                {"key": "notes", "label": "Notes:"},
            ])
            ttk.Button(form, text="Save vital signs", command=self.add).pack(
                side=tk.LEFT, anchor="s", padx=20)
        self._search_row(self.parent)
        bar = self._bar()
        ttk.Button(bar, text="Trends (12 months)", command=self.trends).pack(side=tk.LEFT)
        self.alert_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.alert_var, foreground="#b03a2e").pack(
            side=tk.LEFT, padx=10)
        self._make_tree([("ID", 50), ("Student", 90), ("Date", 95), ("BP", 80), ("HR", 50),
                         ("Temp", 60), ("Weight", 65), ("BMI", 55), ("By", 100),
                         ("Alerts", 260)])
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("Only the health team can record vital signs.")
            return
        values = {k: self._form_value(k) for k in (
            "student_id", "measurement_date", "systolic", "diastolic", "heart_rate",
            "temperature", "weight", "height", "notes")}

        def save(conn):
            return self.vitals.record_vitals(conn, recorded_by=self.username, **values)

        result = self._write(save)
        if result:
            vid, alerts = result
            self._info(f"Vital signs saved (#{vid})." +
                       ("\n\nAlerts:\n- " + "\n- ".join(alerts) if alerts else ""))
            self.vars["_search_student"].set(values["student_id"])
            self.refresh()

    def refresh(self):
        self._clear_tree()
        sid = self._scoped_sid()
        if sid is None:
            return
        try:
            rows = self._run(lambda conn: self.vitals.list_vitals(conn, sid or None))
        except Exception as exc:
            self._err(f"Could not load vital signs: {exc}")
            return
        flagged = 0
        for r in rows:
            bp = (f"{r['blood_pressure_systolic']}/{r['blood_pressure_diastolic']}"
                  if r["blood_pressure_systolic"] and r["blood_pressure_diastolic"] else "")
            flagged += bool(r["alerts"])
            self.tree.insert("", tk.END, values=(
                r["id"], r["student_id"], r["measurement_date"], bp, r["heart_rate"] or "",
                r["temperature"] or "", r["weight"] or "", r["bmi"] or "",
                r["recorded_by"] or "", "; ".join(r["alerts"])))
        self.alert_var.set(f"{flagged} reading(s) outside normal ranges" if flagged else "")

    def trends(self):
        sid = self._scoped_sid()
        if not sid:
            self._err("Enter a student ID to see trends.")
            return
        try:
            data = self._run(lambda conn: self.vitals.vitals_trends(conn, sid))
        except Exception as exc:
            self._err(f"Could not work out trends: {exc}")
            return
        if not data["count"]:
            self._info(f"No vital signs for {sid} in the last 12 months.")
            return
        lines = [f"{data['count']} measurement(s), {data['from']} to {data['to']}", ""]
        for label, m in data["measures"].items():
            lines.append(f"{label}: average {m['average']}, range {m['lowest']}–{m['highest']}, "
                         f"latest {m['latest']} (change {m['change']:+})")
        messagebox.showinfo(f"Vital sign trends — {sid}", "\n".join(lines), parent=self.parent)


# --------------------------------------------------------------------------
# Insurance + verification history
# --------------------------------------------------------------------------
class InsurancePanel(_ParityPanel):
    title = "Insurance Information"

    def build(self):
        from education_system.systems.university.domains.health.domain.health.records.student import (
            insurance,
        )
        from education_system.systems.university.domains.health.application.health import (
            integrations,
        )
        self.insurance, self.integrations = insurance, integrations
        self._header()
        self._search_row(self.parent)
        form = ttk.LabelFrame(self.parent, text="Add or update a policy", padding=10)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        left, right = ttk.Frame(form), ttk.Frame(form)
        left.pack(side=tk.LEFT, anchor="n")
        right.pack(side=tk.LEFT, anchor="n", padx=(20, 0))
        self._build_form(left, [
            {"key": "insurance_provider", "label": "Provider:"},
            {"key": "policy_number", "label": "Policy number:"},
            {"key": "group_number", "label": "Group number:"},
            {"key": "subscriber_name", "label": "Subscriber:"},
        ])
        self._build_form(right, [
            {"key": "relationship_to_subscriber", "label": "Relationship:", "kind": "combo",
             "values": list(insurance.RELATIONSHIPS)},
            {"key": "effective_date", "label": "Effective (YYYY-MM-DD):", "kind": "date"},
            {"key": "expiry_date", "label": "Expiry (YYYY-MM-DD):"},
        ])
        buttons = ttk.Frame(form)
        buttons.pack(side=tk.LEFT, anchor="s", padx=20)
        ttk.Button(buttons, text="Add policy", command=lambda: self.save(False)).pack(fill=tk.X)
        ttk.Button(buttons, text="Update selected", command=lambda: self.save(True)).pack(
            fill=tk.X, pady=(4, 0))
        bar = self._bar()
        if access_ui.is_clinician(self.auth):
            ttk.Button(bar, text="Record insurer verification…",
                       command=self.verify).pack(side=tk.LEFT)
        ttk.Label(bar, text="Policies (top) and verification history (bottom)",
                  foreground="#555555").pack(side=tk.LEFT, padx=10)
        self._make_tree([("ID", 50), ("Provider", 160), ("Policy", 110), ("Group", 90),
                         ("Subscriber", 130), ("Relationship", 90), ("Effective", 90),
                         ("Expiry", 90), ("Status", 100)])
        self.policies = self.tree
        self.policies.configure(height=6)
        self.policies.bind("<<TreeviewSelect>>", lambda _e: self._fill_form())
        self._make_tree([("ID", 50), ("When", 140), ("Outcome", 90), ("Reference", 110),
                         ("By", 100), ("Provider", 140), ("Policy", 100), ("Notes", 220)])
        self.history = self.tree
        self.history.configure(height=6)
        self.tree = self.policies
        self.rows = []
        self.refresh()

    def _sid_for_write(self):
        own = access_ui.own_student_id(self.auth)
        if own:
            return own
        sid = self.vars["_search_student"].get().strip()
        if not sid:
            self._err("Enter the student ID in the filter first.")
            return None
        return sid

    def _fill_form(self):
        chosen = _selection(self.policies)
        row = next((r for r in self.rows if str(r["id"]) == str(chosen)), None)
        if not row:
            return
        for key in self.insurance.INSURANCE_FIELDS:
            if key in self.vars:
                self.vars[key].set(row.get(key) or "")

    def save(self, update):
        if not (access_ui.is_clinician(self.auth) or access_ui.own_student_id(self.auth)):
            self._err("Insurance details are kept by the health team or the student.")
            return
        sid = self._sid_for_write()
        if not sid:
            return
        insurance_id = _selection(self.policies) if update else None
        if update and not insurance_id:
            self._err("Select the policy to update.")
            return
        values = {k: self._form_value(k) for k in self.insurance.INSURANCE_FIELDS}
        user_id = self._user_id() or self.username
        if self._write(lambda conn: self.insurance.save_insurance(
                conn, sid, values, by_user_id=user_id, insurance_id=insurance_id),
                "Insurance information saved."):
            self.refresh()

    def verify(self):
        if not access_ui.require_clinician(self.parent, self.auth, "record insurer verifications"):
            return
        sid = self._sid_for_write()
        if not sid:
            return
        outcome = simpledialog.askstring(
            self.title, "Insurer's answer — one of: "
                        + ", ".join(self.integrations.VERIFICATION_OUTCOMES), parent=self.parent)
        if not outcome:
            return
        reference = simpledialog.askstring(self.title, "Insurer reference (optional):",
                                           parent=self.parent)
        notes = simpledialog.askstring(self.title, "Notes (how verified, who you spoke to):",
                                       parent=self.parent)
        if self._write(lambda conn: self.integrations.record_insurance_verification(
                conn, student_id=sid, outcome=outcome.strip().lower(), by=self.username,
                reference=reference, notes=notes), "Verification recorded."):
            self.refresh()

    def refresh(self):
        for tree in (getattr(self, "policies", None), getattr(self, "history", None)):
            if tree is not None:
                for item in tree.get_children():
                    tree.delete(item)
        sid = self._scoped_sid()
        if sid is None:
            return
        if not sid:
            self.policies.insert("", tk.END, values=("", "Enter a student ID and press Refresh",
                                                     "", "", "", "", "", "", ""))
            return
        try:
            self.rows = self._run(lambda conn: self.insurance.list_insurance(conn, sid))
            checks = self._run(lambda conn: self.integrations.insurance_verifications(conn, sid))
        except Exception as exc:
            self._err(f"Could not load insurance information: {exc}")
            return
        for r in self.rows:
            self.policies.insert("", tk.END, values=(
                r["id"], r["insurance_provider"] or "", r["policy_number"] or "",
                r["group_number"] or "", r["subscriber_name"] or "",
                r["relationship_to_subscriber"] or "", r["effective_date"] or "",
                r["expiry_date"] or "", r["status"].upper()))
        for v in checks:
            self.history.insert("", tk.END, values=(
                v["id"], v["at"], v["outcome"], v["reference"] or "", v["by"] or "",
                v["provider"] or "", v["policy_number"] or "", v["notes"] or ""))


# --------------------------------------------------------------------------
# Health advisories
# --------------------------------------------------------------------------
class AdvisoriesPanel(_ParityPanel):
    title = "Health Advisories"

    def build(self):
        from education_system.systems.university.domains.health.domain.health.records.admin import (
            advisories,
        )
        self.adv = advisories
        self.can_issue = self._can_issue()
        self._header()
        if self.can_issue:
            form = ttk.LabelFrame(self.parent, text="Issue an advisory", padding=10)
            form.pack(fill=tk.X, padx=10, pady=(0, 6))
            left, right = ttk.Frame(form), ttk.Frame(form)
            left.pack(side=tk.LEFT, anchor="n")
            right.pack(side=tk.LEFT, anchor="n", padx=(20, 0))
            self._build_form(left, [
                {"key": "title", "label": "Title:", "width": 40},
                {"key": "content", "label": "Advisory text:", "kind": "text", "height": 4},
            ])
            self._build_form(right, [
                {"key": "advisory_type", "label": "Type:", "kind": "combo",
                 "values": list(advisories.ADVISORY_TYPES)},
                {"key": "priority", "label": "Priority:", "kind": "combo",
                 "values": list(advisories.PRIORITIES)},
                {"key": "target_audience", "label": "Audience:", "kind": "combo",
                 "values": list(advisories.AUDIENCES)},
                {"key": "effective_date", "label": "Effective (YYYY-MM-DD):", "kind": "date"},
                {"key": "expiry_date", "label": "Expiry (blank = none):"},
            ])
            ttk.Button(form, text="Issue and notify", command=self.issue).pack(
                side=tk.LEFT, anchor="s", padx=20)
        bar = self._bar()
        ttk.Label(bar, text="Show:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="Published now")
        choices = ["Published now"] if not self.can_issue else [
            "Published now", "All active", "Last 30 days", "All (incl. expired)"]
        ttk.Combobox(bar, textvariable=self.filter_var, values=choices, state="readonly",
                     width=18).pack(side=tk.LEFT, padx=5)
        ttk.Label(bar, text="Priority:").pack(side=tk.LEFT, padx=(10, 0))
        self.priority_var = tk.StringVar(value="Any")
        ttk.Combobox(bar, textvariable=self.priority_var, state="readonly", width=10,
                     values=["Any"] + list(advisories.PRIORITIES)).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=5)
        if self.can_issue:
            ttk.Button(bar, text="Expire selected", command=self.expire).pack(side=tk.LEFT)
        self._make_tree([("ID", 50), ("Title", 240), ("Type", 140), ("Priority", 80),
                         ("Audience", 130), ("Effective", 90), ("Expires", 90),
                         ("Issued by", 100), ("Status", 70)])
        self.tree.configure(height=8)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_selected())
        self.content_box = self._text_box(height=6)
        self.rows = []
        self.refresh()

    def _can_issue(self):
        try:
            return bool(self.auth.check_permission("issue_health_advisories"))
        except Exception:
            return False

    def issue(self):
        if not self._can_issue():
            self._err("You don't have permission to issue health advisories.")
            return
        values = {k: self._form_value(k) for k in (
            "title", "advisory_type", "content", "priority", "target_audience",
            "effective_date", "expiry_date")}

        def save(conn):
            advisory_id = self.adv.issue_advisory(conn, issued_by=self.username,
                                                  by_user_id=self._user_id(), **values)
            return advisory_id, self.adv.advisory_recipients(conn, values["target_audience"])

        result = self._write(save)
        if not result:
            return
        advisory_id, recipients = result
        queued, failed = self.adv.notify_advisory(recipients, values["title"], values["content"],
                                                  values["priority"])
        from education_system.systems.university.domains.health.application.health import notices
        self._info(f"Advisory #{advisory_id} issued.\n\nNotices queued: {queued}"
                   + (f", not queued: {failed}" if failed else "") + "\n\n"
                   + notices.delivery_note())
        self.refresh()

    def expire(self):
        advisory_id = _selection(self.tree)
        if not advisory_id:
            self._err("Select an advisory to expire.")
            return
        if not messagebox.askyesno(self.title, f"Expire advisory #{advisory_id} now? Students "
                                               "will no longer see it.", parent=self.parent):
            return
        if self._write(lambda conn: _must(self.adv.expire_advisory(
                conn, advisory_id, by=self.username, by_user_id=self._user_id()),
                "That advisory is not active"), "Advisory expired."):
            self.refresh()

    def _show_selected(self):
        chosen = _selection(self.tree)
        row = next((r for r in self.rows if str(r["id"]) == str(chosen)), None)
        self._show_text(self.content_box, (row or {}).get("content") or "")

    def refresh(self):
        self._clear_tree()
        if not self._audit_view(access_ui.own_student_id(self.auth)):
            return
        mode = self.filter_var.get()
        student_view = not self.can_issue
        priority = None if self.priority_var.get() == "Any" else self.priority_var.get()
        kwargs = {"published_only": mode == "Published now" or student_view,
                  "for_students": student_view and not access_ui.is_clinician(self.auth),
                  "priority": priority,
                  "recent_days": 30 if mode == "Last 30 days" else None,
                  "include_expired": mode in ("All (incl. expired)", "Last 30 days")}
        try:
            self.rows = self._run(lambda conn: self.adv.list_advisories(conn, **kwargs))
        except Exception as exc:
            self._err(f"Could not load advisories: {exc}")
            return
        for r in self.rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["title"], r["advisory_type"], r["priority"], r["target_audience"],
                r["effective_date"] or "", r["expiry_date"] or "No expiry", r["issued_by"] or "",
                r["status"]))
        self._show_text(self.content_box, "" if self.rows else "No advisories to show.")


# --------------------------------------------------------------------------
# Disease surveillance + outbreak investigations
# --------------------------------------------------------------------------
class SurveillancePanel(_ParityPanel):
    title = "Disease Surveillance"
    clinician_only = True

    def build(self):
        from education_system.systems.university.domains.health.domain.health.services import (
            surveillance,
        )
        self.sv = surveillance
        self._header()
        if not self._can("issue_health_advisories"):
            ttk.Label(self.parent, text="Disease surveillance needs the "
                                        "'issue health advisories' permission.",
                      padding=20).pack(anchor="w")
            return
        if not self._audit_view():
            return
        notebook = ttk.Notebook(self.parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        cases_tab, outbreak_tab = ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(cases_tab, text="Cases")
        notebook.add(outbreak_tab, text="Outbreaks & investigations")
        self._build_cases(cases_tab)
        self._build_outbreaks(outbreak_tab)
        self.refresh()

    def _build_cases(self, tab):
        form = ttk.LabelFrame(tab, text="Report a case", padding=10)
        form.pack(fill=tk.X, pady=(6, 6))
        left, right = ttk.Frame(form), ttk.Frame(form)
        left.pack(side=tk.LEFT, anchor="n")
        right.pack(side=tk.LEFT, anchor="n", padx=(20, 0))
        self._build_form(left, [
            {"key": "case_student", "label": "Student ID:"},
            {"key": "disease_name", "label": "Disease:", "kind": "combo",
             "values": list(self.sv.COMMON_DISEASES)},
            {"key": "case_date", "label": "Case date (YYYY-MM-DD):", "kind": "date"},
        ])
        self.widgets["disease_name"].configure(state="normal")   # other diseases can be typed
        self._build_form(right, [
            {"key": "severity", "label": "Severity:", "kind": "combo",
             "values": list(self.sv.SEVERITIES)},
            {"key": "symptoms", "label": "Symptoms:"},
            {"key": "tracing", "label": "Contact tracing needed:", "kind": "check"},
            {"key": "isolation", "label": "Isolation required:", "kind": "check"},
        ])
        ttk.Button(form, text="Report case", command=self.report).pack(
            side=tk.LEFT, anchor="s", padx=20)
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bar, text="Disease filter:").pack(side=tk.LEFT)
        self.case_filter = tk.StringVar()
        ttk.Entry(bar, textvariable=self.case_filter, width=16).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Label(bar, text="Set selected to:").pack(side=tk.LEFT, padx=(15, 0))
        self.case_status = tk.StringVar(value=self.sv.CASE_STATUSES[1])
        ttk.Combobox(bar, textvariable=self.case_status, values=list(self.sv.CASE_STATUSES),
                     state="readonly", width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Apply", command=self.set_status).pack(side=tk.LEFT)
        frame = ttk.Frame(tab)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = [("ID", 50), ("Disease", 120), ("Date", 90), ("Student", 90), ("Name", 150),
                ("Severity", 80), ("Status", 130), ("Tracing", 60), ("Isolation", 65)]
        self.cases = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", height=9)
        for heading, width in cols:
            self.cases.heading(heading, text=heading)
            self.cases.column(heading, width=width, anchor=tk.W)
        self.cases.pack(fill=tk.BOTH, expand=True)

    def _build_outbreaks(self, tab):
        ttk.Label(tab, text="Diseases with 3+ open or confirmed cases in 14 days:",
                  font=("Arial", 10, "bold")).pack(anchor="w", pady=(6, 2))
        self.outbreaks = ttk.Treeview(tab, columns=("Disease", "Cases", "First", "Last"),
                                      show="headings", height=4)
        for c in ("Disease", "Cases", "First", "Last"):
            self.outbreaks.heading(c, text=c)
            self.outbreaks.column(c, width=150, anchor=tk.W)
        self.outbreaks.pack(fill=tk.X)
        form = ttk.LabelFrame(tab, text="Open an investigation for the selected disease",
                              padding=10)
        form.pack(fill=tk.X, pady=6)
        self._build_form(form, [
            {"key": "case_definition", "label": "Case definition:", "width": 60},
            {"key": "suspected_source", "label": "Suspected source(s):", "width": 60},
            {"key": "locations", "label": "Locations / extra cases:", "width": 60},
            {"key": "confirm_cases", "label": "Mark these cases confirmed:", "kind": "check"},
        ])
        measures = ttk.Frame(form)
        measures.grid(row=10, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.measure_vars = []
        for i, measure in enumerate(self.sv.control_measures()):
            var = tk.BooleanVar()
            ttk.Checkbutton(measures, text=measure, variable=var).grid(
                row=i // 4, column=i % 4, sticky="w", padx=(0, 10))
            self.measure_vars.append((measure, var))
        ttk.Button(form, text="Open investigation", command=self.investigate).grid(
            row=11, column=1, sticky="w", pady=(8, 0))
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="Selected investigation →").pack(side=tk.LEFT)
        for status in self.sv.INVESTIGATION_STATUSES:
            ttk.Button(bar, text=status.title(),
                       command=lambda s=status: self.set_investigation(s)).pack(
                side=tk.LEFT, padx=3)
        self.investigations = ttk.Treeview(
            tab, columns=("ID", "Disease", "Status", "Cases", "Opened by", "Opened", "Closed"),
            show="headings", height=5)
        for c in ("ID", "Disease", "Status", "Cases", "Opened by", "Opened", "Closed"):
            self.investigations.heading(c, text=c)
            self.investigations.column(c, width=110, anchor=tk.W)
        self.investigations.pack(fill=tk.BOTH, expand=True)

    def report(self):
        values = dict(student_id=self._form_value("case_student"),
                      disease_name=self._form_value("disease_name"),
                      case_date=self._form_value("case_date"),
                      symptoms=self._form_value("symptoms"),
                      severity=self._form_value("severity"),
                      contact_tracing_needed=self.vars["tracing"].get(),
                      isolation_required=self.vars["isolation"].get())
        result = self._write(lambda conn: self.sv.report_case(
            conn, by_user_id=self._user_id(), **values))
        if result:
            text = f"Case #{result['id']} reported."
            if result["outbreak_alert"]:
                text += (f"\n\nOUTBREAK ALERT: {result['recent_cases']} {values['disease_name']} "
                         "cases in 14 days. Consider an outbreak investigation.")
            self._info(text)
            self.refresh()

    def set_status(self):
        case_id = _selection(self.cases)
        if not case_id:
            self._err("Select a case.")
            return
        if self._write(lambda conn: self.sv.set_case_status(
                conn, case_id, self.case_status.get(), by_user_id=self._user_id())):
            self.refresh()

    def investigate(self):
        disease = _selection(self.outbreaks)
        if not disease:
            self._err("Select a disease in the outbreak list.")
            return
        measures = [m for m, var in self.measure_vars if var.get()]
        result = self._write(lambda conn: self.sv.open_investigation(
            conn, disease_name=disease, opened_by=self.username, by_user_id=self._user_id(),
            case_definition=self._form_value("case_definition"),
            suspected_source=self._form_value("suspected_source"),
            locations=self._form_value("locations"), measures=measures,
            confirm_cases=self.vars["confirm_cases"].get()),
            lambda iid: f"Investigation #{iid} opened.")
        if result:
            self.refresh()

    def set_investigation(self, status):
        investigation_id = _selection(self.investigations)
        if not investigation_id:
            self._err("Select an investigation.")
            return
        if self._write(lambda conn: self.sv.set_investigation_status(
                conn, investigation_id, status, by=self.username, by_user_id=self._user_id())):
            self.refresh()

    def refresh(self):
        if not hasattr(self, "cases"):
            return
        try:
            data = self._run(lambda conn: (
                self.sv.list_cases(conn, disease=self.case_filter.get().strip() or None),
                self.sv.potential_outbreaks(conn), self.sv.list_investigations(conn)))
        except Exception as exc:
            self._err(f"Could not load surveillance data: {exc}")
            return
        cases, outbreaks, investigations = data
        for tree in (self.cases, self.outbreaks, self.investigations):
            for item in tree.get_children():
                tree.delete(item)
        for c in cases:
            self.cases.insert("", tk.END, values=(
                c["id"], c["disease_name"], c["case_date"], c["student_id"],
                f"{c['first_name'] or ''} {c['last_name'] or ''}".strip(), c["severity"] or "",
                c["status"], "Yes" if c["contact_tracing_needed"] else "No",
                "Yes" if c["isolation_required"] else "No"))
        for o in outbreaks:
            self.outbreaks.insert("", tk.END, values=(o["disease"], o["cases"], o["first_case"],
                                                      o["last_case"]))
        for i in investigations:
            self.investigations.insert("", tk.END, values=(
                i["id"], i["disease_name"], i["status"], i["case_count"], i["opened_by"] or "",
                i["opened_at"] or "", i["closed_at"] or ""))


# --------------------------------------------------------------------------
# Risk assessment
# --------------------------------------------------------------------------
class RiskAssessmentPanel(_ParityPanel):
    title = "Health Risk Assessment"
    clinician_only = True

    def build(self):
        from education_system.systems.university.domains.health.domain.health.portal.data_privacy import (
            risk_assessment,
        )
        self.ra = risk_assessment
        self.result = None
        self._header()
        form = ttk.LabelFrame(self.parent, text="Assess a student", padding=10)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "assessment_type", "label": "Assessment type:", "kind": "combo",
             "values": list(risk_assessment.ASSESSMENT_TYPES)},
            {"key": "follow_up_date", "label": "Follow-up (YYYY-MM-DD, optional):"},
        ])
        buttons = ttk.Frame(form)
        buttons.grid(row=99, column=1, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Assess", command=self.assess).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Save assessment", command=self.save).pack(side=tk.LEFT, padx=6)
        self.result_box = self._text_box(height=8)
        self._search_row(self.parent)
        self._make_tree([("ID", 50), ("Student", 90), ("Name", 150), ("Type", 170),
                         ("Score", 60), ("Level", 110), ("Assessed", 90), ("By", 100),
                         ("Follow-up", 90)])
        self.refresh()

    def assess(self):
        sid = self._form_value("student_id").strip()
        if not sid:
            self._err("Enter a student ID.")
            return
        if not access_ui.record_view(self.parent, self.auth, self.title, student_id=sid):
            return
        try:
            self.result = self._run(lambda conn: self.ra.assess(
                conn, sid, self._form_value("assessment_type")))
        except (ValueError, LookupError) as exc:
            self._err(str(exc))
            return
        r = self.result
        self._show_text(self.result_box, "\n".join(
            [f"{r['name']} ({r['student_id']}) — {r['assessment_type']}",
             f"Risk score: {r['risk_score']}/100  ({r['risk_level']})", "", "Risk factors:"]
            + [f"  - {f}" for f in r["risk_factors"] or ["none found in the record"]]
            + ["", "Recommendations:"] + [f"  - {x}" for x in r["recommendations"]]))

    def save(self):
        if self.result is None or self.result["student_id"] != self._form_value("student_id").strip():
            self._err("Run the assessment for this student first.")
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to save risk assessments.")
            return
        follow_up = self._form_value("follow_up_date")
        result = self.result
        if self._write(lambda conn: self.ra.save_assessment(
                conn, result, assessed_by=self.username, by_user_id=self._user_id(),
                follow_up_date=follow_up), lambda rid: f"Risk assessment #{rid} saved."):
            self.ra.publish_assessment(result, assessed_by=self.username,
                                       follow_up_date=follow_up)
            self.refresh()

    def refresh(self):
        self._clear_tree()
        sid = self._scoped_sid()
        if sid is None:
            return
        try:
            rows = self._run(lambda conn: self.ra.list_assessments(conn, sid or None))
        except Exception as exc:
            self._err(f"Could not load risk assessments: {exc}")
            return
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["student_id"], f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
                r["assessment_type"], r["risk_score"], r["risk_level"], r["assessed_date"] or "",
                r["assessed_by"] or "", r["follow_up_date"] or ""))


# --------------------------------------------------------------------------
# Quality assurance
# --------------------------------------------------------------------------
class QualityAssurancePanel(_ParityPanel):
    title = "Quality Assurance"
    clinician_only = True

    def build(self):
        self._header()
        if not self._can("view_any_health_record"):
            ttk.Label(self.parent, text="Quality assurance needs the 'view any health record' "
                                        "permission.", padding=20).pack(anchor="w")
            return
        from education_system.systems.university.domains.health.domain.health.records import (
            quality_assurance as qa,
        )
        self.reports = [
            ("Data Quality Metrics", qa.data_quality_metrics),
            ("Clinical Quality Indicators", qa.clinical_quality_indicators),
            ("Patient Safety Metrics", lambda auth: qa.patient_safety_metrics(auth, pause=False)),
            ("Performance Improvement", lambda auth: qa.performance_improvement(auth, pause=False)),
            ("Compliance Monitoring", lambda auth: qa.compliance_monitoring(auth, pause=False)),
        ]
        bar = self._bar()
        for label, fn in self.reports:
            ttk.Button(bar, text=label, command=lambda l=label, f=fn: self.show(l, f)).pack(
                side=tk.LEFT, padx=(0, 6))
        self.box = self._text_box(height=24)
        self.show(*self.reports[0])

    def show(self, label, fn):
        """Run the CLI report and show what it prints."""
        if not self._audit_view():
            return
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                fn(self.auth)
        except Exception as exc:
            logger.exception("QA report %s failed", label)
            out.write(f"\nThe report stopped with an error: {exc}\n")
        self._show_text(self.box, f"{label}\n{'=' * len(label)}\n{out.getvalue().strip()}")

    def refresh(self):
        pass


# --------------------------------------------------------------------------
# Data retention
# --------------------------------------------------------------------------
class RetentionPanel(_ParityPanel):
    title = "Data Retention Policies"
    clinician_only = True

    def build(self):
        from education_system.systems.university.domains.health.application.health import (
            retention,
        )
        self.ret = retention
        self.manager = retention.may_manage(self.who)
        self._header()
        ttk.Label(self.parent, text="Rows older than a policy's period are removed by the daily "
                                    "worker only when the policy has auto-delete on.",
                  foreground="#555555").pack(anchor="w", padx=10)
        bar = self._bar()
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(bar, text="Dry run (what would be removed)", command=self.dry_run).pack(
            side=tk.LEFT, padx=6)
        if self.manager:
            ttk.Button(bar, text="Purge now…", command=self.purge).pack(side=tk.LEFT)
            form = ttk.LabelFrame(self.parent, text="Edit the selected policy", padding=10)
            form.pack(fill=tk.X, padx=10, pady=(0, 6))
            self._build_form(form, [
                {"key": "retention_period_days", "label": "Retention (days):", "width": 10},
                {"key": "deletion_method", "label": "Deletion method:", "kind": "combo",
                 "values": list(retention.DELETION_METHODS)},
                {"key": "auto_delete", "label": "Auto-delete:", "kind": "check"},
                {"key": "is_active", "label": "Active:", "kind": "check", "default": True},
            ])
            ttk.Button(form, text="Save policy", command=self.save).grid(
                row=99, column=1, sticky="w", pady=(8, 0))
        else:
            ttk.Label(bar, text="Only a health administrator can change policies or purge.",
                      foreground="#555555").pack(side=tk.LEFT, padx=10)
        self._make_tree([("ID", 50), ("Data type", 160), ("Applies to", 150), ("Days", 70),
                         ("Auto-delete", 80), ("Method", 70), ("Active", 60),
                         ("Last cleanup", 140)])
        self.tree.configure(height=8)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._fill())
        self.box = self._text_box(height=6)
        self.rows = []
        self.refresh()

    def _fill(self):
        chosen = _selection(self.tree)
        row = next((r for r in self.rows if str(r["id"]) == str(chosen)), None)
        if not row or not self.manager:
            return
        self.vars["retention_period_days"].set(row.get("retention_period_days") or "")
        self.vars["deletion_method"].set(row.get("deletion_method") or "soft")
        self.vars["auto_delete"].set(bool(row.get("auto_delete")))
        self.vars["is_active"].set(row.get("is_active") in (None, 1, "1", True))

    def save(self):
        policy_id = _selection(self.tree)
        if not policy_id:
            self._err("Select a policy.")
            return
        values = dict(retention_period_days=self._form_value("retention_period_days"),
                      deletion_method=self._form_value("deletion_method"),
                      auto_delete=self.vars["auto_delete"].get(),
                      is_active=self.vars["is_active"].get())
        if self._write(lambda conn: self.ret.update_policy(conn, self.who, policy_id, **values),
                       "Policy saved."):
            self.refresh()

    def dry_run(self):
        try:
            report = self._run(lambda conn: self.ret.purge(conn, by=self.username, dry_run=True))
            everything = self._run(lambda conn: self.ret.plan(conn, auto_only=False))
        except Exception as exc:
            self._err(f"Could not work out the plan: {exc}")
            return
        auto = {e["policy_id"] for e in report["plan"]}
        lines = ["Dry run — nothing has been changed.", ""]
        for e in everything:
            flag = "WILL be removed" if e["policy_id"] in auto else "kept (auto-delete off)"
            lines.append(f"{e['data_type']}: {e['count']} row(s) in {e['table']} older than "
                         f"{e['cutoff']} — {flag} ({e['method']})")
        self._show_text(self.box, "\n".join(lines if everything else
                                            lines + ["No policy applies to a health table."]))

    def purge(self):
        try:
            self.ret.require_manager(self.who, "run a retention purge")
        except PermissionError as exc:
            self._err(str(exc))
            return
        report = self._run(lambda conn: self.ret.purge(conn, by=self.username, dry_run=True))
        total = sum(e["count"] for e in report["plan"])
        if not total:
            self._info("Nothing is past its retention period.")
            return
        typed = simpledialog.askstring(
            self.title, f"{total} row(s) will be removed or marked deleted.\n"
                        "Type PURGE to go ahead:", parent=self.parent)
        if typed != "PURGE":
            return
        result = self._write(lambda conn: self.ret.purge(conn, by=self.username, dry_run=False))
        if result is not None:
            self._show_text(self.box, "Purged:\n" + "\n".join(
                f"{k}: {v}" for k, v in result["removed"].items()) or "nothing")
            self.refresh()

    def refresh(self):
        self._clear_tree()
        if not self._audit_view():
            return
        try:
            self.rows = self._run(self.ret.list_policies)
        except Exception as exc:
            self._err(f"Could not load retention policies: {exc}")
            return
        for r in self.rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r.get("data_type") or "", r["applies_to"] or "(not a health table)",
                r.get("retention_period_days") or "", "Yes" if r.get("auto_delete") else "No",
                r.get("deletion_method") or "", "No" if r.get("is_active") in (0, "0") else "Yes",
                r.get("last_cleanup_date") or ""))


# --------------------------------------------------------------------------
# Backup & recovery (administrators)
# --------------------------------------------------------------------------
class BackupRecoveryPanel(_ParityPanel):
    title = "Backup & Recovery"

    def build(self):
        from education_system.systems.university.domains.health.domain.health.records import (
            backup_export,
        )
        self.bx = backup_export
        self._header()
        if not backup_export.may_back_up(access_ui.current_user(self.auth)):
            ttk.Label(self.parent, text="Backup and recovery is for administrators.",
                      padding=20).pack(anchor="w")
            return
        ttk.Label(self.parent, text="Backs up the university database, which holds the health "
                                    f"records. Folder: {backup_export.health_backup_dir()}",
                  foreground="#555555").pack(anchor="w", padx=10)
        bar = self._bar()
        ttk.Button(bar, text="Create backup", command=self.create).pack(side=tk.LEFT)
        ttk.Button(bar, text="Restore selected…", command=self.restore).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        self._make_tree([("File", 380), ("Kind", 120), ("Size", 110), ("Created", 160)])
        self.refresh()

    def create(self):
        try:
            path = self.bx.make_backup(by_user_id=self._user_id() or self.username)
        except Exception as exc:
            self._err(f"Backup failed: {exc}")
            return
        self._info(f"Backup created:\n{path}")
        self.refresh()

    def restore(self):
        name = _selection(self.tree)
        if not name:
            self._err("Select a backup.")
            return
        path = str(self.bx.health_backup_dir() / name)
        if not messagebox.askyesno(self.title, f"Restore {name}?\n\nThis OVERWRITES the current "
                                               "database for everyone. A copy of the current "
                                               "database is taken first.", parent=self.parent,
                                   icon="warning"):
            return
        typed = simpledialog.askstring(self.title, "Type RESTORE to confirm:", parent=self.parent)
        if typed != "RESTORE":
            return
        typed = simpledialog.askstring(self.title, "Type your username to confirm:",
                                       parent=self.parent)
        if typed != self.username:
            self._err("Username mismatch. Nothing was restored.")
            return
        try:
            safety = self.bx.restore_backup(path, by_user_id=self._user_id() or self.username)
        except Exception as exc:
            self._err(f"Nothing was restored: {exc}")
            return
        self._info(f"Restored from {name}.\nThe previous database was saved as {safety.name}.\n\n"
                   "Restart the application so every window reloads.")
        self.refresh()

    def refresh(self):
        if self.tree is None:
            return
        self._clear_tree()
        for b in self.bx.list_backups():
            self.tree.insert("", tk.END, values=(b["name"], b["kind"], f"{b['size']:,} bytes",
                                                 b["modified"]))


# --------------------------------------------------------------------------
# Record templates
# --------------------------------------------------------------------------
class RecordTemplatesPanel(_ParityPanel):
    title = "Record Templates"
    clinician_only = True

    def build(self):
        from education_system.systems.university.domains.health.domain.health.services import (
            templates,
        )
        self.tp = templates
        self._header()
        body = ttk.Frame(self.parent)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)
        cols = ("Name", "Category", "Source")
        self.list = ttk.Treeview(left, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (180, 120, 70)):
            self.list.heading(c, text=c)
            self.list.column(c, width=w, anchor=tk.W)
        self.list.pack(fill=tk.Y, expand=True)
        self.list.bind("<<TreeviewSelect>>", lambda _e: self._load())
        side = ttk.Frame(left)
        side.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(side, text="Usage (30 days)", command=self.usage).pack(side=tk.LEFT)
        ttk.Button(side, text="New template", command=self._new).pack(side=tk.LEFT, padx=4)

        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        meta = ttk.Frame(right)
        meta.pack(fill=tk.X)
        self._build_form(meta, [
            {"key": "name", "label": "Template name:"},
            {"key": "category", "label": "Category:", "kind": "combo",
             "values": list(templates.TEMPLATE_CATEGORIES)},
            {"key": "record_type", "label": "Record type:"},
        ])
        ttk.Label(right, text="Content ([FILL IN] marks what the clinician completes):").pack(
            anchor="w", pady=(6, 0))
        actions = ttk.LabelFrame(right, text="Use it for a student", padding=8)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self._build_form(actions, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "record_date", "label": "Record date:", "kind": "date"},
            {"key": "provider", "label": "Provider:", "default": self.username or ""},
            {"key": "confidential", "label": "Confidential:", "kind": "check"},
        ])
        buttons = ttk.Frame(actions)
        buttons.grid(row=99, column=1, sticky="w", pady=(6, 0))
        ttk.Button(buttons, text="Create health record", command=self.use).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Save as template", command=self.save).pack(side=tk.LEFT, padx=6)
        self.body_text = tk.Text(right, height=10, wrap="word")
        self.body_text.pack(fill=tk.BOTH, expand=True)
        self.templates = []
        self.current = None
        self.refresh()

    def _new(self):
        self.current = None
        for key in ("name", "record_type"):
            self.vars[key].set("")
        self.body_text.delete("1.0", tk.END)

    def _load(self):
        chosen = self.list.selection()
        if not chosen:
            return
        self.current = self.templates[int(chosen[0])]
        self.vars["name"].set(self.current["name"])
        self.vars["category"].set(self.current["category"] or "Other")
        self.vars["record_type"].set(self.current["record_type"])
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert("1.0", self.current["body"])

    def use(self):
        if not self.current:
            self._err("Choose a template.")
            return
        sid = self._form_value("student_id").strip()
        if not sid:
            self._err("Enter the student ID.")
            return
        template = dict(self.current, record_type=self._form_value("record_type")
                        or self.current["record_type"])
        description = self.body_text.get("1.0", tk.END).strip()
        if self._write(lambda conn: self.tp.create_record_from_template(
                conn, self.who, template, student_id=sid, description=description,
                record_date=self._form_value("record_date"),
                provider=self._form_value("provider"),
                confidential=self.vars["confidential"].get()),
                lambda rid: f"Health record #{rid} created for {sid}."):
            self.refresh()

    def save(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to manage templates.")
            return
        template_id = self.current["id"] if self.current and self.current["source"] == "saved" \
            and self.current["name"] == self._form_value("name").strip() else None
        if self._write(lambda conn: self.tp.save_record_template(
                conn, name=self._form_value("name"), category=self._form_value("category"),
                record_type=self._form_value("record_type"),
                body=self.body_text.get("1.0", tk.END), by=self.username,
                template_id=template_id), "Template saved."):
            self.refresh()

    def usage(self):
        stats = self._run(self.tp.template_usage)
        if not stats:
            self._info("No health records have been created from a template in the last "
                       "30 days.")
            return
        self._info("Records created from templates (30 days):\n\n" + "\n".join(
            f"{s['template']}: {s['uses']} (last {s['last_used']})" for s in stats))

    def refresh(self):
        for item in self.list.get_children():
            self.list.delete(item)
        if not self._audit_view():
            return
        try:
            self.templates = self._run(self.tp.list_record_templates)
        except Exception as exc:
            self._err(f"Could not load templates: {exc}")
            return
        for index, t in enumerate(self.templates):
            self.list.insert("", tk.END, iid=str(index),
                             values=(t["name"], t["category"], t["source"]))


# --------------------------------------------------------------------------
# Student health dashboard
# --------------------------------------------------------------------------
def dashboard_data(conn, who, student_id) -> dict:
    """Everything the dashboard shows for one student (read only; the
    caller has checked and audited access)."""
    from datetime import date
    from education_system.systems.university.domains.health.application.health import (
        access, diary, personal_metrics, prescribing,
    )
    access.require_view(who, student_id)
    today = date.today().isoformat()
    appointments = [a for a in diary.appointments(conn, student_id=student_id, date_from=today,
                                                  include_closed=False)]
    vaccinations = [tuple(r) for r in conn.execute(
        "SELECT vaccine_name, administered_date, expiry_date, verified FROM vaccination_records "
        "WHERE student_id = ? ORDER BY administered_date DESC", (str(student_id),)).fetchall()]
    try:
        accommodations = [tuple(r) for r in conn.execute(
            "SELECT accommodation_type, status, start_date, COALESCE(end_date, expiration_date) "
            "FROM accommodations WHERE student_id = ? ORDER BY start_date DESC",
            (str(student_id),)).fetchall()]
    except Exception:
        accommodations = []
    try:
        metrics = personal_metrics.trends(conn, who, student_id)
    except Exception:
        metrics = []
    student = conn.execute("SELECT first_name, last_name FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
    return {"name": f"{student[0]} {student[1]}" if student else str(student_id),
            "appointments": appointments, "allergies": prescribing.allergies_for(conn, student_id),
            "vaccinations": vaccinations, "accommodations": accommodations, "metrics": metrics}


class StudentDashboardPanel(_ParityPanel):
    title = "Student Health Dashboard"

    def build(self):
        self._header()
        self._search_row(self.parent)
        self.box = self._text_box(height=28)
        self.refresh()

    def refresh(self):
        sid = self._scoped_sid()
        if sid is None:
            return
        if not sid:
            self._show_text(self.box, "Enter a student ID and press Refresh.")
            return
        try:
            data = self._run(lambda conn: dashboard_data(conn, self.who, sid))
        except (PermissionError, LookupError) as exc:
            self._show_text(self.box, str(exc))
            return
        except Exception as exc:
            self._err(f"Could not build the dashboard: {exc}")
            return
        lines = [f"Health dashboard — {data['name']} ({sid})", ""]
        lines.append("UPCOMING APPOINTMENTS")
        for a in data["appointments"] or []:
            who = "anonymous booking" if a.get("anonymous") else a.get("provider") or ""
            lines.append(f"  {a['date']} {a.get('time') or ''}  {a.get('type') or ''} "
                         f"— {who} [{a.get('status') or ''}] ({a['source']})")
        if not data["appointments"]:
            lines.append("  none booked")
        lines += ["", "ALLERGIES"]
        lines += [f"  {x['allergen']} ({x['severity']}, {x['source']})"
                  for x in data["allergies"]] or ["  none recorded"]
        lines += ["", "VACCINATIONS"]
        lines += [f"  {v[0]}  given {v[1] or '?'}  expires {v[2] or '—'}  "
                  f"{'verified' if v[3] else 'not verified'}"
                  for v in data["vaccinations"]] or ["  none recorded"]
        lines += ["", "ACCOMMODATIONS"]
        lines += [f"  {a[0]} [{a[1]}] {a[2] or ''} – {a[3] or 'open'}"
                  for a in data["accommodations"]] or ["  none"]
        lines += ["", "PERSONAL METRICS (30 days)"]
        lines += [f"  {m['label']}: latest {m['latest']}{('/' + str(m['latest2'])) if m['latest2'] else ''} "
                  f"{m['unit']} on {m['latest_on']}, average {m['average']} over {m['count']} reading(s)"
                  for m in data["metrics"]] or ["  nothing logged"]
        self._show_text(self.box, "\n".join(lines))


# --------------------------------------------------------------------------
# Drug interaction table
# --------------------------------------------------------------------------
class DrugInteractionsPanel(_ParityPanel):
    title = "Drug Interactions"
    clinician_only = True

    def build(self):
        from education_system.systems.university.domains.health.application.health import (
            prescribing,
        )
        self.rx = prescribing
        self._header()
        ttk.Label(self.parent, text="The table the prescribing safety check uses. A+B and B+A "
                                    "are the same entry.", foreground="#555555").pack(
            anchor="w", padx=10)
        form = ttk.LabelFrame(self.parent, text="Add or change an interaction", padding=10)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "drug_a", "label": "Drug A:"},
            {"key": "drug_b", "label": "Drug B:"},
            {"key": "severity", "label": "Severity:", "kind": "combo",
             "values": list(prescribing.INTERACTION_SEVERITIES)},
            {"key": "description", "label": "Effect / advice:", "width": 60},
        ])
        buttons = ttk.Frame(form)
        buttons.grid(row=99, column=1, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=lambda: self.save(False)).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Update selected", command=lambda: self.save(True)).pack(
            side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="Remove selected…", command=self.delete).pack(side=tk.LEFT)
        bar = self._bar()
        ttk.Label(bar, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        self._make_tree([("ID", 50), ("Drug A", 150), ("Drug B", 150), ("Severity", 80),
                         ("Description", 420)])
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._fill())
        self.rows = []
        self.refresh()

    def _fill(self):
        chosen = _selection(self.tree)
        row = next((r for r in self.rows if str(r["id"]) == str(chosen)), None)
        if row:
            for key in ("drug_a", "drug_b", "severity", "description"):
                self.vars[key].set(row[key])

    def save(self, update):
        interaction_id = _selection(self.tree) if update else None
        if update and not interaction_id:
            self._err("Select the interaction to update.")
            return
        values = {k: self._form_value(k) for k in ("drug_a", "drug_b", "severity", "description")}
        if self._write(lambda conn: self.rx.save_interaction(
                conn, self.who, interaction_id=interaction_id, **values), "Interaction saved."):
            self.refresh()

    def delete(self):
        interaction_id = _selection(self.tree)
        if not interaction_id:
            self._err("Select the interaction to remove.")
            return
        reason = simpledialog.askstring(self.title, "Why is this interaction being removed?",
                                        parent=self.parent)
        if not reason:
            return
        if self._write(lambda conn: self.rx.delete_interaction(conn, self.who, interaction_id,
                                                               reason), "Interaction removed."):
            self.refresh()

    def refresh(self):
        self._clear_tree()
        if not self._audit_view():
            return
        try:
            self.rows = self._run(lambda conn: self.rx.list_interactions(
                conn, self.search_var.get().strip() or None))
        except Exception as exc:
            self._err(f"Could not load the interaction table: {exc}")
            return
        for r in self.rows:
            self.tree.insert("", tk.END, values=(r["id"], r["drug_a"], r["drug_b"], r["severity"],
                                                 r["description"]))


# --------------------------------------------------------------------------
# Personal metrics
# --------------------------------------------------------------------------
class PersonalMetricsPanel(_ParityPanel):
    title = "Personal Health Metrics"

    def build(self):
        from education_system.systems.university.domains.health.application.health import (
            personal_metrics,
        )
        self.pm = personal_metrics
        self.labels = {v[0]: k for k, v in personal_metrics.METRICS.items()}
        self._header()
        self.own = access_ui.own_student_id(self.auth)
        if self.own:
            form = ttk.LabelFrame(self.parent, text="Log a reading", padding=10)
            form.pack(fill=tk.X, padx=10, pady=(0, 6))
            self._build_form(form, [
                {"key": "metric", "label": "Metric:", "kind": "combo",
                 "values": list(self.labels)},
                {"key": "value", "label": "Value (systolic for BP):", "width": 10},
                {"key": "value2", "label": "Diastolic (BP only):", "width": 10},
                {"key": "recorded_on", "label": "Date (YYYY-MM-DD):", "kind": "date"},
                {"key": "notes", "label": "Notes:"},
            ])
            ttk.Button(form, text="Log reading", command=self.log).grid(
                row=99, column=1, sticky="w", pady=(8, 0))
        else:
            ttk.Label(self.parent, text="Students log their own readings; the health team can "
                                        "read them here.", foreground="#555555").pack(
                anchor="w", padx=10)
        self._search_row(self.parent)
        bar = self._bar()
        ttk.Label(bar, text="Days:").pack(side=tk.LEFT)
        self.days_var = tk.StringVar(value="30")
        ttk.Combobox(bar, textvariable=self.days_var, values=["7", "30", "90", "365"],
                     state="readonly", width=6).pack(side=tk.LEFT, padx=5)
        if self.own:
            ttk.Button(bar, text="Remove selected", command=self.remove).pack(side=tk.LEFT,
                                                                              padx=6)
        self.trend_var = tk.StringVar()
        ttk.Label(self.parent, textvariable=self.trend_var, justify="left",
                  foreground="#2c3e50").pack(anchor="w", padx=10)
        self._make_tree([("ID", 50), ("Date", 95), ("Metric", 170), ("Value", 80),
                         ("Second", 80), ("Unit", 70), ("Notes", 300)])
        self.refresh()

    def log(self):
        metric = self.labels.get(self._form_value("metric"))
        if self._write(lambda conn: self.pm.log(
                conn, self.who, self.own, metric, self._form_value("value"),
                self._form_value("value2") or None, notes=self._form_value("notes"),
                recorded_on=self._form_value("recorded_on")), "Reading logged."):
            self.refresh()

    def remove(self):
        entry_id = _selection(self.tree)
        if not entry_id:
            self._err("Select a reading.")
            return
        if self._write(lambda conn: _must(self.pm.remove(conn, self.who, entry_id),
                                          "That reading is not yours"), "Reading removed."):
            self.refresh()

    def refresh(self):
        self._clear_tree()
        sid = self._scoped_sid()
        if sid is None:
            return
        if not sid:
            self.trend_var.set("Enter a student ID and press Refresh.")
            return
        days = int(self.days_var.get() or 30)
        try:
            rows = self._run(lambda conn: self.pm.history(conn, self.who, sid, days=days))
            trends = self._run(lambda conn: self.pm.trends(conn, self.who, sid, days=days))
        except PermissionError as exc:
            self.trend_var.set(str(exc))
            return
        except Exception as exc:
            self._err(f"Could not load metrics: {exc}")
            return
        names = {k: v[0] for k, v in self.pm.METRICS.items()}
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["recorded_on"], names.get(r["metric"], r["metric"]), r["value"],
                r["value2"] if r["value2"] is not None else "", r["unit"] or "", r["notes"] or ""))
        self.trend_var.set("\n".join(
            f"{t['label']}: latest {t['latest']}, average {t['average']}, range "
            f"{t['lowest']}–{t['highest']}, change {t['change']:+} ({t['count']} readings)"
            for t in trends) or "No readings in this period.")


__all__ = [
    "VitalSignsPanel", "InsurancePanel", "AdvisoriesPanel", "SurveillancePanel",
    "RiskAssessmentPanel", "QualityAssurancePanel", "RetentionPanel", "BackupRecoveryPanel",
    "RecordTemplatesPanel", "StudentDashboardPanel", "DrugInteractionsPanel",
    "PersonalMetricsPanel", "dashboard_data",
]
