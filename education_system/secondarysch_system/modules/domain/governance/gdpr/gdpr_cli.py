"""CLI flows for Secondary School GDPR."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.governance.gdpr import gdpr as data
from education_system.secondarysch_system.modules.domain.governance.gdpr.gdpr import (
    BREACH_SEVERITIES,
    BREACH_STATUSES,
    CONSENT_PURPOSES,
    DEFAULT_BREACH_SEVERITY,
    DEFAULT_BREACH_STATUS,
    DEFAULT_CONSENT_PURPOSE,
    DEFAULT_PROCESSING_STATUS,
    DEFAULT_REQUEST_STATUS,
    DEFAULT_REQUEST_TYPE,
    DEFAULT_SUBJECT_TYPE,
    LAWFUL_BASES,
    PROCESSING_STATUSES,
    REQUEST_STATUSES,
    REQUEST_TYPES,
    SUBJECT_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
           allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
               default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                     default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


# ── Print helpers ──────────────────────────────────────────────────

def _print_requests(rows: list[data.Request]) -> None:
    if not rows:
        print("\n  (no requests)")
        return
    print()
    print(f"  {'#':>4}  {'Type':<28}  {'Subject':<24}  "
          f"{'Received':<10}  {'Due':<10}  "
          f"{'Days':>5}  Status")
    print("  " + "-" * 110)
    for r in rows:
        dr = r.days_remaining
        days = ("OVR" if r.is_overdue
                else (str(dr) if dr is not None else "—"))
        print(f"  {r.request_id:>4}  {r.request_type[:28]:<28}  "
              f"{r.subject_name[:24]:<24}  "
              f"{r.received_date:<10}  {r.due_date:<10}  "
              f"{days:>5}  {r.status}")
    print(f"\n  {len(rows)} request(s).")


def _print_processing(rows: list[data.ProcessingActivity]) -> None:
    if not rows:
        print("\n  (no processing activities)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<32}  {'Basis':<22}  "
          f"{'Status':<14}  {'Next review':<12}  DPIA")
    print("  " + "-" * 110)
    for p in rows:
        dpia = ("required" if p.dpia_required and
                not p.dpia_completed
                else "done" if p.dpia_completed else "—")
        print(f"  {p.activity_id:>4}  {p.name[:32]:<32}  "
              f"{p.lawful_basis[:22]:<22}  "
              f"{p.status:<14}  {(p.next_review or '—'):<12}  "
              f"{dpia}")
    print(f"\n  {len(rows)} activit{'y' if len(rows) == 1 else 'ies'}.")


def _print_breaches(rows: list[data.Breach]) -> None:
    if not rows:
        print("\n  (no breaches)")
        return
    print()
    print(f"  {'#':>4}  {'Discovered':<10}  {'Title':<32}  "
          f"{'Severity':<10}  {'Status':<16}  "
          f"{'Affect':>6}  ICO")
    print("  " + "-" * 110)
    for b in rows:
        ico = ("Yes" if b.ico_notifiable else "No")
        print(f"  {b.breach_id:>4}  {b.discovered_date:<10}  "
              f"{b.title[:32]:<32}  {b.severity:<10}  "
              f"{b.status:<16}  {b.affected_count:>6}  {ico}")
    print(f"\n  {len(rows)} breach(es).")


def _print_consents(rows: list[data.Consent]) -> None:
    if not rows:
        print("\n  (no consents)")
        return
    print()
    print(f"  {'#':>4}  {'Subject':<24}  {'Purpose':<26}  "
          f"{'Granted':<10}  {'Expires':<10}  {'Withdrawn':<10}  "
          f"State")
    print("  " + "-" * 110)
    for c in rows:
        state = ("active" if c.is_active else "inactive")
        print(f"  {c.consent_id:>4}  {c.subject_name[:24]:<24}  "
              f"{c.purpose[:26]:<26}  {c.granted_date:<10}  "
              f"{(c.expires_date or '—'):<10}  "
              f"{(c.withdrawn_date or '—'):<10}  {state}")
    print(f"\n  {len(rows)} consent(s).")


# ── Request flows ─────────────────────────────────────────────────

def _collect_request(existing: data.Request | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["subject_name"] = _input(
        "Subject name",
        default=existing.subject_name if is_edit else "",
        allow_empty=not is_edit)
    p["subject_type"] = _pick_from(
        "Subject type", list(SUBJECT_TYPES),
        default=existing.subject_type if is_edit
        else DEFAULT_SUBJECT_TYPE)
    p["subject_ref"] = _input(
        "Subject reference (e.g. S12345, optional)",
        default=(existing.subject_ref or "") if is_edit else "")
    p["request_type"] = _pick_from(
        "Request type", list(REQUEST_TYPES),
        default=existing.request_type if is_edit
        else DEFAULT_REQUEST_TYPE)
    p["received_date"] = _input(
        "Received date (YYYY-MM-DD)",
        default=existing.received_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["due_date"] = _input(
        "Due date (YYYY-MM-DD, blank = +30 days)",
        default=(existing.due_date if is_edit else ""))
    p["identity_verified"] = _yes_no(
        "Identity verified?",
        default=existing.identity_verified if is_edit else False)
    p["status"] = _pick_from(
        "Status", list(REQUEST_STATUSES),
        default=existing.status if is_edit
        else DEFAULT_REQUEST_STATUS)
    p["responded_date"] = _input(
        "Responded date (YYYY-MM-DD, optional)",
        default=(existing.responded_date or "") if is_edit else "")
    p["handler"] = _input(
        "Handler (staff ID/name, optional)",
        default=(existing.handler or "") if is_edit else "")
    p["description"] = _input(
        "Description (optional)",
        default=(existing.description or "") if is_edit else "")
    p["response_summary"] = _input(
        "Response summary (optional)",
        default=(existing.response_summary or "")
        if is_edit else "")
    p["refusal_reason"] = _input(
        "Refusal reason (required if status=Refused)",
        default=(existing.refusal_reason or "") if is_edit else "")
    p["contact_email"] = _input(
        "Contact email (optional)",
        default=(existing.contact_email or "") if is_edit else "")
    p["contact_phone"] = _input(
        "Contact phone (optional)",
        default=(existing.contact_phone or "") if is_edit else "")
    p["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return p


def list_open_requests() -> None:
    print("\n═══ Open DSAR / Rights Requests ═══")
    _print_requests(data.list_requests(open_only=True))
    _pause()


def list_overdue_requests() -> None:
    print("\n═══ Overdue Requests ═══")
    _print_requests(data.list_requests(overdue_only=True))
    _pause()


def list_all_requests() -> None:
    print("\n═══ All Requests ═══")
    _print_requests(data.list_requests())
    _pause()


def search_requests() -> None:
    print("\n═══ Search Requests ═══")
    try:
        q = _input("Search text (name / ref / desc / notes)",
                    allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_requests(data.list_requests(search=q))
    _pause()


def view_request(request_id: int | None = None) -> None:
    print("\n═══ View Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    r = data.get_request(rid)
    if r is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    print()
    print(f"    Request #{r.request_id}  ({r.request_type})")
    print(f"    Subject       : {r.subject_name}  "
          f"[{r.subject_type}]  {r.subject_ref or ''}")
    print(f"    Received      : {r.received_date}")
    print(f"    Due           : {r.due_date}  "
          f"({'OVERDUE' if r.is_overdue else 'in time'})")
    print(f"    Status        : {r.status}")
    print(f"    Identity ✓    : "
          f"{'yes' if r.identity_verified else 'no'}")
    print(f"    Handler       : {r.handler or '—'}")
    print(f"    Contact       : "
          f"{r.contact_email or '—'} / "
          f"{r.contact_phone or '—'}")
    if r.description:
        print(f"\n    Description:\n      {r.description}")
    if r.response_summary:
        print(f"\n    Response:\n      {r.response_summary}")
    if r.refusal_reason:
        print(f"\n    Refusal reason:\n      {r.refusal_reason}")
    if r.notes:
        print(f"\n    Notes:\n      {r.notes}")
    _pause()


def new_request() -> None:
    print("\n═══ New Request ═══")
    try:
        payload = _collect_request(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_request(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created request #{r.request_id} "
          f"(due {r.due_date})")
    _pause()


def edit_request_flow(request_id: int | None = None) -> None:
    print("\n═══ Edit Request ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_request(rid)
    if existing is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    try:
        payload = _collect_request(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_request(rid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{rid}")
    _pause()


def set_request_status_flow(request_id: int | None = None) -> None:
    print("\n═══ Change Request Status ═══")
    try:
        rid = request_id if request_id is not None else int(
            _input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_request(rid)
    if existing is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    try:
        new = _pick_from("New status", list(REQUEST_STATUSES),
                            default=existing.status)
        summary = (_input("Response summary (optional)")
                    if new in ("Responded", "Fulfilled",
                                "Partially Fulfilled", "Closed")
                    else None)
        refusal = (_input("Refusal reason", allow_empty=False)
                    if new == "Refused" else None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_request_status(
            rid, new,
            response_summary=summary, refusal_reason=refusal)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{rid} → {new}")
    _pause()


def delete_request_flow() -> None:
    print("\n═══ Delete Request ═══")
    try:
        rid = int(_input("Request ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_request(rid) is None:
        print(f"  ✗ No request #{rid}")
        _pause()
        return
    if _input(f"Delete request #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_request(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


# ── Processing flows ──────────────────────────────────────────────

def _collect_processing(existing: data.ProcessingActivity | None
                         ) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["name"] = _input(
        "Activity name", default=existing.name if is_edit else "",
        allow_empty=not is_edit)
    p["controller"] = _input(
        "Controller (organisation)",
        default=(existing.controller or "") if is_edit else "")
    p["purpose"] = _input(
        "Purpose",
        default=existing.purpose if is_edit else "",
        allow_empty=not is_edit)
    p["lawful_basis"] = _pick_from(
        "Lawful basis", list(LAWFUL_BASES),
        default=existing.lawful_basis if is_edit else "Public Task")
    p["data_categories"] = _input(
        "Data categories",
        default=(existing.data_categories or "") if is_edit else "")
    p["data_subjects"] = _input(
        "Data subjects",
        default=(existing.data_subjects or "") if is_edit else "")
    p["recipients"] = _input(
        "Recipients (internal / third parties)",
        default=(existing.recipients or "") if is_edit else "")
    p["retention"] = _input(
        "Retention period",
        default=(existing.retention or "") if is_edit else "")
    p["transfers"] = _input(
        "International transfers (if any)",
        default=(existing.transfers or "") if is_edit else "")
    p["security_measures"] = _input(
        "Security measures",
        default=(existing.security_measures or "") if is_edit else "")
    p["dpia_required"] = _yes_no(
        "DPIA required?",
        default=existing.dpia_required if is_edit else False)
    p["dpia_completed"] = _yes_no(
        "DPIA completed?",
        default=existing.dpia_completed if is_edit else False)
    p["dpia_date"] = _input(
        "DPIA date (YYYY-MM-DD, optional)",
        default=(existing.dpia_date or "") if is_edit else "")
    p["status"] = _pick_from(
        "Status", list(PROCESSING_STATUSES),
        default=existing.status if is_edit
        else DEFAULT_PROCESSING_STATUS)
    p["last_reviewed"] = _input(
        "Last reviewed (YYYY-MM-DD, optional)",
        default=(existing.last_reviewed or "") if is_edit else "")
    p["next_review"] = _input(
        "Next review (YYYY-MM-DD, optional)",
        default=(existing.next_review or "") if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def list_processing_flow() -> None:
    print("\n═══ Processing Activities (RoPA) ═══")
    _print_processing(data.list_processing())
    _pause()


def search_processing_flow() -> None:
    print("\n═══ Search Processing ═══")
    try:
        q = _input("Search text", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_processing(data.list_processing(search=q))
    _pause()


def new_processing_flow() -> None:
    print("\n═══ New Processing Activity ═══")
    try:
        payload = _collect_processing(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_processing(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created activity #{p.activity_id} ({p.name})")
    _pause()


def edit_processing_flow() -> None:
    print("\n═══ Edit Processing Activity ═══")
    try:
        aid = int(_input("Activity ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_processing(aid)
    if existing is None:
        print(f"  ✗ No activity #{aid}")
        _pause()
        return
    try:
        payload = _collect_processing(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_processing(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{aid}")
    _pause()


def delete_processing_flow() -> None:
    print("\n═══ Delete Processing Activity ═══")
    try:
        aid = int(_input("Activity ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_processing(aid) is None:
        print(f"  ✗ No activity #{aid}")
        _pause()
        return
    if _input(f"Delete activity #{aid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_processing(aid):
        print(f"\n  ✓ Deleted #{aid}")
    _pause()


# ── Breach flows ──────────────────────────────────────────────────

def _collect_breach(existing: data.Breach | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["title"] = _input(
        "Title", default=existing.title if is_edit else "",
        allow_empty=not is_edit)
    p["discovered_date"] = _input(
        "Discovered date (YYYY-MM-DD)",
        default=existing.discovered_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["occurred_date"] = _input(
        "Occurred date (YYYY-MM-DD, optional)",
        default=(existing.occurred_date or "") if is_edit else "")
    p["reported_by"] = _input(
        "Reported by",
        default=(existing.reported_by or "") if is_edit else "")
    p["severity"] = _pick_from(
        "Severity", list(BREACH_SEVERITIES),
        default=existing.severity if is_edit
        else DEFAULT_BREACH_SEVERITY)
    p["status"] = _pick_from(
        "Status", list(BREACH_STATUSES),
        default=existing.status if is_edit else DEFAULT_BREACH_STATUS)
    p["affected_count"] = _input(
        "Approx affected count",
        default=str(existing.affected_count) if is_edit else "0")
    p["affected_categories"] = _input(
        "Affected data categories",
        default=(existing.affected_categories or "")
        if is_edit else "")
    p["summary"] = _input(
        "Summary",
        default=existing.summary if is_edit else "",
        allow_empty=not is_edit)
    p["root_cause"] = _input(
        "Root cause",
        default=(existing.root_cause or "") if is_edit else "")
    p["remediation"] = _input(
        "Remediation taken",
        default=(existing.remediation or "") if is_edit else "")
    p["ico_notifiable"] = _yes_no(
        "ICO notifiable?",
        default=existing.ico_notifiable if is_edit else False)
    p["ico_notified_date"] = _input(
        "ICO notified date (YYYY-MM-DD, optional)",
        default=(existing.ico_notified_date or "")
        if is_edit else "")
    p["ico_reference"] = _input(
        "ICO reference (optional)",
        default=(existing.ico_reference or "") if is_edit else "")
    p["subjects_notified"] = _yes_no(
        "Subjects notified?",
        default=existing.subjects_notified if is_edit else False)
    p["subjects_notified_date"] = _input(
        "Subjects notified date (YYYY-MM-DD, optional)",
        default=(existing.subjects_notified_date or "")
        if is_edit else "")
    p["closed_date"] = _input(
        "Closed date (YYYY-MM-DD, optional)",
        default=(existing.closed_date or "") if is_edit else "")
    p["lessons_learned"] = _input(
        "Lessons learned",
        default=(existing.lessons_learned or "") if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def list_breaches_flow() -> None:
    print("\n═══ Breaches ═══")
    _print_breaches(data.list_breaches())
    _pause()


def list_open_breaches_flow() -> None:
    print("\n═══ Open Breaches ═══")
    _print_breaches(data.list_breaches(open_only=True))
    _pause()


def view_breach_flow() -> None:
    print("\n═══ View Breach ═══")
    try:
        bid = int(_input("Breach ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    b = data.get_breach(bid)
    if b is None:
        print(f"  ✗ No breach #{bid}")
        _pause()
        return
    print()
    print(f"    Breach #{b.breach_id}  ({b.severity})")
    print(f"    Title       : {b.title}")
    print(f"    Discovered  : {b.discovered_date}")
    print(f"    Occurred    : {b.occurred_date or '—'}")
    print(f"    Reported by : {b.reported_by or '—'}")
    print(f"    Status      : {b.status}")
    print(f"    Affected    : {b.affected_count}  "
          f"({b.affected_categories or '—'})")
    print(f"    ICO notif.  : "
          f"{'yes' if b.ico_notifiable else 'no'}"
          f" on {b.ico_notified_date or '—'} "
          f"(ref {b.ico_reference or '—'})")
    subj_state = (
        f"notified {b.subjects_notified_date or ''}"
        if b.subjects_notified else "not notified")
    print(f"    Subjects    : {subj_state}")
    print(f"    Closed      : {b.closed_date or '—'}")
    if b.summary:
        print(f"\n    Summary:\n      {b.summary}")
    if b.root_cause:
        print(f"\n    Root cause:\n      {b.root_cause}")
    if b.remediation:
        print(f"\n    Remediation:\n      {b.remediation}")
    if b.lessons_learned:
        print(f"\n    Lessons learned:\n      {b.lessons_learned}")
    if b.notes:
        print(f"\n    Notes:\n      {b.notes}")
    _pause()


def new_breach_flow() -> None:
    print("\n═══ Report Breach ═══")
    try:
        payload = _collect_breach(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_breach(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created breach #{b.breach_id} ({b.severity})")
    _pause()


def edit_breach_flow() -> None:
    print("\n═══ Edit Breach ═══")
    try:
        bid = int(_input("Breach ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_breach(bid)
    if existing is None:
        print(f"  ✗ No breach #{bid}")
        _pause()
        return
    try:
        payload = _collect_breach(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_breach(bid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{bid}")
    _pause()


def delete_breach_flow() -> None:
    print("\n═══ Delete Breach ═══")
    try:
        bid = int(_input("Breach ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_breach(bid) is None:
        print(f"  ✗ No breach #{bid}")
        _pause()
        return
    if _input(f"Delete breach #{bid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_breach(bid):
        print(f"\n  ✓ Deleted #{bid}")
    _pause()


# ── Consent flows ─────────────────────────────────────────────────

def _collect_consent(existing: data.Consent | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["subject_name"] = _input(
        "Subject name",
        default=existing.subject_name if is_edit else "",
        allow_empty=not is_edit)
    p["subject_type"] = _pick_from(
        "Subject type", list(SUBJECT_TYPES),
        default=existing.subject_type if is_edit
        else DEFAULT_SUBJECT_TYPE)
    p["subject_ref"] = _input(
        "Subject reference (optional)",
        default=(existing.subject_ref or "") if is_edit else "")
    p["purpose"] = _pick_from(
        "Purpose", list(CONSENT_PURPOSES),
        default=existing.purpose if is_edit
        else DEFAULT_CONSENT_PURPOSE)
    p["granted"] = _yes_no(
        "Granted?",
        default=existing.granted if is_edit else True)
    p["granted_date"] = _input(
        "Granted date (YYYY-MM-DD)",
        default=existing.granted_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["expires_date"] = _input(
        "Expires date (YYYY-MM-DD, optional)",
        default=(existing.expires_date or "") if is_edit else "")
    p["withdrawn_date"] = _input(
        "Withdrawn date (YYYY-MM-DD, optional)",
        default=(existing.withdrawn_date or "") if is_edit else "")
    p["source"] = _input(
        "Source (form / verbal / parental)",
        default=(existing.source or "") if is_edit else "")
    p["detail"] = _input(
        "Detail (optional)",
        default=(existing.detail or "") if is_edit else "")
    p["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return p


def list_consents_flow() -> None:
    print("\n═══ Consents ═══")
    _print_consents(data.list_consents())
    _pause()


def list_active_consents_flow() -> None:
    print("\n═══ Active Consents ═══")
    _print_consents(data.list_consents(active_only=True))
    _pause()


def search_consents_flow() -> None:
    print("\n═══ Search Consents ═══")
    try:
        q = _input("Search text", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_consents(data.list_consents(search=q))
    _pause()


def new_consent_flow() -> None:
    print("\n═══ New Consent ═══")
    try:
        payload = _collect_consent(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_consent(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created consent #{c.consent_id}")
    _pause()


def edit_consent_flow() -> None:
    print("\n═══ Edit Consent ═══")
    try:
        cid = int(_input("Consent ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_consent(cid)
    if existing is None:
        print(f"  ✗ No consent #{cid}")
        _pause()
        return
    try:
        payload = _collect_consent(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_consent(cid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{cid}")
    _pause()


def withdraw_consent_flow() -> None:
    print("\n═══ Withdraw Consent ═══")
    try:
        cid = int(_input("Consent ID", allow_empty=False))
        when = _input("Withdrawn date (YYYY-MM-DD)",
                        default=_date.today().isoformat(),
                        allow_empty=False)
        notes = _input("Notes (optional)")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_consent(cid) is None:
        print(f"  ✗ No consent #{cid}")
        _pause()
        return
    try:
        data.withdraw_consent(cid, withdrawn_date=when,
                                notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Consent #{cid} withdrawn on {when}")
    _pause()


def delete_consent_flow() -> None:
    print("\n═══ Delete Consent ═══")
    try:
        cid = int(_input("Consent ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_consent(cid) is None:
        print(f"  ✗ No consent #{cid}")
        _pause()
        return
    if _input(f"Delete consent #{cid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_consent(cid):
        print(f"\n  ✓ Deleted #{cid}")
    _pause()


# ── Overview ─────────────────────────────────────────────────────

def overview_flow() -> None:
    print("\n═══ GDPR Overview ═══")
    o = data.overview()
    print(f"\n  Requests")
    print(f"    Total              : {o.total_requests}")
    print(f"    Open               : {o.open_requests}")
    print(f"    Overdue            : {o.overdue_requests}")
    if o.requests_by_type:
        print("    By type:")
        for k, n in sorted(o.requests_by_type.items(),
                            key=lambda kv: -kv[1]):
            if n:
                print(f"      {k:<30} : {n}")
    print(f"\n  Processing register (RoPA)")
    print(f"    Total              : {o.total_processing}")
    print(f"    Active             : {o.processing_active}")
    print(f"    Reviews due / overdue: {o.processing_due_review}")
    print(f"\n  Breaches")
    print(f"    Total              : {o.total_breaches}")
    print(f"    Open               : {o.open_breaches}")
    print(f"    High / Critical    : {o.high_or_critical_breaches}")
    print(f"    ICO notifiable open: {o.ico_notifiable_open}")
    print(f"\n  Consents")
    print(f"    Total              : {o.total_consents}")
    print(f"    Active             : {o.active_consents}")
    print(f"    Withdrawn          : {o.withdrawn_consents}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview",                   overview_flow),
    ("Open Requests",              list_open_requests),
    ("Overdue Requests",           list_overdue_requests),
    ("All Requests",               list_all_requests),
    ("Search Requests",            search_requests),
    ("View Request",               view_request),
    ("New Request",                new_request),
    ("Edit Request",               edit_request_flow),
    ("Change Request Status",      set_request_status_flow),
    ("Delete Request",             delete_request_flow),
    ("List Processing (RoPA)",     list_processing_flow),
    ("Search Processing",          search_processing_flow),
    ("New Processing Activity",    new_processing_flow),
    ("Edit Processing Activity",   edit_processing_flow),
    ("Delete Processing Activity", delete_processing_flow),
    ("List Breaches",              list_breaches_flow),
    ("Open Breaches",              list_open_breaches_flow),
    ("View Breach",                view_breach_flow),
    ("Report Breach",              new_breach_flow),
    ("Edit Breach",                edit_breach_flow),
    ("Delete Breach",              delete_breach_flow),
    ("List Consents",              list_consents_flow),
    ("Active Consents",            list_active_consents_flow),
    ("Search Consents",            search_consents_flow),
    ("New Consent",                new_consent_flow),
    ("Edit Consent",               edit_consent_flow),
    ("Withdraw Consent",           withdraw_consent_flow),
    ("Delete Consent",             delete_consent_flow),
]


def run() -> None:
    while True:
        print("\n── GDPR ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("GDPR CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "GDPR":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("GDPR CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
