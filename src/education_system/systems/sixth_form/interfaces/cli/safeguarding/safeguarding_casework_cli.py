"""CLI flows for safeguarding casework: referrals, plans, LADO, transfers.

Reached from the Safeguarding submenu (and "LADO Allegations" for the
Principal). Every function is DSL-only in the domain layer; refusals are
printed, not raised.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.sixth_form.domain.safeguarding import (
    safeguarding as sg,
)
from education_system.systems.sixth_form.domain.safeguarding import (
    safeguarding_casework as cw,
)
from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.safeguarding.safeguarding_cli import (
    _UserAbort,
    _input,
    _pause,
    _pick_from,
    _pick_student,
    _yes_no,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _int(prompt: str) -> int:
    raw = _input(prompt, allow_empty=False)
    if not raw.isdigit():
        print("  ✗ Must be a number.")
        raise _UserAbort
    return int(raw)


def _menu(title: str, items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        try:
            items[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except (ValidationError, sg.AccessDenied) as e:
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("%s CLI handler crashed", title)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def _optional_choice(label: str, options: tuple[str, ...]) -> str:
    return "" if not _yes_no(f"Set {label.lower()}?") else \
        _pick_from(label, list(options))


# ── Referrals ─────────────────────────────────────────────────────

def _print_referrals(rows: list[cw.Referral]) -> None:
    if not rows:
        print("\n  (no referrals)")
        return
    print(f"\n  {'#':>4}  {'Concern':<8} {'Learner':<10} {'Agency':<22} "
          f"{'Referred':<10} {'Follow-up':<10} {'Status':<7} Outcome")
    print("  " + "-" * 96)
    for r in rows:
        flag = " OVERDUE" if r.follow_up_overdue() else ""
        print(f"  {r.referral_id:>4}  #{r.concern_id:<7} {r.student_id:<10} "
              f"{r.agency[:22]:<22} {r.referral_date:<10} "
              f"{r.follow_up_due or '—':<10} {r.status:<7} "
              f"{r.outcome or '—'}{flag}")


def referrals_list() -> None:
    _print_referrals(cw.list_referrals(open_only=_yes_no("Open only?", True)))
    _pause()


def referrals_overdue() -> None:
    print("\n═══ Overdue Referral Follow-ups ═══")
    _print_referrals(cw.overdue_referral_follow_ups())
    _pause()


def referrals_new() -> None:
    print("\n═══ New Referral ═══")
    cid = _int("Concern #")
    c = sg.get_concern(cid)
    if c is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    print(f"  Learner {c.student_id}, age "
          f"{sg.student_age(c.student_id) or '—'}; suggested: "
          f"{', '.join(sg.suggested_agencies(c.student_id))}")
    agency = _pick_from("Agency", list(cw.REFERRAL_AGENCIES),
                        default=sg.suggested_agencies(c.student_id)[0])
    when = _input("Referral date", default=_today(), allow_empty=False)
    warning = sg.agency_warning(c.student_id, agency, when)
    if warning:
        print(f"  ⚠ {warning}")
        if not _yes_no("Record it anyway?"):
            return
    r = cw.create_referral({
        "concern_id": cid, "agency": agency, "referral_date": when,
        "reference": _input("Reference (optional)"),
        "reason": _input("Reason (optional)"),
        "next_action": _input("Next action (optional)"),
        "follow_up_due": _input("Follow-up due (YYYY-MM-DD, optional)"),
    })
    print(f"\n  ✓ Referral #{r.referral_id} to {r.agency} recorded")
    _pause()


def referrals_outcome() -> None:
    rid = _int("Referral #")
    outcome = _pick_from("Outcome", list(cw.REFERRAL_OUTCOMES))
    r = cw.record_referral_outcome(
        rid, outcome=outcome,
        outcome_date=_input("Outcome date", default=_today()),
        next_action=_input("Next action (optional)"),
        follow_up_due=_input("Follow-up due (optional)"))
    print(f"\n  ✓ Referral #{r.referral_id}: {r.outcome}")
    _pause()


def referrals_close() -> None:
    rid = _int("Referral #")
    cw.close_referral(rid, reason=_input("Reason", allow_empty=False))
    print(f"\n  ✓ Referral #{rid} closed")
    _pause()


def run_referrals() -> None:
    _menu("Safeguarding Referrals", [
        ("List referrals", referrals_list),
        ("Overdue follow-ups", referrals_overdue),
        ("New referral", referrals_new),
        ("Record outcome", referrals_outcome),
        ("Close referral", referrals_close),
    ])


# ── Plans ─────────────────────────────────────────────────────────

def _print_plans(rows: list[cw.Plan]) -> None:
    if not rows:
        print("\n  (no plans)")
        return
    print(f"\n  {'#':>4}  {'Learner':<10} {'Plan':<24} {'Start':<10} "
          f"{'Next review':<11} {'Status':<13} Lead professional")
    print("  " + "-" * 96)
    for pl in rows:
        flag = " OVERDUE" if pl.review_overdue() else ""
        print(f"  {pl.plan_id:>4}  {pl.student_id:<10} {pl.plan_type:<24} "
              f"{pl.start_date:<10} {pl.next_review_date or '—':<11} "
              f"{pl.status:<13} {pl.lead_professional or '—'}{flag}")


def plans_list() -> None:
    _print_plans(cw.list_plans(active_only=_yes_no("Active only?", True)))
    _pause()


def plans_overdue() -> None:
    print("\n═══ Overdue Plan Reviews ═══")
    _print_plans(cw.overdue_plan_reviews())
    _pause()


def plans_new() -> None:
    print("\n═══ New Plan ═══")
    sid = _pick_student()
    pl = cw.create_plan({
        "student_id": sid,
        "plan_type": _pick_from("Plan type", list(cw.PLAN_TYPES)),
        "start_date": _input("Start date", default=_today()),
        "local_authority": _input("Local authority (optional)"),
        "lead_professional": _input("Lead professional (optional)"),
        "lead_agency": _input("Lead agency (optional)"),
        "college_contact": _input("College contact (optional)"),
        "next_review_date": _input("Next review (blank = default)"),
        "concern_id": _input("Linked concern # (optional)"),
        "notes": _input("Notes (optional)"),
    })
    print(f"\n  ✓ {pl.plan_type} #{pl.plan_id}; next review "
          f"{pl.next_review_date}")
    _pause()


def plans_meetings() -> None:
    pid = _int("Plan #")
    for m in cw.list_meetings(pid):
        print(f"  {m.meeting_date}  {m.meeting_type:<36} "
              f"next {m.next_meeting_date or '—'}")
        for line in (m.summary or "").splitlines():
            print(f"      {line}")
    if _yes_no("Add a meeting?"):
        m = cw.add_meeting(pid, {
            "meeting_type": _pick_from("Type", list(cw.MEETING_TYPES),
                                       default="Core Group"),
            "meeting_date": _input("Date", default=_today()),
            "attendees": _input("Attendees (optional)"),
            "college_attended": _yes_no("College attended?", True),
            "college_rep": _input("College representative (optional)"),
            "summary": _input("Summary (optional)"),
            "actions": _input("Actions (optional)"),
            "next_meeting_date": _input("Next meeting (optional)"),
        })
        print(f"  ✓ Meeting #{m.meeting_id} recorded")
    _pause()


def plans_review() -> None:
    pid = _int("Plan #")
    pl = cw.record_review(
        pid, review_date=_input("Review date", default=_today()),
        next_review_date=_input("Next review (blank = default)") or None,
        summary=_input("Summary (optional)"),
        attendees=_input("Attendees (optional)"))
    print(f"\n  ✓ Reviewed; next review {pl.next_review_date}")
    _pause()


def plans_step_down() -> None:
    pid = _int("Plan #")
    pl = cw.step_down_plan(
        pid, to=_pick_from("Step down to", list(cw.STEP_DOWN_TARGETS)),
        on=_input("Date", default=_today()),
        reason=_input("Reason (optional)"))
    print(f"\n  ✓ Plan #{pid} stepped down"
          + (f"; new plan #{pl.successor_plan_id}"
             if pl.successor_plan_id else ""))
    _pause()


def plans_end() -> None:
    pid = _int("Plan #")
    cw.end_plan(pid, reason=_pick_from("Reason", list(cw.PLAN_END_REASONS)),
                on=_input("Date", default=_today()))
    print(f"\n  ✓ Plan #{pid} ended")
    _pause()


def run_plans() -> None:
    _menu("Plans (CP / CIN / Early Help)", [
        ("List plans", plans_list),
        ("Overdue reviews", plans_overdue),
        ("New plan", plans_new),
        ("Meetings / add meeting", plans_meetings),
        ("Record review", plans_review),
        ("Step down", plans_step_down),
        ("End plan", plans_end),
    ])


# ── LADO ──────────────────────────────────────────────────────────

def _print_allegations(rows: list[cw.Allegation]) -> None:
    if not rows:
        print("\n  (no allegations)")
        return
    print(f"\n  {'#':>4}  {'Name':<22} {'Role':<18} {'Date':<10} "
          f"{'To LADO':<10} {'Outcome':<16} {'DBS':<4} {'TRA':<4} Status")
    print("  " + "-" * 100)
    for a in rows:
        print(f"  {a.allegation_id:>4}  {a.subject_name[:22]:<22} "
              f"{a.subject_role[:18]:<18} {a.allegation_date:<10} "
              f"{a.reported_to_lado_date or 'NOT YET':<10} "
              f"{a.outcome or '—':<16} {'Y' if a.dbs_referral else '':<4} "
              f"{'Y' if a.tra_referral else '':<4} {a.status}")


def lado_list() -> None:
    _print_allegations(cw.list_allegations(
        open_only=_yes_no("Open only?", True)))
    _pause()


def lado_late() -> None:
    print("\n═══ Not Yet Reported to LADO (over 1 working day) ═══")
    _print_allegations(cw.lado_not_reported())
    _pause()


def lado_new() -> None:
    print("\n═══ New LADO Allegation ═══")
    a = cw.create_allegation({
        "staff_id": _input("Staff ID (blank if not staff)"),
        "subject_name": _input("Name (blank = from staff record)"),
        "subject_role": _pick_from("Role", list(cw.LADO_SUBJECT_ROLES)),
        "allegation_date": _input("Allegation date", default=_today()),
        "allegation": _input("Allegation", allow_empty=False),
        "reported_by": _input("Reported by (optional)"),
        "reported_to_lado_date": _input("Reported to LADO on (optional)"),
        "lado_reference": _input("LADO reference (optional)"),
        "lado_officer": _input("LADO officer (optional)"),
        "police_involved": _yes_no("Police involved?"),
        "suspended": _yes_no("Suspended?"),
        "actions": _input("Actions (optional)"),
    })
    print(f"\n  ✓ Allegation #{a.allegation_id} recorded")
    _pause()


def lado_update() -> None:
    aid = _int("Allegation #")
    a = cw.get_allegation(aid)
    if a is None:
        print(f"  ✗ No allegation #{aid}")
        _pause()
        return
    cw.update_allegation(aid, {
        "reported_to_lado_date": _input(
            "Reported to LADO on", default=a.reported_to_lado_date or ""),
        "lado_reference": _input("LADO reference",
                                 default=a.lado_reference or ""),
        "lado_officer": _input("LADO officer", default=a.lado_officer or ""),
        "strategy_meeting_date": _input(
            "Strategy meeting", default=a.strategy_meeting_date or ""),
        "actions": _input("Actions", default=a.actions or ""),
    })
    print("  ✓ Updated")
    _pause()


def lado_outcome() -> None:
    aid = _int("Allegation #")
    dbs = _yes_no("Referred to DBS?")
    tra = _yes_no("Referred to the TRA?")
    a = cw.record_lado_outcome(
        aid, outcome=_pick_from("Outcome", list(cw.LADO_OUTCOMES)),
        outcome_date=_input("Outcome date", default=_today()),
        dbs_referral=dbs,
        dbs_referral_date=_input("DBS referral date", default=_today())
        if dbs else None,
        tra_referral=tra,
        tra_referral_date=_input("TRA referral date", default=_today())
        if tra else None,
        actions=_input("Actions (optional)") or None)
    print(f"\n  ✓ Outcome recorded: {a.outcome}")
    _pause()


def lado_close() -> None:
    aid = _int("Allegation #")
    cw.close_allegation(aid, reason=_input("Reason", allow_empty=False))
    print(f"\n  ✓ Allegation #{aid} closed")
    _pause()


def run_lado() -> None:
    try:
        cw.require_lado_access(action="lado-open")
    except sg.AccessDenied as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _menu("LADO Register", [
        ("List allegations", lado_list),
        ("Not yet reported to LADO", lado_late),
        ("New allegation", lado_new),
        ("Update LADO details", lado_update),
        ("Record outcome", lado_outcome),
        ("Close allegation", lado_close),
    ])


# ── Transfers ─────────────────────────────────────────────────────

def _print_transfers(rows: list[cw.Transfer]) -> None:
    if not rows:
        print("\n  (no transfers)")
        return
    print(f"\n  {'#':>4}  {'Dir':<4}{'Learner':<10} {'Institution':<24} "
          f"{'Due by':<10} {'Sent/Recv':<10} {'Status':<18}")
    print("  " + "-" * 90)
    for t in rows:
        flag = " OVERDUE" if t.overdue() else ""
        print(f"  {t.transfer_id:>4}  {t.direction:<4}{t.student_id:<10} "
              f"{t.institution[:24]:<24} {t.due_by or '—':<10} "
              f"{(t.date_sent or t.date_received or '—'):<10} "
              f"{t.status:<18}{flag}")


def transfers_list() -> None:
    _print_transfers(cw.list_transfers())
    _pause()


def transfers_awaiting() -> None:
    print("\n═══ Sent — Awaiting Receipt ═══")
    _print_transfers(cw.outgoing_awaiting_receipt())
    print("\n═══ Incoming — Overdue ═══")
    _print_transfers(cw.incoming_overdue())
    _pause()


def transfers_send() -> None:
    print("\n═══ Send Safeguarding File ═══")
    sid = _pick_student()
    t = cw.record_transfer_out(
        sid, institution=_input("Receiving institution", allow_empty=False),
        institution_contact=_input("Receiving DSL / contact (optional)"),
        method=_pick_from("Method", list(cw.TRANSFER_METHODS)),
        leaving_date=_input("Leaving / start date", default=_today()),
        date_sent=_input("Date sent (blank = not yet)") or None,
        notes=_input("Notes (optional)"))
    print(f"\n  ✓ Transfer #{t.transfer_id}; pack written to {t.file_path}")
    print(f"    Due by {t.due_by}. Send separately from the main file.")
    _pause()


def transfers_mark_sent() -> None:
    tid = _int("Transfer #")
    cw.mark_transfer_sent(tid, date_sent=_input("Date sent",
                                                default=_today()))
    print("  ✓ Marked sent")
    _pause()


def transfers_receipt() -> None:
    tid = _int("Transfer #")
    cw.confirm_receipt(
        tid, confirmed_by=_input("Confirmed by (receiving DSL)",
                                 allow_empty=False),
        confirmed_on=_input("Confirmed on", default=_today()))
    print("  ✓ Receipt confirmed")
    _pause()


def transfers_expect() -> None:
    print("\n═══ Expect File From Previous Setting ═══")
    sid = _pick_student()
    t = cw.expect_incoming(
        sid, institution=_input("Previous institution", allow_empty=False),
        institution_contact=_input("Contact (optional)"),
        start_date=_input("Start date", default=_today()),
        notes=_input("Notes (optional)"))
    print(f"\n  ✓ Expecting file by {t.due_by} (transfer #{t.transfer_id})")
    _pause()


def transfers_received() -> None:
    tid = _int("Transfer #")
    method = _optional_choice("Method", cw.TRANSFER_METHODS)
    cw.record_received(
        tid, date_received=_input("Date received", default=_today()),
        method=method or None,
        file_ref=_input("Where it is kept (separate file ref)"),
        notes=_input("Notes (optional)") or None)
    print("  ✓ Recorded as received (kept separately)")
    _pause()


def transfers_pack() -> None:
    sid = _input("Student ID (leavers too)", allow_empty=False)
    print(f"\n  ✓ Pack written to {cw.build_transfer_pack(sid)}")
    _pause()


def run_transfers() -> None:
    _menu("Safeguarding File Transfers", [
        ("List transfers", transfers_list),
        ("Awaiting receipt / overdue", transfers_awaiting),
        ("Send a file (builds transfer pack)", transfers_send),
        ("Mark sent", transfers_mark_sent),
        ("Confirm receipt", transfers_receipt),
        ("Expect a file from previous setting", transfers_expect),
        ("Record file received", transfers_received),
        ("Build transfer pack only", transfers_pack),
    ])


# ── Summary ───────────────────────────────────────────────────────

def casework_summary_flow() -> None:
    try:
        s = cw.casework_summary()
    except sg.AccessDenied as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print("\n═══ Safeguarding Casework Summary ═══")
    rows: list[tuple[str, Any]] = [
        ("Referrals open", s.referrals_open),
        ("Referral follow-ups overdue", s.referrals_overdue),
        ("Plans active", s.plans_active),
        ("Plan reviews overdue", s.plans_review_overdue),
        ("LADO allegations open", s.lado_open),
        ("LADO not yet reported (>1 day)", s.lado_not_reported),
        ("Files sent, awaiting receipt", s.transfers_out_awaiting_receipt),
        ("Incoming files overdue", s.transfers_in_overdue),
    ]
    for label, n in rows:
        print(f"  {label:<34}: {n}")
    for t, n in sorted(s.plans_by_type.items()):
        print(f"    {t:<32}: {n}")
    _pause()
