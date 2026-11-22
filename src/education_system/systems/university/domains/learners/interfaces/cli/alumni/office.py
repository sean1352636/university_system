"""Alumni office menus: records, consent and suppression, data requests,
the directory, newsletters, roles and the audit log."""

from __future__ import annotations

import json

from education_system.systems.university.application.alumni import access as aa
from education_system.systems.university.application.alumni import comms as ac
from education_system.systems.university.application.alumni import records as ar
from education_system.systems.university.domains.learners.interfaces.cli.alumni import _io

_LIST_COLS = [("alumni_id", "Alumni id", 12), ("first_name", "First", 14),
              ("last_name", "Last", 16), ("graduation_year", "Year", 6),
              ("email_address", "E-mail", 26), ("marketing_consent", "Consent", 9),
              ("do_not_contact", "DNC", 5)]


# ── records ─────────────────────────────────────────────────────────────


def list_alumni(ctx) -> None:
    search = _io.ask("Search (blank = all)")
    filt = _io.ask_choice("Filter", ["consented", "not_asked", "suppressed", "deceased", "all"],
                          "all")
    rows = _io.read(ar.listing, ctx.who, search or None, None if filt in ("", "all") else filt)
    if rows is not None:
        _io.table(rows, _LIST_COLS)


def register(ctx) -> None:
    sid = _io.ask("Student id (blank to add a graduate by hand)")
    data = {"graduation_year": _io.ask("Graduation year"),
            "degree_earned": _io.ask("Degree")}
    if not sid:
        data.update(alumni_id=_io.ask("New alumni id"), first_name=_io.ask("First name"),
                    last_name=_io.ask("Last name"), email_address=_io.ask("E-mail"))
    result = _io.run(ar.register, ctx.who, sid or None, data)
    if result:
        print(f"\n✅ Alumni record {result} created.")


def view(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    row = _io.read(ar.profile, ctx.who, alumni_id)
    if not row:
        return
    _io.section(f"{row.get('first_name') or ''} {row.get('last_name') or ''} ({alumni_id})")
    _io.show([(k.replace("_", " ").capitalize(), row.get(k)) for k in (
        "graduation_year", "degree_earned", "email_address", "phone", "current_employer",
        "job_title", "industry", "city", "country", "marketing_consent", "consent_source",
        "do_not_contact", "email_bounced", "deceased_at", "anonymised_at",
        "graduate_outcomes_due") if k in row])
    if row.get("transition"):
        print("\n  Transition steps:")
        for step in row["transition"]:
            print(f"    {'✓' if step['done'] else '·'} {step['step']}")
    if row.get("history"):
        print("\n  History:")
        for h in row["history"][-10:]:
            print(f"    {h['at']}  {h['actor'] or '—'}  {h['action']}")


def edit_profile(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    print("  Leave a field blank to keep it.")
    data = {k: v for k in ar.SELF_FIELDS if (v := _io.ask(k.replace("_", " ").capitalize()))}
    if _io.run(ar.update_profile, ctx.who, alumni_id, data):
        print("\n✅ Saved.")


def consent(ctx) -> None:
    alumni_id = _io.ask("Alumni id")
    agree = _io.ask_choice("Newsletters and appeals allowed", ["yes", "no"]) == "yes"
    source = _io.ask("How was this given (e.g. phone call 16 Oct)")
    if _io.run(ar.set_consent, ctx.who, alumni_id, agree, source):
        print("\n✅ Consent recorded.")


def do_not_contact(ctx) -> None:
    alumni_id = _io.ask("Alumni id")
    flag = _io.ask_choice("Do not contact", ["on", "off"]) == "on"
    if _io.run(ar.set_do_not_contact, ctx.who, alumni_id, flag, _io.ask("Reason")):
        print("\n✅ Saved.")


def deceased(ctx) -> None:
    alumni_id = _io.ask("Alumni id")
    if not _io.confirm(f"Record {alumni_id} as deceased (stops all contact, ends mentoring, "
                       "cancels pledges)?"):
        return
    if _io.run(ar.record_deceased, ctx.who, alumni_id, _io.ask("Date of death (YYYY-MM-DD)"),
               _io.ask("Source (e.g. letter from family)")):
        print("\n✅ Recorded.")


def bounced(ctx) -> None:
    if _io.run(ac.mark_bounced, ctx.who, _io.ask("Alumni id")):
        print("\n✅ Marked as bounced; no more mailings until the address changes.")


def export(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    data = _io.run(ar.export, ctx.who, alumni_id)
    if not data:
        return
    path = _io.ask("Save to file", f"alumni_{alumni_id}_data.json")
    if _io.write_file(path, json.dumps(data, indent=2, default=str)):
        print(f"\n✅ Everything held about {alumni_id} saved to {path}.")


def erase(ctx) -> None:
    alumni_id = _io.ask("Alumni id")
    if not _io.confirm(f"Erase (anonymise) {alumni_id}? This cannot be undone"):
        return
    result = _io.run(ar.erase, ctx.who, alumni_id, _io.ask("Reason / request reference"))
    if result:
        kept = result.get("gift_aid_kept_until")
        print("\n✅ Erased." + (f" Gift Aid declarations are kept until {kept} (HMRC)."
                               if kept else ""))


def data_requests(ctx) -> None:
    rows = _io.read(ar.data_requests, ctx.who, "open")
    if rows is not None:
        _io.table(rows, [("request_id", "Id", 6), ("alumni_id", "Alumni", 12),
                         ("kind", "Kind", 10), ("requested_by", "By", 14),
                         ("requested_at", "When", 20), ("note", "Note", 24)])


def transition(ctx) -> None:
    from education_system.systems.university.domains.learners.application.alumni_transition import (  # noqa: E501
        transition_to_alumni,
    )
    sid = _io.ask("Student / alumni id")
    try:
        added = transition_to_alumni(sid)
    except ValueError as exc:
        print(f"\n❌ {exc}")
        return
    print(f"\n✅ Transition steps recorded ({added} were missing).")


def records_menu(ctx) -> str:
    return _io.menu("Alumni records", [
        ("List / filter alumni", lambda: list_alumni(ctx)),
        ("View an alumnus", lambda: view(ctx)),
        ("Register an alumnus", lambda: register(ctx)),
        ("Edit a profile", lambda: edit_profile(ctx)),
        ("Record consent", lambda: consent(ctx)),
        ("Do-not-contact", lambda: do_not_contact(ctx)),
        ("Record a death", lambda: deceased(ctx)),
        ("Mark e-mail bounced", lambda: bounced(ctx)),
        ("Export someone's data (JSON)", lambda: export(ctx)),
        ("Erase a record", lambda: erase(ctx)),
        ("Open data requests", lambda: data_requests(ctx)),
        ("Catch up the alumni transition", lambda: transition(ctx)),
    ])


# ── directory ───────────────────────────────────────────────────────────


def directory_search(ctx) -> None:
    rows = _io.read(ar.search_directory, ctx.who, _io.ask("Name") or None,
                    _io.ask_int("Graduation year"), _io.ask("Industry") or None,
                    _io.ask("Country") or None,
                    skills=_io.ask("Skills (comma-separated, all must match)") or None,
                    location=_io.ask("Town or country") or None)
    if rows is not None:
        _io.table(rows, [("name", "Name", 22), ("graduation_year", "Year", 6),
                         ("degree_earned", "Degree", 16), ("current_employer", "Employer", 16),
                         ("skills", "Skills", 20), ("city", "Town", 12),
                         ("email_address", "E-mail", 22)])
        print("  Only alumni who chose to be listed appear, showing only what they chose. "
              "Skills are searched only where an alumnus shows their employment; a town "
              "only where they show their contact details.")


# ── newsletters ─────────────────────────────────────────────────────────


def _audience() -> dict:
    print("  Audience (blank = no filter):")
    return {"year_from": _io.ask("Graduated from year"), "year_to": _io.ask("Graduated to year"),
            "degree_contains": _io.ask("Degree contains"), "country": _io.ask("Country"),
            "chapter_id": _io.ask("Chapter id"),
            "donors_only": _io.confirm("Donors only?")}


def preview(ctx) -> None:
    result = _io.read(ac.preview, ctx.who, _audience())
    if result:
        _io.show([("Matching alumni", result["matching"]), ("Will be sent", result["will_send"])]
                 + [(f"Suppressed: {k}", v) for k, v in result["suppressed"].items()])


def create_newsletter(ctx) -> None:
    title = _io.ask("Title")
    print("Content (finish with a line containing only '.'):")
    lines = []
    while (line := input()) != ".":
        lines.append(line)
    nid = _io.run(ac.create, ctx.who, title, "\n".join(lines), _audience())
    if nid:
        print(f"\n✅ Draft newsletter {nid} saved. Preview and send it from this menu.")


def list_newsletters(ctx) -> None:
    rows = _io.read(ac.newsletters)
    if rows is not None:
        _io.table(rows, [("newsletter_id", "Id", 5), ("title", "Title", 30),
                         ("status", "Status", 8), ("sent_at", "Sent", 20),
                         ("sent_count", "Sent to", 8), ("suppressed_count", "Suppressed", 11)])


def send_newsletter(ctx) -> None:
    nid = _io.ask_int("Newsletter id")
    if nid is None or not _io.confirm("Send it now to every consenting, unsuppressed alumnus?"):
        return
    result = _io.run(ac.send, ctx.who, nid)
    if result:
        print(f"\n✅ Sent to {result['sent']}; {result['suppressed']} suppressed.")


def deliveries(ctx) -> None:
    rows = _io.read(ac.deliveries, _io.ask_int("Newsletter id"))
    if rows is not None:
        _io.table(rows, [("alumni_id", "Alumni", 14), ("outcome", "Outcome", 34),
                         ("at", "When", 20)])


def newsletter_menu(ctx) -> str:
    return _io.menu("Newsletters", [
        ("List newsletters", lambda: list_newsletters(ctx)),
        ("Preview an audience", lambda: preview(ctx)),
        ("Write a newsletter", lambda: create_newsletter(ctx)),
        ("Send a newsletter", lambda: send_newsletter(ctx)),
        ("Who got it (and who was suppressed)", lambda: deliveries(ctx)),
    ])


# ── roles and audit ─────────────────────────────────────────────────────


def roles_menu(ctx) -> str:
    def show_roles():
        rows = _io.read(aa.roles)
        if rows is not None:
            _io.table(rows, [("username", "Username", 18), ("role", "Role", 24),
                             ("granted_by", "By", 14), ("granted_at", "When", 20)])

    def grant():
        role = _io.ask_choice("Role", list(aa.ROLES))
        if role and _io.run(aa.grant_role, ctx.who, _io.ask("Staff username"), role):
            print("\n✅ Granted.")

    def revoke():
        role = _io.ask_choice("Role", list(aa.ROLES))
        if role and _io.run(aa.revoke_role, ctx.who, _io.ask("Staff username"), role):
            print("\n✅ Removed.")

    def audit_log():
        rows = _io.read(aa.recent_audit, ctx.who, 50)
        if rows is not None:
            _io.table(rows, [("at", "When", 20), ("actor", "Who", 14), ("entity", "What", 14),
                             ("entity_id", "Id", 12), ("action", "Action", 22)])

    return _io.menu("Roles and audit", [("Who holds alumni roles", show_roles),
                                        ("Give a role", grant), ("Remove a role", revoke),
                                        ("Audit log (latest 50)", audit_log)])
