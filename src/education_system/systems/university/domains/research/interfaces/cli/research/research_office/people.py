"""Integrity (declarations of interest), People and Dashboard menus."""

from __future__ import annotations

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import integrity as ri
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.application.research import reminders as rm

from ._io import ask, ask_choice, ask_int, ask_yes, form, menu, run, show, table, write

_DECL = [("declaration_id", "ID", 5), ("username", "Who", 16), ("kind", "Kind", 13),
         ("counterpart", "With", 22), ("declared_at", "Declared", 20), ("status", "Status", 10)]


# ── integrity ───────────────────────────────────────────────────────────


def _mine(who):
    table(run(ri.declarations, who, True) or [], _DECL)


def _declare(who):
    kind = ask_choice("Kind of interest", [k for k in ri.KINDS if k != "none"])
    write(ri.declare, who, kind, counterpart=ask("Who it is with", required=True),
          description=ask("Description", required=True), value=ask("Value £ (optional)") or None,
          project_id=ask("Research project ID (optional)") or None, done="Declared.")


def _declare_none(who):
    if ask_yes("Declare that you have no interests to declare"):
        write(ri.declare, who, "none", done="Nil return recorded.")


def _review(who):
    rows = run(ri.to_review, who) or []
    table(rows, _DECL + [("description", "Description", 30)])
    if not rows or not ask_yes("Review one"):
        return
    did = ask_int("Declaration ID")
    outcome = ask_choice("Outcome", ri.REVIEW_OUTCOMES)
    plan = ask("Management plan", required=True) if outcome == "managed" else ""
    write(ri.review, who, did, outcome, plan, done="Reviewed.")


def _overdue(who):
    table(run(ri.overdue) or [], [("username", "Username", 16), ("name", "Name", 28),
                                  ("last_declared", "Last declared", 20)])


def integrity_menu(who):
    actions = [("My declarations", _mine), ("Declare an interest", _declare),
               ("Declare no interests", _declare_none),
               ("Declarations to review", _review)]
    if who.is_office:
        actions.append(("Who is overdue", _overdue))
    menu("RESEARCH INTEGRITY", actions, who)


# ── people ──────────────────────────────────────────────────────────────


def _directory(who):
    table(run(rp.directory, ask("Search (blank = all)") or None) or [],
          [("username", "Username", 16), ("name", "Name", 26), ("department", "Department", 20),
           ("uoa", "UoA", 8), ("research_interests", "Interests", 30)])


def _profile(who, username=None):
    username = username or ask("Username", who.username)
    p = run(rp.profile, username)
    if p is None:
        return
    show(f"{p['name']} ({username})", p, [
        ("department", "Department"), ("research_interests", "Interests"),
        ("orcid_id", "ORCID"), ("google_scholar_id", "Google Scholar"),
        ("scopus_id", "Scopus"), ("researchgate_url", "ResearchGate"),
        ("outputs", "Outputs"), ("projects", "Projects"), ("uoa", "REF UoA")])


def _edit_profile(who):
    username = ask("Username", who.username) if who.is_office else who.username
    _profile(who, username)
    fields = [("research_interests", "Research interests"), ("orcid_id", "ORCID iD"),
              ("google_scholar_id", "Google Scholar ID"), ("scopus_id", "Scopus ID"),
              ("researchgate_url", "ResearchGate URL")]
    write(rp.save_profile, who, username, form(fields, edit=True), done="Profile saved.")


def _roles(who):
    table(run(ra.roles) or [], [("username", "Username", 16), ("role", "Role", 20),
                               ("scope", "Scope", 18), ("granted_by", "By", 14)])
    choice = ask("(g)rant a role, (r)evoke one, or Enter").lower()
    if choice[:1] not in ("g", "r"):
        return
    username = ask("Username", required=True)
    role = ask_choice("Role", list(ra.ROLES.items()))
    scope = ask("Department / UoA (for heads of department and REF leads)") \
        if role in ra.SCOPED else ""
    fn = ra.grant_role if choice.startswith("g") else ra.revoke_role
    write(fn, who, username, role, scope)


def people_menu(who):
    actions = [("Research directory", _directory), ("View a profile", _profile),
               ("Edit my research profile", _edit_profile)]
    if who.is_office:
        actions.append(("Research roles", _roles))
    menu("PEOPLE", actions, who)


# ── dashboard ───────────────────────────────────────────────────────────


def _attention(who):
    items = run(rm.attention, who) or []
    if not items:
        print("  Nothing needs your attention.")
    for item in items:
        ref = f"  [{item['ref'][0]} {item['ref'][1]}]" if item.get("ref") else ""
        print(f"  {item['area']:<10} {item['title']}{ref}")
        if item.get("detail"):
            print(f"             {item['detail']}")


def _run_reminders(who):
    result = run(rm.run, write=True, force=ask_yes("Send again even if already run today"))
    if result:
        print(f"  ✓ Reminders sent: {result['reminded']}; ethics approvals expired: "
              f"{result['expired']}")


def _pgr(who):
    try:
        print(f"  ✓ PGR escalations created: {rm.run_pgr_escalations()}")
    except Exception as exc:
        print(f"  ✗ {exc}")


def dashboard_menu(who):
    actions = [("What needs my attention", _attention)]
    if who.is_office:
        actions += [("Run today's reminders", _run_reminders),
                    ("Escalate overdue PGR items", _pgr)]
    menu("RESEARCH DASHBOARD", actions, who)
