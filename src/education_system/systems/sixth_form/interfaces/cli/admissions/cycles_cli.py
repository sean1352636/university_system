"""Admissions CLI: admissions cycles, places (capacity), oversubscription
criteria, feeder schools and ranking."""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    capacity,
    cycles,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _attempt,
    _input,
    _pause,
    _pick_from,
    _run_submenu,
    _yes,
)


def _pick_cycle(label: str = "Cycle", *, include_archived: bool = True
                ) -> str:
    rows = cycles.list_cycles(include_archived=include_archived)
    if not rows:
        print("    No cycles set up — create one first.")
        raise _UserAbort
    cur = cycles.current_cycle()
    labels = [f"{c.cycle} [{c.status}]" for c in rows]
    default = next((x for x in labels if x.startswith(f"{cur} ")), None)
    return _pick_from(label, labels, default=default).split()[0]


def _cycle_line(c: cycles.Cycle) -> str:
    return (f"{c.cycle:<8} [{c.status:<8}] {c.opens_on} → {c.closes_on}  "
            f"interviews {c.interview_from or '—'}–{c.interview_to or '—'}  "
            f"respond {c.offer_response_days or '—'}d  results "
            f"{c.results_day or '—'}  enrol {c.enrolment_start or '—'}")


# ── Cycles ─────────────────────────────────────────────────────────

def list_cycles_flow() -> None:
    print("\n═══ Admissions Cycles ═══")
    print(f"  Current: {cycles.current_cycle() or '—'}   taking applications "
          f"today: {cycles.open_cycle_for() or '—'}")
    rows = cycles.list_cycles()
    for c in rows:
        n = len(cycles.applications_in_cycle(c.cycle))
        print(f"  {_cycle_line(c)}  ({n} applications)")
    if not rows:
        print("  (none)")
    _pause()


def _cycle_fields(c: cycles.Cycle | None = None) -> dict[str, Any]:
    def ask(label: str, attr: str) -> str | None:
        return _input(label, default=str(getattr(c, attr) or "") if c else ""
                      ) or None
    out = {
        "opens_on": ask("Applications open (YYYY-MM-DD)", "opens_on"),
        "closes_on": ask("Applications close (YYYY-MM-DD)", "closes_on"),
        "interview_from": ask("Interviews from", "interview_from"),
        "interview_to": ask("Interviews to", "interview_to"),
        "offer_response_days": ask("Days to respond to an offer",
                                   "offer_response_days"),
        "results_day": ask("GCSE results day", "results_day"),
        "enrolment_start": ask("Enrolment starts", "enrolment_start"),
        "notes": ask("Notes", "notes"),
    }
    return out


def create_cycle_flow() -> None:
    print("\n═══ New Admissions Cycle ═══")
    last = cycles.list_cycles()
    default = cycles.next_cycle_name(last[0].cycle) if last else \
        data.default_intake_year()
    name = _input("Cycle (intake year, e.g. 2027/28)", default=default,
                  allow_empty=False)
    ok, c = _attempt(cycles.create_cycle, name, **_cycle_fields())
    if ok:
        print(f"  ✓ {c.cycle} created [{c.status}] — open it when ready")
    _pause()


def edit_cycle_flow() -> None:
    c = cycles.get_cycle(_pick_cycle())
    ok, c2 = _attempt(cycles.update_cycle, c.cycle, **_cycle_fields(c))
    if ok:
        print("  ✓ " + _cycle_line(c2))
    _pause()


def cycle_status_flow() -> None:
    c = cycles.get_cycle(_pick_cycle())
    new = _pick_from(f"{c.cycle} is {c.status} — move to",
                     [s for s in cycles.CYCLE_STATUSES if s != c.status])
    ok, c2 = _attempt(cycles.set_cycle_status, c.cycle, new)
    if ok:
        print(f"  ✓ {c2.cycle} → {c2.status}")
    _pause()


def delete_cycle_flow() -> None:
    c = _pick_cycle()
    if _yes(f"Delete cycle {c} (only a Planned one with no applications)?"):
        ok, _ = _attempt(cycles.delete_cycle, c)
        if ok:
            print("  ✓ Deleted")
    _pause()


def rollover_report_flow() -> None:
    frm = _pick_cycle("From cycle")
    to = _input("To cycle", default=cycles.next_cycle_name(frm))
    ok, rep = _attempt(cycles.rollover_report, frm, to)
    if ok:
        print()
        for line in rep.lines():
            print("  " + line)
    _pause()


def duplicates_flow() -> None:
    c = _pick_cycle()
    groups = cycles.duplicate_applications(c)
    print(f"\n═══ Possible duplicate applications in {c} ═══")
    for g in groups:
        print("  • " + "  |  ".join(
            f"{a.applicant_id} {a.full_name} [{a.status}]" for a in g))
    if not groups:
        print("  (none)")
    else:
        print("\n  Merge them under Applicants → Bulk & selection → Merge "
              "duplicates.")
    _pause()


def reapplications_flow() -> None:
    c = _pick_cycle()
    rows = [a for a in cycles.applications_in_cycle(c)
            if cycles.reapplied_from(a.applicant_id)]
    print(f"\n═══ Re-applications in {c} ═══")
    for a in rows:
        print(f"  {a.applicant_id} {a.full_name} [{a.status}] ← "
              f"{cycles.reapplied_from(a.applicant_id)}")
    if not rows:
        print("  (none)")
    _pause()


def lapsed_offers_flow() -> None:
    rows = cycles.lapsed_offers()
    print("\n═══ Lapsed Offers (expired, no answer) ═══")
    for a in rows:
        print(f"  {a.applicant_id} {a.full_name:<24} expired {a.offer_expiry}")
    if not rows:
        print("  (none)")
        _pause()
        return
    if _yes(f"Withdraw these {len(rows)} with reason "
            f"'{cycles.LAPSE_REASON}'?"):
        ok, res = _attempt(cycles.lapse_expired_offers)
        if ok:
            done, errors = res
            print(f"  ✓ Lapsed {len(done)}")
            for e in errors:
                print(f"  ✗ {e}")
    _pause()


# ── Places, criteria, ranking ──────────────────────────────────────

def _pick_programme(cycle: str) -> tuple[str, str]:
    rows = capacity.programme_places(cycle)
    labels = [p.label for p in rows] + ["(type one)"]
    got = _pick_from("Programme", labels)
    if got == "(type one)":
        q = _pick_from("Qualification", list(data.programme_types()),
                       default="A Level")
        return q, _input("Subject", allow_empty=False)
    p = rows[labels.index(got)]
    return p.qualification_type, p.subject


def places_flow() -> None:
    c = _pick_cycle()
    print(f"\n═══ Places — {c} ═══")
    print(f"  {'Programme':<34}{'Places':>7}{'Held':>6}{'Left':>6}"
          f"{'Competing':>11}")
    for p in capacity.programme_places(c):
        left = p.places_left
        print(f"  {p.label[:34]:<34}{p.places if p.places is not None else '—':>7}"
              f"{p.held:>6}{left if left is not None else '—':>6}"
              f"{p.competing:>11}"
              + ("  FULL" if p.is_full else "")
              + ("  oversubscribed" if p.oversubscribed else ""))
    _pause()


def set_places_flow() -> None:
    c = _pick_cycle()
    prog = _pick_programme(c)
    cur = capacity.get_programme_places(c, prog)
    raw = _input("Places (blank removes the limit)",
                 default=str(cur.places) if cur.places is not None else "")
    ok, _ = _attempt(capacity.set_places, c, prog,
                     int(raw) if raw.isdigit() else None,
                     notes=_input("Notes", default=cur.notes or "") or None)
    if ok:
        print("  ✓ Saved")
    _pause()


def criteria_flow() -> None:
    while True:
        rows = capacity.list_criteria()
        print("\n═══ Oversubscription Criteria (highest first) ═══")
        for i, cr in enumerate(rows, 1):
            print(f"    {i}) {'[on] ' if cr.enabled else '[off]'} {cr.label}"
                  + ("" if cr.available else f"  — {cr.notes}"))
        cmd = _input("  (t)oggle <n>, (u)p <n>, (d)own <n>, Enter) back",
                     default="")
        if not cmd:
            return
        parts = cmd.split()
        if len(parts) < 2 or not parts[1].isdigit() or not (
                1 <= int(parts[1]) <= len(rows)):
            print("  ✗ Give a number, e.g. 'u 3'.")
            continue
        i = int(parts[1]) - 1
        if parts[0].lower() == "t":
            _attempt(capacity.set_criterion_enabled, rows[i].key,
                     not rows[i].enabled)
        elif parts[0].lower() in ("u", "d"):
            j = i - 1 if parts[0].lower() == "u" else i + 1
            if 0 <= j < len(rows):
                keys = [r.key for r in rows]
                keys[i], keys[j] = keys[j], keys[i]
                _attempt(capacity.set_criteria_order, keys)


def ranking_flow() -> None:
    c = _pick_cycle()
    prog = _pick_programme(c)
    holders = _yes("Include applicants already holding a place?")
    ok, rows = _attempt(capacity.rank_applicants, c, prog,
                        include_holders=holders)
    if ok:
        print(f"\n═══ Ranking — {capacity.programme_label(*prog)} ({c}) ═══")
        for r in rows:
            print(f"  {r.position:>3}. {r.applicant_id} {r.name[:24]:<24} "
                  f"[{r.status}]{' (holds place)' if r.holds_place else ''}"
                  f"  {r.reasons}")
        if not rows:
            print("  (no applicants)")
    _pause()


# ── Feeder schools ─────────────────────────────────────────────────

def feeder_schools_flow() -> None:
    while True:
        rows = capacity.list_feeder_schools(include_inactive=True)
        print("\n═══ Feeder Schools ═══")
        for i, f in enumerate(rows, 1):
            print(f"    {i}) {f.name:<32} URN {f.urn or '—':<8} "
                  f"{'partner' if f.partner else '':<8}"
                  f"{'guaranteed-place' if f.guaranteed_place_scheme else '':<17}"
                  f"{'' if f.active else '(inactive)'}")
        if not rows:
            print("    (none)")
        cmd = _input("  (a)dd, (e)dit <n>, (r)emove <n>, Enter) back",
                     default="")
        if not cmd:
            return
        parts = cmd.split()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        try:
            if parts[0].lower() == "a":
                ok, f = _attempt(
                    capacity.add_feeder_school,
                    _input("School name", allow_empty=False),
                    partner=_yes("Partner school?", default="y"),
                    guaranteed_place_scheme=_yes("Guaranteed-place scheme?"),
                    urn=_input("URN") or None, notes=_input("Notes") or None)
                if ok:
                    print(f"  ✓ Added {f.name}")
            elif idx is not None and 0 <= idx < len(rows):
                f = rows[idx]
                if parts[0].lower() == "e":
                    ok, _ = _attempt(
                        capacity.update_feeder_school, f.school_id,
                        name=_input("Name", default=f.name),
                        urn=_input("URN", default=f.urn or "") or None,
                        partner=_yes("Partner?",
                                     default="y" if f.partner else "n"),
                        guaranteed_place_scheme=_yes(
                            "Guaranteed-place scheme?",
                            default="y" if f.guaranteed_place_scheme else "n"),
                        active=_yes("Active?",
                                    default="y" if f.active else "n"),
                        notes=_input("Notes", default=f.notes or "") or None)
                    if ok:
                        print("  ✓ Updated")
                elif parts[0].lower() == "r" and _yes(
                        f"Mark {f.name} inactive?"):
                    _attempt(capacity.remove_feeder_school, f.school_id)
            else:
                print("  ✗ Unrecognised action.")
        except _UserAbort:
            continue


def apply_feeder_rules_flow() -> None:
    c = _pick_cycle()
    ok, changed = _attempt(capacity.apply_feeder_rules_all, c)
    if ok:
        print(f"  ✓ Guaranteed-place flag set on {len(changed)} application(s)"
              + (f": {', '.join(changed)}" if changed else ""))
    _pause()


MENU = [
    ("List cycles", list_cycles_flow),
    ("New cycle", create_cycle_flow),
    ("Edit cycle dates", edit_cycle_flow),
    ("Change cycle status (Planned/Open/Closed/Archived)", cycle_status_flow),
    ("Delete a planned cycle", delete_cycle_flow),
    ("Rollover report", rollover_report_flow),
    ("Duplicate applications in a cycle", duplicates_flow),
    ("Re-applications in a cycle", reapplications_flow),
    ("Lapsed offers (withdraw)", lapsed_offers_flow),
    ("─" * 6, lambda: None),
    ("Places by programme", places_flow),
    ("Set places for a programme", set_places_flow),
    ("Oversubscription criteria", criteria_flow),
    ("Rank applicants for a programme", ranking_flow),
    ("─" * 6, lambda: None),
    ("Feeder schools", feeder_schools_flow),
    ("Apply feeder-school rules to a cycle", apply_feeder_rules_flow),
]


def run() -> None:
    _run_submenu("Cycles, Places & Criteria", MENU)
