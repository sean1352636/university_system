"""Graduation office menus not tied to one ceremony: eligibility, holds,
certificate names, conferrals (in absentia, review after a board reopens,
revocation, replacement certificates), print jobs, verification,
graduation roles and the audit log.
"""

from __future__ import annotations

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.domains.progression.interfaces.cli.graduation._io import (
    ask,
    ask_choice,
    ask_int,
    confirm,
    run,
    section,
    show,
    table,
)


def eligibility(cli, student_id=None) -> None:
    section("Can this student graduate?")
    sid = student_id or ask("Student id")
    if not sid:
        return
    r = run(ge.check, sid)
    if not r:
        return
    award = r["award"] or {}
    show([("Student", f"{r['student_name']} ({sid})"), ("Status", r["status"]),
          ("Award", award.get("award_name")), ("Classification", award.get("classification")),
          ("Credits", f"{r['credits_earned']:.0f} of {r['credits_required']} "
                      f"({r['credits_source']})"),
          ("Certificate name", r["certificate_name"] +
           ("" if r["name_confirmed"] else "  (not confirmed)")),
          ("Conferred", (r["conferral"] or {}).get("certificate_number")),
          ("Eligible", "YES" if r["eligible"] else "no")])
    for b in r["blockers"]:
        print(f"  ✗ {b}")
    for w in r["warnings"]:
        print(f"  ! {w}")


# ── holds and names ─────────────────────────────────────────────────────


def holds(cli) -> None:
    section("Open graduation holds")
    table(run(ge.all_open_holds, write=False) or [],
          [("hold_id", "Id", 6), ("student_id", "Student", 12), ("kind", "Kind", 12),
           ("reason", "Reason", 36), ("placed_by", "By", 12), ("placed_at", "On", 20)])


def place_hold(cli) -> None:
    section("Place a graduation hold")
    sid = ask("Student id")
    kind = ask_choice("Kind", ge.HOLD_KINDS, "appeal")
    if sid and kind and run(ge.place_hold, cli.who, sid, kind, ask("Reason")) is not None:
        print("\n✓ Hold placed.")


def release_hold(cli) -> None:
    section("Release a hold")
    hid = ask_int("Hold id")
    if hid and run(ge.release_hold, cli.who, hid, ask("Why it is released")) is not None:
        print("\n✓ Released.")


def set_name(cli) -> None:
    section("Set the certificate name")
    sid = ask("Student id")
    if not sid:
        return
    current = run(ge.certificate_name, sid, write=False)
    if current:
        print(f"  Now: {current['certificate_name']}"
              + ("  (confirmed)" if current["confirmed"] else "  (not confirmed)"))
    name = ask("Name for the certificate")
    if name and run(ge.set_name, cli.who, sid, name,
                    ask("Evidence seen (e.g. passport, deed poll)")) is not None:
        print("\n✓ Name set.")


# ── conferrals ──────────────────────────────────────────────────────────


def confer(cli) -> None:
    section("Confer in absentia")
    sid = ask("Student id")
    if not sid:
        return
    eligibility(cli, sid)
    delivery = ask_choice("Certificate delivery", ("post", "collect"), "post")
    address = ask("Postal address (blank = the address on record)") if delivery == "post" else ""
    if not confirm("Confer the award now?"):
        return
    result = run(gc.confer, cli.who, sid, mode="in_absentia", delivery=delivery,
                 address=address or None, conferral_date=ask("Conferral date (blank = today)")
                 or None)
    if result:
        gc.after_commit(result)
        print(f"\n✓ Conferred. Certificate {result['certificate_number']}, verification code "
              f"{result['verification_code']}.")


def conferrals(cli) -> None:
    section("Conferrals")
    rows = run(gc.listing, cli.who, status=ask("Status (blank = all)") or None,
               search=ask("Search (blank = all)") or None, write=False) or []
    table(rows, [("conferral_id", "Id", 6), ("student_id", "Student", 12),
                 ("certificate_name", "Name", 24), ("award_name", "Award", 26),
                 ("classification", "Class", 18), ("conferral_date", "Date", 12),
                 ("mode", "Mode", 12), ("status", "Status", 11)])


def view(cli) -> None:
    cid = ask_int("Conferral id")
    row = run(gc.record, cli.who, cid, write=False) if cid else None
    if not row:
        return
    show([(k.replace("_", " ").capitalize(), row.get(k)) for k in (
        "student_id", "certificate_name", "award_name", "classification", "academic_year",
        "conferral_date", "mode", "ceremony_id", "certificate_number", "verification_code",
        "status", "status_reason", "replaces_conferral_id")])
    for job in row["print_jobs"]:
        print(f"  print job {job['job_id']}: {job['kind']} {job['delivery']} {job['status']}")
    for h in row["history"]:
        print(f"  {h['at']}  {h['actor'] or ''}  {h['action']}  {h['detail'] or ''}")


def review(cli) -> None:
    section("Review a suspended conferral (after the assessment board)")
    cid = ask_int("Conferral id")
    if not cid:
        return
    result = run(gc.review_suspended, cli.who, cid)
    if not result:
        return
    if result.get("reinstated"):
        print("\n✓ The award stands unchanged; the conferral is reinstated.")
    else:
        gc.after_commit(result)
        print(f"\n✓ Reissued against the new award: certificate "
              f"{result['certificate_number']}.")


def revoke(cli) -> None:
    section("Revoke an award")
    cid = ask_int("Conferral id")
    if cid and confirm("Revoke this award? Its certificate and credential stop verifying.") and \
            run(gc.revoke, cli.who, cid, ask("Reason")) is not None:
        print("\n✓ Revoked.")


def replacement(cli) -> None:
    section("Replacement certificate")
    cid = ask_int("Conferral id")
    if not cid:
        return
    delivery = ask_choice("Delivery", ("post", "collect"), "post")
    address = ask("Postal address") if delivery == "post" else None
    waive = confirm(f"Waive the £{gc.REPLACEMENT_FEE:.2f} fee?")
    result = run(gc.replace_certificate, cli.who, cid, ask("Reason"), delivery=delivery,
                 address=address, waive_fee=waive)
    if result:
        gc.charge_replacement_fee(result, cli.who.username)
        print(f"\n✓ New certificate {result['certificate_number']} (fee £{result['fee']:.2f}). "
              "The old certificate no longer verifies.")


def print_jobs(cli) -> None:
    section("Certificate print jobs")
    rows = run(gc.print_jobs, ask("Status (blank = all)") or None, write=False) or []
    table(rows, [("job_id", "Job", 6), ("student_id", "Student", 12),
                 ("certificate_name", "Name", 22), ("certificate_number", "Certificate", 20),
                 ("kind", "Kind", 12), ("delivery", "Delivery", 10), ("status", "Status", 11),
                 ("fee", "Fee", 6)])


def move_job(cli) -> None:
    section("Move a print job on")
    jid = ask_int("Job id")
    status = ask_choice("New status", gc.JOB_STATUSES) if jid else ""
    if status and run(gc.set_job_status, cli.who, jid, status, ask("Note")) is not None:
        print("\n✓ Updated.")


def verify(cli) -> None:
    section("Verify a certificate")
    ref = ask("Certificate number or verification code")
    r = run(gc.verify, ref) if ref else None
    if r:
        print(f"\n  {'VALID' if r['valid'] else 'NOT VALID'} — {r['message']}")
        if r.get("name"):
            show([("Name", r["name"]), ("Award", r["award"]),
                  ("Classification", r["classification"]),
                  ("Conferred", r["conferral_date"]),
                  ("In absentia", "yes" if r["in_absentia"] else "no")])


# ── roles and audit ─────────────────────────────────────────────────────


def roles(cli) -> None:
    section("Graduation roles")
    table(run(ga.roles, write=False) or [],
          [("username", "Username", 20), ("role", "Role", 20), ("granted_by", "By", 14),
           ("granted_at", "On", 20)])
    action = ask_choice("Grant, remove or leave", ("grant", "remove", "leave"), "leave")
    if action in ("grant", "remove"):
        user = ask("Username")
        role = ask_choice("Role", tuple(ga.ROLES))
        fn = ga.grant_role if action == "grant" else ga.revoke_role
        if user and role and run(fn, cli.who, user, role) is not None:
            print("\n✓ Done.")


def audit(cli) -> None:
    section("Recent graduation activity")
    table(run(ga.recent_audit, 60, write=False) or [],
          [("at", "When", 20), ("actor", "Who", 14), ("entity", "What", 16),
           ("entity_id", "Id", 12), ("action", "Action", 22)])
