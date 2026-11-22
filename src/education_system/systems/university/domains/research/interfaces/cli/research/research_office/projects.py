"""Projects menu: the register, teams, links and data management plans."""

from __future__ import annotations

from education_system.systems.university.application.research import integrity as ri
from education_system.systems.university.application.research import projects as rp

from ._io import ask, ask_choice, ask_int, ask_yes, form, history, menu, run, section, show, \
    table, write

_COLUMNS = [("project_id", "ID", 5), ("reference", "Ref", 12), ("project_title", "Title", 34),
            ("principal_investigator_id", "PI", 16), ("department", "Department", 18),
            ("status", "Status", 10)]
_FIELDS = [("project_title", "Title"), ("project_description", "Description"),
           ("department", "Department (blank = the PI's)"), ("project_type", "Type", rp.TYPES),
           ("start_date", "Start date (YYYY-MM-DD)"), ("end_date", "End date (YYYY-MM-DD)"),
           ("funding_source", "Funding source"), ("needs_ethics", "Needs ethics approval", "yes")]
_PLAN_FIELDS = [("data_types", "Data to be collected"), ("storage", "Storage and security"),
                ("sharing", "Sharing and access"), ("repository", "Repository"),
                ("retention_years", "Retention (years)"),
                ("personal_data", "Involves personal data", "yes"),
                ("dpia_reference", "DPIA reference")]


def _list(who):
    status = ask_choice("Status (blank = all)", rp.STATUSES, required=False)
    rows = run(rp.listing, who, status, ask("Search (blank = all)") or None)
    if rows is not None:
        table(rows, _COLUMNS)


def view(who, project_id=None):
    project_id = project_id or ask_int("Project ID")
    rec = run(rp.record, who, project_id)
    if rec is None:
        return
    show(f"{rec.get('reference') or rec['project_id']} — {rec['project_title']}", rec, [
        ("principal_investigator_id", "Principal investigator"), ("department", "Department"),
        ("project_type", "Type"), ("status", "Status"), ("start_date", "Start"),
        ("end_date", "End"), ("funding_source", "Funding"), ("needs_ethics", "Needs ethics"),
        ("ethics_approval_status", "Ethics approval"), ("project_description", "Description")])
    section("Team", rec["team"], [("username", "Username", 16), ("role", "Role", 20),
                                  ("join_date", "Joined", 12), ("is_active", "Active", 7)])
    section("Ethics", rec["ethics"], [("review_id", "ID", 5), ("reference", "Ref", 18),
                                      ("status", "Status", 20), ("approval_expiry_date",
                                                                 "Expires", 12)])
    section("Grants", rec["grants"], [("application_id", "ID", 5), ("grant_name", "Grant", 30),
                                      ("status", "Status", 18)])
    section("Outputs", rec["outputs"], [("publication_id", "ID", 5), ("title", "Title", 44)])
    section("IP", rec["ip"], [("disclosure_id", "ID", 5), ("reference", "Ref", 14),
                              ("title", "Title", 30), ("status", "Status", 12)])
    section("Data management plans", rec["data_plans"], [("plan_id", "ID", 5),
                                                         ("version", "Version", 8),
                                                         ("status", "Status", 18)])
    section("Declared interests", rec["interests"], [("username", "Who", 16), ("kind", "Kind", 14),
                                                     ("counterpart", "With", 24),
                                                     ("status", "Status", 12)])
    history(rec["history"])


def _new(who):
    data = form(_FIELDS)
    if who.is_office:
        data["principal_investigator_id"] = ask("PI username (blank = you)") or None
    pid = write(rp.create, who, {k: v for k, v in data.items() if v not in (None, "")},
                done=None)
    if pid:
        print(f"  ✓ Project {pid} registered.")


def _edit(who):
    pid = ask_int("Project ID")
    write(rp.update, who, pid, form(_FIELDS, edit=True))


def _status(who):
    pid = ask_int("Project ID")
    status = ask_choice("New status", rp.STATUSES)
    write(rp.set_status, who, pid, status, ask("Reason"))


def _add_member(who):
    pid = ask_int("Project ID")
    username = ask("Username", required=True)
    role = ask_choice("Role", rp.TEAM_ROLES)
    write(rp.add_member, who, pid, username, role, ask("Contribution % (optional)") or None)


def _remove_member(who):
    pid = ask_int("Project ID")
    write(rp.remove_member, who, pid, ask("Username", required=True))


def _link(who):
    pid = ask_int("Project ID")
    kind = ask_choice("Link a", ("grant", "output", "ip", "ethics"))
    write(rp.link, who, kind, ask_int("Record ID"), pid)


def _change_pi(who):
    pid = ask_int("Project ID")
    write(rp.transfer_pi, who, pid, ask("New PI username", required=True),
          ask("Reason", required=True))


def _plans(who):
    pid = ask_int("Project ID")
    rows = run(ri.plans, pid)
    if rows is not None:
        table(rows, [("plan_id", "ID", 5), ("version", "Version", 8), ("status", "Status", 18),
                     ("data_types", "Data", 24), ("storage", "Storage", 20),
                     ("review_note", "Review note", 30)])


def _draft_plan(who):
    pid = ask_int("Project ID")
    print("  Blank answers keep what the latest version says.")
    plan = write(ri.draft_plan, who, pid, form(_PLAN_FIELDS, edit=True), done=None)
    if plan:
        print(f"  ✓ Draft plan {plan} saved.")


def _submit_plan(who):
    write(ri.submit_plan, who, ask_int("Plan ID"), done="Submitted for review.")


def _review_plan(who):
    waiting = run(ri.plans_to_review, who) or []
    table(waiting, [("plan_id", "ID", 5), ("project_title", "Project", 34),
                    ("version", "Version", 8), ("submitted_at", "Submitted", 20)])
    if not waiting:
        return
    plan = ask_int("Plan ID")
    approve = ask_yes("Approve")
    write(ri.review_plan, who, plan, approve, "" if approve else ask("What needs changing",
                                                                    required=True))


def projects_menu(who):
    actions = [("List projects", _list), ("View a project", view), ("Register a project", _new),
               ("Edit a project", _edit), ("Change status", _status),
               ("Add team member", _add_member), ("Remove team member", _remove_member),
               ("Link a grant / output / IP / ethics record", _link),
               ("Data management plans", _plans), ("Draft / edit data management plan",
                                                   _draft_plan),
               ("Submit data management plan", _submit_plan)]
    if who.is_office:
        actions += [("Change principal investigator", _change_pi),
                    ("Review data management plans", _review_plan)]
    menu("RESEARCH PROJECTS", actions, who)
