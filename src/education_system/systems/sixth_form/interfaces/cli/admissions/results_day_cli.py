"""CLI: GCSE results day — evaluate conditions, confirm / decline /
offer an alternative, dashboard."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    gcse_results_day as rd,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_from,
    _run_submenu,
    _UserAbort,
    _yes,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.entry_requirements_cli import (
    _user,
)


def dashboard_flow() -> None:
    d = rd.dashboard()
    print(f"\n═══ Results day {d.cycle} — {d.total} conditional offer(s) ═══")
    print("  Outcomes:  " + (", ".join(f"{k} {v}" for k, v in
                                        d.by_outcome.items()) or "—"))
    print("  Decisions: " + (", ".join(f"{k} {v}" for k, v in
                                        d.by_decision.items()) or "—"))
    print(f"  Awaiting results: {d.awaiting_results}   "
          f"awaiting decision: {d.awaiting_decision}")
    for r in d.rows:
        print(f"  {r.applicant_id:<10} {(r.applicant_name or '')[:24]:<24} "
              f"{r.outcome or '':<10} {r.decision or '':<22} "
              f"{r.outcome_detail or ''}")
    _pause()


def evaluate_all_flow() -> None:
    counts = rd.evaluate_all()
    print("\n  ✓ Evaluated: " + (", ".join(f"{k} {v}" for k, v in
                                          counts.items()) or "nobody"))
    _pause()


def _pick_row() -> str:
    rows = rd.dashboard().rows
    if not rows:
        print("    No applicants holding a conditional offer.")
        raise _UserAbort
    label = _pick_from("Applicant", [
        f"{r.applicant_id} {r.applicant_name or ''} [{r.outcome} / "
        f"{r.decision}]" for r in rows])
    return label.split()[0]


def _run(fn, *args, **kw) -> None:
    try:
        r = fn(*args, **kw)
        if r is not None:
            print(f"  ✓ {r.applicant_id}: {r.outcome} → {r.decision}")
        else:
            print("  ✓ Done")
    except ValueError as e:
        print(f"  ✗ {e}")
    _pause()


def evaluate_one_flow() -> None:
    _run(rd.evaluate_applicant, _pick_row())


def confirm_flow() -> None:
    aid = _pick_row()
    row = rd.get_row(aid)
    near = bool(row and row.outcome == "Near miss")
    if near and not _yes("Near miss — confirm the place anyway?"):
        return
    _run(rd.confirm, aid, by=_user(), allow_near_miss=near,
         notes=_input("Notes", default="") or None)


def decline_flow() -> None:
    aid = _pick_row()
    if _yes(f"Decline {aid} (offer conditions not met)?"):
        _run(rd.decline, aid, by=_user(),
             notes=_input("Notes", default="") or None)


def alternative_flow() -> None:
    aid = _pick_row()
    print("  Alternative programme, one choice per line as "
          "'Qualification: Subject' (blank line ends).")
    choices = []
    while True:
        line = _input("Choice", default="")
        if not line:
            break
        q, _, s = line.partition(":")
        choices.append({"qualification_type": q.strip() if s else "A Level",
                        "subject": (s or q).strip()})
    if choices:
        _run(rd.offer_alternative, aid, choices=choices, by=_user(),
             notes=_input("Notes", default="") or None)


def reset_flow() -> None:
    aid = _pick_row()
    if _yes(f"Reset the results-day decision for {aid}?"):
        _run(rd.reset_decision, aid)


def live_offers_flow() -> None:
    """Applicants holding a live conditional offer now (not archived,
    merged, closed or enrolled)."""
    year = _input("Intake year (blank = all)") or None
    rows = rd.conditional_applicants(intake_year=year)
    print(f"\n═══ Live Conditional Offers ({year or 'all intakes'}) — "
          f"{len(rows)} ═══")
    for a in rows:
        print(f"  {a.applicant_id:<10} {a.full_name[:24]:<24} [{a.status}] "
              f"{a.intake_year or '—'}  {a.offer_conditions or ''}")
    _pause()


MENU = [
    ("Dashboard", dashboard_flow),
    ("Evaluate everyone against actual results", evaluate_all_flow),
    ("Evaluate one applicant", evaluate_one_flow),
    ("─" * 6, lambda: None),
    ("Confirm place (Met / near miss)", confirm_flow),
    ("Decline (conditions not met)", decline_flow),
    ("Offer an alternative programme", alternative_flow),
    ("Reset a decision", reset_flow),
    ("─" * 6, lambda: None),
    ("Live conditional offers", live_offers_flow),
]


def run() -> None:
    _run_submenu("GCSE Results Day", MENU)
