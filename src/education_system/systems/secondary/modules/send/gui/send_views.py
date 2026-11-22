"""SEND screen - the SENCO's register.

The old SEND window is the first tab ("Register"), with its toolbar (Year,
Stage and Status filters; Apply, New / update, Edit, Reviews, Overdue,
Delete, Refresh), its columns (ID, Academic yr, Pupil, Yr, Stage, Primary
need, Status, Next review), its record dialog (Primary need, Secondary need,
Status, SENCo, Keyworker, Parent contact, EHCP reference, Start date, Next
review, Provision summary, Diagnosis, Notes) and its Reviews window (Add
review, Delete selected, Refresh; ID, Date, Reviewer, Outcome, Next review,
Progress). The old Accessibility window is the "Access arrangements" tab
(Year, Type and Status filters, Exam only; Apply, New, Edit, Status, Expired,
Delete, Refresh).

Added: need and area filters and search, open pupil, record summary, invite
the family to a review, LA report / decision for annual reviews, history,
export; and the tabs Plans (assess-plan-do-review cycles, pupil passports,
share with the family), Provision map, Agencies, Strategies (for every member
of staff, "my classes" too), Due and Reports. One SEN store: the pupil's SEN
status and :mod:`modules.pupils.domain.sen_details`; rules are in
:mod:`modules.send.domain.send`.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.send.domain import send as S
from education_system.systems.secondary.modules.send.gui.send_page import (
    YEARS,
    Table,
    TabbedPage,
    changed,
    filled,
    money,
    num,
)
from education_system.systems.secondary.modules.pupils.domain import sen_details as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_NEED_CHOICES = [f"{k} - {v}" for k, v in SD.NEEDS.items()]


def _code(v: Any) -> str:
    return str(v or "").split(" - ")[0].strip()


def _need(code: str | None) -> str:
    return f"{code} - {SD.NEEDS[code]}" if code in SD.NEEDS else (code or "")


def _record_fields(r: S.Record | None, parent: str) -> list:
    """The old record dialog's fields, in its order, then the new ones."""
    g = (lambda k, d="": getattr(r, k) if r is not None and getattr(r, k) is not None else d)
    return [
        ("stage", "Stage", r.stage if r else S.SUPPORT, list(S.STAGES)),
        ("primary_need", "Primary need", _need(g("primary_need")), ["", *_NEED_CHOICES]),
        ("secondary_need", "Secondary need", _need(g("secondary_need")),
         ["", *_NEED_CHOICES]),
        ("status", "Status", g("status", S.STATUSES[0]), list(S.STATUSES)),
        ("senco", "SENCo", g("senco"), None),
        ("keyworker", "Keyworker", g("keyworker"), None),
        ("ehcp_reference", "EHCP reference", g("ehcp_reference"), None),
        ("added_on", "Start date", g("added_on"), None),
        ("next_review_date", "Next review", g("next_review_date"), None),
        ("provision", "Provision summary", g("provision"), "text"),
        ("diagnosis", "Diagnosis", g("diagnosis"), "text"),
        ("notes", "Notes", g("notes"), "text"),
        ("ehcp_issued_on", "EHCP issued on", g("ehcp_issued_on"), None),
        ("strategies", "Strategies for staff", g("strategies"), "text"),
        ("exam_access", "Exam access", g("exam_access"), "text"),
        ("ehcna_status", "EHC needs assessment", g("ehcna_status"),
         ["", *S.EHCNA_STATUSES]),
        ("ehcna_requested_on", "Assessment requested on", g("ehcna_requested_on"), None),
        ("ehcna_decision_on", "Decision to assess on", g("ehcna_decision_on"), None),
        ("ehcna_plan_on", "Plan issued on", g("ehcna_plan_on"), None),
    ]


def _plan_fields(pl: S.Plan | None, pupil: str = "") -> list:
    g = (lambda k, d="": getattr(pl, k) if pl is not None and getattr(pl, k) is not None
         else d)
    head = [] if pl else [("pupil_id", "Pupil ID / admission no.", pupil, None)]
    return head + [
        ("kind", "Kind", g("kind", S.PLAN_KINDS[0]), list(S.PLAN_KINDS)),
        ("title", "Title", g("title"), None),
        ("start_date", "Start date (blank = today)", g("start_date"), None),
        ("review_date", "Review date (blank = in a term)", g("review_date"), None),
        ("assess", "Assess - what we know", g("assess"), "text"),
        ("outcomes", "Plan - outcomes", g("outcomes"), "text"),
        ("provision", "Do - support", g("provision"), "text"),
        ("strategies", "Strategies for staff", g("strategies"), "text"),
        ("pupil_voice", "Pupil's views", g("pupil_voice"), "text"),
        ("parent_voice", "Family's views", g("parent_voice"), "text"),
        ("status", "Status", g("status", S.PLAN_STATUSES[0]), list(S.PLAN_STATUSES)),
    ]


def _prov_fields(x: S.Provision | None) -> list:
    g = (lambda k, d="": getattr(x, k) if x is not None and getattr(x, k) is not None
         else d)
    return [
        ("provision", "Provision", g("provision"), ("edit", S.provision_names())),
        ("need_area", "Area", g("need_area"), ["", *S.NEED_AREAS]),
        ("provider", "Provider", g("provider"), None),
        ("delivery", "Delivery", g("delivery", S.DELIVERY[0]), list(S.DELIVERY)),
        ("group_size", "Group size", g("group_size", 1), None),
        ("hours_per_week", "Hours a week", g("hours_per_week"), None),
        ("weeks", "Weeks", g("weeks"), None),
        ("cost_per_hour", "Cost per hour £", g("cost_per_hour"), None),
        ("fixed_cost", "Fixed cost £ (instead)", g("fixed_cost"), None),
        ("start_date", "Start date", g("start_date"), None),
        ("end_date", "End date", g("end_date"), None),
        ("status", "Status", g("status", S.PROVISION_STATUSES[0]),
         list(S.PROVISION_STATUSES)),
        ("in_ehcp", "In the EHC plan", bool(x and x.in_ehcp), "check"),
        ("outcome", "Outcome", g("outcome"), "text"),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _acc_fields(a: S.Arrangement | None) -> list:
    g = (lambda k, d="": getattr(a, k) if a is not None and getattr(a, k) is not None
         else d)
    head = [] if a else [("pupil_id", "Pupil ID / admission no.", "", None)]
    return head + [
        ("arrangement_type", "Type", g("arrangement_type", S.ACCESS_TYPES[0]),
         list(S.ACCESS_TYPES)),
        ("category", "Category", g("category", S.ACCESS_CATEGORIES[0]),
         ("edit", S.ACCESS_CATEGORIES)),
        ("description", "Description", g("description"), "text"),
        ("exam_only", "Exam only", bool(a and a.exam_only), "check"),
        ("start_date", "Start date", g("start_date"), None),
        ("end_date", "End date", g("end_date"), None),
        ("status", "Status", g("status", S.ACCESS_STATUSES[0]), list(S.ACCESS_STATUSES)),
        ("approved_by", "Approved by", g("approved_by"), None),
        ("approval_date", "Approval date", g("approval_date"), None),
        ("review_date", "Review date", g("review_date"), None),
        ("notes", "Notes", g("notes"), "text"),
        ("evidence_source", "Evidence source", g("evidence_source"),
         ["", *S.EVIDENCE_SOURCES]),
        ("evidence_reference", "Evidence reference", g("evidence_reference"), None),
        ("assessor", "Assessor (Form 8)", g("assessor"), None),
        ("assessed_on", "Assessed on (Form 8)", g("assessed_on"), None),
    ]


def _agency_fields(x: S.Agency | None) -> list:
    g = (lambda k, d="": getattr(x, k) if x is not None and getattr(x, k) is not None
         else d)
    head = [] if x else [("pupil_id", "Pupil ID / admission no.", "", None)]
    return head + [
        ("agency", "Agency", g("agency"), ("edit", S.AGENCIES)),
        ("contact_name", "Contact", g("contact_name"), None),
        ("contact_details", "Contact details", g("contact_details"), None),
        ("referred_on", "Referred on", g("referred_on"), None),
        ("referred_by", "Referred by", g("referred_by"), None),
        ("status", "Status", g("status", S.AGENCY_STATUSES[0]), list(S.AGENCY_STATUSES)),
        ("first_seen_on", "First seen on", g("first_seen_on"), None),
        ("next_appointment", "Next appointment", g("next_appointment"), None),
        ("report_received_on", "Report received on", g("report_received_on"), None),
        ("outcome", "Outcome", g("outcome"), "text"),
        ("notes", "Notes", g("notes"), "text"),
    ]


class SendPage(TabbedPage):
    TITLE = "SEND"
    TABS = ("Register", "Plans", "Provision map", "Access arrangements", "Agencies",
            "Strategies", "Due", "Reports")

    def __init__(self, parent, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        activity_log.record("send.view")
        super().__init__(parent, principal=principal, state=state, open_pupil=open_pupil,
                         editor=S.is_editor(principal))

    # ── Register (the old SEND window) ───────────────────────────────

    def _tab_register(self, tab):
        bar = self.bar(tab)
        self.year = self.combo(bar, "Year:", "year", ["", *YEARS], self.refresh, 5)
        self.stage = self.combo(bar, "Stage:", "stage", ["", *S.STAGES], self.refresh, 26)
        self.status = self.combo(bar, "Status:", "status", ["", *S.STATUSES], self.refresh, 12)
        self.buttons(bar, (("Apply", self.refresh), ("New / update", self.new, True),
                           ("Edit", self.edit, True), ("Reviews", self.reviews),
                           ("Overdue", self.overdue), ("Delete", self.delete, True),
                           ("Refresh", self.refresh)))
        bar2 = self.bar(tab)
        self.need = self.combo(bar2, "Need:", "need", ["", *SD.NEEDS], self.refresh, 6)
        self.area = self.combo(bar2, "Area:", "area", ["", *S.NEED_AREAS], self.refresh, 28)
        self.search = self.entry(bar2, "Search:", "search", self.refresh)
        self.buttons(bar2, (("Open pupil", lambda: self.open_selected(self.reg)),
                            ("Summary", self.summary), ("Invite to review…", self.invite, True),
                            ("Copy exam access", self.copy_access, True),
                            ("History", self.history), ("Export CSV…", self.export)))
        self.reg = Table(tab, [("id", "ID", 80), ("ayear", "Academic yr", 80),
                               ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                               ("stage", "Stage", 200), ("need", "Primary need", 220),
                               ("status", "Status", 90), ("next", "Next review", 90)],
                         stretch={"pupil", "need"})
        self.reg.on_double(self.reviews)
        return self.refresh

    def refresh(self) -> None:
        rows = S.list_records(year_group=self.year.get() or None, stage=self.stage.get() or None,
                              status=self.status.get() or None, need=self.need.get() or None,
                              area=self.area.get() or None, search=self.search.get() or None)
        today = S._today().isoformat()
        self.reg.fill(rows, lambda r: r.pupil_id, lambda r: (
            r.admission_no, r.academic_year, r.pupil_name, r.year_group, r.stage,
            r.primary_label or "", r.status, r.next_review_date or ""),
            lambda r: "bad" if r.next_review_date and r.next_review_date < today
            and r.status == "Active" else ("muted" if r.status != "Active" else None))
        s = S.cohort_summary(year_group=self.year.get() or None)
        self.summary_var.set(f"On the register: {s['total']}    SEN support: "
                             f"{s['support_count']}    EHCP: {s['ehcp_count']}    Monitoring: "
                             f"{s['monitoring']}    On roll: {s['on_roll']}")

    def _save_record(self, ref: Any, v: dict, cur: S.Record | None) -> None:
        for k in ("primary_need", "secondary_need"):
            v[k] = _code(v.get(k))
        data = changed(cur, v) if cur else filled(v)
        S.save_record(ref, data, actor=self.principal)

    def new(self) -> None:
        def save(v):
            ref = v.pop("pupil_id")
            if not ref:
                raise S.ValidationError(["Give the pupil ID or admission number"])
            self._save_record(ref, v, S.get(ref))
        self.form("New / update SEND record",
                  [("pupil_id", "Pupil ID / admission no.", "", None),
                   *_record_fields(None, "")], save,
                  note="If the pupil is already on the register, their record is updated. "
                       "Changing the stage changes the SEN status on the pupil record.")

    def edit(self) -> None:
        r = self.pick(self.reg, "Edit")
        if r is None:
            return
        parent = S.parent_contact(r.pupil_id) or "none recorded"
        self.form(f"SEND record - {r.pupil_name}", _record_fields(r, parent),
                  lambda v: self._save_record(r.pupil_id, v, r),
                  note=f"Parent contact (from the pupil's contacts): {parent}")

    def delete(self) -> None:
        r = self.pick(self.reg, "Delete")
        if r and self.ask("Delete", f"Take {r.pupil_name} off the SEND register? Plans, "
                                    "reviews and the SEN status on the pupil record stay."):
            S.delete(r.pupil_id, actor=self.principal)
            self.refresh_all()

    def overdue(self) -> None:
        rows = S.overdue_reviews()
        self.text("Overdue reviews", "\n".join(
            f"{r.next_review_date}  {r.pupil_name} ({r.admission_no}) Yr{r.year_group}  "
            f"{r.stage}" for r in rows) or "No overdue reviews.")

    def summary(self) -> None:
        r = self.pick(self.reg, "Summary")
        if r is None:
            return
        s = S.record_summary(r.pupil_id)
        rec = s["record"]
        lines = [f"{rec.pupil_name} ({rec.admission_no}), Year {rec.year_group}", ""]
        for label, v in (("Stage", rec.stage), ("Status", rec.status),
                         ("Primary need", rec.primary_label), ("Area", rec.area),
                         ("Secondary need", SD.NEEDS.get(rec.secondary_need or "")),
                         ("SENCo", rec.senco), ("Keyworker", rec.keyworker),
                         ("Parent contact", s["parent_contact"]),
                         ("EHCP reference", rec.ehcp_reference),
                         ("EHCP issued", rec.ehcp_issued_on),
                         ("Annual review due", s["ehcp_due"]),
                         ("Assessment", rec.ehcna_status), ("Diagnosis", rec.diagnosis),
                         ("Next review", rec.next_review_date), ("Provision", rec.provision),
                         ("Strategies", rec.strategies), ("Exam access", rec.exam_access),
                         ("Notes", rec.notes)):
            if v:
                lines.append(f"{label + ':':<20} {v}")
        lines += ["", f"Reviews: {s['review_count']} (last {s['last_review'] or '-'})"]
        lines += [f"  {v.review_date} {v.review_type}: {v.outcome}" for v in s["reviews"]]
        lines += ["", "Plans:"] + [f"  #{p.plan_id} {p.kind} cycle {p.cycle} ({p.status}), "
                                   f"review {p.review_date or '-'}" for p in s["plans"]]
        lines += ["", "Provision:"] + [f"  {x.provision}: {x.hours_per_week or 0}h/wk, "
                                       f"{money(x.cost)} ({x.status})" for x in s["provision"]]
        lines += ["", "Access arrangements:"] + [f"  {a.category} ({a.status})"
                                                 for a in s["access"]]
        lines += ["", "Agencies:"] + [f"  {g.agency} ({g.status})" for g in s["agencies"]]
        self.text("SEND summary", "\n".join(lines), save_name="send_summary.txt")

    def invite(self) -> None:
        r = self.pick(self.reg, "Invite to review")
        if r is None:
            return

        def save(v):
            res = S.invite_to_review(r.pupil_id, actor=self.principal, when=v["when"],
                                     review_type=v["review_type"], where=v["where"],
                                     note=v["note"])
            self.deliver("Invite to review", res)
        default = S.ANNUAL if r.sen_status == "E" else S.REVIEW_TYPES[0]
        self.form(f"Invite the family - {r.pupil_name}", [
            ("review_type", "Review", default, list(S.REVIEW_TYPES)),
            ("when", "When (date and time)", r.next_review_date or "", None),
            ("where", "Where", "", None), ("note", "Message (optional)", "", "text")], save,
            note="E-mailed to contacts with parental responsibility.")

    def copy_access(self) -> None:
        r = self.pick(self.reg, "Copy exam access")
        if r is None:
            return
        d = S.copy_exam_access(r.pupil_id, actor=self.principal)
        self.refresh_all()
        self.info("Copy exam access", f"The SEN record's exam access now reads:\n\n"
                                      f"{d.exam_access or '(none)'}")

    def history(self) -> None:
        r = self.reg.selected()
        self.text("History", self.history_text(S.history(r.pupil_id if r else None)))

    def export(self) -> None:
        self.save_csv("send_register.csv", lambda p: S.export_csv(
            p, actor=self.principal, year_group=self.year.get() or None,
            stage=self.stage.get() or None, status=self.status.get() or None), "record")

    # ── The old Reviews window ───────────────────────────────────────

    def reviews(self) -> None:
        r = self.pick(self.reg, "Reviews")
        if r is None:
            return
        win, frm = W.dialog(self.parent, f"Reviews — {r.pupil_name}", size="900x440")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        table = Table(frm, [("id", "ID", 50), ("date", "Date", 90), ("type", "Type", 150),
                            ("reviewer", "Reviewer", 120), ("outcome", "Outcome", 100),
                            ("next", "Next review", 90), ("la", "LA decision", 110),
                            ("progress", "Progress", 260)], height=12, stretch={"progress"})

        def refresh() -> None:
            table.fill(S.list_reviews(r.pupil_id), lambda v: v.review_id, lambda v: (
                v.review_id, v.review_date, v.review_type, v.reviewer or "", v.outcome,
                v.next_review_date or "", v.la_decision or "", v.progress or ""))

        def add() -> None:
            def save(v):
                S.add_review({**filled(v), "pupil_id": r.pupil_id}, actor=self.principal)
                refresh()
                self.refresh_all()
            W.form_dialog(win, f"Review — {r.pupil_name}", [
                ("review_date", "Date (blank = today)", "", None),
                ("reviewer", "Reviewer", self.principal.username, None),
                ("outcome", "Outcome", S.DEFAULT_OUTCOME, list(S.REVIEW_OUTCOMES)),
                ("next_review_date", "Next review (blank = default)", "", None),
                ("progress", "Progress", "", "text"),
                ("adjustments", "Adjustments", "", "text"), ("notes", "Notes", "", "text"),
                ("review_type", "Type", S.ANNUAL if r.sen_status == "E" else
                 S.REVIEW_TYPES[0], list(S.REVIEW_TYPES)),
                ("attendees", "Attendees", "", None),
                ("pupil_views", "Pupil's views", "", "text"),
                ("parent_views", "Family's views", "", "text")], save)

        def remove() -> None:
            v = table.selected()
            if v is None or not messagebox.askyesno("Delete review",
                                                    f"Delete review #{v.review_id}?",
                                                    parent=win):
                return
            try:
                S.delete_review(v.review_id, actor=self.principal)
            except W.ERRORS as e:
                messagebox.showerror("Delete review", W.problems(e), parent=win)
                return
            refresh()

        def la() -> None:
            v = table.selected()
            if v is None:
                return

            def save(x):
                S.record_la(v.review_id, actor=self.principal,
                            report_sent_on=x["sent"] or None, decision=x["decision"] or None,
                            decision_on=x["on"] or None)
                refresh()
            W.form_dialog(win, f"LA - review #{v.review_id}", [
                ("sent", "Report sent to LA on", v.la_report_sent_on or "", None),
                ("decision", "LA decision", v.la_decision or "", ["", *S.LA_DECISIONS]),
                ("on", "Decision date", v.la_decision_on or "", None)], save,
                note=f"Send the report within {S.LA_REPORT_DAYS} days of the meeting; the "
                     f"LA decides within {S.LA_DECISION_DAYS} days of that.")

        def view() -> None:
            v = table.selected()
            if v:
                W.text_window(win, f"Review #{v.review_id}", "\n".join(
                    f"{k}: {x}" for k, x in (
                        ("Date", v.review_date), ("Type", v.review_type),
                        ("Reviewer", v.reviewer), ("Attendees", v.attendees),
                        ("Outcome", v.outcome), ("Progress", v.progress),
                        ("Adjustments", v.adjustments), ("Pupil's views", v.pupil_views),
                        ("Family's views", v.parent_views),
                        ("Next review", v.next_review_date),
                        ("LA report sent", v.la_report_sent_on),
                        ("LA decision", v.la_decision), ("Notes", v.notes)) if x))
        for text, cmd, ok in (("Add review", add, self.editor),
                              ("Delete selected", remove, self.editor),
                              ("Refresh", refresh, True), ("View", view, True),
                              ("LA report / decision…", la, self.editor)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not ok:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        table.on_double(view)
        refresh()

    # ── Plans ────────────────────────────────────────────────────────

    def _tab_plans(self, tab):
        self.note(tab, "SEN support plans and pupil passports run in assess - plan - do - "
                       "review cycles. Reviewing a plan records the review and starts the next "
                       "cycle.")
        bar = self.bar(tab)
        self.pl_status = self.combo(bar, "Status:", "plan_status", ["", *S.PLAN_STATUSES],
                                    lambda: self._run("Plans"), 10)
        self.pl_kind = self.combo(bar, "Kind:", "plan_kind", ["", *S.PLAN_KINDS],
                                  lambda: self._run("Plans"), 18)
        self.pl_year = self.combo(bar, "Year:", "plan_year", ["", *YEARS],
                                  lambda: self._run("Plans"), 5)
        self.buttons(bar, (("New plan", self.new_plan, True), ("Edit", self.edit_plan, True),
                           ("View", self.view_plan), ("Review…", self.review_plan, True),
                           ("Close", self.close_plan, True), ("Delete", self.delete_plan, True),
                           ("Share with family…", self.share_plan, True),
                           ("Open pupil", lambda: self.open_selected(self.plans))))
        self.plans = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                                 ("kind", "Kind", 140), ("title", "Title", 180),
                                 ("cycle", "Cycle", 50), ("status", "Status", 80),
                                 ("start", "Start", 90), ("review", "Review", 90),
                                 ("shared", "Shared", 90)], stretch={"pupil", "title"})
        self.plans.on_double(self.view_plan)

        def refresh() -> None:
            today = S._today().isoformat()
            self.plans.fill(S.list_plans(status=self.pl_status.get() or None,
                                         kind=self.pl_kind.get() or None,
                                         year_group=self.pl_year.get() or None),
                            lambda p: p.plan_id, lambda p: (
                p.plan_id, f"{p.pupil_name} ({p.admission_no})", p.pupil_year, p.kind,
                p.title or "", p.cycle, p.status, p.start_date, p.review_date or "",
                p.shared_on or ""),
                lambda p: "bad" if p.status == "Active" and p.review_date
                and p.review_date < today else None)
        return refresh

    def new_plan(self) -> None:
        r = self.reg.selected() if hasattr(self, "reg") else None
        self.form("New plan", _plan_fields(None, r.admission_no if r else ""),
                  lambda v: S.create_plan(filled(v), actor=self.principal))

    def edit_plan(self) -> None:
        p = self.pick(self.plans, "Edit plan")
        if p:
            self.form(f"Plan #{p.plan_id} - {p.pupil_name}", _plan_fields(p),
                      lambda v: S.update_plan(p.plan_id, changed(p, v), actor=self.principal),
                      note="Reviewed and closed plans can't be changed.")

    def view_plan(self) -> None:
        p = self.pick(self.plans, "View plan")
        if p:
            self.text(f"Plan #{p.plan_id}", S.plan_text(p), save_name="send_plan.txt")

    def review_plan(self) -> None:
        p = self.pick(self.plans, "Review plan")
        if p is None:
            return

        def save(v):
            res = S.review_plan(p.plan_id, filled(v) | {"next_cycle": v["next_cycle"]},
                                actor=self.principal)
            if res["next"]:
                self.info("Review plan", f"Reviewed. Cycle {res['next'].cycle} started as plan "
                                         f"#{res['next'].plan_id}.")
        self.form(f"Review plan #{p.plan_id} - {p.pupil_name}", [
            ("outcome", "Outcome", S.DEFAULT_OUTCOME, list(S.REVIEW_OUTCOMES)),
            ("review_notes", "Review - how did it go", "", "text"),
            ("reviewed_on", "Reviewed on (blank = today)", "", None),
            ("reviewer", "Reviewer", self.principal.username, None),
            ("attendees", "Attendees", "", None),
            ("pupil_views", "Pupil's views", "", "text"),
            ("parent_views", "Family's views", "", "text"),
            ("next_review_date", "Next review (blank = in a term)", "", None),
            ("next_cycle", "Start the next cycle", True, "check")], save,
            note="Discharge ends the cycles and marks the register entry discharged.")

    def close_plan(self) -> None:
        p = self.pick(self.plans, "Close plan")
        if p and self.ask("Close plan", f"Close plan #{p.plan_id} without a review?"):
            S.close_plan(p.plan_id, actor=self.principal)
            self.refresh_all()

    def delete_plan(self) -> None:
        p = self.pick(self.plans, "Delete plan")
        if p and self.ask("Delete plan", f"Delete draft plan #{p.plan_id}?"):
            S.delete_plan(p.plan_id, actor=self.principal)
            self.refresh_all()

    def share_plan(self) -> None:
        p = self.pick(self.plans, "Share plan")
        if p is None:
            return

        def save(v):
            self.deliver("Share plan", S.share_plan(p.plan_id, actor=self.principal,
                                                    note=v["note"]))
        self.form(f"Share plan #{p.plan_id} with the family",
                  [("note", "Message (optional)", "", "text")], save,
                  note="The plan is e-mailed to contacts with parental responsibility.")

    # ── Provision map ────────────────────────────────────────────────

    def _tab_provision_map(self, tab):
        bar = self.bar(tab)
        self.pm_year = self.combo(bar, "Year:", "pm_year", ["", *YEARS],
                                  lambda: self._run("Provision map"), 5)
        self.pm_status = self.combo(bar, "Status:", "pm_status", ["", *S.PROVISION_STATUSES],
                                    lambda: self._run("Provision map"), 10)
        self.buttons(bar, (("Add provision…", self.add_provision, True),
                           ("Edit", self.edit_provision, True),
                           ("Delete", self.delete_provision, True),
                           ("Open pupil", lambda: self.open_selected(self.prov))))
        self.heading(tab, "By provision (this school year)")
        self.pmap = Table(tab, [("prov", "Provision", 260), ("pupils", "Pupils", 70),
                                ("active", "Active", 70), ("hours", "Hours", 80),
                                ("cost", "Cost", 100), ("areas", "Areas", 300)], height=7,
                          stretch={"prov", "areas"})
        self.heading(tab, "By pupil")
        self.prov = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                                ("prov", "Provision", 200), ("area", "Area", 160),
                                ("hrs", "Hrs/wk", 60), ("weeks", "Weeks", 55),
                                ("cost", "Cost", 90), ("status", "Status", 80),
                                ("ehcp", "EHCP", 45)], height=10, stretch={"pupil", "prov"})
        self.prov.on_double(self.edit_provision)

        def refresh() -> None:
            y = self.pm_year.get() or None
            rows = S.provision_map(year_group=y)
            self.pmap.fill(rows, None, lambda g: (g["provision"], g["pupils"], g["active"],
                                                  num(g["hours"]), money(g["cost"]), g["areas"]))
            self.prov.fill(S.list_provision(year_group=y, status=self.pm_status.get() or None),
                           lambda x: x.provision_id, lambda x: (
                x.provision_id, f"{x.pupil_name} ({x.admission_no})", x.pupil_year,
                x.provision, x.need_area or "", num(x.hours_per_week), num(x.weeks),
                money(x.cost), x.status, "yes" if x.in_ehcp else ""))
            self.summary_var.set(f"Provision this year: {sum(g['pupils'] for g in rows)} "
                                 f"place(s), {num(round(sum(g['hours'] for g in rows), 1))} "
                                 f"hours, {money(sum(g['cost'] for g in rows))}")
        return refresh

    def add_provision(self) -> None:
        pupils = [(r.pupil_id, f"{r.pupil_name} ({r.admission_no}) Yr{r.year_group}")
                  for r in S.list_records()]

        def save(v):
            ids = v.pop("pupil_ids")
            if not ids:
                raise S.ValidationError(["Choose at least one pupil"])
            S.add_provision_many(ids, filled(v) | {"in_ehcp": v["in_ehcp"]},
                                 actor=self.principal)
        self.form("Add provision", [("pupil_ids", "Pupils (register)", [], ("pupils", pupils)),
                                    *_prov_fields(None)], save,
                  note="Cost is the fixed cost, else hours a week x weeks x cost per hour, "
                       "shared by the group size.")

    def edit_provision(self) -> None:
        x = self.pick(self.prov, "Edit provision")
        if x:
            self.form(f"Provision #{x.provision_id} - {x.pupil_name}", _prov_fields(x),
                      lambda v: S.update_provision(x.provision_id, changed(x, v),
                                                   actor=self.principal))

    def delete_provision(self) -> None:
        x = self.pick(self.prov, "Delete provision")
        if x and self.ask("Delete provision", f"Delete {x.provision} for {x.pupil_name}?"):
            S.delete_provision(x.provision_id, actor=self.principal)
            self.refresh_all()

    # ── Access arrangements (the old Accessibility window) ───────────

    def _tab_access_arrangements(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Access arrangements")  # noqa: E731
        self.ac_year = self.combo(bar, "Year:", "ac_year", ["", *YEARS], run, 5)
        self.ac_type = self.combo(bar, "Type:", "ac_type", ["", *S.ACCESS_TYPES], run, 22)
        self.ac_status = self.combo(bar, "Status:", "ac_status", ["", *S.ACCESS_STATUSES], run,
                                    12)
        self.ac_exam = self.check(bar, "Exam only", "ac_exam", run)
        self.buttons(bar, (("Apply", run), ("New", self.new_access, True),
                           ("Edit", self.edit_access, True),
                           ("Status", self.access_status, True),
                           ("Expired", self.expired_access), ("Delete", self.delete_access, True),
                           ("Refresh", run)))
        bar2 = self.bar(tab)
        self.buttons(bar2, (("View", self.view_access), ("Summary", self.access_summary),
                            ("Open pupil", lambda: self.open_selected(self.acc))))
        self.acc = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                               ("type", "Type", 160), ("cat", "Category", 180),
                               ("status", "Status", 90), ("exam", "Exam", 45),
                               ("start", "Start", 90), ("end", "End", 90),
                               ("evidence", "Evidence", 140)], stretch={"pupil", "cat"})
        self.acc.on_double(self.view_access)

        def refresh() -> None:
            self.acc.fill(S.list_arrangements(
                year_group=self.ac_year.get() or None,
                arrangement_type=self.ac_type.get() or None,
                status=self.ac_status.get() or None,
                exam_only=True if self.ac_exam.get() else None), lambda a: a.arrangement_id,
                lambda a: (a.arrangement_id, f"{a.pupil_name} ({a.admission_no})", a.pupil_year,
                           a.arrangement_type, a.category, a.status,
                           "yes" if a.exam_only else "", a.start_date, a.end_date or "",
                           a.evidence_source or ""),
                lambda a: "bad" if a.expired else ("muted" if a.status in (
                    "Expired", "Withdrawn") else None))
        return refresh

    def new_access(self) -> None:
        self.form("New arrangement", _acc_fields(None),
                  lambda v: S.add_arrangement(filled(v) | {"exam_only": v["exam_only"]},
                                              actor=self.principal),
                  note="An Active arrangement needs who approved it. Exam access needs "
                       "evidence; JCQ Form 8 needs the assessor and a date from Year 9 on.")

    def edit_access(self) -> None:
        a = self.pick(self.acc, "Edit arrangement")
        if a:
            self.form(f"Arrangement #{a.arrangement_id} - {a.pupil_name}", _acc_fields(a),
                      lambda v: S.update_arrangement(a.arrangement_id, changed(a, v),
                                                     actor=self.principal))

    def access_status(self) -> None:
        a = self.pick(self.acc, "Status")
        if a:
            self.form(f"Status - arrangement #{a.arrangement_id}", [
                ("status", "Status", a.status, list(S.ACCESS_STATUSES)),
                ("approved_by", "Approved by (for Active)", a.approved_by or "", None)],
                lambda v: S.set_arrangement_status(a.arrangement_id, v["status"],
                                                   actor=self.principal,
                                                   approved_by=v["approved_by"] or None))

    def expired_access(self) -> None:
        rows = S.expired_arrangements()
        if not rows:
            self.info("Expired", "No Active arrangement is past its end date.")
            return
        text = "\n".join(f"#{a.arrangement_id} {a.pupil_name}: {a.category} (ended "
                         f"{a.end_date})" for a in rows)
        if self.editor and self.ask("Expired", text + "\n\nMark these Expired?"):
            n = S.expire_overdue(actor=self.principal)
            self.refresh_all()
            self.info("Expired", f"{n} marked expired.")
        elif not self.editor:
            self.text("Expired", text)

    def delete_access(self) -> None:
        a = self.pick(self.acc, "Delete arrangement")
        if a and self.ask("Delete", f"Delete arrangement #{a.arrangement_id}?"):
            S.delete_arrangement(a.arrangement_id, actor=self.principal)
            self.refresh_all()

    def view_access(self) -> None:
        a = self.pick(self.acc, "View")
        if a:
            self.text(f"Arrangement #{a.arrangement_id}", "\n".join(
                [f"{a.pupil_name} ({a.admission_no}), Year {a.pupil_year}", ""]
                + [f"{label}: {'yes' if v is True else v}" for _k, label, v in (
                    (f[0], f[1], getattr(a, f[0])) for f in _acc_fields(a))
                   if v not in (None, "", False)]))

    def access_summary(self) -> None:
        s = S.access_summary(year_group=self.ac_year.get() or None)
        self.text("Arrangements summary", "\n".join((
            f"Total: {s['total']}   Exam only: {s['exam_only']}   Expired: {s['expired']}   "
            f"Pupils with an active arrangement: {s['pupils']}", "",
            "By type: " + self.counts(s["by_type"]),
            "By category: " + self.counts(s["by_category"]),
            "By status: " + self.counts(s["by_status"]))))

    # ── Agencies ─────────────────────────────────────────────────────

    def _tab_agencies(self, tab):
        bar = self.bar(tab)
        run = lambda: self._run("Agencies")  # noqa: E731
        self.ag_status = self.combo(bar, "Status:", "ag_status", ["", *S.AGENCY_STATUSES], run,
                                    11)
        self.ag_year = self.combo(bar, "Year:", "ag_year", ["", *YEARS], run, 5)
        self.buttons(bar, (("New referral", self.new_agency, True),
                           ("Edit", self.edit_agency, True),
                           ("Delete", self.delete_agency, True),
                           ("Open pupil", lambda: self.open_selected(self.ag))))
        self.ag = Table(tab, [("id", "ID", 50), ("pupil", "Pupil", 200), ("yr", "Yr", 35),
                              ("agency", "Agency", 200), ("contact", "Contact", 140),
                              ("ref", "Referred", 90), ("status", "Status", 90),
                              ("next", "Next appointment", 110), ("report", "Report", 90)],
                        stretch={"pupil", "agency"})
        self.ag.on_double(self.edit_agency)

        def refresh() -> None:
            self.ag.fill(S.list_agencies(status=self.ag_status.get() or None,
                                         year_group=self.ag_year.get() or None),
                         lambda g: g.agency_id, lambda g: (
                g.agency_id, f"{g.pupil_name} ({g.admission_no})", g.pupil_year, g.agency,
                g.contact_name or "", g.referred_on or "", g.status, g.next_appointment or "",
                g.report_received_on or ""),
                lambda g: "muted" if g.status in ("Discharged", "Declined") else None)
        return refresh

    def new_agency(self) -> None:
        self.form("New agency referral", _agency_fields(None),
                  lambda v: S.add_agency(filled(v), actor=self.principal))

    def edit_agency(self) -> None:
        g = self.pick(self.ag, "Edit referral")
        if g:
            self.form(f"Agency #{g.agency_id} - {g.pupil_name}", _agency_fields(g),
                      lambda v: S.update_agency(g.agency_id, changed(g, v),
                                                actor=self.principal))

    def delete_agency(self) -> None:
        g = self.pick(self.ag, "Delete referral")
        if g and self.ask("Delete", f"Delete the {g.agency} referral for {g.pupil_name}?"):
            S.delete_agency(g.agency_id, actor=self.principal)
            self.refresh_all()

    # ── Strategies (every member of staff) ───────────────────────────

    def _tab_strategies(self, tab):
        self.note(tab, "What every teacher needs to know: needs, strategies and adjustments "
                       "for pupils on the SEND register.")
        bar = self.bar(tab)
        run = lambda: self._run("Strategies")  # noqa: E731
        self.st_mine = self.check(bar, "Only my classes", "st_mine", run)
        self.st_year = self.combo(bar, "Year:", "st_year", ["", *YEARS], run, 5)
        self.st_form = self.entry(bar, "Form:", "st_form", run, 8)
        self.buttons(bar, (("Refresh", run), ("Print view", self.print_strategies),
                           ("Open pupil", lambda: self.open_selected(self.st))))
        self.st = Table(tab, [("pupil", "Pupil", 190), ("yr", "Yr", 35), ("form", "Form", 55),
                              ("stage", "Stage", 120), ("needs", "Needs", 200),
                              ("strat", "Strategies", 320), ("adj", "Adjustments", 200)],
                        height=16, stretch={"strat", "adj"})
        self.st.on_double(self.print_strategies)

        def refresh() -> None:
            self.st.fill(self._strategies(), lambda r: r["pupil_id"], lambda r: (
                f"{r['pupil_name']} ({r['admission_no']})", r["year_group"],
                r["form_group"] or "", r["stage"], r["needs"],
                (r["strategies"] or "").replace("\n", " "),
                (r["adjustments"] or "").replace("\n", " ")))
        return refresh

    def _strategies(self) -> list[dict[str, Any]]:
        return S.strategies(actor=self.principal, mine=self.st_mine.get(),
                            year_group=None if self.st_mine.get() else (
                                self.st_year.get() or None),
                            form_group=self.st_form.get() or None)

    def print_strategies(self) -> None:
        sel = self.st.selected()
        rows = [sel] if sel else self._strategies()
        out = []
        for r in rows:
            out.append(f"{r['pupil_name']} ({r['admission_no']}), Year {r['year_group']} "
                       f"{r['form_group'] or ''} - {r['stage']}")
            for label, key in (("Needs", "needs"), ("Strategies", "strategies"),
                               ("Adjustments", "adjustments"), ("Exam access", "exam_access"),
                               ("Keyworker", "keyworker")):
                if r[key]:
                    out.append(f"  {label}: {r[key]}")
            out.append("")
        self.text("Strategies", "\n".join(out) or "No pupils.", save_name="send_strategies.txt")

    # ── Due ──────────────────────────────────────────────────────────

    def _tab_due(self, tab):
        self.note(tab, f"Reviews, plans, EHCP annual reviews (12 months from issue or the last "
                       f"review), LA deadlines, assessment deadlines and access arrangements "
                       f"due in the next {S.DUE_SOON_DAYS} days, and anything overdue.")
        bar = self.bar(tab)
        self.du_year = self.combo(bar, "Year:", "du_year", ["", *YEARS],
                                  lambda: self._run("Due"), 5)
        self.buttons(bar, (("Open pupil", lambda: self.open_selected(self.due)),
                           ("Go to record", self.goto_record)))
        self.due = Table(tab, [("due", "Due", 90), ("flag", "", 75), ("pupil", "Pupil", 220),
                               ("yr", "Yr", 35), ("item", "What", 420)], height=18,
                         stretch={"item"})
        self.due.on_double(self.goto_record)

        def refresh() -> None:
            self.due.fill(S.due(year_group=self.du_year.get() or None), None, lambda d: (
                d["due"], "OVERDUE" if d["overdue"] else "",
                f"{d['pupil_name']} ({d['admission_no']})", d["year_group"], d["item"]),
                lambda d: "bad" if d["overdue"] else None)
        return refresh

    def goto_record(self) -> None:
        d = self.due.selected()
        if d is None:
            return
        self.show_tab("Register")
        for v in (self.year, self.stage, self.status, self.need, self.area, self.search):
            v.set("")
        self.refresh()
        iid = str(d["pupil_id"])
        if self.reg.tree.exists(iid):
            self.reg.tree.selection_set(iid)
            self.reg.tree.see(iid)

    # ── Reports ──────────────────────────────────────────────────────

    def _tab_reports(self, tab):
        self.buttons(self.bar(tab), (("Refresh", lambda: self._run("Reports")),
                                     ("Cohort summary", self.cohort_text)))
        self.heading(tab, "Primary need by year (SEN support and EHC plans)")
        years = [str(y) for y in S.P.YEAR_GROUPS]
        self.rep_need = Table(tab, [("need", "Need", 60), ("label", "Label", 280),
                                    ("area", "Area", 200),
                                    *[(f"y{y}", f"Y{y}", 40) for y in years],
                                    ("total", "Total", 50)], height=8, stretch={"label"})
        self.heading(tab, "SEN support (K) and EHC plans (E) by year")
        self.rep_stage = Table(tab, [("year", "Year", 60), ("roll", "On roll", 70),
                                     ("k", "K", 50), ("kp", "K %", 60), ("e", "E", 50),
                                     ("ep", "E %", 60), ("mon", "Monitoring", 80)], height=6)
        self.heading(tab, "By area of need")
        self.rep_area = Table(tab, [("area", "Area", 320), ("pupils", "Pupils", 80)], height=5)

        def refresh() -> None:
            self.rep_need.fill(S.needs_by_year(), None, lambda r: (
                r["need"], r["label"], r["area"], *[r[y] for y in S.P.YEAR_GROUPS],
                r["total"]))
            self.rep_stage.fill(S.stage_by_year(), None, lambda r: (
                r["year"], r["on_roll"], r["K"], num(r["k_pct"]), r["E"], num(r["e_pct"]),
                r["monitoring"]))
            self.rep_area.fill(S.by_area(), None, lambda r: (r["area"], r["pupils"]))
        return refresh

    def cohort_text(self) -> None:
        s = S.cohort_summary()
        self.text("Cohort summary", "\n".join((
            f"On the register: {s['total']}   SEN support: {s['support_count']}   EHCP: "
            f"{s['ehcp_count']}   Monitoring: {s['monitoring']}   On roll: {s['on_roll']}", "",
            "By stage: " + self.counts(s["by_stage"]),
            "By primary need: " + self.counts(s["by_primary_need"]),
            "By status: " + self.counts(s["by_status"]))), save_name="send_summary.txt")


def draw_send(parent: ttk.Frame, *, principal: Principal, state: dict,
              open_pupil: Callable[[int], None] | None = None) -> SendPage:
    return SendPage(parent, principal=principal, state=state, open_pupil=open_pupil)
