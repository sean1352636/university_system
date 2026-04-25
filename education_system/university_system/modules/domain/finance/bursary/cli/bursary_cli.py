"""Console menu for the bursary module — mirrors employer_portal_cli style."""
from __future__ import annotations

from typing import Any

from education_system.university_system.modules.domain.finance.bursary.services.bursary_service import (
    BursaryService,
    BursaryError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access bursary management.")
        return False
    return True


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------

def _create_fund(svc: BursaryService) -> None:
    name = input("Fund name: ").strip()
    if not name:
        print("Error: fund name is required.")
        return
    ftype = input(
        "Type (hardship/maintenance/scholarship/emergency, default=hardship): "
    ).strip() or "hardship"
    try:
        budget = float(input("Total budget: ").strip() or 0)
        fid = svc.create_fund(name, fund_type=ftype, total_budget=budget)
        print(f"Fund #{fid} created.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_funds(svc: BursaryService) -> None:
    ftype = input("Filter by type (Enter for all): ").strip() or None
    status = input("Filter by status (open/closed/exhausted, Enter for all): ").strip() or None
    try:
        rows = svc.list_funds(fund_type=ftype, status=status)
    except BursaryError as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No funds found.")
        return
    print(f"\n{'ID':<5} {'Name':<25} {'Type':<13} {'Budget':>12} "
          f"{'Allocated':>12} {'Remaining':>12} {'Status':<10}")
    print("-" * 95)
    for r in rows:
        budget = r.get("total_budget") or 0
        alloc = r.get("allocated") or 0
        print(f"{r['fund_id']:<5} {(r.get('name') or '')[:25]:<25} "
              f"{(r.get('fund_type') or '-'):<13} "
              f"{budget:>12.2f} {alloc:>12.2f} "
              f"{(budget - alloc):>12.2f} "
              f"{(r.get('status') or '-'):<10}")
    print(f"\nTotal: {len(rows)}")


def _update_fund_budget(svc: BursaryService) -> None:
    try:
        fid = int(input("Fund ID: ").strip())
        budget = float(input("New total budget: ").strip())
        svc.update_fund_budget(fid, budget)
        print("Fund budget updated.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def _submit_application(svc: BursaryService) -> None:
    try:
        sid = int(input("Student ID: ").strip())
        fid = int(input("Fund ID: ").strip())
        amount = float(input("Requested amount: ").strip())
        income_raw = input("Household income (blank=skip): ").strip()
        income = float(income_raw) if income_raw else None
        circumstances = input("Circumstances: ").strip()
        aid = svc.submit_application(sid, fid, amount,
                                     household_income=income,
                                     circumstances=circumstances)
        print(f"Application #{aid} submitted.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_applications(svc: BursaryService) -> None:
    status = input(
        "Status filter (submitted/under_review/approved/rejected/awarded, Enter=all): "
    ).strip() or None
    sid = input("Student ID filter (Enter=all): ").strip()
    fid = input("Fund ID filter (Enter=all): ").strip()
    try:
        rows = svc.list_applications(
            status=status,
            student_id=int(sid) if sid else None,
            fund_id=int(fid) if fid else None,
        )
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No applications found.")
        return
    print(f"\n{'ID':<5} {'Stu':<6} {'Fund':<5} {'Requested':>10} "
          f"{'Status':<14} {'Submitted':<20}")
    print("-" * 70)
    for r in rows:
        print(f"{r['application_id']:<5} {r['student_id']:<6} {r['fund_id']:<5} "
              f"{(r.get('requested_amount') or 0):>10.2f} "
              f"{(r.get('status') or '-'):<14} "
              f"{(r.get('submitted_at') or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


def _update_application_status(svc: BursaryService) -> None:
    try:
        aid = int(input("Application ID: ").strip())
        status = input(
            "New status (submitted/under_review/approved/rejected/awarded): "
        ).strip()
        notes = input("Decision notes (blank=none): ").strip() or None
        svc.update_application_status(aid, status, decision_notes=notes)
        print("Application status updated.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def _add_evidence(svc: BursaryService) -> None:
    try:
        aid = int(input("Application ID: ").strip())
        etype = input("Evidence type (e.g. payslip/benefit_letter/bank_statement): ").strip()
        filename = input("Filename (blank=none): ").strip()
        desc = input("Description (blank=none): ").strip()
        eid = svc.add_evidence(aid, etype, filename=filename, description=desc)
        print(f"Evidence #{eid} added.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _verify_evidence(svc: BursaryService) -> None:
    try:
        eid = int(input("Evidence ID: ").strip())
        verifier = input("Verified by (your name/role): ").strip()
        svc.verify_evidence(eid, verifier)
        print("Evidence verified.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_evidence(svc: BursaryService) -> None:
    try:
        aid = int(input("Application ID: ").strip())
        rows = svc.list_evidence(aid)
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No evidence found.")
        return
    print(f"\n{'ID':<5} {'Type':<18} {'Filename':<22} {'Verified':<9} "
          f"{'By':<15} {'Uploaded':<20}")
    print("-" * 92)
    for r in rows:
        print(f"{r['evidence_id']:<5} "
              f"{(r.get('evidence_type') or '-')[:18]:<18} "
              f"{(r.get('filename') or '-')[:22]:<22} "
              f"{('Yes' if r.get('verified') else 'No'):<9} "
              f"{(r.get('verified_by') or '-')[:15]:<15} "
              f"{(r.get('uploaded_at') or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


# ---------------------------------------------------------------------------
# Awards & payments
# ---------------------------------------------------------------------------

def _award_bursary(svc: BursaryService) -> None:
    try:
        aid = int(input("Application ID: ").strip())
        amount = float(input("Award amount: ").strip())
        freq = input("Frequency (one_off/weekly/monthly/termly): ").strip()
        n = int(input("Number of payments: ").strip() or 1)
        start = input("Start date (YYYY-MM-DD): ").strip()
        award_id = svc.award_bursary(aid, amount, freq, n, start)
        print(f"Award #{award_id} created with {n} scheduled payment(s).")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _mark_payment_paid(svc: BursaryService) -> None:
    try:
        pid = int(input("Payment ID: ").strip())
        ref = input("Payment reference: ").strip()
        svc.mark_payment_paid(pid, ref)
        print("Payment marked as paid.")
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")


def _payment_schedule(svc: BursaryService) -> None:
    try:
        award_id = int(input("Award ID: ").strip())
        rows = svc.get_payment_schedule(award_id)
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No payments found.")
        return
    print(f"\n{'ID':<5} {'Scheduled':<12} {'Amount':>10} {'Status':<10} "
          f"{'Paid':<20} {'Reference':<20}")
    print("-" * 82)
    for r in rows:
        print(f"{r['payment_id']:<5} "
              f"{(r.get('scheduled_date') or '-'):<12} "
              f"{(r.get('amount') or 0):>10.2f} "
              f"{(r.get('status') or '-'):<10} "
              f"{(r.get('paid_date') or '-')[:19]:<20} "
              f"{(r.get('reference') or '-')[:20]:<20}")
    print(f"\nTotal: {len(rows)}")


def _application_summary(svc: BursaryService) -> None:
    try:
        aid = int(input("Application ID: ").strip())
        summary = svc.get_application_summary(aid)
    except (BursaryError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    app = summary["application"]
    fund = summary["fund"]
    award = summary["award"]
    print(f"\nApplication #{app['application_id']}")
    print(f"  Student:    {app['student_id']}")
    print(f"  Fund:       {fund['name']} ({fund['fund_type']})")
    print(f"  Requested:  {app.get('requested_amount', 0):.2f}")
    print(f"  Status:     {app.get('status')}")
    print(f"  Submitted:  {app.get('submitted_at')}")
    print(f"  Decision:   {app.get('decision_notes') or '-'}")
    print(f"\nEvidence ({len(summary['evidence'])} items):")
    for e in summary["evidence"]:
        flag = "[verified]" if e.get("verified") else "[unverified]"
        print(f"  - #{e['evidence_id']} {e['evidence_type']} {flag}")
    if award:
        print(f"\nAward #{award['award_id']}: {award['awarded_amount']:.2f} "
              f"({award['payment_frequency']}, {award['num_payments']} payments)")
        print(f"  {award['start_date']} -> {award['end_date']}  status={award['status']}")
        print(f"\nPayments ({len(summary['payments'])}):")
        for p in summary["payments"]:
            print(f"  #{p['payment_id']} {p['scheduled_date']}  "
                  f"{p['amount']:>8.2f}  {p['status']}"
                  f"{('  ref=' + p['reference']) if p.get('reference') else ''}")
    else:
        print("\nNo award yet.")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def display_bursary_menu() -> None:
    """Top-level bursary management menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = BursaryService(db_path)

    actions = {
        "1":  ("Create Fund",                _create_fund),
        "2":  ("List Funds",                 _list_funds),
        "3":  ("Update Fund Budget",         _update_fund_budget),
        "4":  ("Submit Application",         _submit_application),
        "5":  ("List Applications",          _list_applications),
        "6":  ("Update Application Status",  _update_application_status),
        "7":  ("Add Evidence",               _add_evidence),
        "8":  ("Verify Evidence",            _verify_evidence),
        "9":  ("List Evidence",              _list_evidence),
        "10": ("Award Bursary",              _award_bursary),
        "11": ("Mark Payment Paid",          _mark_payment_paid),
        "12": ("Payment Schedule",           _payment_schedule),
        "13": ("Application Summary",        _application_summary),
    }
    while True:
        print("\nBursary Management")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except BursaryError as exc:
            print(f"Error: {exc}")
