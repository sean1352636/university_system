"""
Leave sub-menus: sickness absence, family leave, flexible working and
(HR) leave entitlements. Reached from ``leave_menu``; ``actor`` is the
signed-in person (the domain modules check what they may do).
"""

from education_system.systems.university.domains.staff.domain.staff_hr import (
    absence,
    access,
    entitlement,
    family_leave,
    flexible_working,
    leave_rules,
)


def _ask(label: str, default: str = '') -> str:
    value = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _yes(label: str) -> bool:
    return input(f"{label} (y/n): ").strip().lower() == 'y'


def _int(label: str):
    try:
        return int(input(f"{label}: ").strip())
    except ValueError:
        print("Please enter a number.")
        return None


def _pick(label: str, options) -> str:
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    try:
        n = int(input(f"{label}: ").strip())
        return options[n - 1] if 1 <= n <= len(options) else ''
    except ValueError:
        return ''


def _do(action, done: str = "Done.") -> None:
    try:
        action()
        print(f"\n{done}")
    except (PermissionError, ValueError) as e:
        print(f"\nNot done: {e}")
    input("Press Enter to continue...")


def _menu(title: str, options: list) -> str:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    for key, label in options:
        print(f"  {key}. {label}")
    print("\n  0. Return")
    return input("\nEnter choice: ").strip()


# ── absence ─────────────────────────────────────────────────────────────


def _list_episodes(actor) -> None:
    rows = absence.episodes(actor)
    print("\n" + "-" * 60)
    for e in rows:
        print(f"  [{e['episode_id']}] {e['name']}: {e['start_date']} to "
              f"{e['end_date'] or '(open)'} — {float(e['working_days'] or 0):g} days, "
              f"{e['reason_category']}, {e['certification']}, {e['status']}"
              + (", RTW held" if e['rtw'] else ""))
        if e['reason_detail']:
            print(f"        detail: {e['reason_detail']}")
    if not rows:
        print("  No absence recorded.")
    for item in absence.due_actions(actor):
        print(f"  ! {item['name']}: {item['detail']}")
    print("-" * 60)


def absence_menu(actor) -> None:
    me = access.username_of(actor)
    manager = access.can(actor, 'manager')
    hr = access.can(actor, 'hr')
    while True:
        options = [('1', 'View Absence'), ('2', 'Report Sickness'), ('3', 'Record Return'),
                   ('4', 'Add Fit Note'), ('5', 'Confirm Return-to-Work Record'),
                   ('6', 'Occupational Health Consent')]
        if manager:
            options += [('7', 'Return-to-Work Interview'), ('8', 'Trigger Alerts'),
                        ('9', 'Refer to Occupational Health'), ('10', 'Cancel Episode')]
        if hr:
            options += [('11', 'Book OH / Record OH Report / Close Referral')]
        choice = _menu("SICKNESS ABSENCE", options)
        if choice == '0':
            return
        if choice == '1':
            _list_episodes(actor)
            input("\nPress Enter to continue...")
        elif choice == '2':
            who = _ask("Person (username)", me) if manager else me
            start = _ask("First day off (YYYY-MM-DD)", leave_rules.today().isoformat())
            end = _ask("Last day off (blank if still off)")
            category = _pick("Reason category", absence.REASONS) or 'Other'
            detail = _ask("Medical detail (seen by HR and the person only)")
            _do(lambda: absence.record(actor, who, start, end or None, reason_category=category,
                                       reason_detail=detail or None), "Absence recorded.")
        elif choice == '3':
            ep = _int("Episode id")
            end = _ask("Last day of absence", leave_rules.today().isoformat())
            if ep:
                _do(lambda: absence.close(actor, ep, end), "Return recorded.")
        elif choice == '4':
            ep = _int("Episode id")
            if ep:
                issued = _ask("Issued on", leave_rules.today().isoformat())
                f, t = _ask("Covers from"), _ask("Covers to")
                may = _yes("'May be fit for work'?")
                adjustments = _ask("Suggested adjustments") if may else ''
                condition = _ask("Condition (HR and the person only)")
                _do(lambda: absence.add_fit_note(
                    actor, ep, issued, f, t, assessment='may_be_fit' if may else 'not_fit',
                    adjustments=adjustments or None, condition=condition or None),
                    "Fit note recorded.")
        elif choice == '5':
            ep = _int("Episode id")
            if ep:
                comments = _ask("Your comments")
                _do(lambda: absence.confirm_rtw(actor, ep, comments or None), "Confirmed.")
        elif choice == '6':
            for r in absence.referrals(actor, me):
                print(f"  [{r['referral_id']}] {r['reason']} — {r['status']}")
            ref = _int("Referral id")
            if ref:
                given = _yes("Do you consent")
                _do(lambda: absence.consent(actor, ref, given), "Recorded.")
        elif choice == '7' and manager:
            ep = _int("Episode id")
            if ep:
                day = _ask("Interview date", leave_rules.today().isoformat())
                fit = _yes("Fit to return?")
                adj = _ask("Adjustments agreed")
                support = _ask("Support offered")
                trig = _yes("Trigger points discussed?")
                oh = _yes("Recommend an occupational health referral?")
                _do(lambda: absence.record_rtw(actor, ep, day, fit_to_return=fit,
                                               adjustments_agreed=adj or None,
                                               support_offered=support or None,
                                               triggers_discussed=trig,
                                               oh_referral_recommended=oh),
                    "Interview recorded.")
        elif choice == '8' and manager:
            alerts = absence.alerts(actor)
            for a in alerts:
                print(f"  [{a['alert_id']}] {a['name']}: {a['trigger_kind']} {a['value']:g} "
                      f"(trigger {a['threshold']:g}) {a['window_start']} – {a['window_end']}")
            if not alerts:
                print("  No open alerts.")
            elif _yes("Review one now?"):
                aid = _int("Alert id")
                status = _pick("Outcome", ['reviewed', 'actioned', 'dismissed'])
                outcome = _ask("What was done")
                if aid and status:
                    _do(lambda: absence.review_alert(actor, aid, status, outcome), "Updated.")
                    continue
            input("\nPress Enter to continue...")
        elif choice == '9' and manager:
            who = _ask("Person (username)")
            reason = _ask("Reason for referral")
            questions = _ask("Questions for OH")
            _do(lambda: absence.refer(actor, who, reason, questions or None),
                "Referral made; awaiting their consent.")
        elif choice == '10' and manager:
            ep = _int("Episode id")
            if ep:
                reason = _ask("Why")
                _do(lambda: absence.cancel(actor, ep, reason), "Cancelled.")
        elif choice == '11' and hr:
            for r in absence.referrals(actor, open_only=True):
                print(f"  [{r['referral_id']}] {r['name']}: {r['status']}")
            ref = _int("Referral id")
            if not ref:
                continue
            what = _pick("Action", ['book appointment', 'record report', 'close'])
            if what == 'book appointment':
                provider, day = _ask("Provider"), _ask("Appointment date")
                _do(lambda: absence.book_oh(actor, ref, provider, day), "Booked.")
            elif what == 'record report':
                fitness = _pick("Fitness", list(absence.OH_FITNESS))
                adj = _ask("Recommended adjustments (shared with the manager)")
                outcome = _ask("Medical outcome (HR and the person only)")
                _do(lambda: absence.record_oh_report(actor, ref, fitness, adj or None,
                                                     outcome or None), "Report recorded.")
            elif what == 'close':
                _do(lambda: absence.close_referral(actor, ref), "Closed.")
        else:
            print("Invalid choice.")


# ── family leave ────────────────────────────────────────────────────────


def family_menu(actor) -> None:
    me = access.username_of(actor)
    manager = access.can(actor, 'manager')
    hr = access.can(actor, 'hr')
    while True:
        options = [('1', 'View Cases'), ('2', 'Notify Family Leave'), ('3', 'Cancel a Case')]
        if manager:
            options += [('4', 'Add KIT / SPLIT Day'), ('5', 'Record Return')]
        if hr:
            options += [('6', 'Update a Case (dates, earnings)'), ('7', 'Confirm a Case')]
        choice = _menu("FAMILY LEAVE", options)
        if choice == '0':
            return
        if choice == '1':
            for c in family_leave.cases(actor):
                print(f"\n  [{c['case_id']}] {c['name']} — {c['kind_label']} ({c['status']})")
                print(f"     EWC {c['ewc'] or '-'}, qualifying week {c['qualifying_week'] or '-'};"
                      f" leave {c['leave_start'] or '?'} to {c['leave_end'] or '?'}, "
                      f"return {c['return_date'] or '?'}")
                if not c.get('pay_hidden') and c['pay_schedule']:
                    total = sum(w['amount'] for w in c['pay_schedule'])
                    print(f"     {c['pay_name']}: {len(c['pay_schedule'])} weeks, £{total:,.2f}")
                if c['kit_limit']:
                    print(f"     KIT days: {len(c['kit_days'])}/{c['kit_limit']}")
                if c['eligibility_notes']:
                    print("     " + c['eligibility_notes'].replace('\n', '; '))
            input("\nPress Enter to continue...")
        elif choice == '2':
            who = _ask("Person (username)", me) if hr else me
            kind = _pick("Kind", list(family_leave.KINDS))
            if not kind:
                continue
            due = matching = ''
            if kind == 'adoption':
                matching = _ask("Matching date")
            else:
                due = _ask("Expected due date")
            start = _ask("Planned leave start")
            weeks = _ask("Weeks (blank = the most allowed)")
            used = _ask("Maternity / adoption weeks already used", '0') \
                if kind == 'shared_parental' else '0'
            _do(lambda: family_leave.notify(actor, who, kind, due_date=due or None,
                                            matching_date=matching or None,
                                            leave_start=start or None,
                                            leave_weeks=int(weeks) if weeks else None,
                                            statutory_weeks_used=int(used or 0)),
                "Family leave notified.")
        elif choice == '3':
            cid = _int("Case id")
            if cid:
                reason = _ask("Reason")
                _do(lambda: family_leave.cancel(actor, cid, reason), "Cancelled.")
        elif choice == '4' and manager:
            cid = _int("Case id")
            if cid:
                day = _ask("Day (YYYY-MM-DD)")
                _do(lambda: family_leave.add_kit_day(actor, cid, day), "KIT day recorded.")
        elif choice == '5' and manager:
            cid = _int("Case id")
            if cid:
                day = _ask("Back at work on", leave_rules.today().isoformat())
                _do(lambda: family_leave.record_return(actor, cid, day), "Return recorded.")
        elif choice == '6' and hr:
            cid = _int("Case id")
            if not cid:
                continue
            changes = {}
            for key in family_leave.EDITABLE:
                value = _ask(f"{key} (blank = unchanged)")
                if value:
                    changes[key] = (float(value) if key == 'average_weekly_earnings' else
                                    int(value) if key in ('leave_weeks', 'statutory_weeks_used')
                                    else value)
            if changes:
                _do(lambda: family_leave.update(actor, cid, **changes), "Updated.")
        elif choice == '7' and hr:
            cid = _int("Case id")
            if cid:
                _do(lambda: family_leave.confirm(actor, cid), "Confirmed and booked.")
        else:
            print("Invalid choice.")


# ── flexible working ────────────────────────────────────────────────────


def flexible_menu(actor) -> None:
    manager = access.can(actor, 'manager')
    while True:
        options = [('1', 'View Requests'), ('2', 'Make a Request'), ('3', 'Withdraw'),
                   ('4', 'Appeal a Refusal')]
        if manager:
            options += [('5', 'Requests to Decide'), ('6', 'Schedule Meeting'),
                        ('7', 'Record Consultation'), ('8', 'Decide'), ('9', 'Decide Appeal'),
                        ('10', 'Extend Deadline (agreed)')]
        choice = _menu("FLEXIBLE WORKING", options)
        if choice == '0':
            return
        if choice in ('1', '5'):
            rows = flexible_working.requests(actor, to_decide=choice == '5')
            for r in rows:
                print(f"\n  [{r['fw_id']}] {r['name']} — {r['requested_pattern']}")
                print(f"     {r['status']}; decide by {r['deadline']}"
                      + (" (OVERDUE)" if r['overdue'] else '')
                      + (f"; refused: {r['rejection_reason']}" if r['rejection_reason'] else ''))
            if not rows:
                print("  None.")
            input("\nPress Enter to continue...")
        elif choice == '2':
            pattern = _ask("Working pattern you are asking for")
            change = _pick("Kind of change", list(flexible_working.CHANGE_TYPES)) or 'other'
            days = _ask("New working days (0=Mon ... 6=Sun, e.g. 0,1,2,3; blank to skip)")
            hours = _ask("New hours a week (blank to skip)")
            start = _ask("From (YYYY-MM-DD)")
            until = _ask("Until (temporary only)")
            _do(lambda: flexible_working.submit(
                actor, pattern, change_type=change,
                requested_days=[int(d) for d in days.split(',') if d.strip().isdigit()] or None,
                requested_hours=float(hours) if hours else None, requested_start=start or None,
                temporary_until=until or None), "Request submitted.")
        elif choice == '3':
            fid = _int("Request id")
            if fid:
                _do(lambda: flexible_working.withdraw(actor, fid), "Withdrawn.")
        elif choice == '4':
            fid = _int("Request id")
            if fid:
                grounds = _ask("Grounds")
                _do(lambda: flexible_working.appeal(actor, fid, grounds), "Appeal made.")
        elif choice == '6' and manager:
            fid = _int("Request id")
            if fid:
                day = _ask("Meeting date")
                _do(lambda: flexible_working.schedule_meeting(actor, fid, day), "Arranged.")
        elif choice == '7' and manager:
            fid = _int("Request id")
            if fid:
                notes = _ask("What was discussed")
                _do(lambda: flexible_working.record_consultation(actor, fid, notes), "Recorded.")
        elif choice == '8' and manager:
            fid = _int("Request id")
            if not fid:
                continue
            outcome = _pick("Decision", list(flexible_working.OUTCOMES))
            reason = _pick("Statutory refusal reason", list(flexible_working.REFUSAL_REASONS)) \
                if outcome == 'rejected' else None
            notes = _ask("Explanation")
            trial = _ask("Trial ends") if outcome == 'approved_trial' else None
            _do(lambda: flexible_working.decide(actor, fid, outcome, notes=notes or None,
                                                refusal_reason=reason, trial_end=trial or None),
                "Decision recorded.")
        elif choice == '9' and manager:
            fid = _int("Request id")
            if fid:
                upheld = _yes("Uphold the appeal?")
                notes = _ask("Reasons")
                _do(lambda: flexible_working.decide_appeal(actor, fid, upheld, notes),
                    "Appeal decided.")
        elif choice == '10' and manager:
            fid = _int("Request id")
            if fid:
                day, note = _ask("New decision date"), _ask("How the person agreed")
                _do(lambda: flexible_working.extend(actor, fid, day, note), "Extended.")
        else:
            print("Invalid choice.")


# ── entitlements (HR) ───────────────────────────────────────────────────


def entitlements_menu(actor) -> None:
    while True:
        choice = _menu("LEAVE ENTITLEMENTS (HR)", [
            ('1', 'View Rules and Policy'), ('2', 'Edit a Rule (HR admin)'),
            ('3', 'Change a Policy Setting (HR admin)'), ('4', 'Allocate a Leave Year'),
            ('5', 'Set a Balance by Hand'), ('6', 'Set a Working Pattern'),
            ('7', 'Leaver Position'), ('8', 'Add / Remove a Closure Day')])
        if choice == '0':
            return
        if choice == '1':
            for r in entitlement.rules():
                print(f"  [{r['leave_type_id']}] {r['leave_type_name']}: "
                      f"{entitlement.BASIS_LABELS.get(r['basis'], r['basis'])}, "
                      f"{float(r['full_time_days'] or 0):g} days"
                      + (", carries over" if r['carry_over'] else ''))
            print()
            for key, value in leave_rules.settings().items():
                print(f"  {key} = {value}   ({leave_rules.DEFAULTS[key][1]})")
            input("\nPress Enter to continue...")
        elif choice == '2':
            tid = _int("Leave type id")
            if not tid:
                continue
            r = entitlement.rule_for(tid)
            basis = _pick("Basis", list(entitlement.BASES)) or r['basis']
            days = _ask("Full-time days", str(r['full_time_days'] or 0))
            carry = _yes("Carry over unused days?")
            cap = _ask("Carry-over cap (blank = policy setting)")
            _do(lambda: entitlement.set_rule(actor, tid, basis, float(days), carry,
                                             float(cap) if cap else None), "Rule saved.")
        elif choice == '3':
            key = _pick("Setting", list(leave_rules.DEFAULTS))
            if key:
                value = _ask("New value", str(leave_rules.setting(key)))
                _do(lambda: leave_rules.set_setting(actor, key, value), "Saved.")
        elif choice == '4':
            year = _ask("Leave year", str(leave_rules.leave_year_of()))
            force = _yes("Also recalculate balances set by hand?")
            try:
                r = entitlement.allocate_year(actor, int(year), force=force)
                print(f"\n{r['allocated']} balances for {r['people']} people "
                      f"({r['manual_kept']} set by hand kept).")
            except (PermissionError, ValueError) as e:
                print(f"\nNot done: {e}")
            input("Press Enter to continue...")
        elif choice == '5':
            who, tid = _ask("Person (username)"), _int("Leave type id")
            year = _ask("Leave year", str(leave_rules.leave_year_of()))
            days, carried = _ask("Allocated days"), _ask("Carried over", '0')
            note = _ask("Why")
            if tid:
                _do(lambda: entitlement.set_manual(actor, who, tid, int(year), float(days or 0),
                                                   float(carried or 0), note), "Balance set.")
        elif choice == '6':
            who = _ask("Person (username)")
            days = _ask("Working days (0=Mon ... 6=Sun)", '0,1,2,3,4')
            hours = _ask("Hours a week (blank to skip)")
            fte = _ask("FTE (blank = from hours)")
            _do(lambda: leave_rules.set_pattern(
                actor, who, [int(d) for d in days.split(',') if d.strip().isdigit()],
                float(hours) if hours else None, float(fte) if fte else None),
                "Pattern saved; allocate the leave year to apply it.")
        elif choice == '7':
            who, day = _ask("Person (username)"), _ask("Leaving date")
            try:
                for r in entitlement.leaver_position(actor, who, day or None):
                    print(f"  {r['leave_type_name']}: {r['position']:+g} days")
            except (PermissionError, ValueError) as e:
                print(f"\nNot done: {e}")
            input("Press Enter to continue...")
        elif choice == '8':
            day = _ask("Date (YYYY-MM-DD)")
            if _yes("Remove it (instead of adding)?"):
                _do(lambda: leave_rules.remove_closure(actor, day), "Removed.")
            else:
                name = _ask("Name", "University closure")
                _do(lambda: leave_rules.add_closure(actor, day, name), "Added.")
        else:
            print("Invalid choice.")


__all__ = ['absence_menu', 'family_menu', 'flexible_menu', 'entitlements_menu']
