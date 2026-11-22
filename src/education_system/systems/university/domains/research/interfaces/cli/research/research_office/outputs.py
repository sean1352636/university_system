"""Outputs and REF menus."""

from __future__ import annotations

import os

from education_system.systems.university.application.research import outputs as ro
from education_system.systems.university.application.research import ref as rr

from ._io import ask, ask_choice, ask_int, ask_yes, form, history, menu, run, section, show, \
    table, write

_COLUMNS = [("publication_id", "ID", 5), ("title", "Title", 36),
            ("publication_type", "Type", 16), ("publication_date", "Published", 11),
            ("uoa", "UoA", 7), ("oa_status", "Open access", 22)]
_FIELDS = [("title", "Title"), ("publication_type", "Type", ro.TYPES), ("venue", "Venue"),
           ("journal_name", "Journal"), ("issn", "ISSN"),
           ("acceptance_date", "Accepted (YYYY-MM-DD)"),
           ("publication_date", "Published (YYYY-MM-DD)"),
           ("deposit_date", "Deposited in repository (YYYY-MM-DD)"),
           ("repository_url", "Repository URL"), ("oa_route", "Open-access route", ro.OA_ROUTES),
           ("oa_exception", "REF open-access exception", ro.OA_EXCEPTIONS), ("doi", "DOI"),
           ("uoa", "Unit of assessment (e.g. UoA 11)"), ("project_id", "Research project ID"),
           ("abstract", "Abstract")]
_AUTHORS = "Authors in order, ';'-separated; mark staff as 'Name [username]'"


def _list(who):
    rows = run(ro.listing, who, ask("Search (blank = all)") or None)
    if rows is not None:
        table(rows, _COLUMNS)


def _mine(who):
    rows = run(ro.listing, who, None, None, True)
    if rows is not None:
        table(rows, _COLUMNS)


def _problems(who):
    rows = run(ro.oa_problems, who)
    if rows is not None:
        table(rows, _COLUMNS)


def view(who, publication_id=None):
    pid = publication_id or ask_int("Output ID")
    rec = run(ro.record, who, pid)
    if rec is None:
        return
    show(rec["title"], rec, [("publication_type", "Type"), ("authors", "Authors"),
                             ("venue", "Venue"), ("doi", "DOI"), ("acceptance_date", "Accepted"),
                             ("publication_date", "Published"), ("deposit_date", "Deposited"),
                             ("oa_status", "Open access"), ("uoa", "UoA"),
                             ("quality_rating", "Agreed rating"),
                             ("ref_submitted", "Selected for REF")])
    reviews = run(rr.reviews, pid) or []
    if reviews and who.leads_ref(rec.get("uoa")):
        section("Internal reviews", reviews, [("reviewer", "Reviewer", 16), ("score", "Score", 6),
                                              ("comment", "Comment", 44)])
    history(rec["history"])


def _new(who):
    data = {k: v for k, v in form(_FIELDS).items() if v not in (None, "")}
    authors = ask(_AUTHORS, f"{who.username} [{who.username}]", required=True)
    pid = write(ro.create, who, data, authors, done=None)
    if pid:
        print(f"  ✓ Output {pid} recorded.")


def _edit(who):
    pid = ask_int("Output ID")
    data = form(_FIELDS, edit=True)
    authors = ask(_AUTHORS + " (blank = unchanged)") or None
    write(ro.update, who, pid, data, authors)


def _remove(who):
    write(ro.remove, who, ask_int("Output ID"), ask("Reason", required=True))


def outputs_menu(who):
    actions = [("List outputs", _list), ("My outputs", _mine),
               ("Open-access problems", _problems), ("View an output", view),
               ("Record an output", _new), ("Edit an output", _edit)]
    if who.is_office:
        actions.append(("Remove an output", _remove))
    menu("RESEARCH OUTPUTS", actions, who)


# ── REF ─────────────────────────────────────────────────────────────────


def _uoa():
    return ask("Unit of assessment (e.g. UoA 11)", required=True)


def _summary(who):
    s = run(rr.uoa_summary, _uoa())
    if s is None:
        return
    show(f"REF summary — {s['uoa']}", s, [
        ("staff", "Staff"), ("fte", "FTE"), ("required_outputs", "Outputs required"),
        ("outputs", "Outputs recorded"), ("selected", "Outputs selected"),
        ("average_rating", "Average rating"), ("four_star", "4*"), ("three_star", "3*"),
        ("impact_cases", "Impact cases"), ("environment_version", "Environment version")])
    for gap in s["gaps"]:
        print(f"  ! {gap}")


def _candidates(who):
    rows = run(rr.candidates, _uoa()) or []
    for r in rows:
        r["selected"] = "yes" if r.get("ref_submitted") else ""
        r["reviews"] = f"{r['review']['count']} (mean {r['review']['mean']})" + (
            " MODERATE" if r["review"]["needs_moderation"] else "")
        r["blocking"] = "; ".join(r["problems"])
    table(rows, [("publication_id", "ID", 5), ("title", "Title", 30),
                 ("quality_rating", "Rating", 7), ("reviews", "Reviews", 20),
                 ("selected", "Sel", 4), ("blocking", "Cannot select because", 40)])


def _review(who):
    write(rr.add_review, who, ask_int("Output ID"), ask("Score 0-4", required=True),
          ask("Comment"), done="Score saved.")


def _rating(who):
    write(rr.set_rating, who, ask_int("Output ID"), ask("Agreed rating 0-4", required=True))


def _select(who):
    pid = ask_int("Output ID")
    write(rr.select, who, pid, ask_yes("Select it (n = take it out)", True))


def _staff(who):
    uoa = ask("Unit of assessment (blank = all)") or None
    table(run(rr.staff, uoa) or [], [("username", "Username", 16), ("name", "Name", 26),
                                     ("uoa", "UoA", 8), ("fte", "FTE", 5)])
    choice = ask("(a)ttribute someone, (r)emove one, or Enter").lower()
    if choice.startswith("a"):
        write(rr.attribute, who, ask("Username", required=True), _uoa(), ask("FTE", "1.0"))
    elif choice.startswith("r"):
        write(rr.unattribute, who, ask("Username", required=True))


def _cases(who):
    uoa = ask("Unit of assessment (blank = all)") or None
    table(run(rr.impact_cases, uoa) or [], [("id", "ID", 5), ("uoa", "UoA", 8),
                                            ("title", "Title", 36), ("status", "Status", 10),
                                            ("lead_username", "Lead", 14),
                                            ("quality_rating", "Rating", 7)])
    choice = ask("(n)ew case, (e)dit a case, or Enter").lower()
    fields = [("title", "Title"), ("summary", "Summary"), ("lead_username", "Lead (username)"),
              ("reach_significance", "Reach and significance"),
              ("beneficiaries", "Beneficiaries"), ("evidence_links", "Evidence"),
              ("status", "Status", rr.CASE_STATUSES), ("quality_rating", "Rating")]
    if choice.startswith("n"):
        data = {k: v for k, v in form(fields).items() if v not in (None, "")}
        write(rr.save_impact_case, who, {"uoa": _uoa(), **data})
    elif choice.startswith("e"):
        cid = ask_int("Case ID")
        write(rr.save_impact_case, who, form(fields, edit=True), cid)


def _environment(who):
    uoa = _uoa()
    rows = run(rr.environment_statements, uoa) or []
    for r in rows[:3]:
        print(f"\n  Version {r['version']} ({r['created_at']}):\n  {r['narrative_text']}")
    if ask_yes("Write a new version"):
        write(rr.add_environment_statement, who, uoa, ask("Statement", required=True))


def _export(who):
    uoa = _uoa()
    default = os.path.abspath(f"ref_{uoa.replace(' ', '')}.csv")
    path = ask("Save to", default)
    count = run(rr.export, uoa, path)
    if count is not None:
        print(f"  ✓ {count} row(s) written to {path}")


def ref_menu(who):
    menu("REF", [("UoA summary", _summary), ("Candidate outputs", _candidates),
                 ("Score an output", _review), ("Set agreed rating", _rating),
                 ("Select / deselect an output", _select), ("Staff in UoAs", _staff),
                 ("Impact case studies", _cases), ("Environment statement", _environment),
                 ("Export a UoA (CSV)", _export)], who)
