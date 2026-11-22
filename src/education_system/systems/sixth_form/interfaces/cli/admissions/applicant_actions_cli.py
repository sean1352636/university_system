"""Admissions CLI: the per-applicant actions menu."""

from __future__ import annotations

import json
import os
from datetime import date as _date
from datetime import timedelta as _timedelta
from typing import Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    admissions_comms as comms,
    record_safety,
    references as refs,
    status_rules,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    DOCUMENT_TYPES,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    REQUIRED_DOCS,
    _UserAbort,
    _age,
    _fresh,
    _input,
    _open_path,
    _pause,
    _pick_applicant,
    _pick_from,
    _pick_subject,
    _run_submenu,
    _send_to_printer,
    _yes,
    _attempt,
    _cli_user,
    _show_messages,
)
from education_system.systems.sixth_form.interfaces.cli.admissions import (
    applicant_profile_cli as profile,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.decisions_cli import (
    _reopen,
    defer_applicant,
    offer_with_capacity_check,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.interviews_cli import (
    _capture_scorecard,
)



# ── Per-applicant operations (items 12–20, 38, 49, 50) ────────────

def timeline_flow(a: Applicant) -> None:
    print(f"\n═══ Timeline — {a.applicant_id} ═══")
    events = data.list_events(a.applicant_id)
    if not events:
        print("  (no events)")
    for e in events:
        print(f"    {e.at}  {e.actor or 'system':<14} [{e.kind}]  {e.detail}")
    _pause()

def notes_flow(a: Applicant) -> None:
    print(f"\n═══ Notes — {a.applicant_id} ═══")
    for n in data.list_notes(a.applicant_id):
        print(f"    {n.at}  —  {n.author or 'unknown'}")
        print(f"      {n.body}")
    if _yes("\n  Add a note?"):
        author = _input("Author")
        body = _input("Note", allow_empty=False)
        data.add_note(a.applicant_id, body, author=author or None)
        print("  ✓ Note added.")
    _pause()


def documents_flow(a: Applicant) -> None:
    while True:
        print(f"\n═══ Documents — {a.applicant_id} ═══")
        docs = data.list_documents(a.applicant_id)
        for d in docs:
            print(f"    {d.id:>4})  [{d.doc_type}]  {d.label or '—'}")
            print(f"           {d.path}")
        if not docs:
            print("  (no documents)")
        choice = _input("\n  (a)dd, (r)emove, or Enter to go back",
                         default="")
        if choice.lower() == "a":
            try:
                path = _input("File path", allow_empty=False)
                doc_type = _pick_from("Type", list(DOCUMENT_TYPES))
                label = _input("Label (optional)")
                data.add_document(a.applicant_id, path, doc_type=doc_type,
                                  label=label or None)
                print("  ✓ Document attached.")
            except (ValidationError, _UserAbort) as e:
                print(f"  ✗ {e}")
        elif choice.lower() == "r":
            did = _input("Document id to remove", allow_empty=False)
            if did.isdigit() and data.remove_document(int(did)):
                print("  ✓ Removed.")
            else:
                print("  ✗ Not found.")
        else:
            return


def reference_flow(a: Applicant) -> None:
    """Reference status comes from the reference tracker: request, send,
    chase and correct the referee through it (the status follows)."""
    while True:
        a = _fresh(a)
        print(f"\n═══ Reference — {a.applicant_id} ═══")
        print(f"    Status  : {a.reference_status}"
              f"  (tracker says {refs.tracker_status(a.applicant_id) or '—'})")
        rows = refs.list_references(applicant_id=a.applicant_id)
        for r in rows:
            print(f"    #{r.reference_id} {r.referee_name} "
                  f"({r.referee_email or 'no e-mail'}) [{r.status}] due "
                  f"{r.effective_due or '—'}"
                  f"{' OVERDUE' if r.is_overdue else ''}"
                  f"{' chases=' + str(r.chase_count) if r.chase_count else ''}")
        if not rows:
            print(f"    Referee on form: {a.reference_name or '—'} "
                  f"({a.reference_contact or '—'}) — no tracked request")
        print("\n    1) Request & e-mail referee   2) E-mail an unsent "
              "request   3) Chase (e-mail)\n    4) Edit referee   "
              "5) Re-sync status   Enter) back")
        choice = _input("  Select", default="")
        if not choice:
            return
        open_rows = [r for r in rows if r.is_open]
        if choice == "1":
            ok, r = _attempt(
                refs.request_reference, a.applicant_id,
                referee_name=_input("Referee name",
                                    default=a.reference_name or "",
                                    allow_empty=False),
                referee_role=_input("Role") or None,
                referee_school=_input("School",
                                      default=a.previous_school or "") or None,
                referee_email=_input("E-mail",
                                     default=a.reference_contact or "") or None,
                referee_phone=_input("Phone") or None,
                send=_yes("E-mail the request now?", default="y"))
            if ok:
                print(f"  ✓ Reference #{r.reference_id} [{r.status}]")
                _show_log_tail(a.applicant_id, 1)
        elif choice in ("2", "3", "4") and not (open_rows or rows):
            print("  ✗ No tracked reference — use 1 first.")
        elif choice == "2":
            r = _pick_ref([x for x in open_rows if x.status == "Requested"])
            if r:
                ok, m = _attempt(comms.send_reference_request, r.reference_id)
                if ok:
                    _show_messages([m])
        elif choice == "3":
            r = _pick_ref(open_rows)
            if r:
                ok, m = _attempt(comms.send_reference_chase, r.reference_id)
                if ok:
                    _show_messages([m])
        elif choice == "4":
            r = _pick_ref(rows)
            if r:
                ok, r2 = _attempt(
                    refs.update_referee, r.reference_id,
                    referee_name=_input("Name", default=r.referee_name),
                    referee_role=_input("Role",
                                        default=r.referee_role or "") or None,
                    referee_school=_input(
                        "School", default=r.referee_school or "") or None,
                    referee_email=_input(
                        "E-mail", default=r.referee_email or "") or None,
                    referee_phone=_input(
                        "Phone", default=r.referee_phone or "") or None,
                    due_date=_input("Due date",
                                    default=r.due_date or "") or None)
                if ok:
                    print(f"  ✓ Referee updated (#{r2.reference_id})")
        elif choice == "5":
            ok, n = _attempt(refs.sync_reference_status, a.applicant_id)
            if ok:
                print(f"  ✓ {n} record(s) re-synced")


def _pick_ref(rows: list) -> "refs.Reference | None":
    if not rows:
        print("  ✗ No matching reference.")
        return None
    labels = [f"#{r.reference_id} {r.referee_name} [{r.status}]" for r in rows]
    return rows[labels.index(_pick_from("Reference", labels))]


def _show_log_tail(aid: str, n: int) -> None:
    ok, rows = _attempt(comms.communications_log, aid)
    for r in (rows or [])[:n]:
        print(f"    {r['kind']} → {r['to_address'] or '—'}: {r['label']}")

def scorecard_flow(a: Applicant) -> None:
    print(f"\n═══ Interview Scorecard — {a.applicant_id} ═══")
    score = data.get_interview_score(a.applicant_id)
    if score:
        print(f"    Current avg: {score.average}  "
              f"(rec: {score.recommendation or '—'})")
    try:
        vals = _capture_scorecard(a)
        data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Scorecard saved.")
    _pause()


def gcse_check_flow(a: Applicant) -> None:
    print(f"\n═══ GCSE Check — {a.applicant_id} ═══")
    print(f"    Predicted  : {a.predicted_gcses or '—'}")
    print(f"    Conditions : {a.offer_conditions or '—'}")
    concern = reports.gcse_concern(a.predicted_gcses, a.offer_conditions)
    print(f"\n    {'⚠ ' + concern if concern else '✓ No obvious concern.'}")
    _pause()


def offer_letter_flow(a: Applicant) -> None:
    print(f"\n═══ Offer Letter — {a.applicant_id} ═══")
    if not a.offer_type:
        print("  ✗ No offer has been made yet.")
        _pause()
        return
    letter = reports.render_offer_letter(a.applicant_id)
    print("\n" + "\n".join("    " + ln for ln in letter.splitlines()))
    if _yes("\n  E-mail it to the applicant?"):
        parents = _yes("  Copy to parents/carers?")
        ok, msgs = _attempt(comms.send_offer_letter, a.applicant_id,
                            include_parents=parents)
        if ok:
            _show_messages(msgs)
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"offer_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(letter)
        print(f"  ✓ Saved to {path}")
    _pause()

def email_flow(a: Applicant) -> None:
    print(f"\n═══ Email — {a.applicant_id} ═══")
    subject, body = reports.render_status_email(a.applicant_id)
    print(f"\n    Subject: {subject}\n")
    for ln in body.splitlines():
        print(f"    {ln}")
    if _yes("\n  Send it now (through the outbox)?"):
        parents = _yes("  Copy to parents/carers who receive "
                       "correspondence?")
        ok, msgs = _attempt(comms.send_status_email, a.applicant_id,
                            include_parents=parents)
        if ok:
            _show_messages(msgs)
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"email_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"Subject: {subject}\n\n{body}")
        print(f"  ✓ Saved to {path}")
    _pause()

def open_student_flow(a: Applicant) -> None:
    print(f"\n═══ Linked Student — {a.applicant_id} ═══")
    if not a.converted_student_id:
        print("  ✗ This applicant has not been enrolled.")
        _pause()
        return
    from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
        students as _students,
    )
    st = _students.get_student(a.converted_student_id)
    if st is None:
        print(f"  ✗ Student {a.converted_student_id} not found.")
    else:
        print(f"    Student ID : {st.student_id}")
        print(f"    Name       : {st.first_name} {st.last_name}")
        print(f"    Email      : {getattr(st, 'email', '—')}")
        print(f"    Subjects   : {getattr(st, 'subject_1', '—')}, "
              f"{getattr(st, 'subject_2', '—')}, "
              f"{getattr(st, 'subject_3', '—')}")
    _pause()


def find_duplicates_flow(a: Applicant) -> None:
    print(f"\n═══ Possible Duplicates — {a.applicant_id} ═══")
    dups = data.find_duplicates(email=a.email, first_name=a.first_name,
                                 last_name=a.last_name, dob=a.dob,
                                 exclude_id=a.applicant_id)
    if not dups:
        print("  ✓ None found.")
    for d in dups:
        print(f"    {d.applicant_id} — {d.full_name} "
              f"({d.email or 'no email'})")
    _pause()


def follow_up_flow(a: Applicant) -> None:
    new = not a.follow_up
    data.set_follow_up(a.applicant_id, new)
    print(f"\n  ✓ Follow-up flag {'set' if new else 'cleared'} for "
          f"{a.applicant_id}")
    _pause()


def manage_subjects_flow(a: Applicant) -> None:
    print(f"\n═══ Subjects — {a.applicant_id} ═══")
    subs = list(a.subjects)
    print(f"    Current: {', '.join(subs) if subs else '—'}")
    new = [
        _pick_subject("Subject 1", default=a.subject_1),
        _pick_subject("Subject 2", default=a.subject_2),
        _pick_subject("Subject 3", default=a.subject_3),
    ]
    try:
        data.update_applicant(a.applicant_id, {
            "subject_1": new[0], "subject_2": new[1], "subject_3": new[2]})
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Subjects updated.")
    _pause()


def gdpr_export_flow(a: Applicant) -> None:
    print(f"\n═══ GDPR Export — {a.applicant_id} ═══")
    payload = json.dumps(reports.gdpr_export(a.applicant_id), indent=2,
                          default=str)
    path = _input("Save JSON to path",
                   default=f"gdpr_{a.applicant_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"  ✓ Exported to {path}")
    _pause()


def gdpr_erase_flow(a: Applicant) -> None:
    """Erasure needs two people: this records the request; someone else
    with the governance permission approves (and that erases)."""
    print(f"\n═══ GDPR Erasure Request — {a.applicant_id} ═══")
    print("  Erasure permanently deletes the applicant and ALL related "
          "records/files.\n  It needs a second person with the governance "
          "permission to approve it.")
    reason = _input("Reason (e.g. the data subject's request)",
                    allow_empty=False)
    if not _yes("  Record the erasure request?"):
        print("  Cancelled.")
        return
    ok, req = _attempt(record_safety.request_erasure, a.applicant_id,
                       reason=reason)
    if ok:
        print(f"  ✓ Request #{req.request_id} recorded [{req.status}] — "
              "awaiting approval by someone else (Governance → erasure "
              "requests).")
    _pause()


# ── Per-applicant action menu (item 7 — context-menu analogue) ────

def applicant_actions_flow() -> None:
    print("\n═══ Applicant Actions ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    actions: list[tuple[str, Callable[[], None]]] = [
        ("View record",        lambda: _view_inline(_fresh(a))),
        ("Timeline",           lambda: timeline_flow(_fresh(a))),
        ("Notes",              lambda: notes_flow(_fresh(a))),
        ("Documents / photo",  lambda: documents_flow(_fresh(a))),
        ("Reference status",   lambda: reference_flow(_fresh(a))),
        ("Interview scorecard", lambda: scorecard_flow(_fresh(a))),
        ("GCSE check",         lambda: gcse_check_flow(_fresh(a))),
        ("Manage subjects",    lambda: manage_subjects_flow(_fresh(a))),
        ("Toggle follow-up",   lambda: follow_up_flow(_fresh(a))),
        ("Missing documents",  lambda: missing_docs_flow(_fresh(a))),
        ("Preview / open document", lambda: document_preview_flow(_fresh(a))),
        ("Add several documents", lambda: bulk_upload_docs_flow(_fresh(a))),
        ("Communications log", lambda: communication_log_flow(_fresh(a))),
        ("Score vs cohort",    lambda: score_comparison_flow(_fresh(a))),
        ("─" * 6,              lambda: None),
        ("Quick standard offer", lambda: quick_offer_flow(_fresh(a))),
        ("Offer status / expiry", lambda: offer_expiry_flow(_fresh(a))),
        ("Offer letter",       lambda: offer_letter_flow(_fresh(a))),
        ("Print offer letter", lambda: print_offer_letter_flow(_fresh(a))),
        ("Email applicant",    lambda: email_flow(_fresh(a))),
        ("Custom email",       lambda: custom_email_flow(_fresh(a))),
        ("Open student record", lambda: open_student_flow(_fresh(a))),
        ("Find duplicates",    lambda: find_duplicates_flow(_fresh(a))),
        ("GDPR export",        lambda: gdpr_export_flow(_fresh(a))),
        ("GDPR erase (request — two-person)",
         lambda: gdpr_erase_flow(_fresh(a))),
        ("─" * 6,              lambda: None),
        *[(label, (lambda f=fn: f(_fresh(a))))
          for label, fn in profile.ACTIONS],
        ("Reopen (closed application)", lambda: _reopen_one(_fresh(a))),
        ("Defer to a later intake", lambda: _defer_one(_fresh(a))),
        ("Archive", lambda: _archive_one(_fresh(a))),
    ]
    _run_submenu(f"Actions — {a.applicant_id} {a.full_name}", actions)


def _view_inline(a: Applicant) -> None:
    print()
    print(f"    {a.applicant_id}  {a.full_name}  [{a.status}]")
    print(f"    Email {a.email or '—'} · Phone {a.phone or '—'} · "
          f"Age {_age(a.dob) if _age(a.dob) is not None else '—'}")
    print(f"    Subjects: {', '.join(a.subjects) or '—'}")
    print(f"    Reference: {a.reference_status} · Follow-up: "
          f"{'yes' if a.follow_up else 'no'}")
    if a.offer_type:
        print(f"    Offer: {a.offer_type} "
              f"(expires {a.offer_expiry or '—'}) — {a.offer_conditions or '—'}")
    _pause()


# ══ Per-applicant flows (GUI items 36–45) ═════════════════════════

def custom_email_flow(a: Applicant) -> None:
    """Item 36 — compose a custom email from the status template."""
    print(f"\n═══ Custom Email — {a.applicant_id} ═══")
    try:
        subject, body = reports.render_status_email(a.applicant_id)
    except Exception:  # noqa: BLE001
        subject, body = "", f"Dear {a.first_name},\n\n"
    print(f"  To: {a.email or '(no email on file)'}")
    subject = _input("Subject", default=subject)
    print("  Enter body lines; end with a single '.' on its own line:")
    print("  (template shown below — retype or edit)")
    for line in body.splitlines():
        print(f"    | {line}")
    lines: list[str] = []
    while True:
        try:
            line = input("  | ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == ".":
            break
        lines.append(line)
    final_body = "\n".join(lines) if lines else body
    composed = f"To: {a.email or ''}\nSubject: {subject}\n\n{final_body}\n"
    print("\n  ── Composed email ──\n")
    print(composed)
    if _yes("Send it now (through the outbox)?"):
        parents = _yes("Copy to parents/carers who receive correspondence?")
        ok, msgs = _attempt(comms.send_to_applicant, a.applicant_id, subject,
                            final_body, include_parents=parents)
        if ok:
            _show_messages(msgs)
    if _yes("Save to a file?"):
        path = _input("Save to path", default=f"email_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(composed)
        print(f"  ✓ Saved to {path}")
    _pause()


def offer_expiry_flow(a: Applicant) -> None:
    """Item 37 — offer expiry countdown, set/extend, remind."""
    print(f"\n═══ Offer Status — {a.applicant_id} ═══")
    if not a.offer_type or a.offer_type == "Not Offered":
        print("  No offer has been made.")
        _pause()
        return
    if a.offer_expiry:
        try:
            exp = _date.fromisoformat(a.offer_expiry[:10])
            days = (exp - _date.today()).days
            state = ("EXPIRED" if days < 0 else f"{days} day(s) remaining")
        except ValueError:
            state = "unknown"
        print(f"  Offer {a.offer_type} expires {a.offer_expiry} — {state}")
    else:
        print(f"  Offer {a.offer_type} has no expiry date.")
    if _yes("Set / extend the expiry date?"):
        default = (_date.today() + _timedelta(days=14)).isoformat()
        new = _input("Expiry date (YYYY-MM-DD, blank clears)",
                     default=a.offer_expiry or default)
        try:
            data.set_offer_expiry(a.applicant_id, new.strip() or None)
            print("  ✓ Expiry updated.")
        except ValidationError as e:
            print(f"  ✗ {e}")
    if a.offer_expiry and a.status == "Offer Made" and _yes(
            "E-mail an expiry reminder?"):
        parents = _yes("Copy to parents/carers?")
        ok, msgs = _attempt(comms.send_offer_expiry_warning, a.applicant_id,
                            include_parents=parents)
        if ok:
            _show_messages(msgs)
    _pause()


def print_offer_letter_flow(a: Applicant) -> None:
    """Item 39 — send the offer letter to the printer."""
    print(f"\n═══ Print Offer Letter — {a.applicant_id} ═══")
    if not a.offer_type:
        print("  No offer has been made yet.")
        _pause()
        return
    try:
        _send_to_printer(reports.render_offer_letter(a.applicant_id))
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Could not print: {e}")
        _pause()
        return
    print("  ✓ Offer letter sent to the default printer.")
    _pause()


def document_preview_flow(a: Applicant) -> None:
    """Item 40 — inspect / open a document with the OS handler."""
    print(f"\n═══ Document Preview — {a.applicant_id} ═══")
    docs = data.list_documents(a.applicant_id)
    if not docs:
        print("  (no documents)")
        _pause()
        return
    for i, d in enumerate(docs, 1):
        print(f"    {i:>2}) [{d.doc_type}]  {d.label or '—'}  —  {d.path}")
    raw = _input(f"  Open which #1..{len(docs)} (blank = none)", default="")
    if raw.isdigit() and 1 <= int(raw) <= len(docs):
        d = docs[int(raw) - 1]
        print(f"  Opening {d.path} …")
        try:
            _open_path(d.path)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {e}")
    _pause()


def bulk_upload_docs_flow(a: Applicant) -> None:
    """Item 41 — attach several documents at once."""
    print(f"\n═══ Add Several Documents — {a.applicant_id} ═══")
    raw = _input("File paths (comma-separated)", allow_empty=False)
    paths = [p.strip() for p in raw.split(",") if p.strip()]
    if not paths:
        print("  ✗ No paths given.")
        _pause()
        return
    try:
        doc_type = _pick_from("Type for all", list(DOCUMENT_TYPES))
    except _UserAbort:
        return
    added, fail = 0, []
    for p in paths:
        try:
            data.add_document(a.applicant_id, p, doc_type=doc_type)
            added += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{os.path.basename(p)}: {e}")
    print(f"\n  ✓ Added {added} document(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def missing_docs_flow(a: Applicant) -> None:
    """Item 42 — required-document checklist."""
    print(f"\n═══ Required Documents — {a.applicant_id} ═══")
    present = {d.doc_type for d in data.list_documents(a.applicant_id)}
    for req in REQUIRED_DOCS:
        ok = req in present
        print(f"    {'✓' if ok else '✗'}  {req}")
    missing = [r for r in REQUIRED_DOCS if r not in present]
    print(f"\n  {len(missing)} missing." if missing else "\n  All present.")
    _pause()


def score_comparison_flow(a: Applicant) -> None:
    """Item 43 — interview score vs the cohort average."""
    print(f"\n═══ Score vs Cohort — {a.applicant_id} ═══")
    mine = data.get_interview_score(a.applicant_id)
    if mine is None or mine.average is None:
        print("  This applicant has no interview score yet.")
        _pause()
        return
    averages = []
    for other in data.list_applicants():
        s = data.get_interview_score(other.applicant_id)
        if s is not None and s.average is not None:
            averages.append(s.average)
    cohort = round(sum(averages) / len(averages), 1) if averages else 0
    rank = sum(1 for v in averages if v > mine.average) + 1
    print(f"    Applicant average : {mine.average}")
    print(f"    Cohort average    : {cohort}  (n={len(averages)})")
    print(f"    Difference        : {round(mine.average - cohort, 1):+}")
    print(f"    Rank              : {rank} of {len(averages)}")
    _pause()


def communication_log_flow(a: Applicant) -> None:
    """Item 44 — e-mails sent (with their real delivery state), notes and
    communication events."""
    print(f"\n═══ Communications — {a.applicant_id} ═══")
    ok, msgs = _attempt(comms.communications_log, a.applicant_id)
    print("\n  E-mails:")
    for r in msgs or []:
        print(f"    {r['created_at'][:16]}  {r['kind']:<18} to "
              f"{r['recipient_role']} {r['to_address'] or '—'}  "
              f"\"{r['subject']}\"  — {r['label']}"
              f"  (by {r['sent_by'] or '—'})")
    if ok and not msgs:
        print("    (none sent)")
    entries: list[tuple[str, str, str]] = []
    for n in data.list_notes(a.applicant_id):
        entries.append((n.at, "note", f"{n.author or 'unknown'}: {n.body}"))
    for e in data.list_events(a.applicant_id):
        if e.kind in ("note", "email", "offer", "status", "reference"):
            entries.append((e.at, e.kind, f"{e.detail} ({e.actor or '—'})"))
    entries.sort(key=lambda t: t[0], reverse=True)
    print("\n  Notes & events:")
    if not entries:
        print("    (none recorded)")
    for at, kind, detail in entries:
        print(f"    {at}  [{kind}]  {detail}")
    _pause()

def quick_offer_flow(a: Applicant) -> None:
    """Item 45 — one-step standard conditional offer."""
    print(f"\n═══ Quick Standard Offer — {a.applicant_id} ═══")
    conditions = "Achieve at least grade 6 in your chosen subjects."
    if not _yes(f"Make a standard {DEFAULT_OFFER_TYPE} offer "
                f"(conditions: {conditions})?"):
        print("\n  Cancelled.")
        return
    if offer_with_capacity_check(a.applicant_id, offer_type=DEFAULT_OFFER_TYPE,
                                 conditions=conditions,
                                 decided_by=_cli_user()):
        print("  ✓ Offer made.")
    _pause()


def _reopen_one(a: Applicant) -> None:
    if a.status not in status_rules.REOPENABLE:
        print(f"  {a.applicant_id} is {a.status}; only a declined, rejected "
              "or withdrawn application can be reopened.")
    else:
        _reopen(a)
    _pause()


def _defer_one(a: Applicant) -> None:
    defer_applicant(a)
    _pause()


def _archive_one(a: Applicant) -> None:
    reason = _input("Reason for archiving", allow_empty=False)
    ok, _ = _attempt(record_safety.archive_applicant, a.applicant_id,
                     reason=reason)
    if ok:
        print(f"  ✓ {a.applicant_id} archived (restore from Applicants → "
              "Archived).")
    _pause()
