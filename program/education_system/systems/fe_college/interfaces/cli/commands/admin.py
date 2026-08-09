"""Admin commands — dashboards, finance and the account/record join."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import (
    BURSARY_TYPES,
    FEE_TYPES,
    PAYMENT_METHODS,
)
from education_system.systems.fe_college.domain.finance.bursaries import Bursary
from education_system.systems.fe_college.domain.finance.fees import Fee
from education_system.systems.fe_college.domain.finance.payments import Payment
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    finance_repository as finance_repo,
)
from education_system.systems.fe_college.interfaces.cli import shell as sh


# ── Dashboards ──────────────────────────────────────────────────────────────

def dashboard(ctl) -> None:
    """Whichever dashboard fits the signed-in view."""
    if ctl.identity.is_admin:
        _college_dashboard(ctl)
    elif ctl.identity.is_staff:
        _staff_dashboard(ctl)
    else:
        _student_dashboard(ctl)


def _college_dashboard(ctl) -> None:
    stats = ctl.reports.college_stats()
    sh.header(f"{ctl.college_name} — {ctl.academic_year}",
              f"Attendance {sh.pct(stats.attendance_pct)} ({stats.attendance_band})")
    sh.key_values([
        ("Learners on roll", stats.learners_on_roll),
        ("Applicants", stats.applicants),
        ("Staff", f"{stats.staff_total} ({stats.teaching_staff} teaching)"),
        ("Courses running", f"{stats.courses_running} "
                            f"({stats.courses_at_risk} recruiting badly)"),
        ("Attendance", f"{sh.pct(stats.attendance_pct)} ({stats.attendance_band})"),
        ("Learners at risk", stats.learners_at_risk),
        ("Work to be marked", stats.marking_outstanding),
        ("Open referrals", f"{stats.open_referrals} "
                           f"({stats.safeguarding_open} safeguarding)"),
        ("Tutorials overdue", stats.tutorials_overdue),
        ("Fees charged", sh.money(stats.fees_charged)),
        ("Fees outstanding", sh.money(stats.fees_outstanding)),
        ("Collected", sh.pct(stats.fees_collected_pct)),
        ("Bursaries awarded", sh.money(stats.bursary_awarded)),
    ])

    sh.section("Attendance by course (worst first)")
    sh.table(
        [("course_id", "Code"), ("title", "Title"),
         ("attendance_pct", "Attendance"), ("band", "Band")],
        [{**r, "attendance_pct": sh.pct(r["attendance_pct"])}
         for r in ctl.reports.attendance_report()],
        limit=8, empty="No registers taken yet.",
    )

    sh.section("Recruitment (worst first)")
    sh.table(
        [("course_id", "Code"), ("title", "Title"), ("enrolled", "On"),
         ("capacity", "Cap"), ("fill_pct", "Filled"), ("viability", "Viability")],
        [{**r, "fill_pct": sh.pct(r["fill_pct"])}
         for r in ctl.reports.viability_report()],
        limit=8, empty="No courses set up.",
    )


def _staff_dashboard(ctl) -> None:
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record, so there is "
                "nothing to show. Ask an administrator to check the join — "
                "records are matched by email.")
        return
    stats = ctl.reports.staff_stats(ctl.staff_id)
    sh.header(f"My teaching — {stats.staff_name}", ctl.subtitle())
    sh.key_values([
        ("My learners", f"{stats.learners} across {stats.courses} course(s)"),
        ("Class groups", stats.groups),
        ("Sessions per week", stats.sessions_per_week),
        ("Their attendance", f"{sh.pct(stats.attendance.attendance_pct)} "
                             f"({stats.attendance.band})"),
        ("Learners at risk", stats.learners_at_risk),
        ("Work to be marked", stats.marking_outstanding),
        ("Assignments open", stats.assignments_open),
    ])

    queue = ctl.assessment.marking_queue(ctl.staff_id)
    sh.section("Waiting to be marked")
    sh.table(
        [("student", "Learner"), ("assignment", "Assignment"),
         ("submitted", "Submitted"), ("late", "Late")],
        [
            {"student": r.student.full_name, "assignment": r.assignment.title,
             "submitted": r.submission.submitted_at, "late": r.is_late}
            for r in queue
        ],
        limit=10, empty="Nothing waiting — the queue is clear.",
    )


def _student_dashboard(ctl) -> None:
    if not ctl.student_id:
        sh.note("Your account is not linked to a learner record, so there is "
                "nothing to show. Ask college administration to check it.")
        return
    stats = ctl.reports.student_stats(ctl.student_id)
    sh.header(f"Hello, {stats.student_name}", ctl.subtitle())
    sh.key_values([
        ("Courses", stats.courses),
        ("My attendance", f"{sh.pct(stats.attendance.attendance_pct)} "
                          f"({stats.attendance.band})"),
        ("Work due", f"{stats.assignments_due} "
                     f"({stats.assignments_overdue} overdue)"),
        ("Grades awarded", stats.grades_awarded),
        ("Pass rate", sh.pct(stats.pass_rate)),
        ("Credits", f"{stats.credits_achieved} of {stats.credits_required}"),
        ("Open targets", stats.targets_open),
        ("Balance", sh.money(stats.balance)),
    ])
    if stats.attendance.attendance_pct is not None and \
            stats.attendance.attendance_pct < 90:
        sh.warn(
            f"Your attendance is {sh.pct(stats.attendance.attendance_pct)}, "
            "below the 90% the college expects. Talk to your personal tutor "
            "if something is getting in the way."
        )


# ── Finance ─────────────────────────────────────────────────────────────────

def finance(ctl) -> None:
    """The college's fee position."""
    totals = finance_repo.outstanding_totals()
    bursaries = finance_repo.bursary_totals()
    sh.header("Finance", ctl.reports.header())
    sh.key_values([
        ("Charged", sh.money(totals["charged"])),
        ("Collected", sh.money(totals["paid"])),
        ("Waived", sh.money(totals["waived"])),
        ("Outstanding", sh.money(totals["outstanding"])),
        ("Bursaries awarded", sh.money(bursaries["awarded"])),
        ("Bursaries paid", sh.money(bursaries["paid"])),
        ("Bursary recipients", bursaries["learners"]),
    ])

    sh.section("Outstanding balances (largest first)")
    sh.table(
        [("student_id", "ID"), ("name", "Name"),
         ("outstanding", "Outstanding"), ("overdue", "Overdue")],
        [
            {**r, "outstanding": sh.money(r["outstanding"]),
             "overdue": sh.money(r["overdue"])}
            for r in ctl.reports.finance_report()
        ],
        limit=25, empty="Nothing is outstanding.",
    )

    sh.section("Funding allocations")
    sh.table(
        [("source", "Stream"), ("year", "Year"), ("allocated", "Allocated"),
         ("earned", "Earned"), ("delivery", "Delivery"), ("status", "Position")],
        [
            {"source": a.funding_source, "year": a.academic_year,
             "allocated": sh.money(a.allocated), "earned": sh.money(a.earned),
             "delivery": sh.pct(a.delivery_pct), "status": a.status}
            for a in finance_repo.list_allocations()
        ],
        empty="No allocations recorded.",
    )


def raise_fee(ctl) -> None:
    """Charge a fee to a learner."""
    learner = _pick_learner(ctl)
    if learner is None:
        return
    result = sh.form(f"Fee for {learner.full_name}", [
        ("fee_type", "Type", "choice", FEE_TYPES),
        ("amount", "Amount (£)", "float"),
        ("description", "Description", "text"),
        ("due_date", "Due date", "date"),
    ], initial={"due_date": date.today()})
    if result is sh.CANCEL:
        return

    try:
        finance_repo.raise_fee(Fee(
            fee_id=None,
            student_id=learner.student_id,
            fee_type=result["fee_type"] or FEE_TYPES[0],
            amount=result["amount"],
            description=result["description"],
            academic_year=ctl.academic_year,
            due_date=result["due_date"],
            raised_on=date.today(),
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Charged {sh.money(result['amount'])} to {learner.full_name}")


def record_payment(ctl) -> None:
    """Record a payment against an outstanding fee."""
    learner = _pick_learner(ctl)
    if learner is None:
        return
    fees = [
        f for f in finance_repo.list_fees(student_id=learner.student_id)
        if f.balance > 0
    ]
    if not fees:
        sh.note(f"{learner.full_name} owes nothing.")
        return

    fee = sh.choose_object(
        "Fee", fees,
        lambda f: f"{f.fee_type} · {f.description or 'no description'} — "
                  f"{sh.money(f.balance)} outstanding",
    )
    if fee is sh.CANCEL:
        return

    amount = sh.ask_float("Amount (£)", fee.balance)
    if amount is sh.CANCEL:
        return
    method = sh.choose("Method", list(PAYMENT_METHODS))
    if method is sh.CANCEL:
        return
    reference = sh.prompt("Reference")
    if reference is sh.CANCEL:
        return

    try:
        finance_repo.record_payment(Payment(
            payment_id=None,
            fee_id=fee.fee_id,
            student_id=learner.student_id,
            amount=amount,
            method=method,
            paid_on=date.today(),
            reference=reference,
            received_by=ctl.staff_id,
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Recorded {sh.money(amount)} from {learner.full_name}")


def bursary(ctl) -> None:
    """Record a bursary application or award."""
    learner = _pick_learner(ctl)
    if learner is None:
        return
    result = sh.form(f"Bursary for {learner.full_name}", [
        ("bursary_type", "Type", "choice", BURSARY_TYPES),
        ("amount_awarded", "Amount (£)", "float"),
        ("attendance_condition_pct", "Attendance condition (%)", "float"),
        ("evidence", "Evidence", "text"),
        ("approve", "Approve it now", "bool"),
    ], initial={"attendance_condition_pct": 90.0})
    if result is sh.CANCEL:
        return

    approving = result["approve"]
    if approving and not ctl.staff_id:
        sh.warn("Your account is not linked to a staff record, so the approval "
                "could not be attributed. Recording it as applied instead.")
        approving = False

    try:
        finance_repo.save_bursary(Bursary(
            bursary_id=None,
            student_id=learner.student_id,
            bursary_type=result["bursary_type"] or BURSARY_TYPES[0],
            status="approved" if approving else "applied",
            amount_awarded=result["amount_awarded"],
            academic_year=ctl.academic_year,
            attendance_condition_pct=result["attendance_condition_pct"],
            applied_on=date.today(),
            decided_on=date.today() if approving else None,
            decided_by=ctl.staff_id if approving else "",
            evidence=result["evidence"],
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(
        f"{'Approved' if approving else 'Recorded'} a "
        f"{sh.money(result['amount_awarded'])} bursary for {learner.full_name}"
    )


# ── Accounts ────────────────────────────────────────────────────────────────

def whoami(ctl) -> None:
    """Show how this account resolves to a college record."""
    identity = ctl.identity
    sh.header("This session")
    sh.key_values([
        ("Signed in as", identity.username),
        ("Display name", identity.display_name),
        ("Launcher role", f"{identity.role} → {identity.view} view"),
        ("Account email", identity.email or "not set on the account"),
        ("Staff record", identity.staff.display_name if identity.staff else "none"),
        ("Learner record",
         identity.student.display_name if identity.student else "none"),
    ])
    if not (identity.staff or identity.student):
        sh.warn(
            "This account has no matching college record, so role-specific "
            "screens will be empty. Records are matched by email — set the "
            "account's email to match a record, or link one for this session."
        )


def link_record(ctl) -> None:
    """Attach a staff or learner record to this session.

    Accounts live in shared auth and are matched to college records by email.
    When that match fails the user gets a working login with no data behind it;
    this repairs it for the session so they are not stuck.
    """
    kind = sh.choose("Link which kind of record?", ["staff", "learner"])
    if kind is sh.CANCEL:
        return

    if kind == "staff":
        query = sh.prompt("Search staff by name or ID")
        if query is sh.CANCEL:
            return
        matches = ctl.staff.search(query=query)
        if not matches:
            sh.note("No staff match.")
            return
        chosen = sh.choose_object("Which one?", matches[:20], lambda s: s.display_name)
        if chosen is sh.CANCEL:
            return
        ctl.rebind_staff(chosen.staff_id)
        sh.success(f"This session is now {chosen.display_name}")
        sh.note(f"To make it permanent, set the account's email to {chosen.email}.")
        return

    query = sh.prompt("Search learners by name or ID")
    if query is sh.CANCEL:
        return
    matches = ctl.students.search(query=query)
    if not matches:
        sh.note("No learners match.")
        return
    chosen = sh.choose_object("Which one?", matches[:20], lambda s: s.display_name)
    if chosen is sh.CANCEL:
        return
    ctl.rebind_student(chosen.student_id)
    sh.success(f"This session is now {chosen.display_name}")


def _pick_learner(ctl):
    query = sh.prompt("Learner — search by name or ID")
    if query is sh.CANCEL:
        return None
    matches = ctl.students.search(query=query)
    if not matches:
        sh.note("No learners match.")
        return None
    if len(matches) == 1:
        return matches[0]
    chosen = sh.choose_object("Which one?", matches[:30], lambda s: s.display_name)
    return None if chosen is sh.CANCEL else chosen


__all__ = [
    "bursary", "dashboard", "finance", "link_record", "raise_fee",
    "record_payment", "whoami",
]
