"""CLI for bursary payments: schedules, payment runs, attendance holds,
the vulnerable bursary, evidence checks and discretionary policy rules.

Reached from the Bursary Applications menu (see ``bursaries_cli._MENU``).
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_bursary as rules,
    attendance_thresholds as thresholds,
)
from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
    bursaries as data,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


def _print_instalments(rows: list[data.Instalment]) -> None:
    names = {}
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    names = {s.student_id: s.full_name for s in students.list_students()}
    ui.table(("#", "Award", "Student", "Name", "Period", "Due", "Amount",
              "State", "Att %", "Note"),
             [(i.instalment_id, i.application_id, i.student_id,
               names.get(i.student_id, "?")[:20],
               f"{i.period_from}→{i.period_to}", i.due_date, ui.money(i.amount),
               i.state, "" if i.attendance_pct is None
               else f"{i.attendance_pct:.1f}", (i.note or "")[:30])
              for i in rows], empty="(no instalments)")


# ── Schedules ──────────────────────────────────────────────────────

@ui.handler
def set_schedule() -> None:
    app_id = ui.ask_int("Application #")
    app = data.get_application(app_id)
    if app is None:
        raise data.ValidationError(f"No application #{app_id}")
    print(f"  {app.student_id} · {app.bursary_type} · awarded "
          f"{ui.money(app.amount_awarded)} · {app.status}")
    freq = ui.pick("Frequency", list(data.PAYMENT_FREQUENCIES),
                   default=app.payment_frequency or data.DEFAULT_FREQUENCY)
    start = ui.ask("Start date (YYYY-MM-DD, blank = from the award)")
    end = ui.ask("End date (blank = 31 July)")
    inst = ui.ask_money("Fixed instalment amount (blank = split evenly)",
                        required=False)
    cond = True
    if app.bursary_type != data.VULNERABLE_TYPE:
        cond = ui.yes_no("Conditional on attendance?", default=True)
    made = data.set_payment_schedule(
        app_id, frequency=freq, start=start or None, end=end or None,
        instalment_amount=inst, attendance_conditional=cond)
    print(f"\n  ✓ {len(made)} instalment(s) scheduled.")
    _print_instalments(made)


@ui.handler
def regenerate_schedule() -> None:
    app_id = ui.ask_int("Application #")
    made = data.generate_schedule(app_id, regenerate=ui.yes_no(
        "Drop undecided instalments and rebuild?", default=False))
    print(f"\n  ✓ {len(made)} new instalment(s).")
    _print_instalments(made)


@ui.handler
def list_schedule() -> None:
    state = ui.pick("State", list(data.INSTALMENT_STATES), allow_none=True)
    sid = ui.ask("Student ID (blank = all)")
    _print_instalments(data.list_instalments(state=state,
                                             student_id=sid or None))


@ui.handler
def cancel_instalment() -> None:
    iid = ui.ask_int("Instalment #")
    data.cancel_instalment(iid, reason=ui.ask("Reason", required=True),
                           by=_who())
    print("\n  ✓ Cancelled.")


# ── Payment run ────────────────────────────────────────────────────

@ui.handler
def payment_run() -> None:
    as_of = ui.ask("Pay instalments due on or before",
                   default=_date.today().isoformat())
    raw = ui.ask("Attendance threshold % (blank = college setting "
                 f"{thresholds.value_of(thresholds.BURSARY_HOLD, default=85.0):g})")
    run = data.payment_run(as_of, threshold_pct=float(raw) if raw else None)
    ui.table(("#", "Student", "Name", "Type", "Period", "Amount", "Decision",
              "Reason"),
             [(i.instalment.instalment_id, i.instalment.student_id,
               i.student_name[:20], i.bursary_type[:18],
               f"{i.instalment.period_from}→{i.instalment.period_to}",
               ui.money(i.instalment.amount), i.decision, i.reason[:50])
              for i in run.items], empty="(nothing due)")
    print(f"\n  {run.summary}")
    if not run.items:
        return
    overrides: dict[int, str] = {}
    while ui.yes_no("Override any recommendation?", default=False):
        iid = ui.ask_int("Instalment #")
        overrides[iid] = ui.pick("Decision", [data.DECISION_PAY,
                                              data.DECISION_HOLD])
    choice = ui.pick("Commit", ["Pay and hold as shown",
                                "Pay only (leave holds for review)",
                                "Do not commit"])
    if choice == "Do not commit":
        return
    counts = data.commit_run(run, decided_by=_who(),
                             pay_only=choice.startswith("Pay only"),
                             overrides=overrides)
    print(f"\n  ✓ {counts['Pay']} paid, {counts['Hold']} held, "
          f"{counts['skipped']} left for review.")


# ── Holds ─────────────────────────────────────────────────────────

@ui.handler
def holds() -> None:
    held = data.held_instalments()
    _print_instalments(held)
    print(f"\n  {ui.money(sum(i.amount for i in held))} held across "
          f"{len(held)} instalment(s).")
    if not held:
        return
    action = ui.pick("Action", ["Release one", "Forfeit one",
                                "Release all whose attendance recovered",
                                "Nothing"])
    if action == "Release one":
        data.release_instalment(ui.ask_int("Instalment #"),
                                released_by=_who(),
                                note=ui.ask("Note") or None)
        print("\n  ✓ Released and paid.")
    elif action == "Forfeit one":
        iid = ui.ask_int("Instalment #")
        if ui.yes_no("Forfeiting writes the money off. Continue?"):
            data.forfeit_instalment(iid, reason=ui.ask("Reason",
                                                       required=True),
                                    by=_who())
            print("\n  ✓ Forfeited.")
    elif action.startswith("Release all"):
        d_from = ui.ask("Attendance window from (YYYY-MM-DD)", required=True)
        d_to = ui.ask("to", default=_date.today().isoformat())
        out = data.release_on_recovery(date_from=d_from, date_to=d_to,
                                       released_by=_who())
        print(f"\n  ✓ {len(out)} released.")


@ui.handler
def attendance_threshold() -> None:
    now = thresholds.value_of(thresholds.BURSARY_HOLD, default=85.0)
    print(f"\n  Bursary payments are held below {now:g}% attendance "
          "(unauthorised absence only).")
    raw = ui.ask("New threshold % (blank = keep)")
    if raw:
        thresholds.set_threshold(thresholds.BURSARY_HOLD, float(raw),
                                 actor=_who())
        print("\n  ✓ Threshold updated.")


@ui.handler
def exemptions() -> None:
    sid = ui.pick_student()
    rows = rules.list_exemptions(student_id=sid)
    ui.table(("#", "Reason", "From", "To", "Granted by", "Detail"),
             [(e.exemption_id, e.reason, e.start_date, e.end_date or "—",
               e.granted_by or "", e.detail or "") for e in rows],
             empty="(no exemptions)")
    action = ui.pick("Action", ["Add exemption", "Remove exemption",
                                "Nothing"])
    if action == "Add exemption":
        rules.add_exemption(
            sid, reason=ui.pick("Reason", list(rules.EXEMPTION_REASONS)),
            start_date=ui.ask("From", default=_date.today().isoformat()),
            end_date=ui.ask("To (blank = open)") or None,
            detail=ui.ask("Detail") or None, granted_by=_who())
        print("\n  ✓ Exemption added.")
    elif action == "Remove exemption":
        if rules.remove_exemption(ui.ask_int("Exemption #")):
            print("\n  ✓ Removed.")


# ── 16-19 fund: vulnerable, evidence, policy ──────────────────────

@ui.handler
def new_vulnerable() -> None:
    sid = ui.pick_student()
    cat = ui.pick("Vulnerable group (check current ESFA guidance)",
                  list(data.VULNERABLE_CATEGORIES))
    app = data.create_vulnerable_application(
        sid, category=cat, academic_year=ui.ask("Academic year",
                                                default="") or None,
        reason=ui.ask("Notes / reason") or None)
    print(f"\n  ✓ Application #{app.application_id} opened "
          "(Awaiting Evidence).")


@ui.handler
def verify_evidence() -> None:
    app_id = ui.ask_int("Application #")
    data.verify_evidence(app_id, verified_by=_who(),
                         evidence_type=ui.pick("Evidence seen",
                                               list(data.EVIDENCE_TYPES)),
                         note=ui.ask("Note") or None)
    print("\n  ✓ Evidence verified.")


@ui.handler
def award_vulnerable() -> None:
    app_id = ui.ask_int("Application #")
    amount = ui.ask_money(
        f"Amount (max {ui.money(data.VULNERABLE_MAX_AWARD)}; lower for "
        "pro-rata)", default=data.VULNERABLE_MAX_AWARD)
    freq = ui.pick("Pay", list(data.PAYMENT_FREQUENCIES),
                   default=data.DEFAULT_FREQUENCY)
    app = data.award_vulnerable(app_id, amount=amount, frequency=freq,
                                start=ui.ask("Start (blank = year start)")
                                or None)
    print(f"\n  ✓ Awarded {ui.money(app.amount_awarded)} "
          f"({app.payment_frequency}); "
          f"{len(data.list_instalments(application_id=app_id))} instalments.")


@ui.handler
def policy_rules() -> None:
    rows = data.list_rules()
    ui.table(("#", "Name", "Year", "Type", "Basis", "Max income", "Min hh",
              "Award", "Pay", "Att?", "Evid?", "Pri", "Active"),
             [(r.rule_id, r.name, r.academic_year or "any",
               r.bursary_type, r.eligibility_basis or "any",
               ui.money(r.max_household_income)
               if r.max_household_income is not None else "—",
               r.min_household_size or "—", ui.money(r.award_amount),
               r.payment_frequency, "Y" if r.attendance_conditional else "N",
               "Y" if r.requires_evidence else "N", r.priority,
               "Y" if r.active else "N") for r in rows],
             empty="(no policy rules yet)")
    action = ui.pick("Action", ["Add rule", "Edit rule", "Delete / retire rule",
                                "Nothing"])
    if action == "Add rule":
        data.create_rule(_rule_form({}))
        print("\n  ✓ Rule added.")
    elif action == "Edit rule":
        rid = ui.ask_int("Rule #")
        rule = data.get_rule(rid)
        if rule is None:
            raise data.ValidationError(f"No rule #{rid}")
        data.update_rule(rid, _rule_form(vars(rule)))
        print("\n  ✓ Rule updated.")
    elif action.startswith("Delete"):
        if data.delete_rule(ui.ask_int("Rule #")):
            print("\n  ✓ Done (rules already used are retired, not deleted).")


def _rule_form(cur: dict) -> dict:
    types = [t for t in data.BURSARY_TYPES if t != data.VULNERABLE_TYPE]
    return {
        "name": ui.ask("Name", default=cur.get("name") or "", required=True),
        "academic_year": ui.ask("Academic year (blank = any)",
                                default=cur.get("academic_year") or ""),
        "bursary_type": ui.pick("Bursary type", types,
                                default=cur.get("bursary_type")
                                or data.DISCRETIONARY_TYPE),
        "eligibility_basis": ui.pick("Eligibility basis",
                                     list(data.ELIGIBILITY_BASES),
                                     default=cur.get("eligibility_basis"),
                                     allow_none=True),
        "max_household_income": ui.ask_money(
            "Max household income (blank = no limit)",
            default=cur.get("max_household_income"), required=False),
        "min_household_size": ui.ask_int(
            "Min household size (blank = any)",
            default=cur.get("min_household_size"), required=False),
        "award_amount": ui.ask_money("Award amount",
                                     default=cur.get("award_amount")),
        "payment_frequency": ui.pick("Pay", list(data.PAYMENT_FREQUENCIES),
                                     default=cur.get("payment_frequency")
                                     or data.DEFAULT_FREQUENCY),
        "attendance_conditional": ui.yes_no(
            "Conditional on attendance?",
            default=cur.get("attendance_conditional", True)),
        "requires_evidence": ui.yes_no(
            "Evidence must be verified first?",
            default=cur.get("requires_evidence", True)),
        "priority": ui.ask_int("Priority (lower is tried first)",
                               default=cur.get("priority") or 100),
        "active": ui.yes_no("Active?", default=cur.get("active", True)),
        "notes": ui.ask("Notes", default=cur.get("notes") or ""),
    }


@ui.handler
def apply_policy() -> None:
    app_id = ui.ask_int("Application #")
    dec = data.evaluate_discretionary(app_id)
    for r in dec.reasons:
        print(f"    - {r}")
    if not dec.eligible:
        print("\n  Not eligible under the policy.")
        return
    print(f"\n  Policy award: {ui.money(dec.amount)} under "
          f"'{dec.rule.name}' ({dec.rule.payment_frequency})")
    if ui.yes_no("Approve and schedule it?", default=True):
        app = data.apply_discretionary_policy(app_id)
        print(f"\n  ✓ Approved {ui.money(app.amount_awarded)}.")


@ui.handler
def schedule_summary() -> None:
    s = data.schedule_summary()
    print(f"\n  Pending instalments : {s.pending} ({ui.money(s.pending_value)})")
    print(f"  Due now             : {s.due_now} ({ui.money(s.due_now_value)})")
    print(f"  Held                : {s.held} ({ui.money(s.held_value)})")
    print(f"  Paid                : {ui.money(s.paid_value)}")
    print(f"  Released            : {ui.money(s.released_value)}")
    print(f"  Forfeited           : {ui.money(s.forfeited_value)}")


MENU = [
    ("Payment Schedule — set for an award", set_schedule),
    ("Payment Schedule — rebuild", regenerate_schedule),
    ("Payment Schedule — list instalments", list_schedule),
    ("Payment Schedule — cancel an instalment", cancel_instalment),
    ("Payment Run (due payments, holds applied)", payment_run),
    ("Attendance Holds", holds),
    ("Attendance Threshold", attendance_threshold),
    ("Attendance Exemptions", exemptions),
    ("Vulnerable Bursary — new application", new_vulnerable),
    ("Verify Evidence", verify_evidence),
    ("Vulnerable Bursary — award", award_vulnerable),
    ("Discretionary Policy Rules", policy_rules),
    ("Apply Discretionary Policy", apply_policy),
    ("Payments Summary", schedule_summary),
]


def run() -> None:
    ui.menu("Bursary Payments & 16-19 Fund", MENU)
