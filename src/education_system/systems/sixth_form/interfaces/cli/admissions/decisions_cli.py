"""Admissions CLI: offers, decisions, waitlist, status changes."""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta as _timedelta
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    admissions_comms as comms,
    capacity,
    cycles,
    references as refs,
    status_rules,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DECISION_REASONS,
    DEFAULT_OFFER_TYPE,
    OFFER_TYPES,
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _pick_grade,
    _yes,
    _attempt,
    _cli_user,
    _pick_reason,
    _pick_status,
    _show_messages,
)



def _build_conditions(a: Applicant) -> str:
    """Structured per-subject grade builder (item 29)."""
    parts: list[str] = []
    subjects = a.subjects or []
    for i in range(max(3, len(subjects))):
        default = subjects[i] if i < len(subjects) else ""
        subj = _input(f"Condition subject {i + 1} (blank to stop)",
                       default=default)
        if not subj:
            break
        grade = _pick_grade(f"Minimum grade for {subj}")
        parts.append(f"{subj} grade {grade} or above")
    return "; ".join(parts)


def offer_with_capacity_check(aid: str, **kwargs) -> Applicant | None:
    """make_offer, handling a full programme: waitlist, override (with a
    reason on the timeline) or cancel. Returns the applicant, or None
    when no offer was made."""
    try:
        return data.make_offer(aid, **kwargs)
    except capacity.CapacityFull as full:
        print(f"\n  ⚠ {full}")
        choice = _pick_from("What now?", [
            "Put on the waitlist", "Override capacity and offer anyway",
            "Cancel"], default="Cancel")
        if choice.startswith("Put"):
            ok, progs = _attempt(capacity.waitlist_if_full, aid)
            if ok:
                print(f"  ✓ {aid} waitlisted (full: {', '.join(progs)})")
            return None
        if choice.startswith("Override"):
            reason = _input("Reason for going over capacity",
                            allow_empty=False)
            ok, out = _attempt(data.make_offer, aid, override_capacity=True,
                               **kwargs)
            if ok:
                data.add_note(aid, f"Capacity override: {reason}",
                              author=_cli_user())
                return out
        return None
    except ValidationError as e:
        print(f"  ✗ {e}")
        return None


def make_offer_flow() -> None:
    print("\n═══ Make Offer ═══")
    try:
        a = _pick_applicant()
        offer_type = _pick_from(
            "Offer type", list(OFFER_TYPES), default=DEFAULT_OFFER_TYPE)
        if _yes("Build conditions from subjects + grades?"):
            conditions = _build_conditions(a)
            print(f"    Conditions: {conditions or '(none)'}")
        else:
            conditions = _input("Conditions",
                                  default=a.offer_conditions or "")
        decided_by = _input("Decided by", default=a.decision_by or "")
        expiry = _input("Offer expiry (YYYY-MM-DD, blank to skip)",
                         default=a.offer_expiry
                         or (_date.today()
                             + _timedelta(days=28)).isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    out = offer_with_capacity_check(
        a.applicant_id, offer_type=offer_type,
        conditions=conditions or None, decided_by=decided_by or None)
    if out is None:
        _pause()
        return
    if expiry:
        ok, out = _attempt(data.set_offer_expiry, a.applicant_id, expiry)
        if not ok:
            _pause()
            return
    print(f"\n  ✓ Offer ({offer_type}) made to {a.applicant_id}"
          + (f", expires {out.offer_expiry}" if out.offer_expiry else ""))
    if _yes("  E-mail the offer letter now?"):
        _send_offer_letter(a.applicant_id)
    _pause()


def _send_offer_letter(aid: str) -> None:
    parents = _yes("  Copy to parents/carers who receive correspondence?")
    ok, msgs = _attempt(comms.send_offer_letter, aid,
                        include_parents=parents)
    if ok:
        _show_messages(msgs)


def accept_offer_flow() -> None:
    print("\n═══ Accept Offer ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.accept_offer(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} accepted offer")
    _pause()


def decline_offer_flow() -> None:
    print("\n═══ Decline Offer ═══")
    try:
        a = _pick_applicant()
        reason = _pick_reason("Why did they decline?",
                              data.WITHDRAWAL_REASONS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.decline_offer(a.applicant_id, reason=reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} declined offer")
    _pause()


def reject_flow() -> None:
    print("\n═══ Reject Applicant ═══")
    try:
        a = _pick_applicant()
        reason = _pick_from("Reason code", list(DECISION_REASONS))
        decided_by = _input("Decided by")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_decision(a.applicant_id, "Rejected", reason=reason,
                              decided_by=decided_by or None,
                              notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} rejected ({reason})")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw Applicant ═══")
    try:
        a = _pick_applicant()
        reason = _pick_reason("Withdrawal reason", data.WITHDRAWAL_REASONS)
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(a.applicant_id, notes=notes or None, reason=reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} withdrawn")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_applicant()
        if a.status in status_rules.REOPENABLE:
            print(f"    {a.applicant_id} is {a.status} (closed).")
            if _yes("    Reopen it (back to Under Review)?"):
                _reopen(a)
            return
        new_status = _pick_status(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.applicant_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} → {new_status}")
    _pause()


# ── Waitlist & decision day (items 34, 35) ────────────────────────

def _reopen(a: Applicant) -> None:
    reason = _input("Reason for reopening", allow_empty=False)
    ok, out = _attempt(data.reopen_application, a.applicant_id,
                       reason=reason)
    if ok:
        print(f"  ✓ {a.applicant_id} reopened → {out.status}")


def reopen_flow() -> None:
    print("\n═══ Reopen Closed Application ═══")
    rows = [a for a in data.list_applicants()
            if a.status in status_rules.REOPENABLE]
    if not rows:
        print("  No declined, rejected or withdrawn applications.")
        _pause()
        return
    labels = [f"{a.applicant_id}  {a.full_name[:24]:<24} [{a.status}]"
              + (f" — {a.withdrawal_reason}" if a.withdrawal_reason else "")
              for a in rows]
    _reopen(rows[labels.index(_pick_from("Application", labels))])
    _pause()


def defer_flow() -> None:
    print("\n═══ Defer to a Later Intake ═══")
    defer_applicant(_pick_applicant())
    _pause()


def defer_applicant(a: Applicant) -> None:
    if "Deferred" not in data.allowed_statuses(a.applicant_id):
        print(f"  ✗ {a.applicant_id} is {a.status}; only an offer can be "
              "deferred.")
        return
    nxt = cycles.next_cycle_name(a.intake_year or data.default_intake_year())
    to = _input("Defer to intake year", default=nxt, allow_empty=False)
    reason = _input("Reason")
    ok, out = _attempt(data.defer, a.applicant_id, to_intake=to,
                       reason=reason or None)
    if ok:
        print(f"  ✓ {a.applicant_id} deferred to {out.intake_year}")


def waitlist_flow() -> None:
    while True:
        print("\n═══ Waitlist ═══")
        wl = data.get_waitlist()
        if not wl:
            print("  (waitlist empty)")
        for i, a in enumerate(wl, 1):
            print(f"    {i:>2}) rank {a.waitlist_rank or '—':<3}  "
                  f"{a.applicant_id}  {a.full_name[:24]:<24}  "
                  f"{', '.join(a.subjects)[:30]}")
        print("\n    (u)p / (d)own <n>, (o)ffer <n>, (r)emove <n>, "
              "Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if cmd in ("u", "d") and idx is not None and 0 <= idx < len(wl):
            data.move_waitlist(wl[idx].applicant_id,
                                -1 if cmd == "u" else 1)
        elif cmd == "o" and idx is not None and 0 <= idx < len(wl):
            make_offer_for(wl[idx])
        elif cmd == "r" and idx is not None and 0 <= idx < len(wl):
            data.set_waitlist_rank(wl[idx].applicant_id, None)
        else:
            print("  ✗ Unrecognised action.")


def make_offer_for(a: Applicant) -> None:
    try:
        offer_type = _pick_from("Offer type", list(OFFER_TYPES),
                                 default=DEFAULT_OFFER_TYPE)
        conditions = _input("Conditions", default=a.offer_conditions or "")
        if offer_with_capacity_check(a.applicant_id, offer_type=offer_type,
                                     conditions=conditions or None):
            print(f"  ✓ Offer made to {a.applicant_id}")
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")


def decision_day_flow() -> None:
    print("\n═══ Decision Day (Interviewed queue) ═══")
    queue = data.list_applicants(status="Interviewed")
    if not queue:
        print("  No applicants awaiting a decision.")
        _pause()
        return
    for n, a in enumerate(queue, 1):
        a = data.get_applicant(a.applicant_id)
        if a is None:
            continue
        score = data.get_interview_score(a.applicant_id)
        print(f"\n  [{n}/{len(queue)}] {a.applicant_id} — {a.full_name}")
        print(f"      Subjects: {', '.join(a.subjects) or '—'}")
        print(f"      Predicted: {a.predicted_gcses or '—'}")
        if score:
            print(f"      Scorecard avg {score.average}  "
                  f"(rec: {score.recommendation or '—'})")
        print("      1) Make offer  2) Waitlist  3) Reject  "
              "4) Skip  0) Finish")
        choice = _input("  Decision", default="4")
        decided_by = ""
        try:
            if choice == "0":
                break
            if choice == "1":
                cond = _input("Conditions")
                decided_by = _input("Decided by")
                if offer_with_capacity_check(
                        a.applicant_id, conditions=cond or None,
                        decided_by=decided_by or None):
                    print("      ✓ Offer made.")
            elif choice == "2":
                data.set_status(a.applicant_id, "Waitlisted")
                data.set_waitlist_rank(a.applicant_id,
                                        len(data.get_waitlist()))
                print("      ✓ Waitlisted.")
            elif choice == "3":
                reason = _pick_from("Reason", list(DECISION_REASONS))
                data.record_decision(a.applicant_id, "Rejected",
                                      reason=reason)
                print("      ✓ Rejected.")
        except (ValidationError, _UserAbort) as e:
            print(f"      ✗ {e}")
    print("\n  Decision day complete.")
    _pause()


def expiring_offers_flow() -> None:
    print("\n═══ Expiring Offers ═══")
    try:
        days = int(_input("Within how many days?", default="7"))
    except (ValueError, _UserAbort):
        return
    rows = data.list_expiring_offers(within_days=days)
    if not rows:
        print(f"  No offers expiring within {days} days.")
    today = _date.today().isoformat()
    for a in rows:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"expires {a.offer_expiry}"
              + ("  (EXPIRED)" if (a.offer_expiry or "") < today else ""))
    if rows and _yes("\n  E-mail an expiry reminder to those not yet "
                     "expired (skips anyone warned recently)?"):
        ok, res = _attempt(comms.send_expiry_warnings, within_days=days)
        if ok:
            print(f"    Queued for {len(res['sent'])}, skipped "
                  f"{len(res['skipped'])} (warned in the last "
                  f"{comms.EXPIRY_WARNING_GAP_DAYS} days)")
            for err in res["errors"]:
                print(f"    ✗ {err}")
            print("    (Delivery depends on the outbox delivery mode — see "
                  "each applicant's communications log.)")
    _pause()


def reference_chase_all_flow() -> None:
    """Item 38 — chase every outstanding reference system-wide, through
    the reference tracker: unsent requests are e-mailed, sent ones chased."""
    print("\n═══ Chase All Outstanding References ═══")
    open_refs = refs.list_references(open_only=True)
    tracked = {r.applicant_id for r in refs.list_references()}
    legacy = [a for a in data.list_applicants(open_only=True)
              if a.applicant_id not in tracked and a.reference_contact
              and a.reference_status in ("Not requested", "Requested")]
    unsent = [r for r in open_refs if r.status == "Requested"]
    to_chase = [r for r in open_refs if r.status in ("Sent", "Chased")]
    print(f"  {len(unsent)} request(s) not yet sent, {len(to_chase)} sent "
          f"and awaiting reply, {len(legacy)} applicant(s) with a referee "
          "on the form but no tracked request.")
    if not (unsent or to_chase or legacy):
        print("  Nothing outstanding.")
        _pause()
        return
    if not _yes("E-mail the requests and reminders now?"):
        print("\n  Cancelled.")
        return
    for a in legacy:
        ok, r = _attempt(refs.adopt_legacy_reference, a.applicant_id)
        if ok:
            unsent.append(r)
    for r in unsent:
        ok, m = _attempt(comms.send_reference_request, r.reference_id)
        if ok:
            print(f"    request #{r.reference_id} {r.applicant_id} → "
                  f"{m.to_address}: {m.label}")
    for r in to_chase:
        ok, m = _attempt(comms.send_reference_chase, r.reference_id)
        if ok:
            print(f"    chase   #{r.reference_id} {r.applicant_id} → "
                  f"{m.to_address}: {m.label}")
    _pause()


def offers_flow() -> None:
    """Item 46 — pending offers with expiry alerts + quick decisions."""
    while True:
        print("\n═══ Pending Offers ═══")
        rows = data.list_applicants(status="Offer Made")
        if not rows:
            print("  (no pending offers)")
            _pause()
            return
        today = _date.today()
        for i, a in enumerate(rows, 1):
            left = "—"
            flag = ""
            if a.offer_expiry:
                try:
                    d = (_date.fromisoformat(a.offer_expiry[:10])
                         - today).days
                    left = str(d)
                    flag = "  ⚠" if d <= 7 else ""
                except ValueError:
                    pass
            print(f"    {i:>2}) {a.applicant_id}  {a.full_name[:22]:<22}  "
                  f"{a.offer_type or '—':<12} expires "
                  f"{a.offer_expiry or '—'} ({left}d){flag}")
        print("\n    (a)ccept <n>, (d)ecline <n>, (e)xpiry <n>, Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if idx is None or not (0 <= idx < len(rows)):
            print("  ✗ Give a row number, e.g. 'a 2'.")
            continue
        a = rows[idx]
        try:
            if cmd == "a":
                data.set_status(a.applicant_id, "Offer Accepted")
                print(f"  ✓ {a.applicant_id} accepted.")
            elif cmd == "d":
                reason = _pick_reason("Why did they decline?",
                                      data.WITHDRAWAL_REASONS)
                data.decline_offer(a.applicant_id, reason=reason)
                print(f"  ✓ {a.applicant_id} declined.")
            elif cmd == "e":
                new = _input("Expiry (YYYY-MM-DD, blank clears)",
                             default=a.offer_expiry or "")
                data.set_offer_expiry(a.applicant_id, new.strip() or None)
                print("  ✓ Expiry updated.")
            else:
                print("  ✗ Unrecognised action.")
        except _UserAbort:
            continue
        except ValidationError as e:
            print(f"  ✗ {e}")


def tasks_flow() -> None:
    """Item 47 — actionable worklist across the pipeline."""
    print("\n═══ Tasks ═══")
    apps = data.list_applicants()
    today = _date.today()

    def show(title: str, items: list[str]) -> None:
        print(f"\n  {title}  ({len(items)})")
        for line in items:
            print(f"      {line}")
        if not items:
            print("      (none)")

    refs = [f"{a.applicant_id}  {a.full_name} — reference "
            f"{a.reference_status}"
            for a in apps
            if a.reference_status in ("Not requested", "Requested")
            and a.is_open]
    follow = [f"{a.applicant_id}  {a.full_name} — [{a.status}]"
              for a in apps if a.follow_up]
    expiring = []
    for a in apps:
        if a.status == "Offer Made" and a.offer_expiry:
            try:
                d = (_date.fromisoformat(a.offer_expiry[:10]) - today).days
                if d <= 7:
                    expiring.append(f"{a.applicant_id}  {a.full_name} — "
                                    f"expires {a.offer_expiry} ({d}d)")
            except ValueError:
                pass
    awaiting = [f"{a.applicant_id}  {a.full_name}"
                for a in apps if a.status == "Interviewed"]
    unscheduled = [f"{a.applicant_id}  {a.full_name}"
                   for a in apps
                   if a.status == "Under Review" and not a.interview_date]
    show("Outstanding references", refs)
    show("Flagged for follow-up / no-show", follow)
    show("Offers expiring ≤7 days", expiring)
    show("Interviewed — awaiting decision", awaiting)
    show("Under review — no interview booked", unscheduled)
    total = len(refs) + len(follow) + len(expiring) + len(awaiting) \
        + len(unscheduled)
    print(f"\n  {total} open task(s).")
    _pause()


def waitlist_auto_promote_flow() -> None:
    """Item 48 — offer to the top-ranked waitlisted applicant."""
    print("\n═══ Auto-Promote Top of Waitlist ═══")
    rows = data.get_waitlist()
    if not rows:
        print("  The waitlist is empty.")
        _pause()
        return
    top = rows[0]
    if not _yes(f"A place has opened — make an offer to {top.applicant_id} "
                f"({top.full_name}, rank {top.waitlist_rank or 1})?"):
        print("\n  Cancelled.")
        return
    if offer_with_capacity_check(
            top.applicant_id, offer_type=DEFAULT_OFFER_TYPE,
            conditions="Promoted from waitlist.",
            decided_by=_cli_user()) is None:
        _pause()
        return
    ok, _ = _attempt(data.set_waitlist_rank, top.applicant_id, None)
    if not ok:
        _pause()
        return
    print(f"  ✓ Offer made to {top.applicant_id} and removed from waitlist.")
    _pause()
