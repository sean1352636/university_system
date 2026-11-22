"""Bursary payment tabs for the Bursary window: Payment Schedule,
Payment Run, Attendance Holds and the 16-19 Fund (vulnerable bursary,
evidence checks and discretionary policy rules).

Added to ``build_bursaries_notebook`` after the original four tabs.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_bursary as rules,
    attendance_thresholds as thresholds,
)
from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
    bursaries as data,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui import (
    _widgets as w,
)


def add_payment_tabs(nb: ttk.Notebook) -> None:
    ScheduleTab(nb)
    RunTab(nb)
    HoldsTab(nb)
    FundTab(nb)


def _names() -> dict[str, str]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return {s.student_id: s.full_name for s in students.list_students()}


_INST_COLS = [("#", 50), ("Award", 60), ("Student", 80), ("Name", 160),
              ("Period", 170), ("Due", 90), ("Amount", 90), ("State", 80),
              ("Att %", 60), ("Decided by", 100), ("Note", 220)]


def _inst_rows(rows: list[data.Instalment]) -> list[tuple]:
    names = _names()
    return [(i.instalment_id, i.application_id, i.student_id,
             names.get(i.student_id, "?"), f"{i.period_from} → {i.period_to}",
             i.due_date, w.money(i.amount), i.state,
             "" if i.attendance_pct is None else f"{i.attendance_pct:.1f}",
             i.decided_by or "", i.note or "") for i in rows]


def _threshold() -> float:
    return thresholds.value_of(thresholds.BURSARY_HOLD, default=85.0) or 85.0


# ── Payment Schedule ───────────────────────────────────────────────

class ScheduleTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Payment Schedule")
        bar = w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Set Schedule for Award…", self.set_schedule),
            ("Rebuild Schedule…", self.rebuild),
            ("Cancel Instalment…", self.cancel),
        ])
        ttk.Label(bar, text="   State:").pack(side="left")
        self.state = tk.StringVar(value="")
        cb = ttk.Combobox(bar, textvariable=self.state, state="readonly",
                          width=12, values=["", *data.INSTALMENT_STATES])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.summary = ttk.Label(self.frame, text="")
        self.summary.pack(fill="x", padx=10)
        self.table = w.Table(self.frame, _INST_COLS)
        self.table.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        rows = data.list_instalments(state=self.state.get() or None)
        self.table.set_rows(_inst_rows(rows),
                            alert=lambda r: r[7] == data.INSTALMENT_HELD)
        s = data.schedule_summary()
        self.summary.configure(
            text=f"Pending {s.pending} ({w.money(s.pending_value)}) · due now "
                 f"{s.due_now} ({w.money(s.due_now_value)}) · held {s.held} "
                 f"({w.money(s.held_value)}) · paid {w.money(s.paid_value)} · "
                 f"forfeited {w.money(s.forfeited_value)}")

    def set_schedule(self) -> None:
        f = w.ask_form(self.frame, "Payment schedule", [
            ("app", "Approved application #", "entry", "", None),
            ("freq", "Frequency", "combo", data.DEFAULT_FREQUENCY,
             data.PAYMENT_FREQUENCIES),
            ("start", "Start (YYYY-MM-DD, blank = award date)", "entry", "",
             None),
            ("end", "End (blank = 31 July)", "entry", "", None),
            ("inst", "Fixed instalment (blank = split evenly)", "entry", "",
             None),
            ("cond", "Conditional on attendance", "check", True, None),
        ])
        if not f:
            return
        made = w.call(self.frame, lambda: data.set_payment_schedule(
            w.whole(f["app"]), frequency=f["freq"], start=f["start"],
            end=f["end"], instalment_amount=w.num(f["inst"]),
            attendance_conditional=f["cond"]))
        if made is not None:
            messagebox.showinfo("Scheduled",
                                f"{len(made)} instalment(s) scheduled.",
                                parent=self.frame)
            self.refresh()

    def rebuild(self) -> None:
        f = w.ask_form(self.frame, "Rebuild schedule", [
            ("app", "Application #", "entry", "", None),
            ("regen", "Drop undecided instalments first", "check", False,
             None)])
        if not f:
            return
        made = w.call(self.frame, lambda: data.generate_schedule(
            w.whole(f["app"]), regenerate=f["regen"]))
        if made is not None:
            messagebox.showinfo("Rebuilt", f"{len(made)} new instalment(s).",
                                parent=self.frame)
            self.refresh()

    def cancel(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        if iid is None:
            return
        f = w.ask_form(self.frame, f"Cancel instalment #{iid}",
                       [("reason", "Reason", "entry", "", None)])
        if f and w.call(self.frame, lambda: data.cancel_instalment(
                iid, reason=f["reason"] or "", by=w.actor()),
                done="Instalment cancelled.") is not None:
            self.refresh()


# ── Payment Run ────────────────────────────────────────────────────

class RunTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Payment Run")
        self.run: data.PaymentRun | None = None
        self.overrides: dict[int, str] = {}
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Due on or before").pack(side="left")
        self.as_of = tk.StringVar(value=_date.today().isoformat())
        ttk.Entry(bar, textvariable=self.as_of, width=12).pack(side="left",
                                                               padx=4)
        ttk.Label(bar, text="Threshold %").pack(side="left")
        # Filled when the tab is first shown: the threshold lives in the
        # attendance settings, which building the window must not touch.
        self.thr = tk.StringVar(value="")
        self.frame.bind("<Map>", self._first_show, add="+")
        ttk.Entry(bar, textvariable=self.thr, width=6).pack(side="left",
                                                            padx=4)
        for label, cmd in (("Preview Run", self.preview),
                           ("Toggle Pay/Hold", self.toggle),
                           ("Commit: Pay and Hold", self.commit_all),
                           ("Commit: Pay Only", self.commit_pay)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)
        self.summary = ttk.Label(self.frame,
                                 text="Preview a run to see what is due. "
                                      "Nothing is paid until you commit.")
        self.summary.pack(fill="x", padx=10)
        self.table = w.Table(self.frame, [
            ("#", 50), ("Student", 80), ("Name", 160), ("Type", 150),
            ("Period", 170), ("Amount", 90), ("Decision", 80),
            ("Reason", 380)])
        self.table.pack(fill="both", expand=True, padx=8, pady=8)

    def _first_show(self, _e=None) -> None:
        if not self.thr.get():
            self.thr.set(f"{_threshold():g}")

    def _show(self) -> None:
        if self.run is None:
            return
        rows = []
        for i in self.run.items:
            dec = self.overrides.get(i.instalment.instalment_id, i.decision)
            mark = " (override)" if i.instalment.instalment_id in \
                self.overrides else ""
            rows.append((i.instalment.instalment_id, i.instalment.student_id,
                         i.student_name, i.bursary_type,
                         f"{i.instalment.period_from} → "
                         f"{i.instalment.period_to}",
                         w.money(i.instalment.amount), dec + mark, i.reason))
        self.table.set_rows(rows, alert=lambda r: str(r[6]).startswith(
            data.DECISION_HOLD))
        self.summary.configure(text=f"As of {self.run.as_of}: "
                               f"{self.run.summary}"
                               + (f" · {len(self.overrides)} override(s)"
                                  if self.overrides else ""))

    def preview(self) -> None:
        thr = self.thr.get().strip()
        run = w.call(self.frame, lambda: data.payment_run(
            self.as_of.get().strip() or None,
            threshold_pct=w.num(thr) if thr else None))
        if run is not None:
            self.run, self.overrides = run, {}
            self._show()

    def toggle(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        if iid is None or self.run is None:
            return
        item = next(i for i in self.run.items
                    if i.instalment.instalment_id == iid)
        cur = self.overrides.get(iid, item.decision)
        new = data.DECISION_HOLD if cur == data.DECISION_PAY \
            else data.DECISION_PAY
        if new == item.decision:
            self.overrides.pop(iid, None)
        else:
            self.overrides[iid] = new
        self._show()

    def _commit(self, pay_only: bool) -> None:
        if self.run is None or not self.run.items:
            messagebox.showinfo("Nothing to commit", "Preview a run first.",
                                parent=self.frame)
            return
        who = w.actor()
        if not who:
            f = w.ask_form(self.frame, "Committed by",
                           [("who", "Your name", "entry", "", None)])
            if not f:
                return
            who = f["who"] or ""
        if not messagebox.askyesno(
                "Commit payment run",
                ("Pay the 'Pay' items and leave holds for review?"
                 if pay_only else "Pay and hold as shown?"),
                parent=self.frame):
            return
        counts = w.call(self.frame, lambda: data.commit_run(
            self.run, decided_by=who, pay_only=pay_only,
            overrides=self.overrides))
        if counts is not None:
            messagebox.showinfo(
                "Committed", f"{counts['Pay']} paid, {counts['Hold']} held, "
                f"{counts['skipped']} left for review.", parent=self.frame)
            self.preview()

    def commit_all(self) -> None:
        self._commit(False)

    def commit_pay(self) -> None:
        self._commit(True)


# ── Attendance Holds ───────────────────────────────────────────────

class HoldsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Attendance Holds")
        w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("Release Selected…", self.release),
            ("Forfeit Selected…", self.forfeit),
            ("Release Where Attendance Recovered…", self.recovered),
            ("Attendance Threshold…", self.set_threshold),
        ])
        self.summary = ttk.Label(self.frame, text="")
        self.summary.pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.Frame(pane)
        pane.add(top, weight=3)
        self.table = w.Table(top, _INST_COLS, height=12)
        self.table.pack(fill="both", expand=True)
        low = ttk.LabelFrame(pane, text="Attendance-condition exemptions")
        pane.add(low, weight=2)
        w.button_bar(low, [("Add Exemption…", self.add_exemption),
                           ("Remove Selected Exemption", self.remove_exemption)])
        self.ex = w.Table(low, [("#", 50), ("Student", 80), ("Name", 160),
                                ("Reason", 200), ("From", 90), ("To", 90),
                                ("Granted by", 100), ("Detail", 260)],
                          height=6)
        self.ex.pack(fill="both", expand=True, padx=4, pady=4)
        # Loaded when first shown (holds read the attendance records).
        self._loaded = False
        self.frame.bind("<Map>", self._first_show, add="+")

    def _first_show(self, _e=None) -> None:
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self) -> None:
        held = data.held_instalments()
        self.table.set_rows(_inst_rows(held))
        self.summary.configure(
            text=f"{len(held)} instalment(s) held, "
                 f"{w.money(sum(i.amount for i in held))} in total · payments "
                 f"are held below {_threshold():g}% attendance (unauthorised "
                 "absence only)")
        names = _names()
        self.ex.set_rows([(e.exemption_id, e.student_id,
                           names.get(e.student_id, "?"), e.reason,
                           e.start_date, e.end_date or "—",
                           e.granted_by or "", e.detail or "")
                          for e in rules.list_exemptions()])

    def release(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        if iid is None:
            return
        f = w.ask_form(self.frame, f"Release instalment #{iid}",
                       [("note", "Note", "entry", "", None)])
        if f and w.call(self.frame, lambda: data.release_instalment(
                iid, released_by=w.actor() or "unknown", note=f["note"]),
                done="Released and paid.") is not None:
            self.refresh()

    def forfeit(self) -> None:
        iid = w.need_selection(self.frame, self.table)
        if iid is None:
            return
        f = w.ask_form(self.frame, f"Forfeit instalment #{iid}",
                       [("reason", "Reason", "entry", "", None)],
                       note="Forfeiting writes the money off.")
        if f and w.call(self.frame, lambda: data.forfeit_instalment(
                iid, reason=f["reason"] or "", by=w.actor()),
                done="Forfeited.") is not None:
            self.refresh()

    def recovered(self) -> None:
        f = w.ask_form(self.frame, "Release on recovery", [
            ("from", "Attendance window from (YYYY-MM-DD)", "entry", "",
             None),
            ("to", "to", "entry", _date.today().isoformat(), None)])
        if not f:
            return
        out = w.call(self.frame, lambda: data.release_on_recovery(
            date_from=f["from"] or "", date_to=f["to"] or "",
            released_by=w.actor() or "unknown"))
        if out is not None:
            messagebox.showinfo("Released", f"{len(out)} released.",
                                parent=self.frame)
            self.refresh()

    def set_threshold(self) -> None:
        f = w.ask_form(self.frame, "Bursary attendance threshold", [
            ("v", "Hold payments below (%)", "entry", f"{_threshold():g}",
             None)])
        if f and w.call(self.frame, lambda: thresholds.set_threshold(
                thresholds.BURSARY_HOLD, w.num(f["v"]),
                actor=w.actor() or None),
                done="Threshold updated.") is not None:
            self.refresh()

    def add_exemption(self) -> None:
        f = w.ask_form(self.frame, "Exempt from attendance condition", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("reason", "Reason", "combo", rules.EXEMPTION_REASONS[0],
             rules.EXEMPTION_REASONS),
            ("start", "From", "entry", _date.today().isoformat(), None),
            ("end", "To (blank = open)", "entry", "", None),
            ("detail", "Detail", "text", "", None)])
        if f and w.call(self.frame, lambda: rules.add_exemption(
                w.student_id(f["student"]) or "", reason=f["reason"] or "",
                start_date=f["start"], end_date=f["end"],
                detail=f["detail"], granted_by=w.actor() or None),
                done="Exemption added.") is not None:
            self.refresh()

    def remove_exemption(self) -> None:
        eid = w.need_selection(self.frame, self.ex)
        if eid is not None and messagebox.askyesno(
                "Remove", f"Remove exemption #{eid}?", parent=self.frame):
            w.call(self.frame, lambda: rules.remove_exemption(eid))
            self.refresh()


# ── 16-19 Fund: vulnerable bursary, evidence, policy ──────────────

class FundTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="16-19 Fund")
        w.button_bar(self.frame, [
            ("Refresh", self.refresh),
            ("New Vulnerable Application…", self.new_vulnerable),
            ("Verify Evidence…", self.verify),
            ("Award Vulnerable Bursary…", self.award),
            ("Apply Discretionary Policy…", self.apply_policy),
        ])
        ttk.Label(self.frame, text=(
            f"Vulnerable bursary: up to "
            f"{w.money(data.VULNERABLE_MAX_AWARD)} a year, needs a defined "
            "group and verified evidence (check current ESFA guidance). "
            "Discretionary awards follow the policy rules below."),
            wraplength=1200).pack(fill="x", padx=10)
        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.LabelFrame(pane, text="Applications needing a decision")
        pane.add(top, weight=3)
        self.apps = w.Table(top, [
            ("#", 50), ("Student", 80), ("Name", 150), ("Type", 150),
            ("Group", 220), ("Status", 110), ("Evidence", 200),
            ("Awarded", 90), ("Pay", 80)], height=10)
        self.apps.pack(fill="both", expand=True, padx=4, pady=4)
        low = ttk.LabelFrame(pane, text="Discretionary policy rules "
                                        "(tried in priority order)")
        pane.add(low, weight=2)
        w.button_bar(low, [("Add Rule…", self.add_rule),
                           ("Edit Rule…", self.edit_rule),
                           ("Delete / Retire Rule", self.delete_rule)])
        self.rules = w.Table(low, [
            ("#", 40), ("Name", 160), ("Year", 70), ("Type", 150),
            ("Basis", 160), ("Max income", 90), ("Min hh", 60),
            ("Award", 80), ("Pay", 80), ("Att?", 40), ("Evid?", 45),
            ("Pri", 40), ("Active", 50)], height=6)
        self.rules.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        names = _names()
        apps = [a for a in data.list_applications()
                if a.status not in ("Rejected", "Cancelled", "Withdrawn")]
        self.apps.set_rows(
            [(a.application_id, a.student_id, names.get(a.student_id, "?"),
              a.bursary_type, a.vulnerable_category or "", a.status,
              f"{a.evidence_type} — {a.evidence_verified_by}"
              if a.evidence_verified else "not verified",
              w.money(a.amount_awarded) if a.amount_awarded else "",
              a.payment_frequency or "") for a in apps],
            alert=lambda r: r[6] == "not verified")
        self.rules.set_rows(
            [(r.rule_id, r.name, r.academic_year or "any", r.bursary_type,
              r.eligibility_basis or "any",
              w.money(r.max_household_income)
              if r.max_household_income is not None else "—",
              r.min_household_size or "—", w.money(r.award_amount),
              r.payment_frequency, "Y" if r.attendance_conditional else "N",
              "Y" if r.requires_evidence else "N", r.priority,
              "Y" if r.active else "N") for r in data.list_rules()])

    def new_vulnerable(self) -> None:
        f = w.ask_form(self.frame, "Vulnerable bursary application", [
            ("student", "Student", "combo", "", w.student_choices()),
            ("cat", "Vulnerable group", "combo", "",
             data.VULNERABLE_CATEGORIES),
            ("year", "Academic year (blank = current)", "entry", "", None),
            ("reason", "Notes", "text", "", None)],
            note="Check the groups against current ESFA 16-19 Bursary "
                 "Fund guidance.")
        if f and w.call(self.frame, lambda: data.create_vulnerable_application(
                w.student_id(f["student"]) or "", category=f["cat"] or "",
                academic_year=f["year"], reason=f["reason"]),
                done="Application opened (Awaiting Evidence).") is not None:
            self.refresh()

    def verify(self) -> None:
        aid = w.need_selection(self.frame, self.apps)
        if aid is None:
            return
        f = w.ask_form(self.frame, f"Verify evidence — application #{aid}", [
            ("type", "Evidence seen", "combo", data.EVIDENCE_TYPES[0],
             data.EVIDENCE_TYPES),
            ("by", "Verified by", "entry", w.actor(), None),
            ("note", "Note", "entry", "", None)])
        if f and w.call(self.frame, lambda: data.verify_evidence(
                aid, verified_by=f["by"] or "", evidence_type=f["type"] or "",
                note=f["note"]), done="Evidence verified.") is not None:
            self.refresh()

    def award(self) -> None:
        aid = w.need_selection(self.frame, self.apps)
        if aid is None:
            return
        f = w.ask_form(self.frame, f"Award vulnerable bursary #{aid}", [
            ("amount", f"Amount (max {w.money(data.VULNERABLE_MAX_AWARD)})",
             "entry", f"{data.VULNERABLE_MAX_AWARD:.2f}", None),
            ("freq", "Pay", "combo", data.DEFAULT_FREQUENCY,
             data.PAYMENT_FREQUENCIES),
            ("start", "Start (blank = year start)", "entry", "", None)],
            note="Never attendance-conditional. Use a lower amount for a "
                 "pro-rata award.")
        if f and w.call(self.frame, lambda: data.award_vulnerable(
                aid, amount=w.num(f["amount"]), frequency=f["freq"],
                start=f["start"], assessed_by=w.actor() or None),
                done="Awarded and scheduled.") is not None:
            self.refresh()

    def apply_policy(self) -> None:
        aid = w.need_selection(self.frame, self.apps)
        if aid is None:
            return
        dec = w.call(self.frame, lambda: data.evaluate_discretionary(aid))
        if dec is None:
            return
        text = "\n".join(f"• {r}" for r in dec.reasons)
        if not dec.eligible:
            messagebox.showinfo("Not eligible", text or "No rule matched.",
                                parent=self.frame)
            return
        if messagebox.askyesno(
                "Apply policy",
                f"{text}\n\nApprove {w.money(dec.amount)} under "
                f"'{dec.rule.name}' ({dec.rule.payment_frequency})?",
                parent=self.frame):
            if w.call(self.frame, lambda: data.apply_discretionary_policy(
                    aid, assessed_by=w.actor() or None),
                    done="Approved and scheduled.") is not None:
                self.refresh()

    def _rule_form(self, cur: dict) -> dict | None:
        types = [t for t in data.BURSARY_TYPES if t != data.VULNERABLE_TYPE]
        f = w.ask_form(self.frame, "Policy rule", [
            ("name", "Name", "entry", cur.get("name", ""), None),
            ("academic_year", "Academic year (blank = any)", "entry",
             cur.get("academic_year") or "", None),
            ("bursary_type", "Bursary type", "combo",
             cur.get("bursary_type") or data.DISCRETIONARY_TYPE, types),
            ("eligibility_basis", "Eligibility basis (blank = any)", "combo",
             cur.get("eligibility_basis") or "",
             ["", *data.ELIGIBILITY_BASES]),
            ("max_household_income", "Max household income", "entry",
             cur.get("max_household_income") or "", None),
            ("min_household_size", "Min household size", "entry",
             cur.get("min_household_size") or "", None),
            ("award_amount", "Award amount", "entry",
             cur.get("award_amount") or "", None),
            ("payment_frequency", "Pay", "combo",
             cur.get("payment_frequency") or data.DEFAULT_FREQUENCY,
             data.PAYMENT_FREQUENCIES),
            ("attendance_conditional", "Conditional on attendance", "check",
             cur.get("attendance_conditional", True), None),
            ("requires_evidence", "Evidence must be verified", "check",
             cur.get("requires_evidence", True), None),
            ("priority", "Priority (lower first)", "entry",
             cur.get("priority") or 100, None),
            ("active", "Active", "check", cur.get("active", True), None),
            ("notes", "Notes", "text", cur.get("notes") or "", None)])
        return f

    def add_rule(self) -> None:
        f = self._rule_form({})
        if f and w.call(self.frame, lambda: data.create_rule(f),
                        done="Rule added.") is not None:
            self.refresh()

    def edit_rule(self) -> None:
        rid = w.need_selection(self.frame, self.rules)
        rule = data.get_rule(rid) if rid is not None else None
        if rule is None:
            return
        f = self._rule_form(vars(rule))
        if f and w.call(self.frame, lambda: data.update_rule(rid, f),
                        done="Rule updated.") is not None:
            self.refresh()

    def delete_rule(self) -> None:
        rid = w.need_selection(self.frame, self.rules)
        if rid is not None and messagebox.askyesno(
                "Delete rule", "Delete this rule? (A rule already used for "
                "an award is retired instead.)", parent=self.frame):
            w.call(self.frame, lambda: data.delete_rule(rid))
            self.refresh()
