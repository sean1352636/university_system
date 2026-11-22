"""Admissions CLI: insights — conversion by feeder school / programme /
cycle / source, time in stage, reasons, offers against places — each
exportable to CSV."""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions_insights as ins,
    cycles,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_from,
    _run_submenu,
    _yes,
)


def _cycle(optional: bool = True) -> str | None:
    names = [c.cycle for c in cycles.list_cycles()]
    if not names:
        return None if optional else _input("Cycle (e.g. 2026/27)",
                                            allow_empty=False)
    opts = (["(all cycles)"] if optional else []) + names
    cur = cycles.current_cycle()
    got = _pick_from("Cycle", opts,
                     default=cur if cur in names and not optional
                     else ("(all cycles)" if optional else None))
    return None if got == "(all cycles)" else got


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}%"


def _offer_csv(rows: list[Any], name: str) -> None:
    if rows and _yes("Save as CSV?"):
        path = _input("Path", default=f"{name}.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(ins.to_csv(rows))
        print(f"  ✓ Saved {len(rows)} row(s) to {path}")


def conversion_flow() -> None:
    dim = _pick_from("Group by", list(ins.DIMENSIONS), default="feeder_school")
    cycle = _cycle()
    rows = ins.conversion_by(dim, cycle=cycle)
    tot = ins.conversion_totals(cycle=cycle)
    print(f"\n═══ Conversion by {dim} ({cycle or 'all cycles'}) ═══")
    print(f"  {'Group':<30}{'Appl':>6}{'Offer':>7}{'Acc':>6}{'Enr':>6}"
          f"{'Offer%':>9}{'Acc%':>8}{'Enr%':>8}{'All%':>8}")
    for r in rows + [tot]:
        label = ("TOTAL" if r is tot else
                 r.group + (" *" if getattr(r, "is_feeder", False) else ""))
        print(f"  {label[:30]:<30}{r.applied:>6}{r.offered:>7}{r.accepted:>6}"
              f"{r.enrolled:>6}{_pct(r.offer_rate):>9}"
              f"{_pct(r.acceptance_rate):>8}{_pct(r.enrolment_rate):>8}"
              f"{_pct(r.overall_rate):>8}")
    if dim == "feeder_school":
        print("  * = feeder / partner school")
    _offer_csv(rows, f"conversion_by_{dim}")
    _pause()


def time_in_stage_flow() -> None:
    cycle = _cycle()
    rows = ins.time_in_stage(cycle=cycle)
    print(f"\n═══ Time in Stage ({cycle or 'all cycles'}) ═══")
    print(f"  {'Stage':<22}{'Passed':>8}{'Now':>6}{'Avg d':>8}{'Median':>8}"
          f"{'Longest':>9}")
    for r in rows:
        print(f"  {r.stage:<22}{r.applicants:>8}{r.current:>6}"
              f"{r.average_days if r.average_days is not None else '—':>8}"
              f"{r.median_days if r.median_days is not None else '—':>8}"
              f"{r.longest_days if r.longest_days is not None else '—':>9}")
    _offer_csv(rows, "time_in_stage")
    _pause()


def reasons_flow() -> None:
    cycle = _cycle()
    rows = ins.reasons_breakdown(cycle=cycle).rows()
    print(f"\n═══ Withdrawal / Decline / Rejection Reasons "
          f"({cycle or 'all cycles'}) ═══")
    for r in rows:
        print(f"  {r['outcome']:<15} {r['reason'][:44]:<44} {r['count']:>4}"
              f"  {_pct(r['share'])}")
    if not rows:
        print("  (no reasons recorded)")
    _offer_csv(rows, "reasons")
    _pause()


def offers_vs_capacity_flow() -> None:
    cycle = _cycle(optional=False)
    if not cycle:
        print("  No cycle.")
        return _pause()
    rows = ins.offers_vs_capacity(cycle)
    print(f"\n═══ Offers vs Places ({cycle}) ═══")
    print(f"  {'Programme':<32}{'Places':>7}{'Apps':>6}{'Offers':>8}{'Acc':>6}"
          f"{'Enr':>6}{'Left':>6}")
    for r in rows:
        print(f"  {r.programme[:32]:<32}"
              f"{r.places if r.places is not None else '—':>7}"
              f"{r.applications:>6}{r.offers_made:>8}{r.accepted:>6}"
              f"{r.enrolled:>6}"
              f"{r.places_left if r.places_left is not None else '—':>6}"
              + ("  OVERSUBSCRIBED" if r.oversubscribed else ""))
    _offer_csv(rows, "offers_vs_capacity")
    _pause()


MENU = [
    ("Conversion by feeder / programme / cycle / source", conversion_flow),
    ("Time in stage", time_in_stage_flow),
    ("Reasons (withdrawn / declined / rejected)", reasons_flow),
    ("Offers vs places", offers_vs_capacity_flow),
]


def run() -> None:
    _run_submenu("Admissions Insights", MENU)
