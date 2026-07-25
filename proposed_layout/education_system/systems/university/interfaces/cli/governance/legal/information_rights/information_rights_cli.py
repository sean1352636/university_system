"""
Information Rights CLI — Subject Access Request (SAR), Freedom of
Information (FOI) and Environmental Information (EIR) request management.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from education_system.systems.university.domain.governance.legal.information_rights.services.information_rights_core import (  # noqa: E501
    InformationRightsService,
    InformationRightsError,
    REQUEST_TYPES,
    REQUEST_STATUSES,
    OUTCOMES,
    FOIA_EXEMPTIONS,
    DPA_EXEMPTIONS,
    EIR_EXCEPTIONS,
)


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def _input_date(prompt: str) -> Optional[date]:
    s = _input(f"{prompt} (YYYY-MM-DD, blank=today)")
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        print("  ! invalid date, using today")
        return None


def _print_request(r: dict) -> None:
    print(f"\n  {r['reference']}  [{r['request_type']}]  status={r['status']}"
          f"  deadline={r['deadline_on']}")
    print(f"    {r['requester_name']} <{r['requester_email']}>")
    print(f"    {r['subject_summary']}")
    if r.get("assigned_officer"):
        print(f"    officer: {r['assigned_officer']}")
    if r.get("extended"):
        print(f"    EXTENDED: {r.get('extension_reason') or ''}")
    if r.get("outcome"):
        print(f"    outcome: {r['outcome']}  closed_on={r.get('closed_on')}")


def _create_request(svc: InformationRightsService, actor: str) -> None:
    print("\nRequest types: " + ", ".join(REQUEST_TYPES))
    rtype = _input("Type", "SAR").upper()
    if rtype not in REQUEST_TYPES:
        print("  invalid type"); return
    name = _input("Requester full name")
    email = _input("Requester email")
    phone = _input("Requester phone (optional)")
    summary = _input("Subject / summary of request")
    scope = _input("Scope details (optional)")
    received = _input_date("Received on")
    officer = _input("Assigned officer (optional)")
    try:
        r = svc.create_request(
            request_type=rtype,
            requester_name=name,
            requester_email=email,
            requester_phone=phone,
            subject_summary=summary,
            scope_details=scope,
            received_on=received,
            assigned_officer=officer,
            actor=actor,
        )
    except InformationRightsError as exc:
        print(f"  ! {exc}"); return
    print(f"  Created {r['reference']} (deadline {r['deadline_on']})")


def _list_requests(svc: InformationRightsService) -> None:
    only_open = _input("Open only? (y/N)", "n").lower().startswith("y")
    rtype = _input("Filter by type (SAR/FOI/EIR or blank)").upper() or None
    if rtype and rtype not in REQUEST_TYPES:
        print("  invalid type"); return
    rows = svc.list_requests(request_type=rtype, include_closed=not only_open)
    if not rows:
        print("  (no requests)"); return
    today = date.today()
    for r in rows:
        days = svc.days_remaining(r, today)
        flag = " OVERDUE" if days < 0 else (" DUE-SOON" if days <= 7 else "")
        print(f"  {r['reference']:<14} {r['request_type']:<3} "
              f"{r['status']:<18} due {r['deadline_on']} "
              f"({days:+}d){flag}  {r['requester_name']}")


def _view_request(svc: InformationRightsService) -> None:
    ref = _input("Reference")
    try:
        r = svc.get_by_reference(ref)
    except InformationRightsError as e:
        print(f"  ! {e}"); return
    _print_request(r)
    days = svc.days_remaining(r)
    print(f"    days remaining: {days:+}")
    comms = svc.list_communications(r["request_id"])
    exempts = svc.list_exemptions(r["request_id"])
    redacts = svc.list_redactions(r["request_id"])
    print(f"    communications: {len(comms)}  exemptions: {len(exempts)}"
          f"  redactions: {len(redacts)}")
    if comms:
        print("\n  Communications:")
        for c in comms:
            print(f"    [{c['occurred_at']}] {c['direction']:<8}"
                  f" {c['channel']:<8} {c['summary']}")
    if exempts:
        print("\n  Exemptions:")
        for e in exempts:
            print(f"    {e['regime']} {e['code']} ({e['label']})"
                  f"\n      reason: {e['reason']}")
    if redacts:
        print("\n  Redactions:")
        for r0 in redacts:
            print(f"    {r0['document_ref']} p={r0['page'] or '-'}"
                  f" type={r0['redaction_type']}: {r0['rationale']}")


def _verify_id(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    try:
        r = svc.get_by_reference(ref)
        verified = _input_date("Verified on")
        restart = _input("Restart clock from verification date? (Y/n)", "y") \
            .lower().startswith("y")
        out = svc.mark_identity_verified(
            r["request_id"], verified_on=verified,
            actor=actor, restart_clock=restart)
        print(f"  ID verified. New deadline: {out['deadline_on']}")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _apply_extension(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference (SAR only)")
    reason = _input("Reason for extension (complex / numerous)")
    try:
        r = svc.get_by_reference(ref)
        out = svc.apply_extension(r["request_id"], reason, actor=actor)
        print(f"  Extension applied. New deadline: {out['deadline_on']}")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _change_status(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    print("Statuses: " + ", ".join(REQUEST_STATUSES))
    new = _input("New status")
    note = _input("Note (optional)")
    try:
        r = svc.get_by_reference(ref)
        out = svc.set_status(r["request_id"], new, actor=actor, note=note)
        print(f"  status -> {out['status']}")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _log_comm(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    direction = _input("Direction (inbound/outbound/internal)", "outbound")
    channel = _input("Channel (email/post/phone/portal)", "email")
    summary = _input("Summary")
    body = _input("Body (optional)")
    try:
        r = svc.get_by_reference(ref)
        cid = svc.log_communication(r["request_id"], direction, channel,
                                    summary, body, author=actor)
        print(f"  logged communication #{cid}")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _apply_exemption(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    regime = _input("Regime (FOIA/DPA/EIR)").upper()
    catalogue = {"FOIA": FOIA_EXEMPTIONS,
                 "DPA": DPA_EXEMPTIONS,
                 "EIR": EIR_EXCEPTIONS}.get(regime)
    if catalogue is None:
        print("  invalid regime"); return
    print("\n  Available codes:")
    for code, label in catalogue.items():
        print(f"    {code:<22} {label}")
    code = _input("\nCode")
    reason = _input("Reason (harm test / public-interest balance)")
    try:
        r = svc.get_by_reference(ref)
        eid = svc.apply_exemption(r["request_id"], regime, code, reason,
                                  actor=actor)
        print(f"  exemption #{eid} recorded")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _log_redaction(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    doc = _input("Document reference (file name / path)")
    page = _input("Page (optional)")
    location = _input("Location e.g. 'para 3' (optional)")
    print("Types: third_party_pii, exempt_info, legally_privileged,"
          " out_of_scope, other")
    rtype = _input("Redaction type", "third_party_pii")
    rationale = _input("Rationale")
    eid = _input("Linked exemption_id (optional)")
    try:
        r = svc.get_by_reference(ref)
        rid = svc.log_redaction(
            r["request_id"], doc, rtype, rationale,
            page=page, location=location,
            exemption_id=int(eid) if eid else None,
            actor=actor)
        print(f"  redaction #{rid} recorded")
    except (InformationRightsError, ValueError) as e:
        print(f"  ! {e}")


def _close(svc: InformationRightsService, actor: str) -> None:
    ref = _input("Reference")
    print("Outcomes: " + ", ".join(OUTCOMES))
    outcome = _input("Outcome")
    note = _input("Closing note (optional)")
    try:
        r = svc.get_by_reference(ref)
        out = svc.close_request(r["request_id"], outcome, actor=actor,
                                note=note)
        print(f"  closed as {out['outcome']} on {out['closed_on']}")
    except InformationRightsError as e:
        print(f"  ! {e}")


def _dashboard(svc: InformationRightsService) -> None:
    s = svc.dashboard_summary()
    print(f"\n  Dashboard as of {s['as_of']}")
    print(f"    open: {s['total_open']}    closed: {s['total_closed']}")
    print(f"    by type:    {s['by_type']}")
    print(f"    by status:  {s['by_status']}")
    print(f"    overdue: {s['overdue_count']}    "
          f"due within 7 days: {s['due_within_7_days']}")
    if s["overdue"]:
        print("\n  OVERDUE:")
        for r in s["overdue"]:
            print(f"    {r['reference']} due {r['deadline_on']} "
                  f"-> {r['requester_name']}")
    if s["due_soon"]:
        print("\n  DUE SOON:")
        for r in s["due_soon"]:
            print(f"    {r['reference']} due {r['deadline_on']} "
                  f"-> {r['requester_name']}")


def display_menu(actor: str = "cli") -> None:
    """Top-level menu loop. Mirrors the legal_cli style."""
    svc = InformationRightsService()
    while True:
        print("\n" + "=" * 70)
        print(" " * 16 + "INFORMATION RIGHTS (SAR / FOI / EIR)")
        print("=" * 70)
        print("\n[Intake & Tracking]")
        print(" 1.  Create request")
        print(" 2.  List requests")
        print(" 3.  View request")
        print(" 4.  Verify requester identity (SAR)")
        print(" 5.  Apply 2-month extension (SAR)")
        print(" 6.  Change status")
        print("\n[Records]")
        print(" 7.  Log communication")
        print(" 8.  Apply exemption / exception")
        print(" 9.  Log redaction")
        print("\n[Closure & Reporting]")
        print("10.  Close request")
        print("11.  Dashboard (deadlines, overdue, due-soon)")
        print("\n 0.  Back")
        print("=" * 70)
        choice = input("\nEnter your choice: ").strip()
        try:
            if choice == "0":
                return
            elif choice == "1":
                _create_request(svc, actor)
            elif choice == "2":
                _list_requests(svc)
            elif choice == "3":
                _view_request(svc)
            elif choice == "4":
                _verify_id(svc, actor)
            elif choice == "5":
                _apply_extension(svc, actor)
            elif choice == "6":
                _change_status(svc, actor)
            elif choice == "7":
                _log_comm(svc, actor)
            elif choice == "8":
                _apply_exemption(svc, actor)
            elif choice == "9":
                _log_redaction(svc, actor)
            elif choice == "10":
                _close(svc, actor)
            elif choice == "11":
                _dashboard(svc)
            else:
                print("  unknown choice")
        except KeyboardInterrupt:
            print()
            return


if __name__ == "__main__":  # pragma: no cover
    display_menu()
