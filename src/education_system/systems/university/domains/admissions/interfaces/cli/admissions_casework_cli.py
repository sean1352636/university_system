"""Admissions casework CLI: conditions & documents, postgraduate
requirements, sponsors, and a supervisor's PGR supervision requests.

The same domain functions back the "Conditions & Documents" and
"Postgraduate" tabs of the Admissions CRM GUI, so anything done here shows
there and vice versa.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.university.domains.admissions.domain.services import (
    admissions_casework as casework,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_checklist as checklist,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_postgraduate as postgraduate,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_sponsors as sponsors,
)
from education_system.systems.university.domains.admissions.interfaces.cli.admissions_crm_cli import (
    _header,
    _pause,
    _prompt,
    _prompt_bool,
    _prompt_float,
    _prompt_int,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)


def _run(action, *args, **kwargs) -> Any:
    """Run a domain action; print a refusal. Truthy on success."""
    try:
        result = action(*args, **kwargs)
    except (AdmissionsBoundaryError, ValueError) as exc:
        print(f"\n✗ {exc}")
        return None
    if result is None:
        print("\n✓ Done.")
        return True
    if isinstance(result, int) and not isinstance(result, bool):
        print(f"\n✓ Saved (#{result}).")
    return result


def _choose(text: str, options) -> str:
    options = list(options)
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    raw = input(f"{text} (1-{len(options)}): ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return ""


# ── Conditions & Documents ─────────────────────────────────────────

def _print_checklist(data: dict) -> None:
    app = data["application"]
    name = f"{app.get('first_name') or ''} {app.get('last_name') or ''}".strip()
    print(f"\nApplication {app['application_id']} — {name} — {app.get('program_applied') or ''}")
    print(f"  Type: {app.get('application_type')}   Status: {app.get('status')}")
    print("\n  Conditions:")
    if not data["conditions"]:
        print("    (none)")
    for c in data["conditions"]:
        extra = c.get("evidence_reference") or c.get("waiver_reason") or ""
        print(f"    #{c['condition_id']:<5}{c['condition_type']:<18}{c['status']:<12}"
              f"{(c['description'] or '')[:40]}  {extra[:30]}")
    print("\n  Required documents:")
    if not data["requirements"]:
        print("    (none)")
    for r in data["requirements"]:
        need = "required" if r["required"] else "optional"
        print(f"    #{r['requirement_id']:<5}{r['requirement_type']:<18}{r['status']:<12}"
              f"{need:<9}{(r['description'] or '')[:40]}")
    decisions = data["decisions"]
    rts = decisions.get("right_to_study")
    print(f"\n  Right to study: {rts['status'] + ' (' + rts['route'] + ')' if rts else 'not recorded'}")
    if data["has_deposit_condition"]:
        dep = decisions.get("deposit")
        print(f"  Deposit decision: {dep['status'] if dep else 'not recorded'}")
    if data["sponsor"]:
        s = data["sponsor"]
        print(f"  Sponsor: {s['organisation']} (decision: {s['sponsorship_decision'] or 'none'})")
    if data["converted_student_id"]:
        print(f"\n  ✓ Converted — student {data['converted_student_id']}")
    elif data["ready"]:
        print("\n  ✓ READY — Convert to Student is available")
    else:
        print("\n  Not ready to enrol:")
        for issue in data["issues"]:
            print(f"    - {issue}")


def _pick_application() -> int | None:
    search = _prompt("Search applicant / programme / application id (blank = recent)")
    rows = checklist.applications(search=search, limit=25)
    if not rows:
        print("\nNo applications found.")
        return None
    print(f"\n{'ID':<6}{'Applicant':<24}{'Type':<22}{'Status':<20}Open")
    for r in rows:
        name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        print(f"{r['application_id']:<6}{name[:23]:<24}{(r['application_type'] or '')[:21]:<22}"
              f"{(r['status'] or '')[:19]:<20}{r['open_conditions']}c/{r['open_requirements']}d")
    return _prompt_int("Application id", allow_blank=True)


def _satisfy(auth, data) -> None:
    cid = _prompt_int("Condition id", allow_blank=False)
    note = _prompt("Evidence note (what showed it was met)")
    _run(checklist.satisfy_condition, auth, cid, note)


def _waive(auth, data) -> None:
    cid = _prompt_int("Condition id", allow_blank=False)
    reason = _prompt("Reason for waiving")
    _run(checklist.waive_condition, auth, cid, reason)


def _verify(auth, data) -> None:
    rid = _prompt_int("Requirement id", allow_blank=False)
    docs = data["documents"]
    if docs:
        print("\n  Documents already on file:")
        for d in docs:
            print(f"    #{d['document_id']}  {d['document_type'] or ''}  "
                  f"{d['original_filename'] or d['document_name'] or ''}  "
                  f"({d['verification_status'] or 'pending'})")
    path = _prompt("Path of a file to attach (blank = none)")
    doc_id = None if path else _prompt_int("Or an existing document id (blank = none)")
    notes = _prompt("Verification note (e.g. original sighted)")
    _run(checklist.verify_document, auth, rid, file_path=path or None,
         document_id=doc_id, notes=notes)


def _add_condition(auth, data) -> None:
    ctype = _choose("Condition type", checklist.CONDITION_TYPES)
    desc = _prompt("Description")
    due = _prompt("Due date (YYYY-MM-DD, optional)")
    amount = _prompt_float("Amount (optional)") if ctype == "deposit" else None
    sponsor = _prompt("Sponsor name (optional)") if ctype == "sponsorship" else ""
    _run(checklist.add_condition, auth, data["application"]["application_id"], ctype, desc,
         due_date=due, amount=amount, currency="GBP" if amount else "", sponsor_name=sponsor)


def _add_requirement(auth, data) -> None:
    rtype = _choose("Document type", checklist.REQUIREMENT_TYPES)
    desc = _prompt("What is needed")
    due = _prompt("Due date (YYYY-MM-DD, optional)")
    required = _prompt_bool("Required for enrolment?", default=True)
    _run(checklist.add_requirement, auth, data["application"]["application_id"], rtype, desc,
         due_date=due, required=required)


def _right_to_study(auth, data) -> None:
    from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
        RightToStudyPolicy,
    )
    route = _choose("Route", sorted(RightToStudyPolicy.ALLOWED_ROUTES))
    evidence = _prompt("Evidence reference (passport no., CAS, share code ...)")
    until = _prompt("Valid until (YYYY-MM-DD, optional)")
    status = _run(checklist.record_right_to_study, auth, data["application"]["application_id"],
                  route, evidence, valid_until=until or None)
    if status:
        print(f"\n✓ Right to study {status}.")


def _deposit(auth, data) -> None:
    required = _prompt_float("Deposit required", allow_blank=False)
    received = _prompt_float("Amount received", allow_blank=False)
    ref = _prompt("Payment reference")
    status = _run(checklist.record_deposit, auth, data["application"]["application_id"],
                  required_amount=required, received_amount=received, payment_reference=ref)
    if status:
        print(f"\n✓ Deposit decision: {status}.")


def _advance(auth, data) -> None:
    if not data["next_statuses"]:
        print("\nNo further status from here (enrolment is via Convert).")
        return
    target = _choose("Move to", data["next_statuses"])
    if target:
        reason = _prompt("Reason (optional)")
        _run(checklist.advance_status, auth, data["application"]["application_id"], target, reason)


def _convert(auth, data) -> None:
    if not data["ready"]:
        print("\nNot ready to enrol: " + "; ".join(data["issues"]))
        return
    if not _prompt_bool("Create the student record now?", default=False):
        return
    student_id = _run(checklist.convert, auth, data["application"]["application_id"])
    if student_id:
        print(f"\n✓ Converted to student {student_id}.")


def _audit(auth, data) -> None:
    for row in data["audit"][:30]:
        print(f"  {row['created_at'][:16]}  {row['actor']:<14}{row['action']:<26}{row['detail'][:50]}")
    if not data["audit"]:
        print("  (no casework recorded yet)")


_CHECKLIST_ACTIONS = {
    "1": _satisfy, "2": _waive, "3": _verify, "4": _add_condition, "5": _add_requirement,
    "6": _right_to_study, "7": _deposit, "8": _advance, "9": _convert, "10": _audit,
}


def run_conditions_documents_menu(auth) -> None:
    """List an application's conditions and documents and act on them."""
    if not casework.can_manage(auth):
        print("\nConditions & Documents is for admissions staff (approve_applications).")
        _pause()
        return
    aid = _pick_application()
    while aid:
        try:
            data = checklist.checklist(aid)
        except AdmissionsBoundaryError as exc:
            print(f"\n✗ {exc}")
            return
        _header("Conditions & Documents")
        _print_checklist(data)
        print("\n[1] Satisfy condition  [2] Waive condition  [3] Verify document")
        print("[4] Add condition  [5] Add required document  [6] Record right to study")
        print("[7] Record deposit  [8] Advance status  [9] Convert to Student")
        print("[10] Casework history  [0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "0":
            return
        action = _CHECKLIST_ACTIONS.get(choice)
        if action is None:
            print("Invalid choice.")
            continue
        action(auth, data)
        _pause()


# ── Postgraduate ───────────────────────────────────────────────────

def _print_pg(data: dict) -> None:
    print(f"\n  Type: {data['application_type']}  "
          f"({'research' if data['research'] else 'taught'})")
    print("\n  Referees:")
    for r in data["referees"] or []:
        print(f"    #{r['referee_id']:<5}{r['name'][:22]:<23}{r['email'][:28]:<29}"
              f"{r['relationship']:<13}{r['status']}")
    if not data["referees"]:
        print("    (none)")
    if data["research"]:
        current = [p for p in data["proposals"] if p["is_current"]]
        print(f"\n  Proposal: {current[0]['title'] if current else 'not uploaded'}")
        print("  Supervisors:")
        for n in data["nominations"]:
            print(f"    #{n['nomination_id']:<5}{n['supervisor_username']:<16}{n['role']:<11}"
                  f"{n['status']:<10}{(n['comment'] or '')[:40]}")
        if not data["nominations"]:
            print("    (none proposed)")
    print("  Interviews:")
    for i in data["interviews"]:
        print(f"    #{i['interview_id']:<5}{i['scheduled_at'][:16]:<18}{(i['panel'] or '')[:24]:<25}"
              f"{i['status']:<11}{i.get('outcome') or ''}")
    if not data["interviews"]:
        print("    (none)")
    print("\n  Outstanding: " + ("; ".join(data["issues"]) if data["issues"] else "none"))


def _pg_add_referee(auth, aid, data) -> None:
    name = _prompt("Referee name")
    email = _prompt("Referee e-mail")
    rel = _choose("Relationship", postgraduate.RELATIONSHIPS)
    _run(postgraduate.add_referee, auth, aid, name, email, rel)


def _pg_request(auth, aid, data) -> None:
    rid = _prompt_int("Referee id", allow_blank=False)
    result = _run(postgraduate.request_reference, auth, rid)
    if result:
        print(f"\n{result['message']}")


def _pg_record(auth, aid, data) -> None:
    rid = _prompt_int("Referee id", allow_blank=False)
    path = _prompt("Path of the reference file (blank = text only)")
    text = _prompt("Reference text / summary (optional)")
    _run(postgraduate.record_reference, auth, rid, text=text, file_path=path or None)


def _pg_withdraw(auth, aid, data) -> None:
    rid = _prompt_int("Referee id", allow_blank=False)
    _run(postgraduate.withdraw_referee, auth, rid, _prompt("Reason"))


def _pg_proposal(auth, aid, data) -> None:
    title = _prompt("Proposal title")
    summary = _prompt("Short summary (optional)")
    path = _prompt("Path of the proposal document")
    _run(postgraduate.add_proposal, auth, aid, title, summary=summary, file_path=path or None)


def _pg_nominate(auth, aid, data) -> None:
    staff = postgraduate.staff_directory()
    if not staff:
        print("\nNo staff accounts found.")
        return
    for s in staff:
        print(f"  {s['username']:<16}{s['first_name']} {s['last_name']} ({s['role']})")
    username = _prompt("Supervisor username")
    role = _choose("Role", postgraduate.SUPERVISOR_ROLES)
    _run(postgraduate.nominate_supervisor, auth, aid, username, role or "primary")


def _pg_interview(auth, aid, data) -> None:
    when = _prompt("Date and time (YYYY-MM-DD HH:MM)")
    panel = _prompt("Panel members")
    fmt = _prompt("Format (in person / online)", default="online")
    location = _prompt("Location or link (optional)")
    _run(postgraduate.schedule_interview, auth, aid, when, panel=panel, format=fmt,
         location=location)


def _pg_outcome(auth, aid, data) -> None:
    iid = _prompt_int("Interview id", allow_blank=False)
    outcome = _choose("Outcome", postgraduate.INTERVIEW_OUTCOMES)
    _run(postgraduate.record_interview_outcome, auth, iid, outcome, _prompt("Notes"))


def _pg_sponsor(auth, aid, data) -> None:
    for s in sponsors.sponsors_for_application(aid):
        print(f"  #{s['sponsor_record_id']}  {s['organisation']}  {s['status']}  "
              f"{s['covers']}  {s['amount'] or ''} {s['currency']}")
    org = _prompt("Sponsoring organisation (blank = cancel)")
    if not org:
        return
    _run(sponsors.record_sponsor, auth, aid, org,
         contact_name=_prompt("Contact name (optional)"),
         contact_email=_prompt("Contact e-mail (optional)"),
         sponsor_reference=_prompt("Sponsor's reference / PO (optional)"),
         covers=_choose("Covers", sponsors.COVERS) or "tuition",
         amount=_prompt_float("Amount (optional)"),
         valid_until=_prompt("Valid until (YYYY-MM-DD, optional)"),
         letter_path=_prompt("Path of the sponsor letter (optional)") or None,
         approve_sponsorship=_prompt_bool("Approve as sponsorship evidence?", default=False))


_PG_ACTIONS = {
    "1": _pg_add_referee, "2": _pg_request, "3": _pg_record, "4": _pg_withdraw,
    "5": _pg_proposal, "6": _pg_nominate, "7": _pg_interview, "8": _pg_outcome,
    "9": _pg_sponsor,
}


def run_postgraduate_menu(auth) -> None:
    """References, research proposal, supervisors, interview and sponsor."""
    if not casework.can_manage(auth):
        print("\nPostgraduate admissions is for admissions staff (approve_applications).")
        _pause()
        return
    aid = _pick_application()
    while aid:
        try:
            data = postgraduate.summary(aid)
        except AdmissionsBoundaryError as exc:
            print(f"\n✗ {exc}")
            return
        _header(f"Postgraduate — application {aid}")
        _print_pg(data)
        print("\n[1] Add referee  [2] Send reference request  [3] Record reference received")
        print("[4] Withdraw referee  [5] Upload research proposal  [6] Propose supervisor")
        print("[7] Schedule interview  [8] Record interview outcome  [9] Sponsor")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "0":
            return
        action = _PG_ACTIONS.get(choice)
        if action is None:
            print("Invalid choice.")
            continue
        if not data["postgraduate"] and choice != "9":
            print("\nThis is not a postgraduate application.")
        else:
            action(auth, aid, data)
        _pause()


# ── Supervisor's view ─────────────────────────────────────────────

def run_supervision_requests_menu(auth) -> None:
    """A member of staff accepts or declines PGR supervision requests."""
    while True:
        rows = postgraduate.supervision_requests(auth)
        _header("PGR Supervision Requests")
        if not rows:
            print("\nNo supervision requests addressed to you.")
            _pause()
            return
        for r in rows:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            print(f"  #{r['nomination_id']:<5}{name[:22]:<23}{(r['program_applied'] or '')[:24]:<25}"
                  f"{r['role']:<11}{r['status']:<10}{(r['proposal_title'] or '')[:30]}")
        nid = _prompt_int("\nRequest id to answer (blank = back)")
        if not nid:
            return
        row = next((r for r in rows if r["nomination_id"] == nid), None)
        if row and row.get("proposal_document_id"):
            path = casework.document_path(row["proposal_document_id"])
            print(f"  Proposal file: {path or 'missing from storage'}")
        accept = _prompt_bool("Accept this supervision?", default=True)
        comment = _prompt("Comment" + ("" if accept else " (required)"))
        status = _run(postgraduate.decide_supervision, auth, nid, accept, comment)
        if status:
            print(f"\n✓ Request {status}.")
        _pause()


__all__ = ["run_conditions_documents_menu", "run_postgraduate_menu",
           "run_supervision_requests_menu"]
