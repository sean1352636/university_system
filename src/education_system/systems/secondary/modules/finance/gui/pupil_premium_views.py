"""Pupil Premium screen.

The old Pupil Premium window is the first tab ("Records"), with its toolbar
(Year, Academic year, Category and Status filters; Apply, New / update,
Edit, Interventions, Delete, Refresh), its columns (ID, Academic yr, Pupil,
Yr, Category, Status, Funding £, Keyworker), its record dialog and its
Interventions window (Add, Edit, Delete, Refresh; ID, Start, Status, Spend £,
Impact, Title). Added to it: record summary, Record FSM from pupil records,
open pupil, history and export.

New tabs: Cohort (everyone eligible this year: recorded categories, FSM from
the pupil record and Ever 6, with funding), Strategy & plan (statement,
budget, spending plan lines in the three tiers, copy to next year), Activities
(allocate a plan line to pupils), Impact (pupil premium against other pupils
for attendance, behaviour and attainment, read from those modules) and Rates.
Rules are in :mod:`modules.finance.domain.pupil_premium`.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.finance.domain import pupil_premium as PP
from education_system.systems.secondary.modules.send.gui.send_page import (
    YEARS,
    Table,
    TabbedPage,
    changed,
    filled,
    money,
    num,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W


def _years() -> list[str]:
    cur = PP.current_year()
    start = int(cur[:4])
    return [f"{y}/{(y + 1) % 100:02d}" for y in range(start + 1, start - 7, -1)]


def _getter(obj: Any) -> Callable[..., Any]:
    return (lambda k, d="": getattr(obj, k) if obj is not None and getattr(obj, k) is not None
            else d)


def _el_fields(e: PP.Eligibility | None, year: str) -> list:
    g = _getter(e)
    head = [] if e else [("pupil_id", "Pupil ID / admission no.", "", None),
                         ("academic_year", "Academic year", year, _years())]
    return head + [
        ("category", "Category", g("category", PP.CATEGORIES[0]), list(PP.CATEGORIES)),
        ("status", "Status", g("status", PP.PP_STATUSES[0]), list(PP.PP_STATUSES)),
        ("funding_amount", "Funding £ (blank = the rate)", g("funding_amount"), None),
        ("start_date", "Start date", g("start_date"), None),
        ("end_date", "End date", g("end_date"), None),
        ("eligibility_source", "Eligibility source / evidence", g("eligibility_source"), None),
        ("keyworker", "Keyworker", g("keyworker"), None),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _act_fields(a: PP.Activity | None, lines: list[PP.Line]) -> list:
    g = _getter(a)
    line_choices = [""] + [f"{x.line_id} - {x.title}" for x in lines]
    cur_line = next((c for c in line_choices if a and a.line_id
                     and c.startswith(f"{a.line_id} - ")), "")
    return [
        ("title", "Title", g("title"), None),
        ("description", "Description", g("description"), "text"),
        ("spend", "Spend £", g("spend"), None),
        ("start_date", "Start date", g("start_date"), None),
        ("end_date", "End date", g("end_date"), None),
        ("status", "Status", g("status", PP.INTERVENTION_STATUSES[0]),
         list(PP.INTERVENTION_STATUSES)),
        ("impact_rating", "Impact", g("impact_rating", PP.IMPACT_RATINGS[0]),
         list(PP.IMPACT_RATINGS)),
        ("impact_notes", "Impact notes", g("impact_notes"), "text"),
        ("line_id", "Plan line", cur_line, line_choices),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _line_id(v: dict[str, Any]) -> dict[str, Any]:
    if "line_id" in v:
        v["line_id"] = str(v["line_id"] or "").split(" - ")[0] or None
    return v


def _line_fields(x: PP.Line | None) -> list:
    g = _getter(x)
    return [
        ("tier", "Tier", g("tier", PP.TIERS[0]), list(PP.TIERS)),
        ("title", "Title", g("title"), None),
        ("description", "Description", g("description"), "text"),
        ("evidence", "Evidence (e.g. EEF toolkit)", g("evidence"), None),
        ("challenge", "Challenge it addresses", g("challenge"), "text"),
        ("success_criteria", "Success criteria", g("success_criteria"), "text"),
        ("owner", "Owner", g("owner"), None),
        ("planned_cost", "Planned cost £", g("planned_cost"), None),
        ("actual_cost", "Actual cost £ (blank = activities)", g("actual_cost"), None),
        ("status", "Status", g("status", PP.INTERVENTION_STATUSES[0]),
         list(PP.INTERVENTION_STATUSES)),
        ("impact_rating", "Impact", g("impact_rating", PP.IMPACT_RATINGS[0]),
         list(PP.IMPACT_RATINGS)),
        ("impact_notes", "Impact notes", g("impact_notes"), "text"),
    ]


class PupilPremiumPage(TabbedPage):
    TITLE = "Pupil Premium"
    TABS = ("Records", "Cohort", "Strategy & plan", "Activities", "Impact", "Rates")

    def __init__(self, parent, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        activity_log.record("pupil_premium.view")
        state.setdefault("ayear", PP.current_year())
        super().__init__(parent, principal=principal, state=state, open_pupil=open_pupil,
                         editor=PP.is_editor(principal))

    def _ay(self) -> str:
        return self.state.get("ayear") or PP.current_year()

    def _summary(self) -> None:
        s = PP.cohort_summary(academic_year=self._ay())
        self.summary_var.set(f"{self._ay()}: {s['total']} of {s['on_roll']} pupils    Funding "
                             f"{money(s['total_funding'])}    Spend {money(s['total_spend'])}"
                             f"    Remaining {money(s['remaining'])}    Without an activity: "
                             f"{s['pp_without_activities']}")

    def refresh_all(self) -> None:
        super().refresh_all()
        self._summary()

    # ── Records (the old Pupil Premium window) ───────────────────────

    def _tab_records(self, tab):
        bar = self.bar(tab)
        self.year = self.combo(bar, "Year:", "year", ["", *YEARS], self.refresh, 5)
        self.ayear = self.combo(bar, "Academic yr:", "ayear", _years(), self.refresh, 9,
                                PP.current_year())
        self.cat = self.combo(bar, "Category:", "category", ["", *PP.CATEGORIES], self.refresh,
                              24)
        self.status = self.combo(bar, "Status:", "status", ["", *PP.PP_STATUSES], self.refresh,
                                 11)
        self.buttons(bar, (("Apply", self.refresh), ("New / update", self.new, True),
                           ("Edit", self.edit, True), ("Interventions", self.interventions),
                           ("Delete", self.delete, True), ("Refresh", self.refresh)))
        bar2 = self.bar(tab)
        self.buttons(bar2, (("Summary", self.record_summary),
                            ("Record FSM from pupil records", self.snapshot, True),
                            ("Open pupil", lambda: self.open_selected(self.recs)),
                            ("History", self.history), ("Export CSV…", self.export)))
        self.recs = Table(tab, [("id", "ID", 50), ("ayear", "Academic yr", 80),
                                ("pupil", "Pupil", 220), ("yr", "Yr", 35),
                                ("cat", "Category", 200), ("status", "Status", 90),
                                ("fund", "Funding £", 90), ("kw", "Keyworker", 140)],
                          stretch={"pupil"})
        self.recs.on_double(self.interventions)
        return self.refresh

    def refresh(self) -> None:
        self.recs.fill(PP.list_records(year_group=self.year.get() or None,
                                       academic_year=self._ay(),
                                       category=self.cat.get() or None,
                                       status=self.status.get() or None),
                       lambda e: e.eligibility_id, lambda e: (
            e.eligibility_id, e.academic_year, f"{e.pupil_name} ({e.admission_no})",
            e.pupil_year, e.category, e.status, money(e.funding_amount), e.keyworker or ""),
            lambda e: None if e.counts else "muted")
        self._summary()

    def new(self) -> None:
        self.form("New / update eligibility", _el_fields(None, self._ay()),
                  lambda v: PP.upsert(filled(v), actor=self.principal),
                  note="One record per pupil, year and category - saving again updates it. "
                       "FSM from the pupil record and Ever 6 are counted without a record.")

    def edit(self) -> None:
        e = self.pick(self.recs, "Edit")
        if e:
            self.form(f"Record #{e.eligibility_id} - {e.pupil_name}", _el_fields(e, ""),
                      lambda v: PP.update(e.eligibility_id, changed(e, v),
                                          actor=self.principal))

    def delete(self) -> None:
        e = self.pick(self.recs, "Delete")
        if e and self.ask("Delete", f"Delete record #{e.eligibility_id} ({e.category}) for "
                                    f"{e.pupil_name} and its interventions?"):
            PP.delete(e.eligibility_id, actor=self.principal)
            self.refresh_all()

    def record_summary(self) -> None:
        e = self.pick(self.recs, "Summary")
        if e is None:
            return
        s = PP.record_summary(e.eligibility_id)
        lines = [f"{e.pupil_name} ({e.admission_no}), Year {e.pupil_year} - {e.academic_year}",
                 f"{e.category} ({e.status})", "",
                 f"Funding {money(s['funding'])}   Spent {money(s['total_spend'])}   "
                 f"Remaining {money(s['remaining'])}", "",
                 "By status: " + self.counts(s["by_status"]),
                 "By impact: " + self.counts(s["by_impact"]), ""]
        lines += [f"#{a.activity_id} {a.start_date} {a.title} - {money(a.spend)} ({a.status}, "
                  f"{a.impact_rating})" for a in s["interventions"]]
        self.text("Pupil premium summary", "\n".join(lines))

    def snapshot(self) -> None:
        n = PP.record_fsm_from_pupils(actor=self.principal, academic_year=self._ay())
        self.refresh_all()
        self.info("Record FSM", f"Added {n} FSM record(s) for {self._ay()} from the pupil "
                                "records' free school meals flag.")

    def history(self) -> None:
        e = self.recs.selected()
        self.text("History", self.history_text(PP.history(e.pupil_id if e else None)))

    def export(self) -> None:
        self.save_csv("pupil_premium.csv", lambda p: PP.export_csv(
            p, actor=self.principal, academic_year=self._ay(),
            year_group=self.year.get() or None), "pupil")

    # ── The old Interventions window ─────────────────────────────────

    def interventions(self) -> None:
        e = self.pick(self.recs, "Interventions")
        if e is None:
            return
        win, frm = W.dialog(self.parent, f"Interventions — {e.pupil_name} ({e.academic_year})",
                            size="820x400")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        table = Table(frm, [("id", "ID", 50), ("start", "Start", 90), ("status", "Status", 90),
                            ("spend", "Spend £", 80), ("impact", "Impact", 120),
                            ("title", "Title", 300)], height=12, stretch={"title"})

        def refresh() -> None:
            table.fill(PP.list_interventions(e.eligibility_id), lambda a: a.activity_id,
                       lambda a: (a.activity_id, a.start_date, a.status, money(a.spend),
                                  a.impact_rating, a.title))

        def after() -> None:
            refresh()
            self.refresh_all()

        def add() -> None:
            W.form_dialog(win, f"Intervention — {e.pupil_name}",
                          _act_fields(None, PP.list_lines(e.academic_year)),
                          lambda v: (PP.add_intervention(
                              _line_id(filled(v)) | {"pp_id": e.pp_id},
                              actor=self.principal), after()))

        def edit() -> None:
            a = table.selected()
            if a:
                W.form_dialog(win, f"Intervention #{a.activity_id}",
                              _act_fields(a, PP.list_lines(e.academic_year)),
                              lambda v: (PP.update_intervention(
                                  a.activity_id, changed(a, _line_id(v)),
                                  actor=self.principal), after()))

        def remove() -> None:
            a = table.selected()
            if a is None or not messagebox.askyesno("Delete", f"Delete intervention "
                                                    f"#{a.activity_id}?", parent=win):
                return
            try:
                PP.delete_intervention(a.activity_id, actor=self.principal)
            except W.ERRORS as ex:
                messagebox.showerror("Delete", W.problems(ex), parent=win)
                return
            after()
        for text, cmd, ok in (("Add", add, self.editor), ("Edit", edit, self.editor),
                              ("Delete", remove, self.editor), ("Refresh", refresh, True)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not ok:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        table.on_double(edit)
        refresh()

    # ── Cohort ───────────────────────────────────────────────────────

    def _tab_cohort(self, tab):
        self.note(tab, "Everyone counted as pupil premium this year: recorded categories, free "
                       "school meals on the pupil record, and Ever 6 (FSM in the last six "
                       "years). Provisional = FSM on the pupil record but not yet recorded here.")
        bar = self.bar(tab)
        run = lambda: self._run("Cohort")  # noqa: E731
        self.co_year = self.combo(bar, "Year:", "co_year", ["", *YEARS], run, 5)
        self.co_form = self.entry(bar, "Form:", "co_form", run, 8)
        self.co_cat = self.combo(bar, "Category:", "co_cat", ["", *PP.CATEGORIES], run, 24)
        self.buttons(bar, (("Refresh", run),
                           ("Open pupil", lambda: self.open_selected(self.cohort))))
        self.cohort = Table(tab, [("adm", "Adm no", 80), ("pupil", "Pupil", 200),
                                  ("yr", "Yr", 35), ("form", "Form", 55),
                                  ("cats", "Categories", 260), ("prov", "Provisional", 160),
                                  ("fund", "Funding", 90), ("kw", "Keyworker", 120)],
                            height=18, stretch={"pupil", "cats"})

        def refresh() -> None:
            rows = PP.cohort(academic_year=self._ay(), year_group=self.co_year.get() or None,
                             form_group=self.co_form.get() or None,
                             category=self.co_cat.get() or None)
            self.cohort.fill([dict(r, pupil_id=r["pupil"].pupil_id) for r in rows],
                             lambda r: r["pupil_id"], lambda r: (
                r["pupil"].admission_no, r["pupil"].display_name, r["pupil"].year_group,
                r["pupil"].form_group or "", ", ".join(r["categories"]),
                ", ".join(r["provisional"]), money(r["funding"]), r["keyworker"] or ""),
                lambda r: "warn" if r["provisional"] else None)
        return refresh

    # ── Strategy & plan ──────────────────────────────────────────────

    def _tab_strategy_plan(self, tab):
        bar = self.bar(tab)
        self.buttons(bar, (("Edit statement…", self.edit_strategy, True),
                           ("Statement", lambda: self.text(
                               "Pupil premium strategy", PP.strategy_text(self._ay()),
                               save_name="pupil_premium_strategy.txt")),
                           ("Add line", self.add_line, True), ("Edit line", self.edit_line, True),
                           ("Delete line", self.delete_line, True),
                           ("Allocate to pupils…", self.allocate, True),
                           ("Line impact", self.line_impact),
                           ("Copy plan to next year", self.copy_plan, True)))
        self.plan_var = ttk.Label(tab, foreground="#333", wraplength=900, justify="left")
        self.plan_var.pack(anchor="w", pady=(0, 4))
        self.tiers = Table(tab, [("tier", "Tier", 240), ("lines", "Lines", 60),
                                 ("planned", "Planned", 100), ("share", "Share %", 70),
                                 ("actual", "Spent", 100)], height=4)
        self.heading(tab, "Spending plan")
        self.lines = Table(tab, [("id", "ID", 50), ("tier", "Tier", 180),
                                 ("title", "Title", 220), ("owner", "Owner", 110),
                                 ("planned", "Planned", 90), ("actual", "Actual", 90),
                                 ("status", "Status", 80), ("impact", "Impact", 110),
                                 ("evidence", "Evidence", 150)], height=12,
                           stretch={"title", "evidence"})
        self.lines.on_double(self.edit_line)

        def refresh() -> None:
            s = PP.plan_summary(self._ay())
            b = s["budget"]
            self.plan_var.configure(text=(
                f"{s['academic_year']}: budget {money(b['total'])} (allocation "
                f"{money(b['allocation'])}, carried forward {money(b['carried_forward'])}"
                + (f", set to {money(b['override'])}" if b.get("override") else "")
                + f")    planned {money(s['planned'])}    spent {money(s['actual'])}    "
                f"unallocated {money(s['unallocated'])}"
                + "".join(f"\n⚠ {w}" for w in s["warnings"])))
            self.tiers.fill(s["tiers"], None, lambda t: (
                t["tier"], t["lines"], money(t["planned"]), num(t["share"]),
                money(t["actual"])))
            self.lines.fill(PP.list_lines(self._ay()), lambda x: x.line_id, lambda x: (
                x.line_id, x.tier, x.title, x.owner or "", money(x.planned_cost),
                money(x.actual_cost), x.status, x.impact_rating, x.evidence or ""),
                lambda x: "muted" if x.status == "Cancelled" else None)
        return refresh

    def edit_strategy(self) -> None:
        st = PP.strategy(self._ay())
        g = (lambda k: "" if st.get(k) is None else st[k])
        self.form(f"Strategy statement - {self._ay()}", [
            ("statement", "Statement of intent", g("statement"), "text"),
            ("challenges", "Challenges", g("challenges"), "text"),
            ("intended_outcomes", "Intended outcomes", g("intended_outcomes"), "text"),
            ("lead", "Pupil premium lead", g("lead"), None),
            ("governor", "Governor", g("governor"), None),
            ("budget_override", "Budget £ (blank = from the rates)", g("budget_override"),
             None),
            ("carried_forward", "Carried forward £", g("carried_forward"), None),
            ("published_on", "Published on", g("published_on"), None),
            ("review_date", "Review date", g("review_date"), None),
            ("reviewed_on", "Reviewed on", g("reviewed_on"), None),
            ("notes", "Notes", g("notes"), "text")],
            lambda v: PP.save_strategy(self._ay(), v, actor=self.principal),
            note="Publishing needs the challenges and the intended outcomes.")

    def add_line(self) -> None:
        self.form(f"New plan line - {self._ay()}", _line_fields(None),
                  lambda v: PP.add_line(self._ay(), filled(v), actor=self.principal))

    def edit_line(self) -> None:
        x = self.pick(self.lines, "Edit line")
        if x:
            self.form(f"Plan line #{x.line_id}", _line_fields(x),
                      lambda v: PP.update_line(x.line_id, changed(x, v), actor=self.principal),
                      note="Complete needs an impact rating.")

    def delete_line(self) -> None:
        x = self.pick(self.lines, "Delete line")
        if x and self.ask("Delete line", f"Delete '{x.title}'?"):
            PP.delete_line(x.line_id, actor=self.principal)
            self.refresh_all()

    def _pp_choices(self) -> list[tuple[int, str]]:
        rows = PP.cohort(academic_year=self._ay())
        return [(r["pupil"].pupil_id, f"{r['pupil'].display_name} ({r['pupil'].admission_no}) "
                 f"Yr{r['pupil'].year_group}") for r in rows]

    def allocate(self, line: PP.Line | None = None) -> None:
        x = line or self.pick(self.lines, "Allocate")
        if x is None:
            return

        def save(v):
            if not v["ids"]:
                raise PP.ValidationError(["Choose at least one pupil"])
            res = PP.allocate(x.line_id, v["ids"], actor=self.principal,
                              spend_each=v["spend"] or None, start_date=v["start"] or None)
            msg = f"Added {len(res['added'])}; {res['skipped']} already had it."
            if res["not_pp"]:
                msg += "\n\nNot pupil premium this year: " + ", ".join(
                    a.pupil_name for a in res["not_pp"])
            self.info("Allocate", msg)
        self.form(f"Allocate '{x.title}' to pupils", [
            ("ids", "Pupil premium pupils", [], ("pupils", self._pp_choices())),
            ("spend", "Spend each £ (blank = share the planned cost)", "", None),
            ("start", "Start date (blank = today)", "", None)], save)

    def line_impact(self) -> None:
        x = self.pick(self.lines, "Line impact")
        if x is None:
            return
        r = PP.line_impact(x.line_id)
        self.text("Line impact", "\n".join((
            f"{x.title} ({x.tier})", "",
            f"Pupils: {r['pupils']} ({r['pp_pupils']} pupil premium)   Spend: "
            f"{money(r['spend'])}",
            f"Attendance: {num(r['attendance'])}% (pupil premium cohort "
            f"{num(r['cohort_attendance'])}%)",
            f"Behaviour incidents per pupil: {num(r['incidents'])} (cohort "
            f"{num(r['cohort_incidents'])})",
            "Impact ratings: " + self.counts(r["by_impact"]))))

    def copy_plan(self) -> None:
        nxt = PP.next_year(self._ay())
        if self.ask("Copy plan", f"Copy this year's plan lines to {nxt}?"):
            n = PP.copy_plan(self._ay(), actor=self.principal)
            self.info("Copy plan", f"Copied {n} line(s) to {nxt}.")

    # ── Activities ───────────────────────────────────────────────────

    def _tab_activities(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Activities")  # noqa: E731
        self.ac_year = self.combo(bar, "Year:", "ac_year", ["", *YEARS], run, 5)
        self.ac_status = self.combo(bar, "Status:", "ac_status",
                                    ["", *PP.INTERVENTION_STATUSES], run, 10)
        self.buttons(bar, (("Edit", self.edit_activity, True),
                           ("Delete", self.delete_activity, True),
                           ("Open pupil", lambda: self.open_selected(self.acts))))
        self.acts = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                                ("title", "Activity", 220), ("line", "Plan line", 60),
                                ("spend", "Spend", 80), ("start", "Start", 90),
                                ("status", "Status", 80), ("impact", "Impact", 110)],
                          height=18, stretch={"pupil", "title"})
        self.acts.on_double(self.edit_activity)

        def refresh() -> None:
            self.acts.fill(PP.list_activities(academic_year=self._ay(),
                                              year_group=self.ac_year.get() or None,
                                              status=self.ac_status.get() or None),
                           lambda a: a.activity_id, lambda a: (
                a.activity_id, f"{a.pupil_name} ({a.admission_no})", a.pupil_year, a.title,
                a.line_id or "", money(a.spend), a.start_date, a.status, a.impact_rating))
        return refresh

    def edit_activity(self) -> None:
        a = self.pick(self.acts, "Edit activity")
        if a:
            self.form(f"Activity #{a.activity_id} - {a.pupil_name}",
                      _act_fields(a, PP.list_lines(a.academic_year)),
                      lambda v: PP.update_activity(a.activity_id, changed(a, _line_id(v)),
                                                   actor=self.principal))

    def delete_activity(self) -> None:
        a = self.pick(self.acts, "Delete activity")
        if a and self.ask("Delete", f"Delete '{a.title}' for {a.pupil_name}?"):
            PP.delete_activity(a.activity_id, actor=self.principal)
            self.refresh_all()

    # ── Impact ───────────────────────────────────────────────────────

    def _tab_impact(self, tab):
        self.note(tab, "Pupil premium pupils against everyone else, read from attendance, "
                       "behaviour and headline measures. Gap = pupil premium minus others.")
        bar = self.bar(tab)
        self.im_year = self.combo(bar, "Year:", "im_year", ["", *YEARS],
                                  lambda: self._run("Impact"), 5)
        self.im_head = ttk.Label(bar, foreground="#555")
        self.im_head.pack(side="left", padx=8)
        self.impact = Table(tab, [("m", "Measure", 280), ("pp", "Pupil premium", 110),
                                  ("other", "Others", 110), ("gap", "Gap", 90),
                                  ("better", "Better is", 80)], height=10)

        def refresh() -> None:
            r = PP.impact(academic_year=self._ay(), year_group=self.im_year.get() or None)
            self.im_head.configure(text=f"{r['academic_year']}: {r['pp']} pupil premium, "
                                        f"{r['other']} others")

            def tag(m):
                if m["gap"] is None or m["gap"] == 0:
                    return None
                worse = m["gap"] < 0 if m["better"] == "higher" else m["gap"] > 0
                return "bad" if worse else "good"
            self.impact.fill(r["measures"], None, lambda m: (
                m["measure"], num(m["pp"]), num(m["other"]), num(m["gap"]), m["better"]), tag)
        return refresh

    # ── Rates ────────────────────────────────────────────────────────

    def _tab_rates(self, tab):
        self.note(tab, "Funding per pupil. Looked-after / previously looked-after replaces the "
                       "deprivation rate; the service premium is added on top.")
        self.buttons(self.bar(tab), (("Change rate…", self.set_rate, True),))
        self.rates = Table(tab, [("cat", "Category", 300), ("rate", "Per pupil", 120)],
                           height=8)

        def refresh() -> None:
            self.rates.fill(PP.rates(self._ay()).items(), lambda x: x[0],
                            lambda x: (x[0], money(x[1])))
        return refresh

    def set_rate(self) -> None:
        sel = self.rates.selected()
        self.form(f"Funding rate - {self._ay()}", [
            ("cat", "Category", sel[0] if sel else PP.CATEGORIES[0], list(PP.CATEGORIES)),
            ("amount", "Per pupil £", sel[1] if sel else "", None)],
            lambda v: PP.set_rate(self._ay(), v["cat"], v["amount"], actor=self.principal))


def draw_pupil_premium(parent: ttk.Frame, *, principal: Principal, state: dict,
                       open_pupil: Callable[[int], None] | None = None) -> PupilPremiumPage:
    return PupilPremiumPage(parent, principal=principal, state=state, open_pupil=open_pupil)
