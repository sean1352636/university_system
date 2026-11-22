"""Grants menu: costing, internal approval, submission, award, spend, reports."""

from __future__ import annotations

from education_system.systems.university.application.research import grants as rg

from ._io import ask, ask_choice, ask_int, ask_yes, form, history, menu, money, run, section, \
    show, table, write

_COLUMNS = [("application_id", "ID", 5), ("grant_name", "Grant", 30),
            ("funding_agency", "Funder", 14), ("principal_investigator_id", "PI", 16),
            ("application_deadline", "Deadline", 11), ("status", "Status", 18)]
_FIELDS = [("grant_name", "Grant name"), ("title", "Project title"),
           ("funding_agency", "Funder"), ("scheme", "Scheme"),
           ("application_deadline", "Funder deadline (YYYY-MM-DD)"),
           ("department", "Department (blank = the PI's)"),
           ("funder_rate", "Funder rate % (UKRI 80)"), ("project_id", "Research project ID"),
           ("co_investigators", "Co-investigators (usernames, comma-separated)"),
           ("ethics_required", "Needs ethics approval", "yes"),
           ("dmp_required", "Funder requires a data management plan", "yes")]


def _list(who):
    status = ask_choice("Status (blank = all)", rg.STATUSES, required=False)
    rows = run(rg.listing, who, status, ask("Search (blank = all)") or None)
    if rows is not None:
        table(rows, _COLUMNS)


def _show_costing(cost):
    section("Costing", cost["lines"], [("line_id", "Line", 6), ("category", "Category", 20),
                                       ("item", "Item", 30), ("amount", "Amount", 12)])
    print(f"  Full economic cost {money(cost['fec'])}  ·  price to funder "
          f"{money(cost['price'])} at {cost['rate']:.0f}%  ·  university contribution "
          f"{money(cost['university_contribution'])}")


def view(who, application_id=None):
    rec = run(rg.record, who, application_id or ask_int("Grant ID"))
    if rec is None:
        return
    show(f"{rec['grant_name']} ({rec['funding_agency']})", rec, [
        ("status", "Status"), ("principal_investigator_id", "PI"),
        ("co_investigators", "Co-investigators"), ("department", "Department"),
        ("application_deadline", "Funder deadline"), ("requested_amount", "Requested"),
        ("hod_approved_by", "Head of dept approval"), ("office_approved_by", "Office approval"),
        ("submission_date", "Submitted"), ("awarded_amount", "Awarded"),
        ("award_reference", "Award reference"), ("grant_period_start", "Starts"),
        ("grant_period_end", "Ends"), ("decision_note", "Note")])
    _show_costing(rec["costing"])
    b = rec["budget"]
    if b["lines"]:
        section("Budget", b["lines"], [("budget_id", "Line", 6), ("category", "Category", 20),
                                       ("approved_amount", "Approved", 12),
                                       ("spent_amount", "Spent", 12),
                                       ("remaining_amount", "Remaining", 12)])
        print(f"  Spent {b['spent_pct']}% of {money(b['total'])}; "
              f"{b['time_pct'] if b['time_pct'] is not None else '—'}% of the time elapsed")
    section("Reports", rec["reports"], [("report_id", "ID", 5), ("kind", "Kind", 10),
                                        ("due_date", "Due", 12), ("submitted_at", "Submitted",
                                                                  20)])
    if rec["blockers"]:
        print("\n  Before the award can be accepted: " + "; ".join(rec["blockers"]))
    history(rec["history"])


def _new(who):
    data = {k: v for k, v in form(_FIELDS).items() if v not in (None, "")}
    if who.is_office:
        data["principal_investigator_id"] = ask("PI username (blank = you)") or None
    gid = write(rg.create, who, data, done=None)
    if gid:
        print(f"  ✓ Draft application {gid} started. Add its costs next.")


def _edit(who):
    write(rg.update, who, ask_int("Grant ID"), form(_FIELDS, edit=True))


def _costs(who):
    gid = ask_int("Grant ID")
    while True:
        cost = run(rg.costing, gid)
        if cost is None:
            return
        _show_costing(cost)
        choice = ask("(a)dd a line, (r)emove a line, or Enter to finish").lower()
        if choice.startswith("a"):
            write(rg.add_cost_line, who, gid,
                  ask_choice("Category", list(rg.COST_CATEGORIES.items())),
                  ask("Item", required=True), ask("Amount (£)", required=True), done=None)
        elif choice.startswith("r"):
            write(rg.remove_cost_line, who, ask_int("Line"), done=None)
        else:
            return


def _request(who):
    write(rg.request_approval, who, ask_int("Grant ID"), done="Sent for approval.")


def _waiting(who):
    rows = run(rg.approvals_for, who) or []
    table(rows, _COLUMNS)
    if not rows or not ask_yes("Act on one"):
        return
    gid = ask_int("Grant ID")
    if ask_yes("Approve it"):
        write(rg.approve, who, gid, ask("Note (optional)"), done="Approved.")
    else:
        write(rg.return_for_changes, who, gid, ask("What needs changing", required=True),
              done="Returned to the PI.")


def _submitted(who):
    write(rg.mark_submitted, who, ask_int("Grant ID"),
          ask("Submitted on (blank = today)") or None, done="Marked submitted.")


def _outcome(who):
    gid = ask_int("Grant ID")
    outcome = ask_choice("Outcome", ("awarded", "rejected"))
    extra = {}
    if outcome == "awarded":
        extra = {"amount": ask("Amount awarded (£)", required=True),
                 "start": ask("Start date", required=True), "end": ask("End date", required=True),
                 "award_reference": ask("Funder's reference")}
    write(rg.record_outcome, who, gid, outcome, note=ask("Note (optional)"), **extra)


def _accept(who):
    write(rg.accept_award, who, ask_int("Grant ID"),
          done="Award accepted: budget set up, reports scheduled, Finance told.")


def _spend(who):
    gid = ask_int("Grant ID")
    b = run(rg.budget, gid)
    if b is None:
        return
    table(b["lines"], [("budget_id", "Line", 6), ("category", "Category", 20),
                       ("remaining_amount", "Remaining", 12)])
    line = ask_int("Budget line")
    over = who.is_office and ask_yes("Allow overspend", False)
    write(rg.record_spend, who, line, ask("Amount (£)", required=True),
          ask("Date spent (YYYY-MM-DD)", required=True), ask("Description", required=True),
          allow_overspend=over, done="Spend recorded.")


def _reports(who):
    gid = ask_int("Grant ID")
    table(run(rg.reports, gid) or [], [("report_id", "ID", 5), ("kind", "Kind", 10),
                                         ("due_date", "Due", 12), ("submitted_at", "Submitted",
                                                                   20)])
    choice = ask("(a)dd a report, (s)ubmit one, or Enter").lower()
    if choice.startswith("a"):
        write(rg.add_report, who, gid, ask_choice("Kind", rg.REPORT_KINDS),
              ask("Due date", required=True), ask("Note"))
    elif choice.startswith("s"):
        write(rg.submit_report, who, ask_int("Report ID"), ask("Note"), done="Submitted.")


def _close(who):
    write(rg.close, who, ask_int("Grant ID"), done="Grant closed.")


def _withdraw(who):
    write(rg.withdraw, who, ask_int("Grant ID"), ask("Reason", required=True))


def _pipeline(who):
    p = run(rg.pipeline, who)
    if p is None:
        return
    print("\n  " + "  ".join(f"{k.replace('_', ' ')}: {v}" for k, v in p["by_status"].items()
                              if v))
    print(f"  Success rate: {p['success_rate'] if p['success_rate'] is not None else '—'}%")
    rows = [{"department": d, **v} for d, v in p["by_department"].items()]
    table(rows, [("department", "Department", 22), ("applications", "Apps", 6),
                 ("requested", "Requested £", 14), ("awarded", "Awarded £", 14)])


def grants_menu(who):
    actions = [("List grants", _list), ("View a grant", view), ("New application", _new),
               ("Edit a draft", _edit), ("Costing (add / remove lines)", _costs),
               ("Ask for internal approval", _request),
               ("Waiting for my approval", _waiting), ("Mark submitted to the funder",
                                                        _submitted),
               ("Record spend", _spend), ("Reports", _reports), ("Withdraw", _withdraw),
               ("Pipeline summary", _pipeline)]
    if who.is_office:
        actions += [("Record funder decision", _outcome), ("Accept an award", _accept),
                    ("Close a grant", _close)]
    menu("RESEARCH GRANTS", actions, who)
