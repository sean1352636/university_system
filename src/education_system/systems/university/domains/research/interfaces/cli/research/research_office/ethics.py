"""Ethics menu: applications, supervisor endorsement, reviews and decisions."""

from __future__ import annotations

from education_system.systems.university.application.research import ethics as et

from ._io import ask, ask_choice, ask_int, ask_yes, form, history, menu, run, section, show, \
    table, write

_COLUMNS = [("review_id", "ID", 5), ("reference", "Ref", 18), ("title", "Title", 32),
            ("risk_level", "Risk", 7), ("status", "Status", 20),
            ("approval_expiry_date", "Expires", 12)]
_FIELDS = [("title", "Study title"), ("category", "Category", et.CATEGORIES),
           ("risk_level", "Risk level", et.RISK_LEVELS), ("summary", "Summary of the study"),
           ("participants", "Participants and recruitment"),
           ("data_handling", "Data handling"), ("start_date", "Start date (YYYY-MM-DD)"),
           ("end_date", "End date (YYYY-MM-DD)"), ("project_id", "Research project ID"),
           ("notes", "Notes")]


def _list(who):
    status = ask_choice("Status (blank = all)", et.STATUSES, required=False)
    rows = run(et.listing, who, status, ask("Search (blank = all)") or None)
    if rows is not None:
        table(rows, _COLUMNS)


def view(who, review_id=None):
    rec = run(et.record, who, review_id or ask_int("Application ID"))
    if rec is None:
        return
    show(f"{rec.get('reference')} — {rec.get('title')}", rec, [
        ("status", "Status"), ("kind", "Kind"), ("route", "Review route"),
        ("reviews_needed", "Reviews needed"), ("applicant_id", "Applicant"),
        ("principal_investigator_id", "Principal investigator"),
        ("supervisor_id", "Supervisor"), ("category", "Category"), ("risk_level", "Risk"),
        ("start_date", "Start"), ("end_date", "End"), ("summary", "Summary"),
        ("participants", "Participants"), ("data_handling", "Data handling"),
        ("decision_date", "Decided"), ("reviewer_comments", "Comments"),
        ("approval_expiry_date", "Approval expires")])
    section("Reviews", rec["allocations"], [("allocation_id", "ID", 5),
                                            ("reviewer", "Reviewer", 16),
                                            ("status", "Status", 12),
                                            ("recommendation", "Recommendation", 24),
                                            ("comments", "Comments", 36)])
    section("Conditions", rec["conditions"], [("condition_id", "ID", 5),
                                              ("condition_text", "Condition", 44),
                                              ("met_at", "Met", 20)])
    section("Amendments and renewals", rec["children"], [("review_id", "ID", 5),
                                                         ("reference", "Ref", 22),
                                                         ("kind", "Kind", 12),
                                                         ("status", "Status", 18)])
    history(rec["history"])


def _new(who):
    data = {k: v for k, v in form(_FIELDS).items() if v not in (None, "")}
    if who.is_student:
        data["supervisor_id"] = ask("Supervisor's username", required=True)
    rid = write(et.create, who, data, done=None)
    if rid:
        print(f"  ✓ Draft application {rid} saved. Submit it when it is complete.")


def _edit(who):
    write(et.update, who, ask_int("Application ID"), form(_FIELDS, edit=True))


def _submit(who):
    write(et.submit, who, ask_int("Application ID"), done="Submitted.")


def _withdraw(who):
    write(et.withdraw, who, ask_int("Application ID"), ask("Reason", required=True))


def _close(who):
    write(et.close, who, ask_int("Application ID"), done="Study closed.")


def _amend(who):
    rid = write(et.amend, who, ask_int("Approved application ID"),
                ask("Describe the change", required=True), done=None)
    if rid:
        print(f"  ✓ Amendment {rid} started as a draft — edit and submit it.")


def _renew(who):
    rid = write(et.renew, who, ask_int("Approved application ID"),
                ask("New end date (YYYY-MM-DD)", required=True), done=None)
    if rid:
        print(f"  ✓ Renewal {rid} started as a draft — submit it.")


def _endorse(who):
    rid = ask_int("Application ID")
    approve = ask_yes("Endorse it")
    write(et.endorse, who, rid, approve, "" if approve else ask("What needs changing",
                                                                required=True))


def _condition(who):
    write(et.meet_condition, who, ask_int("Condition ID"), ask("Evidence", required=True))


def _my_reviews(who):
    rows = run(et.my_reviews, who) or []
    table(rows, [("allocation_id", "Alloc", 6), ("reference", "Ref", 18), ("title", "Title", 34),
                 ("risk_level", "Risk", 7), ("allocated_at", "Allocated", 20)])
    if not rows or not ask_yes("Act on one"):
        return
    alloc = ask_int("Allocation ID")
    if ask_yes("Do you have a conflict of interest"):
        write(et.declare_conflict, who, alloc, ask("Describe the conflict", required=True))
        return
    write(et.submit_review, who, alloc, ask_choice("Recommendation", et.RECOMMENDATIONS),
          ask("Comments", required=True), done="Review submitted.")


def _queue(who):
    queue = run(et.chair_queue) or {"to_allocate": [], "to_decide": []}
    section("Needing reviewers", queue["to_allocate"],
            [("review_id", "ID", 5), ("reference", "Ref", 18), ("risk_level", "Risk", 7),
             ("allocated", "Have", 5), ("needed", "Need", 5)])
    section("Ready for a decision", queue["to_decide"],
            [("review_id", "ID", 5), ("reference", "Ref", 18), ("title", "Title", 40)])


def _allocate(who):
    write(et.allocate, who, ask_int("Application ID"), ask("Reviewer username", required=True),
          done="Reviewer allocated.")


def _decide(who):
    rid = ask_int("Application ID")
    decision = ask_choice("Decision", et.DECISIONS)
    comments = ask("Comments to the applicant", required=True)
    conditions = []
    if decision == "approve_with_conditions":
        print("  Enter conditions, one per line; blank to finish.")
        while text := ask("Condition"):
            conditions.append(text)
    expiry = ask("Approval expiry (blank = study end date)") if decision.startswith(
        "approve") else None
    write(et.decide, who, rid, decision, comments, conditions, expiry or None,
          done="Decision recorded.")


def ethics_menu(who):
    actions = [("List applications", _list), ("View an application", view),
               ("New application", _new), ("Edit a draft", _edit), ("Submit", _submit),
               ("Withdraw", _withdraw), ("Request an amendment", _amend),
               ("Request a renewal", _renew), ("Mark a condition met", _condition)]
    if who.is_staff:
        actions += [("Close a finished study", _close), ("Endorse a student's application",
                                                          _endorse),
                    ("My reviews (review / declare conflict)", _my_reviews)]
    if who.chairs_ethics:
        actions += [("Chair's queue", _queue), ("Allocate a reviewer", _allocate),
                    ("Decide an application", _decide)]
    menu("RESEARCH ETHICS", actions, who)
