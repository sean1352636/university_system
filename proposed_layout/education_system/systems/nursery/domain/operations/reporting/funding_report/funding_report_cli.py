"""CLI flow for the Funding Report (Nursery System).

Prints the entitlement breakdown (over active funded-hours records), a claims
summary (totals + by-status) and the claims detail table, and offers a CSV
export. Read-only.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery.domain.operations.reporting.funding_report import (
    funding_report as data,
)

logger = logging.getLogger(__name__)


def _money(amount: float) -> str:
    return f"£{amount:,.2f}"


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_report() -> None:
    ents = data.entitlement_breakdown()
    cs = data.claims_summary()
    claims = data.list_claims()
    s = data.summary()

    print("\n═══ Funding Report ═══")

    # (a) entitlement breakdown
    print("\n  Entitlement breakdown (active funded-hours records)")
    print(f"  {'Entitlement':<28} {'Children':>8} {'Funded h/pw':>12} "
          f"{'Add. h/pw':>10}")
    print("  " + "-" * 62)
    for e in ents:
        print(f"  {e.entitlement[:28]:<28} {e.children:>8} "
              f"{e.funded_hours_pw_total:>12.1f} "
              f"{e.additional_hours_total:>10.1f}")
    print("  " + "-" * 62)
    print(f"  Funded children: {s['active_funded_children']}   "
          f"Funded h/pw: {s['total_funded_hours_pw']:.1f}   "
          f"Additional h/pw: {s['total_additional_hours_pw']:.1f}")

    # (b) claims summary
    print("\n  Claims summary")
    print(f"  Total claims: {s['claims_count']}   "
          f"Total: {_money(s['total_claim_amount'])}   "
          f"Submitted: {_money(s['submitted_amount'])}   "
          f"Draft: {_money(s['draft_amount'])}")
    by_status = cs["by_status"]
    for status in sorted(by_status):
        v = by_status[status]
        print(f"    {status:<12} {v['count']:>4} claim(s)   "
              f"{_money(v['amount'])}")

    # (c) claims detail
    print("\n  Claims detail")
    print(f"  {'Child':<20} {'Period':<12} {'Entitlement':<16} {'Hrs':>5} "
          f"{'Wks':>4} {'Rate':>7} {'Amount':>11}  Status")
    print("  " + "-" * 92)
    for c in claims:
        print(f"  {c.pupil_name[:20]:<20} {(c.funding_period or '-')[:12]:<12} "
              f"{(c.entitlement or '-')[:16]:<16} {c.funded_hours:>5.1f} "
              f"{c.weeks:>4.0f} {c.hourly_rate:>7.2f} "
              f"{_money(c.claim_amount):>11}  {c.status}")
    print("  " + "-" * 92)


def _export() -> None:
    try:
        raw = input("\n  Export CSV to path (blank = data dir): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    try:
        res = data.export_csv(raw or None)
        print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except OSError as e:
        print(f"  ✗ {e}")


def run(auth=None) -> None:
    """Entry point for the Funding Report CLI screen."""
    while True:
        try:
            _print_report()
        except Exception as e:  # noqa: BLE001
            logger.exception("Funding report failed")
            print(f"\n  ✗ Could not build report: {e}")
            _pause()
            return
        print("\n   1) Export to CSV    0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "1":
            _export()
            _pause()
        elif choice == "0" or choice == "":
            return
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Funding Report":
        return False
    run()
    return True
