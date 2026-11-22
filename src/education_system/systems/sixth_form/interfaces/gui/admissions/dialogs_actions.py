"""Action dialogs (status, offer, interview, scorecard, ...) for Sixth Form Admissions.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
import datetime as _dt
import os
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    OFFER_TYPES,
    RECOMMENDATIONS,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from . import applicant_actions as act
from ._common import _today


class AskChoiceDialog:
    """Tiny modal that returns a single choice from a combobox."""

    def __init__(self, parent: tk.Misc, title: str, label: str,
                 choices: list[str]) -> None:
        self.result: str | None = None
        win = make_toplevel(parent)
        win.title(title)
        grab_when_viewable(win)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=label).grid(row=0, column=0, sticky="e", padx=4)
        cb = ttk.Combobox(frm, values=choices, state="readonly",
                          width=max(24, min(60, max(map(len, choices),
                                                    default=0) + 2)))
        if choices:
            cb.current(0)
        cb.grid(row=0, column=1, sticky="w", padx=4)
        bar = ttk.Frame(frm)
        bar.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        def ok() -> None:
            self.result = cb.get()
            win.destroy()
        ttk.Button(bar, text="OK", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()


class ScorecardDialog:
    """Capture/edit the structured interview scorecard (item 25)."""

    def __init__(self, parent: tk.Misc, applicant_id: str,
                 on_save: Callable[[], None]) -> None:
        self.aid = applicant_id
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Interview scorecard — {applicant_id}")
        grab_when_viewable(self.win)
        existing = data.get_interview_score(applicant_id)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        scale = ("", "1", "2", "3", "4", "5")
        self.cbs: dict[str, ttk.Combobox] = {}
        for i, (attr, lbl) in enumerate((
                ("motivation", "Motivation"),
                ("subject_fit", "Subject fit"),
                ("attainment", "Attainment"))):
            ttk.Label(form, text=f"{lbl} (1–5):").grid(
                row=i, column=0, sticky="e", pady=4)
            cb = ttk.Combobox(form, values=scale, state="readonly", width=6)
            cb.set(str(getattr(existing, attr) or "") if existing else "")
            cb.grid(row=i, column=1, sticky="w", padx=6)
            self.cbs[attr] = cb
        ttk.Label(form, text="Recommendation:").grid(row=3, column=0,
                                                        sticky="e", pady=4)
        self.rec_cb = ttk.Combobox(form, values=("",) + RECOMMENDATIONS,
                                     state="readonly", width=18)
        self.rec_cb.set(existing.recommendation if existing
                         and existing.recommendation else "")
        self.rec_cb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Scored by:").grid(row=4, column=0,
                                                  sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=24)
        if existing and existing.scored_by:
            self.by_e.insert(0, existing.scored_by)
        self.by_e.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Comments:").grid(row=5, column=0,
                                                 sticky="ne", pady=4)
        self.comments_t = tk.Text(form, width=44, height=4)
        if existing and existing.comments:
            self.comments_t.insert("1.0", existing.comments)
        self.comments_t.grid(row=5, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.save_interview_score(
                self.aid,
                motivation=self.cbs["motivation"].get() or None,
                subject_fit=self.cbs["subject_fit"].get() or None,
                attainment=self.cbs["attainment"].get() or None,
                recommendation=self.rec_cb.get() or None,
                scored_by=self.by_e.get().strip() or None,
                comments=self.comments_t.get("1.0", "end").strip() or None,
            )
        except Exception as e:  # noqa: BLE001 — every refusal is shown
            act.show_error(self.win, "Scorecard", e)
            return
        self.win.destroy()
        self.on_save()


class TextViewerDialog:
    """Read-only text viewer with Copy and Save-to-file (items 31, 47, 50)."""

    def __init__(self, parent: tk.Misc, title: str, text: str,
                 save_name: str | None = None) -> None:
        self.text = text
        self.win = make_toplevel(parent)
        self.win.title(title)
        self.win.geometry("620x520")
        box = tk.Text(self.win, wrap="word", font=("TkFixedFont", 10))
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="Copy",
                    command=self._copy).pack(side="left")
        if save_name:
            ttk.Button(bar, text="Save…",
                        command=lambda: self._save(save_name)).pack(
                side="left", padx=6)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _copy(self) -> None:
        self.win.clipboard_clear()
        self.win.clipboard_append(self.text)

    def _save(self, name: str) -> None:
        ext = os.path.splitext(name)[1] or ".txt"
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=ext, initialfile=name)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text)
        except OSError as e:
            messagebox.showerror("Save", str(e), parent=self.win)
            return
        messagebox.showinfo("Saved", f"Saved to {path}", parent=self.win)


class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Status — {existing.applicant_id}")
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        # Only the statuses the workflow allows next ("Enrolled" comes
        # from converting; a closed application is reopened with a reason).
        allowed = data.allowed_statuses(existing.applicant_id)
        self.cb = ttk.Combobox(form, values=(existing.status,) + tuple(
            st for st in allowed if st != existing.status),
            state="readonly", width=22)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        if not allowed:
            from education_system.systems.sixth_form.domain.admissions import (
                status_rules,
            )
            hint = ("Closed — use Reopen (with a reason) to move it on."
                    if existing.status in status_rules.REOPENABLE
                    else "No further status change from here.")
            ttk.Label(form, text=hint, foreground="#a06000").grid(
                row=1, column=2, sticky="w", padx=4)
        ttk.Label(form, text="Decided by:").grid(row=2, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reason code:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(
            form, values=("",) + data.DECISION_REASONS,
            state="readonly", width=30)
        self.reason_cb.set(existing.decision_reason or "")
        self.reason_cb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=4, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        if existing.decision_notes:
            self.notes_t.insert("1.0", existing.decision_notes)
        self.notes_t.grid(row=4, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        act.gate(ttk.Button(bar, text="Save", command=self._save),
                 act.can_admissions()).pack(side="left")
        act.gate(ttk.Button(bar, text="Save + email…",
                            command=lambda: self._save(email=True)),
                 act.can_admissions()).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self, email: bool = False) -> None:
        try:
            data.record_decision(
                self.existing.applicant_id, self.cb.get(),
                reason=self.reason_cb.get() or None,
                decided_by=self.by_e.get().strip() or None,
                notes=self.notes_t.get("1.0", "end").strip() or None,
            )
        except Exception as e:  # noqa: BLE001
            act.show_error(self.win, "Save failed", e)
            return
        master = self.win.master
        self.win.destroy()
        self.on_save()
        if email:
            from . import applicant_email
            applicant_email.email_applicant(master,
                                            self.existing.applicant_id)


class OfferDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Make offer — {existing.applicant_id}")
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Offer type:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=OFFER_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(existing.offer_type or DEFAULT_OFFER_TYPE)
        self.type_cb.grid(row=1, column=1, sticky="w", padx=6)
        # Structured conditions builder (item 29): per-subject grade rows
        # that compose into the free-text conditions box.
        builder = ttk.LabelFrame(form, text="Conditions builder")
        builder.grid(row=2, column=0, columnspan=2, sticky="we",
                      padx=4, pady=4)
        self._cond_rows: list[tuple[ttk.Combobox, ttk.Combobox]] = []
        subjects = existing.subjects or ["", "", ""]
        grades = ("A*", "A", "B", "C", "D", "E", "9", "8", "7", "6", "5", "4")
        for i in range(max(3, len(subjects))):
            ttk.Label(builder, text=f"Subject {i+1}:").grid(
                row=i, column=0, sticky="e", padx=4, pady=1)
            subj = ttk.Combobox(builder, width=24,
                                  values=tuple(existing.subjects))
            if i < len(subjects):
                subj.set(subjects[i])
            subj.grid(row=i, column=1, padx=4, pady=1)
            ttk.Label(builder, text="grade ≥").grid(row=i, column=2, padx=2)
            gr = ttk.Combobox(builder, width=5, values=("",) + grades,
                               state="readonly")
            gr.grid(row=i, column=3, padx=4, pady=1)
            self._cond_rows.append((subj, gr))
        ttk.Button(builder, text="Build conditions text",
                    command=self._build_conditions).grid(
            row=99, column=0, columnspan=2, pady=4)
        ttk.Button(builder, text="From entry requirements",
                    command=self._from_requirements).grid(
            row=99, column=2, columnspan=2, pady=4)
        self._generated_text: str | None = None

        ttk.Label(form, text="Conditions:").grid(row=3, column=0,
                                                    sticky="ne", pady=4)
        self.cond_t = tk.Text(form, width=44, height=3)
        if existing.offer_conditions:
            self.cond_t.insert("1.0", existing.offer_conditions)
        self.cond_t.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Offer expiry:").grid(row=4, column=0,
                                                      sticky="e", pady=4)
        self.expiry_e = ttk.Entry(form, width=14)
        self.expiry_e.insert(0, existing.offer_expiry
                              or (_dt.date.today()
                                  + _dt.timedelta(days=28)).isoformat())
        self.expiry_e.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decided by:").grid(row=5, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=5, column=1, sticky="w", padx=6)
        places = act.places_summary(existing.applicant_id)
        ttk.Label(form, text="Places left: " + (places or "no limits set "
                                                "for these programmes"),
                  foreground="#205080", wraplength=520).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        act.gate(ttk.Button(bar, text="Make offer", command=self._save),
                 act.can_admissions()).pack(side="left")
        ttk.Button(bar, text="Preview letter…",
                    command=self._preview_letter).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _build_conditions(self) -> None:
        parts = []
        for subj, gr in self._cond_rows:
            s, g = subj.get().strip(), gr.get().strip()
            if s and g:
                parts.append(f"{s} grade {g} or above")
        if not parts:
            messagebox.showinfo("Conditions",
                                  "Pick at least one subject + grade.")
            return
        self.cond_t.delete("1.0", "end")
        self.cond_t.insert("1.0", "; ".join(parts))

    def _from_requirements(self) -> None:
        from education_system.systems.sixth_form.interfaces.gui.admissions import (
            entry_requirements_views as _erv,
        )
        text = _erv.conditions_from_requirements(self.win,
                                                 self.existing.applicant_id)
        if text is not None:
            self._generated_text = text
            self.cond_t.delete("1.0", "end")
            self.cond_t.insert("1.0", text)

    def _save(self) -> None:
        text = self.cond_t.get("1.0", "end").strip() or None
        if (self._generated_text and text == self._generated_text
                and self.type_cb.get() == "Conditional"):
            from education_system.systems.sixth_form.interfaces.gui.admissions import (
                entry_requirements_views as _erv,
            )  # unchanged generated wording: keep the structured rows
            if _erv.save_structured_offer(
                    self.win, self.existing.applicant_id,
                    self.by_e.get().strip() or None,
                    self.expiry_e.get().strip()):
                self.win.destroy()
                self.on_save()
            return
        if not self._offer(text):
            return
        self.win.destroy()
        self.on_save()

    def _offer(self, text: str | None) -> bool:
        """Make the offer (handling a full programme) and set its expiry
        (an unconditional offer may still have a response deadline)."""
        out = act.make_offer(self.win, self.existing.applicant_id,
                             offer_type=self.type_cb.get(),
                             conditions=text,
                             decided_by=self.by_e.get().strip() or None)
        if out is None:
            return False
        ok, _ = act.attempt(self.win, "Offer expiry", data.set_offer_expiry,
                            self.existing.applicant_id,
                            self.expiry_e.get().strip() or None)
        return ok

    def _preview_letter(self) -> None:
        # Persist the in-progress offer first so the letter reflects it.
        if not self._offer(self.cond_t.get("1.0", "end").strip() or None):
            return
        TextViewerDialog(
            self.win, f"Offer letter — {self.existing.applicant_id}",
            reports.render_offer_letter(self.existing.applicant_id),
            save_name=f"offer_{self.existing.applicant_id}.txt")
        self.on_save()


class ScheduleDialog:
    def __init__(self, parent: tk.Misc, applicants: list[Applicant],
                 on_save: Callable[[], None]) -> None:
        self.applicants = applicants
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title("Schedule interview")
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Applicant:").grid(row=0, column=0,
                                                   sticky="e", pady=4)
        self._ids = [a.applicant_id for a in applicants]
        self.cb = ttk.Combobox(
            form,
            values=[f"{a.applicant_id} — {a.full_name}"
                     for a in applicants],
            state="readonly", width=44)
        self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Date:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Interviewer:").grid(row=2, column=0,
                                                     sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Schedule",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            messagebox.showerror("Schedule", "Pick an applicant")
            return
        date = self.date_e.get().strip()
        interviewer = self.by_e.get().strip() or None
        # Clash detection (item 23): same interviewer, same day.
        if interviewer:
            clashes = [
                a for a in data.list_applicants()
                if a.interviewer == interviewer
                and a.interview_date == date
                and a.applicant_id != self._ids[idx]]
            if clashes:
                who = ", ".join(a.full_name for a in clashes)
                if not messagebox.askyesno(
                        "Possible clash",
                        f"{interviewer} already interviews {who} on "
                        f"{date}.\nSchedule anyway?"):
                    return
        try:
            data.schedule_interview(
                self._ids[idx],
                interview_date=date,
                interviewer=interviewer,
            )
        except Exception as e:
            messagebox.showerror("Schedule failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RecordOutcomeDialog:
    """Record an interview outcome (item 24): notes move the applicant to
    'Interviewed' and the scorecard (item 25) can be filled in one place."""

    def __init__(self, parent: tk.Misc, applicant: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.aid = applicant.applicant_id
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Interview outcome — {applicant.applicant_id}")
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=f"{applicant.full_name} — interviewed "
                              f"{applicant.interview_date or '—'} by "
                              f"{applicant.interviewer or '—'}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Interview notes:").grid(
            row=1, column=0, sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=50, height=5)
        if applicant.interview_notes:
            self.notes_t.insert("1.0", applicant.interview_notes)
        self.notes_t.grid(row=1, column=1, sticky="w", padx=6)

        # Inline scorecard.
        score = data.get_interview_score(self.aid)
        scale = ("", "1", "2", "3", "4", "5")
        self.cbs: dict[str, ttk.Combobox] = {}
        for i, (attr, lbl) in enumerate((
                ("motivation", "Motivation"),
                ("subject_fit", "Subject fit"),
                ("attainment", "Attainment"))):
            ttk.Label(form, text=f"{lbl} (1–5):").grid(
                row=2 + i, column=0, sticky="e", pady=2)
            cb = ttk.Combobox(form, values=scale, state="readonly", width=6)
            cb.set(str(getattr(score, attr) or "") if score else "")
            cb.grid(row=2 + i, column=1, sticky="w", padx=6)
            self.cbs[attr] = cb
        ttk.Label(form, text="Recommendation:").grid(
            row=5, column=0, sticky="e", pady=2)
        self.rec_cb = ttk.Combobox(form, values=("",) + RECOMMENDATIONS,
                                     state="readonly", width=18)
        self.rec_cb.set(score.recommendation if score
                         and score.recommendation else "")
        self.rec_cb.grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Scored by:").grid(row=6, column=0,
                                                  sticky="e", pady=2)
        self.by_e = ttk.Entry(form, width=24)
        if score and score.scored_by:
            self.by_e.insert(0, score.scored_by)
        elif applicant.interviewer:
            self.by_e.insert(0, applicant.interviewer)
        self.by_e.grid(row=6, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save outcome",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.record_interview(
                self.aid,
                interview_notes=self.notes_t.get("1.0", "end").strip()
                or None)
            if any(self.cbs[a].get() for a in self.cbs) or self.rec_cb.get():
                data.save_interview_score(
                    self.aid,
                    motivation=self.cbs["motivation"].get() or None,
                    subject_fit=self.cbs["subject_fit"].get() or None,
                    attainment=self.cbs["attainment"].get() or None,
                    recommendation=self.rec_cb.get() or None,
                    scored_by=self.by_e.get().strip() or None,
                )
        except Exception as e:  # noqa: BLE001 — every refusal is shown
            act.show_error(self.win, "Record outcome", e)
            return
        self.win.destroy()
        self.on_save()


class DecisionDayDialog:
    """Step through interviewed applicants making a decision each (item 35)."""

    def __init__(self, parent: tk.Misc, queue: list[Applicant],
                 on_done: Callable[[], None]) -> None:
        self.queue = queue
        self.on_done = on_done
        self.i = 0
        self.win = make_toplevel(parent)
        self.win.title("Decision day")
        self.win.geometry("580x560")
        grab_when_viewable(self.win)
        self.body = ttk.Frame(self.win, padding=12)
        self.body.pack(fill="both", expand=True)
        self._render()

    def _render(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        if self.i >= len(self.queue):
            ttk.Label(self.body, text="All applicants reviewed.",
                       font=("TkDefaultFont", 12)).pack(pady=30)
            ttk.Button(self.body, text="Close",
                        command=self._close).pack()
            return
        a = data.get_applicant(self.queue[self.i].applicant_id)
        if a is None:  # erased mid-session
            self.i += 1
            self._render()
            return
        ttk.Label(self.body, text=f"Applicant {self.i + 1} of "
                                   f"{len(self.queue)}",
                   foreground="#666").pack(anchor="w")
        ttk.Label(self.body, text=f"{a.full_name}  ({a.applicant_id})",
                   font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(self.body, text=f"Subjects: {', '.join(a.subjects) or '—'}"
                                   ).pack(anchor="w")
        ttk.Label(self.body, text=f"Predicted GCSEs: "
                                   f"{a.predicted_gcses or '—'}").pack(
            anchor="w")
        score = data.get_interview_score(a.applicant_id)
        if score:
            ttk.Label(
                self.body,
                text=f"Scorecard avg: {score.average} · "
                     f"Recommendation: {score.recommendation or '—'}",
                foreground="#205080").pack(anchor="w", pady=(4, 0))
        if a.interview_notes:
            ttk.Label(self.body, text=f"Interview notes: {a.interview_notes}",
                       wraplength=540, foreground="#444").pack(
                anchor="w", pady=(2, 0))

        form = ttk.Frame(self.body)
        form.pack(fill="x", pady=10)
        ttk.Label(form, text="Decided by:").grid(row=0, column=0, sticky="e")
        self.by_e = ttk.Entry(form, width=22)
        self.by_e.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Conditions:").grid(row=1, column=0, sticky="e")
        self.cond_e = ttk.Entry(form, width=40)
        self.cond_e.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(form, text="Reason:").grid(row=2, column=0, sticky="e")
        self.reason_cb = ttk.Combobox(form, values=("",) + data.DECISION_REASONS,
                                        state="readonly", width=30)
        self.reason_cb.grid(row=2, column=1, sticky="w", padx=4)

        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="Make offer",
                    command=self._offer).pack(side="left")
        ttk.Button(bar, text="Waitlist",
                    command=self._waitlist).pack(side="left", padx=4)
        ttk.Button(bar, text="Reject",
                    command=self._reject).pack(side="left", padx=4)
        ttk.Button(bar, text="Skip",
                    command=self._advance).pack(side="left", padx=4)
        ttk.Button(bar, text="Finish",
                    command=self._close).pack(side="right")

    def _current(self) -> str:
        return self.queue[self.i].applicant_id

    def _offer(self) -> None:
        if act.make_offer(self.win, self._current(),
                          conditions=self.cond_e.get().strip() or None,
                          decided_by=self.by_e.get().strip() or None) is None:
            return
        self._advance()

    def _waitlist(self) -> None:
        try:
            data.set_status(self._current(), "Waitlisted",
                            decision_by=self.by_e.get().strip() or None)
            existing = data.get_waitlist()
            data.set_waitlist_rank(self._current(), len(existing))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Waitlist", str(e))
            return
        self._advance()

    def _reject(self) -> None:
        try:
            data.record_decision(self._current(), "Rejected",
                                  reason=self.reason_cb.get() or None,
                                  decided_by=self.by_e.get().strip() or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Reject", str(e))
            return
        self._advance()

    def _advance(self) -> None:
        self.i += 1
        self._render()

    def _close(self) -> None:
        self.win.destroy()
        self.on_done()
