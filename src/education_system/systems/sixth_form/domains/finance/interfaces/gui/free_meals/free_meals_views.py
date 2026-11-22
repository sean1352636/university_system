"""Free meals (16-19) tab for the Bursary window: entitlements with
evidence, the daily meal log and the monthly claim report."""

from __future__ import annotations

import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
    free_meals as fm,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_free_meals_tab(nb: ttk.Notebook) -> "FreeMealsTab":
    return FreeMealsTab(nb)


class FreeMealsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Free Meals")
        inner = ttk.Notebook(self.frame)
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        self._build_entitlements(inner)
        self._build_day(inner)
        self._build_claim(inner)
        self.refresh()

    # ── Entitlements ──
    def _build_entitlements(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="Entitlements")
        self.ent_frame = f
        w.button_bar(f, [
            ("Refresh", self.refresh),
            ("Add Entitlement…", self.add),
            ("Edit Selected…", self.edit),
            ("Verify Evidence…", self.verify),
            ("End Selected…", self.end),
            ("Daily Allowance…", self.allowance),
        ])
        self.allow_lbl = ttk.Label(f, text="")
        self.allow_lbl.pack(fill="x", padx=10)
        self.ents = w.Table(f, [
            ("#", 50), ("Student", 80), ("Name", 160), ("Year", 70),
            ("Basis", 230), ("From", 90), ("To", 90), ("Daily", 70),
            ("Status", 80), ("Evidence", 220)])
        self.ents.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        names = self._names()
        a = fm.get_default_allowance()
        self.allow_lbl.configure(
            text="College daily allowance: "
                 + (w.money(a) if a is not None else
                    "not set — set it from the current ESFA free-meals rate"))
        self.ents.set_rows(
            [(e.entitlement_id, e.student_id, names.get(e.student_id, "?"),
              e.academic_year or "", e.eligibility_basis, e.start_date,
              e.end_date or "—", w.money(e.daily_allowance), e.status,
              f"{e.evidence_type or ''} — {e.evidence_verified_by}"
              if e.evidence_verified else "NOT verified")
             for e in fm.list_entitlements()],
            alert=lambda r: r[9] == "NOT verified" and r[8] == "Active")
        self.show_day()

    @staticmethod
    def _names() -> dict[str, str]:
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        return {s.student_id: s.full_name for s in students.list_students()}

    def add(self) -> None:
        f = w.ask_form(self.frame, "Free-meal entitlement", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("basis", "Eligibility", "combo", "", fm.ELIGIBILITY_BASES),
            ("start", "Start", "entry", _date.today().isoformat(), None),
            ("end", "End (blank = end of academic year)", "entry", "", None),
            ("allow", "Daily allowance (blank = college default)", "entry",
             "", None),
            ("ev", "Evidence seen (blank = not yet)", "combo", "",
             ["", *fm.EVIDENCE_TYPES]),
            ("ref", "Evidence reference", "entry", "", None),
            ("notes", "Notes", "text", "", None)],
            note="Check eligibility against current ESFA free-meals "
                 "guidance.")
        if not f:
            return
        d = {"student_id": w.student_id(f["student"]),
             "eligibility_basis": f["basis"], "start_date": f["start"],
             "end_date": f["end"], "daily_allowance": f["allow"],
             "notes": f["notes"]}
        if f["ev"]:
            d.update(evidence_type=f["ev"], evidence_reference=f["ref"],
                     evidence_verified_by=w.actor() or "unknown")
        if w.call(self.frame, lambda: fm.create_entitlement(d),
                  done="Entitlement added.") is not None:
            self.refresh()

    def edit(self) -> None:
        eid = w.need_selection(self.frame, self.ents)
        e = fm.get_entitlement(eid) if eid is not None else None
        if e is None:
            return
        f = w.ask_form(self.frame, f"Entitlement #{eid}", [
            ("eligibility_basis", "Eligibility", "combo", e.eligibility_basis,
             fm.ELIGIBILITY_BASES),
            ("start_date", "Start", "entry", e.start_date, None),
            ("end_date", "End", "entry", e.end_date or "", None),
            ("daily_allowance", "Daily allowance", "entry",
             f"{e.daily_allowance:.2f}", None),
            ("status", "Status", "combo", e.status, fm.ENTITLEMENT_STATUSES),
            ("notes", "Notes", "text", e.notes or "", None)])
        if f and w.call(self.frame, lambda: fm.update_entitlement(eid, f),
                        done="Updated.") is not None:
            self.refresh()

    def verify(self) -> None:
        eid = w.need_selection(self.frame, self.ents)
        if eid is None:
            return
        f = w.ask_form(self.frame, "Verify evidence", [
            ("type", "Evidence seen", "combo", fm.EVIDENCE_TYPES[0],
             fm.EVIDENCE_TYPES),
            ("ref", "Reference", "entry", "", None),
            ("by", "Verified by", "entry", w.actor(), None)])
        if f and w.call(self.frame, lambda: fm.verify_evidence(
                eid, verified_by=f["by"] or "", evidence_type=f["type"] or "",
                reference=f["ref"]), done="Evidence verified.") is not None:
            self.refresh()

    def end(self) -> None:
        eid = w.need_selection(self.frame, self.ents)
        if eid is None:
            return
        f = w.ask_form(self.frame, "End entitlement", [
            ("on", "End on", "entry", _date.today().isoformat(), None),
            ("reason", "Reason", "entry", "", None)])
        if f and w.call(self.frame, lambda: fm.end_entitlement(
                eid, on=f["on"], reason=f["reason"]),
                done="Ended.") is not None:
            self.refresh()

    def allowance(self) -> None:
        cur = fm.get_default_allowance()
        f = w.ask_form(self.frame, "Daily free-meal allowance", [
            ("v", "Allowance per day", "entry",
             f"{cur:.2f}" if cur is not None else "", None)],
            note="Set this from the current ESFA free-meals funding rate. "
                 "New entitlements take it unless given their own.")
        if f and w.call(self.frame, lambda: fm.set_default_allowance(
                w.num(f["v"]), by=w.actor() or "unknown"),
                done="Allowance saved.") is not None:
            self.refresh()

    # ── Daily log ──
    def _build_day(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="Daily Log")
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Date").pack(side="left")
        self.day = tk.StringVar(value=_date.today().isoformat())
        ttk.Entry(bar, textvariable=self.day, width=12).pack(side="left",
                                                             padx=4)
        for label, cmd in (("Show", self.show_day),
                           ("Mark Selected Taken", lambda: self.mark(True)),
                           ("Mark Selected Not Taken",
                            lambda: self.mark(False)),
                           ("Everyone Else Not Taken", self.fill_rest)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)
        self.day_lbl = ttk.Label(f, text="")
        self.day_lbl.pack(fill="x", padx=10)
        self.sheet = w.Table(f, [("Student", 90), ("Name", 200),
                                 ("Daily", 80), ("Recorded", 100),
                                 ("By", 120), ("Note", 300)])
        self.sheet.tree.configure(selectmode="extended")
        self.sheet.pack(fill="both", expand=True, padx=8, pady=8)

    def show_day(self) -> None:
        day = self.day.get().strip()
        rows = w.call(self.frame, lambda: fm.day_sheet(day))
        if rows is None:
            return
        names = self._names()
        self.sheet.set_rows(
            [(e.student_id, names.get(e.student_id, "?"),
              w.money(e.daily_allowance),
              "—" if u is None else ("taken" if u.taken else "not taken"),
              (u.recorded_by or "") if u else "", (u.note or "") if u else "")
             for e, u in rows], alert=lambda r: r[3] == "—")
        done = sum(1 for _e, u in rows if u is not None)
        self.day_lbl.configure(text=f"{len(rows)} entitled on {day}, "
                                    f"{done} recorded")

    def _selected_ids(self) -> list[str]:
        return [self.sheet.tree.item(i, "values")[0]
                for i in self.sheet.tree.selection()]

    def mark(self, taken: bool) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Select", "Select one or more learners.",
                                parent=self.frame)
            return
        day = self.day.get().strip()
        who = w.actor() or "unknown"
        w.call(self.frame, lambda: [fm.record_usage(
            sid, day, taken=taken, recorded_by=who) for sid in ids])
        self.show_day()

    def fill_rest(self) -> None:
        day = self.day.get().strip()
        rows = w.call(self.frame, lambda: fm.day_sheet(day)) or []
        rest = [e.student_id for e, u in rows if u is None]
        if not rest or not messagebox.askyesno(
                "Record", f"Mark {len(rest)} unrecorded learner(s) as not "
                "taken?", parent=self.frame):
            return
        who = w.actor() or "unknown"
        w.call(self.frame, lambda: [fm.record_usage(
            sid, day, taken=False, recorded_by=who) for sid in rest])
        self.show_day()

    # ── Monthly claim ──
    def _build_claim(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="Monthly Claim")
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Month (YYYY-MM)").pack(side="left")
        self.month = tk.StringVar(value=_date.today().strftime("%Y-%m"))
        ttk.Entry(bar, textvariable=self.month, width=10).pack(side="left",
                                                               padx=4)
        ttk.Button(bar, text="Run Report", command=self.claim).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Export CSV", command=self.export).pack(
            side="left", padx=2)
        self.claim_lbl = ttk.Label(f, text="")
        self.claim_lbl.pack(fill="x", padx=10)
        self.claim_tbl = w.Table(f, [
            ("Student", 80), ("Name", 180), ("Daily", 70), ("Eligible", 70),
            ("Taken", 60), ("Not taken", 70), ("Unrecorded", 80),
            ("Claim", 90)])
        self.claim_tbl.pack(fill="both", expand=True, padx=8, pady=8)

    def claim(self) -> None:
        rep = w.call(self.frame, lambda: fm.monthly_claim(self.month.get()))
        if rep is None:
            return
        self.claim_tbl.set_rows(
            [(l.student_id, l.student_name, w.money(l.daily_allowance),
              l.eligible_days, l.taken_days, l.not_taken_days,
              l.unrecorded_days, w.money(l.value_claimed))
             for l in rep.lines], alert=lambda r: r[6] not in (0, "0"))
        take = ("—" if rep.take_up_pct is None
                else f"{rep.take_up_pct:.1f}%")
        self.claim_lbl.configure(
            text=f"{rep.date_from} to {rep.date_to}: {rep.learners} learners"
                 f" · {rep.meals_taken} meals · take-up {take} · claim "
                 f"{w.money(rep.total_claimed)} · {rep.unrecorded_days} "
                 "day(s) not recorded")

    def export(self) -> None:
        path = w.call(self.frame, lambda: fm.export_claim_csv(
            self.month.get()))
        if path is not None:
            messagebox.showinfo("Exported", f"Written to\n{path}",
                                parent=self.frame)
