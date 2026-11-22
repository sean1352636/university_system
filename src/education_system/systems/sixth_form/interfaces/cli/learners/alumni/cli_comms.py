"""Alumni CLI: communications, consent, channels, leavers, portal.

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

from ._helpers import (
    COMM_CHANNELS,
    COMM_STATUSES,
    CONSENT_SCOPES,
    ValidationError,
    _UserAbort,
    _date,
)
from education_system.systems.sixth_form.domain.learners.alumni import (
    comms as alumni_comms,
    compliance as alumni_compliance,
    linking as alumni_linking,
    records as alumni_records,
)
from ._helpers import (  # noqa: F401
    _input,
    _pause,
    _pick_alumnus,
    _pick_from,
    _yes_no,
)


# ── Communications / consent / channels / leavers / portal ───────

def comms_flow() -> None:
    print("\n═══ Communications Log ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = alumni_comms.list_communications(a.alumni_id)
        print(f"\n  Comms for #{a.alumni_id} {a.full_name}  "
              f"(bounce_count={a.bounce_count}):")
        if not rows:
            print("    (none)")
        for c in rows[:25]:
            when = (c.sent_at or c.received_at or c.created_at or ""
                      )[:16]
            print(f"    #{c.message_id:<4} {when:<16}  "
                  f"[{c.channel:<18}] {c.status:<10} "
                  f"{(c.subject or '')[:50]}")
        print("\n    a) Add    d) Delete    "
               "b) Record bounce   cb) Clear bounces   0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                alumni_comms.add_communication(a.alumni_id, {
                    "date":     _input("Date (YYYY-MM-DD)",
                                          default=_date.today().isoformat()),
                    "channel":  _pick_from("Channel",
                                             list(COMM_CHANNELS),
                                             default="Email"),
                    "staff_id": _input("Staff id"),
                    "subject":  _input("Subject"),
                    "summary":  _input("Summary"),
                    "status":   _pick_from("Status",
                                             list(COMM_STATUSES),
                                             default="Sent"),
                })
            elif choice == "d":
                cid = int(_input("Delete #id", allow_empty=False))
                if alumni_comms.delete_communication(cid):
                    print("    ✓ Deleted")
            elif choice == "b":
                hard = _yes_no("Hard bounce?", default=True)
                reason = _input("Reason / notes")
                a = alumni_comms.record_bounce(a.alumni_id, hard=hard,
                                         reason=reason or None)
                print(f"    bounce_count now {a.bounce_count} "
                       f"(status={a.status})")
            elif choice == "cb":
                a = alumni_comms.clear_bounces(a.alumni_id)
                print("    ✓ Cleared")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def send_email_flow() -> None:
    print("\n═══ Send Email ═══")
    print("  Templates support {first_name} {last_name} "
           "{preferred_name} {leaving_year}\n")
    print("  1) Single alumnus")
    print("  2) Filtered bulk send")
    try:
        which = _input("Which?", default="1")
        subject = _input("Subject", allow_empty=False)
        print("  Body (end with a single '.' on its own line):")
        lines: list[str] = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        body = "\n".join(lines)
        staff = _input("Logged-by staff id") or None
        if which == "2":
            year = _input("Leaving year (blank = any)") or None
            dest = _input("Destination type (blank = any)") or None
            sent, skipped = alumni_comms.send_email_bulk(
                {"leaving_year": year, "destination_type": dest,
                 "status": "Active"},
                subject, body, staff_id=staff)
            print(f"\n  ✓ Handed to the outbox={sent}  skipped={skipped}"
                  "\n    (the outbox sends, holds or retries each one "
                  "according to the e-mail delivery mode)")
        else:
            a = _pick_alumnus()
            ok = alumni_comms.send_email_to_alumnus(
                a.alumni_id, subject, body, staff_id=staff)
            mark = "✗" if ok.status == "Failed" else "✓"
            print(f"\n  {mark} {alumni_comms.delivery_note(ok)}")
    except _UserAbort:
        print("\n  Cancelled.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def channel_prefs_flow() -> None:
    print("\n═══ Channel Preferences ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    p = alumni_comms.get_channel_prefs(a.alumni_id)
    print(f"\n  Current for #{a.alumni_id} {a.full_name}:")
    print(f"    Email : {'✓' if p.opt_in_email else '✗'}")
    print(f"    Post  : {'✓' if p.opt_in_post  else '✗'}")
    print(f"    Phone : {'✓' if p.opt_in_phone else '✗'}")
    print(f"    SMS   : {'✓' if p.opt_in_sms   else '✗'}")
    try:
        new = alumni_comms.update_channel_prefs(
            a.alumni_id,
            opt_in_email=_yes_no("Email?",  default=p.opt_in_email),
            opt_in_post= _yes_no("Post?",   default=p.opt_in_post),
            opt_in_phone=_yes_no("Phone?",  default=p.opt_in_phone),
            opt_in_sms=  _yes_no("SMS?",    default=p.opt_in_sms),
        )
        print(f"\n  ✓ Saved.  Legacy opt_in_contact = "
               f"{'on' if any([new.opt_in_email, new.opt_in_post, new.opt_in_phone, new.opt_in_sms]) else 'off'}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def consent_flow() -> None:
    print("\n═══ GDPR Consent ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = alumni_compliance.list_consents(a.alumni_id)
        print(f"\n  Consents for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for c in rows:
            state = ("withdrawn " + c.withdrawn_at[:10]
                       if c.withdrawn_at else "active")
            print(f"    #{c.consent_id:<3} {c.scope:<14} {c.version}  "
                  f"granted {c.granted_at[:10]}  [{state}]")
        print("\n    g) Grant    w) Withdraw    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "g":
                scope = _pick_from("Scope", list(CONSENT_SCOPES),
                                     default=CONSENT_SCOPES[0])
                source = _input("Source (e.g. form, email, in person)")
                notes  = _input("Notes")
                alumni_compliance.grant_consent(a.alumni_id, scope,
                                     source=source or None,
                                     notes=notes or None)
            elif choice == "w":
                cid = int(_input("Withdraw consent #id",
                                    allow_empty=False))
                notes = _input("Notes (optional)")
                alumni_compliance.withdraw_consent(cid, notes=notes or None)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def unarchived_leavers_flow() -> None:
    print("\n═══ Unarchived Leavers ═══")
    rows = alumni_linking.find_unarchived_leavers()
    if not rows:
        print("\n  None found.")
        _pause()
        return
    print(f"\n  {len(rows)} student(s) look like leavers without an "
           "alumni row:\n")
    print(f"  {'Student':<10}  {'Name':<26}  {'UCAS':<6} "
           f"{'Exam':<5}  Destination")
    print("  " + "-" * 92)
    for r in rows:
        print(f"  {r.student_id:<10}  {r.full_name[:26]:<26}  "
              f"{str(r.ucas_cycle_year or '—'):<6} "
              f"{str(r.last_exam_year or '—'):<5}  "
              f"{(r.final_destination or '—')[:40]}")
    print(f"\n  {len(rows)} flagged. Use 'Archive student' "
           "to convert one.")
    _pause()


def retention_flow() -> None:
    print("\n═══ Retention ═══")
    try:
        years = int(_input("Years since last update", default="7"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    rows = alumni_compliance.find_retention_candidates(years=years)
    if not rows:
        print(f"\n  No alumni inactive for {years}+ years.")
        _pause()
        return
    print(f"\n  {len(rows)} candidate(s):\n")
    for a in rows:
        print(f"    #{a.alumni_id:<4} {a.full_name:<26} "
              f"[{a.status}]  updated {a.updated_at[:10]}")
    print("\n    A) Anonymise one    D) Delete one    0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "a":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Anonymise #{aid}? (destructive)",
                          default=False):
                alumni_compliance.anonymise_alumnus(aid)
                print("    ✓ Anonymised")
        elif choice == "d":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Delete #{aid}? (irreversible)",
                          default=False):
                alumni_records.delete_alumnus(aid)
                print("    ✓ Deleted")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as ex:
        print(f"  ✗ {ex}")
    _pause()


def portal_token_flow() -> None:
    print("\n═══ Self-Service Portal Token ═══")
    try:
        a = _pick_alumnus()
        ttl = int(_input("TTL days", default="14"))
    except (_UserAbort, ValueError):
        print("\n  Cancelled.")
        return
    try:
        tok = alumni_compliance.create_portal_token(a.alumni_id, ttl_days=ttl)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Token created for #{a.alumni_id} ({a.full_name})")
    print(f"    Token   : {tok.token}")
    print(f"    Expires : {tok.expires_at}")
    print("\n  Share this token with the alumnus so they can "
           "self-update their profile.")
    _pause()
