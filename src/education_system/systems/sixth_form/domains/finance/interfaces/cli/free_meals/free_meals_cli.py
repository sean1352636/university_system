"""CLI for 16-19 free meals: entitlements, the daily log and the
monthly claim. Reached from the Bursary Applications menu."""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
    free_meals as fm,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


def _print_entitlements(rows: list[fm.Entitlement]) -> None:
    ui.table(("#", "Student", "Year", "Basis", "From", "To", "Daily",
              "Status", "Evidence"),
             [(e.entitlement_id, e.student_id, e.academic_year or "",
               e.eligibility_basis[:28], e.start_date, e.end_date or "—",
               ui.money(e.daily_allowance), e.status,
               f"verified by {e.evidence_verified_by}"
               if e.evidence_verified else "NOT verified")
              for e in rows], empty="(no entitlements)")


@ui.handler
def allowance() -> None:
    now = fm.get_default_allowance()
    print(f"\n  College daily allowance: "
          f"{ui.money(now) if now is not None else 'not set'}")
    print("  (Set this from the current ESFA free-meals funding rate.)")
    new = ui.ask_money("New allowance (blank = keep)", required=False)
    if new is not None:
        fm.set_default_allowance(new, by=_who())
        print("\n  ✓ Allowance updated.")


@ui.handler
def list_entitlements() -> None:
    choice = ui.pick("Show", ["Active today", "All", "One student"])
    if choice == "Active today":
        rows = fm.list_entitlements(active_on=_date.today().isoformat())
    elif choice == "One student":
        rows = fm.list_entitlements(student_id=ui.pick_student())
    else:
        rows = fm.list_entitlements()
    _print_entitlements(rows)


@ui.handler
def add_entitlement() -> None:
    sid = ui.pick_student()
    d = {
        "student_id": sid,
        "eligibility_basis": ui.pick("Eligibility (check current ESFA "
                                     "guidance)", list(fm.ELIGIBILITY_BASES)),
        "start_date": ui.ask("Start", default=_date.today().isoformat()),
        "end_date": ui.ask("End (blank = end of academic year)") or None,
        "daily_allowance": ui.ask_money("Daily allowance (blank = college "
                                        "default)", required=False),
        "notes": ui.ask("Notes") or None,
    }
    if ui.yes_no("Evidence seen now?", default=False):
        d["evidence_type"] = ui.pick("Evidence", list(fm.EVIDENCE_TYPES))
        d["evidence_reference"] = ui.ask("Reference") or None
        d["evidence_verified_by"] = _who()
    ent = fm.create_entitlement(d)
    print(f"\n  ✓ Entitlement #{ent.entitlement_id} "
          f"{ent.start_date}→{ent.end_date}.")


@ui.handler
def verify_evidence() -> None:
    eid = ui.ask_int("Entitlement #")
    fm.verify_evidence(eid, verified_by=_who(),
                       evidence_type=ui.pick("Evidence",
                                             list(fm.EVIDENCE_TYPES)),
                       reference=ui.ask("Reference") or None)
    print("\n  ✓ Evidence verified.")


@ui.handler
def edit_entitlement() -> None:
    eid = ui.ask_int("Entitlement #")
    e = fm.get_entitlement(eid)
    if e is None:
        raise fm.ValidationError(f"No entitlement #{eid}")
    fm.update_entitlement(eid, {
        "eligibility_basis": ui.pick("Eligibility", list(fm.ELIGIBILITY_BASES),
                                     default=e.eligibility_basis),
        "start_date": ui.ask("Start", default=e.start_date),
        "end_date": ui.ask("End", default=e.end_date or "") or None,
        "daily_allowance": ui.ask_money("Daily allowance",
                                        default=e.daily_allowance),
        "status": ui.pick("Status", list(fm.ENTITLEMENT_STATUSES),
                          default=e.status),
        "notes": ui.ask("Notes", default=e.notes or "") or None,
    })
    print("\n  ✓ Updated.")


@ui.handler
def end_entitlement() -> None:
    eid = ui.ask_int("Entitlement #")
    fm.end_entitlement(eid, on=ui.ask("End on",
                                      default=_date.today().isoformat()),
                       reason=ui.ask("Reason") or None)
    print("\n  ✓ Ended.")


@ui.handler
def record_day() -> None:
    day = ui.ask("Date", default=_date.today().isoformat())
    sheet = fm.day_sheet(day)
    if not sheet:
        print("\n  Nobody is entitled on that day.")
        return
    ui.table(("Student", "Daily", "Recorded"),
             [(e.student_id, ui.money(e.daily_allowance),
               "—" if u is None else ("taken" if u.taken else "not taken"))
              for e, u in sheet])
    raw = ui.ask("IDs who took a meal (comma separated, '*' = everyone)")
    ids = ({e.student_id for e, _u in sheet} if raw.strip() == "*"
           else {x.strip() for x in raw.split(",") if x.strip()})
    counts = fm.record_day(day, taken_ids=ids, recorded_by=_who())
    print(f"\n  ✓ {counts['taken']} taken, {counts['not_taken']} not taken.")


@ui.handler
def record_one() -> None:
    sid = ui.pick_student()
    u = fm.record_usage(sid, ui.ask("Date",
                                    default=_date.today().isoformat()),
                        taken=ui.yes_no("Meal taken?", default=True),
                        recorded_by=_who(), note=ui.ask("Note") or None)
    print(f"\n  ✓ Recorded ({ui.money(u.amount)}).")


@ui.handler
def usage_log() -> None:
    sid = ui.ask("Student ID (blank = all)") or None
    d_from = ui.ask("From", default=_date.today().replace(day=1).isoformat())
    d_to = ui.ask("To", default=_date.today().isoformat())
    rows = fm.list_usage(student_id=sid, date_from=d_from, date_to=d_to)
    ui.table(("Date", "Student", "Taken", "Amount", "By", "Note"),
             [(u.meal_date, u.student_id, "Y" if u.taken else "N",
               ui.money(u.amount), u.recorded_by or "", u.note or "")
              for u in rows], empty="(no meals recorded)")


@ui.handler
def monthly_claim() -> None:
    month = ui.ask("Month (YYYY-MM)", default=_date.today().strftime("%Y-%m"))
    rep = fm.monthly_claim(month)
    ui.table(("Student", "Name", "Daily", "Eligible", "Taken", "Not taken",
              "Unrecorded", "Claim"),
             [(l.student_id, l.student_name[:22], ui.money(l.daily_allowance),
               l.eligible_days, l.taken_days, l.not_taken_days,
               l.unrecorded_days, ui.money(l.value_claimed))
              for l in rep.lines], empty="(no entitlements in that month)")
    take = "—" if rep.take_up_pct is None else f"{rep.take_up_pct:.1f}%"
    print(f"\n  {rep.learners} learners · {rep.meals_taken} meals · take-up "
          f"{take} · claim {ui.money(rep.total_claimed)}")
    if rep.unrecorded_days:
        print(f"  ! {rep.unrecorded_days} college day(s) not yet recorded.")
    if rep.lines and ui.yes_no("Export to CSV?", default=False):
        print(f"\n  ✓ Written to {fm.export_claim_csv(month)}")


MENU = [
    ("Daily Allowance", allowance),
    ("List Entitlements", list_entitlements),
    ("Add Entitlement", add_entitlement),
    ("Verify Evidence", verify_evidence),
    ("Edit Entitlement", edit_entitlement),
    ("End Entitlement", end_entitlement),
    ("Record a Day's Meals", record_day),
    ("Record One Meal", record_one),
    ("Meal Log", usage_log),
    ("Monthly Claim Report", monthly_claim),
]


def run() -> None:
    ui.menu("Free Meals (16-19)", MENU)
