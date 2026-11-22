"""Early Warning & Interventions window — Student Overview tab.

One student across all three areas, with a sub-tab for each: their
support case, their Early Warning interventions (raise and complete them
here — each is noted on the case history), risk profile and indicators,
coaching and tutoring, and measured outcomes. The join lives in
``early_warning.case_links``.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.student_support.domain.early_warning import (
    case_links,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.student_wellbeing.services.intervention_records import (
    InterventionRecordsError, InterventionRecordsService,
)

logger = logging.getLogger(__name__)

__all__ = ["StudentOverviewFrame"]

_BG = "#f0f4f8"


def _tree(parent, columns, widths=None, height=8):
    """A scrolled Treeview with title-cased headings."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=(5, 5))
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for col in columns:
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=(widths or {}).get(col, 100), anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


def _fill(tree, rows):
    tree.delete(*tree.get_children())
    for values in rows:
        tree.insert("", "end", values=tuple("" if v is None else v for v in values))


def _day(value):
    return str(value or "")[:10]


class StudentOverviewFrame(tk.Frame):
    def __init__(self, parent, user=None, hub=None):
        super().__init__(parent, bg=_BG)
        self._hub = hub
        self._user = user or {}
        self._actor = (self._user.get("username") or self._user.get("email")
                       or str(self._user.get("id") or "") or "staff")
        self._student_id = None
        self._overview = None
        self._choices = []
        self._build()
        self.reload_choices()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        top = tk.Frame(self, bg=_BG)
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, text="Student:", bg=_BG, font=("Segoe UI", 10, "bold")).pack(side="left")
        self._pick_var = tk.StringVar()
        self._picker = ttk.Combobox(top, textvariable=self._pick_var, width=48)
        self._picker.pack(side="left", padx=6)
        self._picker.bind("<<ComboboxSelected>>", lambda _e: self._show_picked())
        self._picker.bind("<Return>", lambda _e: self._show_picked())
        self._picker.bind("<KeyRelease>", self._filter_choices)
        ttk.Button(top, text="Show", command=self._show_picked).pack(side="left", padx=2)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=2)

        self._title = tk.Label(self, text="Choose a student to see their support case, "
                                          "Early Warning record and outcomes together.",
                               bg=_BG, fg="#1e3a5f", font=("Segoe UI", 12, "bold"), anchor="w")
        self._title.pack(fill="x", padx=12, pady=(2, 0))
        self._subtitle = tk.Label(self, text="", bg=_BG, fg="#475569",
                                  font=("Segoe UI", 9), anchor="w", justify="left")
        self._subtitle.pack(fill="x", padx=12, pady=(0, 4))

        self._tabs = ttk.Notebook(self)
        self._tabs.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_case_tab()
        self._build_interventions_tab()
        self._build_risk_tab()
        self._build_support_tab()
        self._build_outcomes_tab()

    def _sub(self, text):
        frame = ttk.Frame(self._tabs)
        self._tabs.add(frame, text=text)
        return frame

    def _build_case_tab(self):
        tab = self._sub("🎓 Support Case")
        btns = ttk.Frame(tab)
        btns.pack(side="bottom", fill="x", padx=10, pady=8)
        self._open_case_btn = ttk.Button(btns, text="Open in Support Cases",
                                         command=self._open_case)
        self._open_case_btn.pack(side="left", padx=3)
        self._create_case_btn = ttk.Button(btns, text="➕ Create Support Case",
                                           command=self._create_case)
        self._create_case_btn.pack(side="left", padx=3)
        self._contact_btn = ttk.Button(btns, text="📧 Log Contact", command=self._log_contact)
        self._contact_btn.pack(side="left", padx=3)

        self._case_fields = {}
        grid = ttk.Frame(tab)
        grid.pack(fill="x", padx=12, pady=(10, 4))
        for i, (label, key) in enumerate([("Name", "name"), ("Program", "program"),
                                          ("Email", "email"), ("GPA", "gpa"),
                                          ("Risk", "risk"), ("Status", "status"),
                                          ("Intervention", "intervention"),
                                          ("Last Contact", "last_contact")]):
            ttk.Label(grid, text=f"{label}:", font=("Segoe UI", 10, "bold")).grid(
                row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=2)
            var = tk.StringVar()
            ttk.Label(grid, textvariable=var).grid(row=i // 2, column=(i % 2) * 2 + 1,
                                                   sticky="w", padx=(0, 30), pady=2)
            self._case_fields[key] = var
        ttk.Label(tab, text="Notes / Case History:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=12, pady=(8, 2))
        self._case_notes = tk.Text(tab, height=8, wrap="word", relief="solid", bd=1)
        self._case_notes.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self._case_notes.configure(state="disabled")

    def _build_interventions_tab(self):
        tab = self._sub("⚠️ Interventions")

        # Forms first (packed at the bottom) so a short screen keeps them.
        forms = ttk.Frame(tab)
        forms.pack(side="bottom", fill="x", padx=10, pady=(0, 8))

        raise_box = ttk.LabelFrame(forms, text="Raise Early Warning Intervention", padding=6)
        raise_box.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._raise = {
            "trigger_type": tk.StringVar(), "intervention_type": tk.StringVar(),
            "priority": tk.StringVar(), "assigned_to": tk.StringVar(),
            "description": tk.StringVar(),
        }
        rows = [("Trigger", "trigger_type", case_links.TRIGGER_TYPES),
                ("Type", "intervention_type", case_links.INTERVENTION_TYPES),
                ("Priority", "priority", case_links.PRIORITIES)]
        for col, (label, key, values) in enumerate(rows):
            ttk.Label(raise_box, text=label + ":").grid(row=0, column=col * 2, sticky="e", padx=2)
            ttk.Combobox(raise_box, textvariable=self._raise[key], values=values,
                         state="readonly", width=14).grid(row=0, column=col * 2 + 1, padx=2, pady=2)
        ttk.Label(raise_box, text="Assigned to:").grid(row=1, column=0, sticky="e", padx=2)
        ttk.Entry(raise_box, textvariable=self._raise["assigned_to"], width=16).grid(
            row=1, column=1, padx=2, pady=2, sticky="w")
        ttk.Label(raise_box, text="Description:").grid(row=1, column=2, sticky="e", padx=2)
        ttk.Entry(raise_box, textvariable=self._raise["description"], width=40).grid(
            row=1, column=3, columnspan=3, padx=2, pady=2, sticky="ew")
        ttk.Button(raise_box, text="➕ Raise Intervention", command=self._raise_intervention).grid(
            row=2, column=0, columnspan=6, pady=(4, 0))

        done_box = ttk.LabelFrame(forms, text="Complete Selected", padding=6)
        done_box.pack(side="left", fill="both", padx=(5, 0))
        self._outcome_var = tk.StringVar(value="successful")
        self._done_notes = tk.StringVar()
        ttk.Label(done_box, text="Outcome:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Combobox(done_box, textvariable=self._outcome_var, values=case_links.OUTCOMES,
                     state="readonly", width=20).grid(row=0, column=1, padx=2, pady=2)
        ttk.Label(done_box, text="Notes:").grid(row=1, column=0, sticky="e", padx=2)
        ttk.Entry(done_box, textvariable=self._done_notes, width=22).grid(row=1, column=1, padx=2, pady=2)
        bar = ttk.Frame(done_box)
        bar.grid(row=2, column=0, columnspan=2, pady=(4, 0))
        ttk.Button(bar, text="✅ Complete", command=self._complete).pack(side="left", padx=2)
        ttk.Button(bar, text="📈 Record Outcome", command=self._record_outcome).pack(side="left", padx=2)

        self._interventions = _tree(
            tab, ("id", "type", "trigger", "priority", "status", "assigned_to",
                  "created", "completed", "outcome", "value_added"),
            {"id": 50, "type": 110, "trigger": 90, "priority": 70, "status": 80,
             "assigned_to": 100, "created": 85, "completed": 85, "outcome": 130,
             "value_added": 85})

    def _build_risk_tab(self):
        tab = self._sub("📊 Risk & Indicators")
        self._risk_text = tk.StringVar(value="No risk profile.")
        ttk.Label(tab, textvariable=self._risk_text, font=("Segoe UI", 10),
                  justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        self._indicators = _tree(
            tab, ("id", "type", "value", "severity", "detected", "resolved", "notes"),
            {"id": 50, "type": 100, "value": 140, "severity": 80, "detected": 90,
             "resolved": 70, "notes": 260})

    def _build_support_tab(self):
        tab = self._sub("🤝 Coaching & Tutoring")
        ttk.Label(tab, text="Coach assignments", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=12, pady=(8, 0))
        self._coaching = _tree(
            tab, ("coach", "frequency", "assigned", "last_meeting", "next_meeting", "status"),
            {"coach": 160, "frequency": 90, "assigned": 90, "last_meeting": 100,
             "next_meeting": 100, "status": 80}, height=4)
        ttk.Label(tab, text="Tutoring recommendations", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=12, pady=(8, 0))
        self._tutoring = _tree(
            tab, ("id", "module", "type", "priority", "status", "tutor", "sessions", "created"),
            {"id": 50, "module": 90, "type": 120, "priority": 70, "status": 80,
             "tutor": 120, "sessions": 80, "created": 90}, height=4)

    def _build_outcomes_tab(self):
        tab = self._sub("📈 Outcomes")
        self._outcome_summary = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self._outcome_summary, justify="left").pack(
            anchor="w", padx=12, pady=(10, 4))
        self._outcomes = _tree(
            tab, ("id", "type", "subject", "sessions", "pre", "post", "value_added", "status"),
            {"id": 50, "type": 120, "subject": 110, "sessions": 80, "pre": 60,
             "post": 60, "value_added": 85, "status": 80})

    # ------------------------------------------------------------------
    # Choosing a student
    # ------------------------------------------------------------------

    def reload_choices(self):
        try:
            self._choices = case_links.student_choices()
        except Exception:
            logger.exception("Could not load students for Student Overview")
            self._choices = []
        self._picker["values"] = [c["label"] for c in self._choices]

    def _filter_choices(self, event):
        if event.keysym in ("Return", "Up", "Down", "Escape"):
            return
        text = self._pick_var.get().lower()
        self._picker["values"] = [c["label"] for c in self._choices
                                  if text in c["label"].lower()] if text else \
            [c["label"] for c in self._choices]

    def _show_picked(self):
        text = self._pick_var.get().strip()
        if not text:
            return
        match = next((c for c in self._choices if c["label"] == text), None)
        self.show_student(match["student_id"] if match else text.split(" - ")[0].strip())

    def show_student(self, student_id):
        """Load one student into every sub-tab."""
        self._student_id = str(student_id)
        label = next((c["label"] for c in self._choices
                      if c["student_id"] == self._student_id), self._student_id)
        self._pick_var.set(label)
        self.refresh()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def refresh(self):
        if not self._student_id:
            return
        try:
            ov = case_links.student_overview(self._student_id)
        except Exception as exc:
            logger.exception("Student Overview failed for %s", self._student_id)
            messagebox.showerror("Student Overview", f"Could not load {self._student_id}: {exc}",
                                 parent=self)
            return
        self._overview = ov
        self._render_header(ov)
        self._render_case(ov)
        self._render_interventions(ov)
        self._render_risk(ov)
        self._render_support(ov)
        self._render_outcomes(ov)

    def _render_header(self, ov):
        stu, case, profile = ov["student"], ov["case"], ov["profile"]
        if stu:
            name = f"{stu.get('first_name') or ''} {stu.get('last_name') or ''}".strip()
            course = stu.get("program") or stu.get("course") or ""
        else:
            name = (case or {}).get("name") or ""
            course = (case or {}).get("program") or ""
        self._title.config(text=f"{name}  ({ov['student_id']})" if name else ov["student_id"])
        bits = [course] if course else []
        if profile:
            bits.append(f"Early Warning risk: {profile.get('risk_level')} "
                        f"({profile.get('overall_risk_score')})")
        bits.append(f"Support case: {case.get('risk')} / {case.get('status')}" if case
                    else "No support case")
        open_count = sum(1 for i in ov["interventions"] if i.get("status") != "completed")
        bits.append(f"{len(ov['interventions'])} interventions ({open_count} open)")
        if not ov["is_student"]:
            bits.append("⚠ not a student record — Early Warning can't link to it")
        self._subtitle.config(text="   ·   ".join(bits))

    def _render_case(self, ov):
        case = ov["case"]
        for key, var in self._case_fields.items():
            var.set((case or {}).get(key) or ("—" if case else ""))
        self._case_notes.configure(state="normal")
        self._case_notes.delete("1.0", "end")
        self._case_notes.insert("1.0", (case or {}).get("notes") or
                                ("" if case else "This student has no support case yet."))
        self._case_notes.configure(state="disabled")
        has_case = case is not None
        self._open_case_btn.state(["!disabled"] if has_case else ["disabled"])
        self._contact_btn.state(["!disabled"] if has_case else ["disabled"])
        self._create_case_btn.state(["disabled"] if has_case or not ov["is_student"] else ["!disabled"])

        # Raise-form defaults follow the case.
        for key, value in case_links.suggest_intervention(case).items():
            self._raise[key].set(value)

    def _render_interventions(self, ov):
        rows = []
        for i in ov["interventions"]:
            out = ov["outcomes"].get(i["intervention_id"]) or {}
            rows.append((i["intervention_id"], i.get("intervention_type"), i.get("trigger_type"),
                         i.get("priority"), i.get("status"), i.get("assigned_to"),
                         _day(i.get("created_at")), _day(i.get("completed_date")),
                         i.get("outcome"), out.get("value_added")))
        _fill(self._interventions, rows)

    def _render_risk(self, ov):
        p = ov["profile"]
        if p:
            self._risk_text.set(
                f"Overall risk: {p.get('overall_risk_score')} ({p.get('risk_level')})    "
                f"Academic {p.get('academic_risk_score')} · Attendance {p.get('attendance_risk_score')} · "
                f"Engagement {p.get('engagement_risk_score')} · Financial {p.get('financial_risk_score')}    "
                f"Last assessed: {_day(p.get('last_assessed'))}")
        else:
            self._risk_text.set("No risk profile — use Calculate Risk on At-Risk Students."
                                if ov["is_student"] else "Not a student record.")
        _fill(self._indicators, [
            (i["indicator_id"], i.get("indicator_type"), i.get("indicator_value"),
             i.get("severity"), _day(i.get("detected_at")),
             "Yes" if i.get("is_resolved") else "No", i.get("notes"))
            for i in ov["indicators"]])

    def _render_support(self, ov):
        _fill(self._coaching, [
            (a.get("coach_name"), a.get("meeting_frequency"), _day(a.get("assigned_date")),
             _day(a.get("last_meeting_date")), _day(a.get("next_meeting_date")), a.get("status"))
            for a in ov["coaching"]])
        _fill(self._tutoring, [
            (r["recommendation_id"], r.get("module_code"), r.get("recommendation_type"),
             r.get("priority"), r.get("status"), r.get("tutor_assigned"),
             f"{r.get('sessions_completed') or 0}/{r.get('sessions_scheduled') or 0}",
             _day(r.get("created_at")))
            for r in ov["tutoring"]])

    def _render_outcomes(self, ov):
        s = ov["outcome_summary"] or {}
        self._outcome_summary.set(
            f"With baseline: {s.get('with_baseline', 0)}    With outcome: {s.get('with_outcome', 0)}    "
            f"Positive value-added: {s.get('positive_value_added', 0)}    "
            f"Average value-added: {s.get('avg_value_added') if s.get('avg_value_added') is not None else 'n/a'}    "
            f"Sessions: {s.get('total_sessions_completed', 0)}/{s.get('total_sessions_planned', 0)}"
            if s else "")
        _fill(self._outcomes, [
            (r["intervention_id"], r.get("intervention_type"), r.get("subject_area"),
             f"{r.get('sessions_completed') or 0}/{r.get('sessions_total') or 0}",
             r.get("pre_assessment_score"), r.get("post_assessment_score"),
             r.get("value_added"), r.get("status"))
            for r in ov["outcomes"].values()])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _need_student(self):
        if not self._student_id:
            messagebox.showwarning("Student Overview", "Choose a student first.", parent=self)
            return False
        return True

    def _selected_intervention(self):
        sel = self._interventions.selection()
        if not sel:
            messagebox.showwarning("Student Overview", "Select an intervention first.", parent=self)
            return None
        return int(self._interventions.item(sel[0])["values"][0])

    def _after_change(self, refresh_support=False):
        self.refresh()
        if self._hub is not None:
            self._hub.refresh_linked(refresh_support=refresh_support)

    def _raise_intervention(self):
        if not self._need_student():
            return
        r = {k: v.get().strip() for k, v in self._raise.items()}
        try:
            iid = case_links.raise_intervention(
                self._student_id, r["trigger_type"], r["intervention_type"], r["priority"],
                r["description"], assigned_to=r["assigned_to"], actor=self._actor)
        except Exception as exc:
            messagebox.showerror("Raise Intervention", str(exc), parent=self)
            return
        noted = " and noted on the support case" if (self._overview or {}).get("case") else ""
        messagebox.showinfo("Raise Intervention", f"Intervention #{iid} raised{noted}.", parent=self)
        self._after_change(refresh_support=True)

    def _complete(self):
        iid = self._selected_intervention()
        if iid is None:
            return
        try:
            case_links.complete_intervention(iid, self._outcome_var.get(),
                                             self._done_notes.get().strip(), actor=self._actor)
        except Exception as exc:
            messagebox.showerror("Complete Intervention", str(exc), parent=self)
            return
        self._done_notes.set("")
        messagebox.showinfo("Complete Intervention", f"Intervention #{iid} completed.", parent=self)
        self._after_change(refresh_support=True)

    def _record_outcome(self):
        iid = self._selected_intervention()
        if iid is not None and self._hub is not None:
            self._hub.open_outcomes(iid)

    def _open_case(self):
        if self._student_id and self._hub is not None:
            self._hub.open_support_case(self._student_id)

    def _create_case(self):
        if not self._need_student():
            return
        try:
            InterventionRecordsService(actor=self._actor).add(
                case_links.case_from_student(self._student_id))
        except (InterventionRecordsError, case_links.CaseLinkError) as exc:
            messagebox.showerror("Create Support Case", str(exc), parent=self)
            return
        messagebox.showinfo("Create Support Case",
                            "Support case created from the student record and risk profile. "
                            "Open it in Support Cases to fill in the rest.", parent=self)
        self.reload_choices()
        self._after_change(refresh_support=True)

    def _log_contact(self):
        if not self._need_student():
            return
        try:
            InterventionRecordsService(actor=self._actor).log_contact(self._student_id)
        except InterventionRecordsError as exc:
            messagebox.showerror("Log Contact", str(exc), parent=self)
            return
        self._after_change(refresh_support=True)
