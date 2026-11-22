"""IP and commercialisation menu."""

from __future__ import annotations

from education_system.systems.university.application.research import ip as rip

from ._io import ask, ask_choice, ask_int, form, history, menu, money, run, section, show, \
    table, write

_COLUMNS = [("disclosure_id", "ID", 5), ("reference", "Ref", 13), ("title", "Title", 34),
            ("ip_type", "Type", 10), ("status", "Status", 12), ("inventor_id", "Lead", 16)]
_FIELDS = [("title", "Title"), ("description", "Description"), ("ip_type", "Type", rip.TYPES),
           ("development_stage", "Development stage"), ("funding_source", "Funding source"),
           ("department", "Department"), ("project_id", "Research project ID")]


def _inventors(default=""):
    raw = ask("Inventors as 'username:percent, …' (must add up to 100)", default, required=True)
    people = []
    for part in raw.split(","):
        name, _sep, pct = part.strip().partition(":")
        people.append((name.strip(), pct.strip() or 0))
    return people


def _list(who):
    status = ask_choice("Status (blank = all)", rip.STATUSES, required=False)
    rows = run(rip.listing, who, status, ask("Search (blank = all)") or None)
    if rows is not None:
        table(rows, _COLUMNS)


def view(who, disclosure_id=None):
    rec = run(rip.record, who, disclosure_id or ask_int("Disclosure ID"))
    if rec is None:
        return
    show(f"{rec.get('reference')} — {rec['title']}", rec, [
        ("status", "Status"), ("ip_type", "Type"), ("department", "Department"),
        ("description", "Description"), ("review_comments", "Assessment"),
        ("filing_date", "Filed"), ("application_number", "Application no."),
        ("jurisdiction", "Jurisdiction")])
    section("Inventors", rec["inventors"], [("username", "Username", 18),
                                            ("contribution_percentage", "%", 6)])
    section("Licences", rec["licences"], [("license_id", "ID", 5), ("licensee_name", "Licensee",
                                                                     24),
                                          ("license_type", "Type", 14), ("status", "Status", 12)])
    for rev in rec["revenue"]:
        mine = f" (your share {money(rev['mine'])})" if "mine" in rev else ""
        print(f"  Income {rev['period']}: {money(rev['total_revenue'])} — inventors "
              f"{money(rev['inventor_share'])}{mine}")
    section("Deadlines", rec["deadlines"], [("deadline_id", "ID", 5), ("kind", "What", 40),
                                            ("due_date", "Due", 12), ("done_at", "Done", 20)])
    history(rec["history"])


def _new(who):
    data = {k: v for k, v in form(_FIELDS).items() if v not in (None, "")}
    did = write(rip.create, who, data, _inventors(f"{who.username}:100"), done=None)
    if did:
        print(f"  ✓ Disclosure {did} saved as a draft.")


def _edit(who):
    did = ask_int("Disclosure ID")
    data = form(_FIELDS, edit=True)
    people = _inventors() if ask("Change inventors? (y/n)", "n").lower().startswith("y") \
        else None
    write(rip.update, who, did, data, people)


def _submit(who):
    write(rip.submit, who, ask_int("Disclosure ID"), done="Submitted to technology transfer.")


def _assess(who):
    write(rip.assess, who, ask_int("Disclosure ID"), ask_choice("Decision", rip.DECISIONS),
          ask("Comments", required=True))


def _filing(who):
    write(rip.record_filing, who, ask_int("Disclosure ID"),
          ask("Filing date (YYYY-MM-DD)", required=True),
          ask("Application number", required=True), ask("Jurisdiction", "GB"),
          done="Filing recorded; patent deadlines set.")


def _deadlines(who):
    table(run(rip.deadlines_due, 365) or [], [("deadline_id", "ID", 5), ("reference", "Ref", 13),
                                              ("kind", "What", 40), ("due_date", "Due", 12)])
    choice = ask("(a)dd a deadline, (d)one, or Enter").lower()
    if choice.startswith("a"):
        write(rip.add_deadline, who, ask_int("Disclosure ID"), ask("What is due", required=True),
              ask("Due date", required=True), ask("Note"))
    elif choice.startswith("d"):
        write(rip.complete_deadline, who, ask_int("Deadline ID"), ask("Note"))


def _licence(who):
    did = ask_int("Disclosure ID")
    write(rip.add_licence, who, did, ask("Licensee", required=True),
          ask_choice("Licence type", rip.LICENCE_TYPES), ask("Start date", required=True),
          end_date=ask("End date (optional)") or None, royalty_rate=ask("Royalty %", "0"),
          annual_fee=ask("Annual fee £", "0"), territory=ask("Territory", "worldwide"),
          notes=ask("Notes"), done="Licence recorded.")


def _end_licence(who):
    write(rip.end_licence, who, ask_int("Licence ID"), ask("Reason", required=True))


def _income(who):
    write(rip.record_revenue, who, ask_int("Licence ID"), ask("Period (e.g. 2026)", required=True),
          ask("Income £", required=True), ask("Payment date (optional)") or None,
          done="Income recorded and shared out.")


def ip_menu(who):
    actions = [("List disclosures", _list), ("View a disclosure", view),
               ("New disclosure", _new), ("Edit a disclosure", _edit), ("Submit", _submit)]
    if who.is_tto:
        actions += [("Assess a disclosure", _assess), ("Record a filing", _filing),
                    ("Deadlines", _deadlines), ("Add a licence", _licence),
                    ("End a licence", _end_licence), ("Record licence income", _income)]
    menu("IP & COMMERCIALISATION", actions, who)
