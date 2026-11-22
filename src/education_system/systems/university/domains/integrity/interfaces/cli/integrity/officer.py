"""What integrity officers (and administrators) can do: run cases from
referral to decision (statements, evidence, previous cases, recommended
outcomes), decide appeals, open a case by hand, change settings, export /
erase / purge records, grant roles, read the audit, import external texts,
run the daily jobs and set the external search key."""

from __future__ import annotations

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.application.integrity import records
from education_system.systems.university.application.integrity import review
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
    add_case_evidence, ask, ask_int, choose, pause, print_case_parts, run, save_json,
    show_evidence_file, table, wrap,
)


def _case(conn, who, outbox, case_id=None) -> None:
    case_id = case_id or ask_int("Case number")
    if not case_id:
        return
    c = review.case(conn, who, case_id)
    print(f"\nCase {c['id']} — student {c['student_id']} — {c['case_type']} — {c['stage']}"
          f" — from {c.get('source') or 'manual'}" + (f" — {c['module_code']}"
                                                     if c.get("module_code") else ""))
    print(wrap(c["description"]))
    rec = c.get("recommended")
    if rec:
        print(f"  Offence {rec['offence_number']}; recommended: {', '.join(rec['outcomes'])}")
    for h in c.get("history") or []:
        print(f"  Earlier case {h['id']} ({(h['created_at'] or '')[:10]}) {h['case_type']}: "
              f"{h['penalty'] or h['stage']}{' — upheld' if h['upheld'] else ''}")
    print_case_parts(c)
    for e in c["events"]:
        print(f"  {e['at']}  {e['stage']:<13} {e['actor'] or ''}: {e['note'] or ''}")
    for a in c["appeals"]:
        print(f"  Appeal {a['appeal_id']} ({a['status']}): {a['grounds'][:200]}")
    print("\n1 investigate  2 invite to a meeting  3 decide  4 close  5 decide an appeal  "
          "6 add evidence  7 withdraw evidence  8 change statement deadline  "
          "9 evidence file  (Enter to go back)")
    choice = ask("Choose")
    if choice in ("1", "2"):
        stage = "investigating" if choice == "1" else "meeting"
        outbox += review.advance(conn, who, case_id, stage, ask("Note (shown to the student "
                                                               "for a meeting)"))
    elif choice == "3":
        outcome = choose("Outcome", [(k, label) for k, (label, _p) in review.OUTCOMES.items()])
        note = ask("Reasons")
        departure = None
        if rec and outcome not in rec["outcomes"] + ["no_case", "panel"]:
            departure = ask("Reason for going outside the recommended outcomes")
        outbox += review.decide(conn, who, case_id, outcome, note, departure_reason=departure)
    elif choice == "4":
        review.close(conn, who, case_id, ask("Note"))
    elif choice == "5":
        appeal_id = ask_int("Appeal number")
        upheld = ask("Uphold the appeal? (y/n)").lower() == "y"
        outbox += review.decide_appeal(conn, who, appeal_id, upheld, ask("Reasons"))
    elif choice == "6":
        add_case_evidence(conn, who, case_id, officer=True)
    elif choice == "7":
        evidence.withdraw_evidence(conn, who, ask_int("Evidence number"), ask("Why"))
    elif choice == "8":
        outbox += evidence.set_response_due(conn, who, case_id, ask("New deadline (YYYY-MM-DD)"),
                                            ask("Reason (sent to the student)"))
    elif choice == "9":
        show_evidence_file(conn, who)
    else:
        return
    print("  Done.")


def _cases(conn, who, outbox) -> None:
    stage = ask(f"Stage ({', '.join(review.STAGES)}; Enter for all)") or None
    table(review.cases(conn, who, stage=stage), ["id", "student_id", "case_type", "stage",
                                                 "status", "outcome", "created_at"])
    case_id = ask_int("\nCase number to open (Enter to go back)")
    if case_id:
        _case(conn, who, outbox, case_id)


def _open_case(conn, who, outbox) -> None:
    module = choose("Module (narrows the lists)", choices.modules(conn, who), optional=True)
    student = choose("Student", choices.students(conn, who, module))
    if not student:
        return
    out = review.open_case(conn, who, student_id=student,
                           case_type=choose("Type", [(t, t) for t in review.CASE_TYPES],
                                            default="plagiarism"),
                           description=ask("What is the concern?"),
                           assignment_id=choose("Assignment",
                                                choices.assignments(conn, who, module),
                                                optional=True),
                           module_code=module)
    outbox += out["emails"]
    print(f"  Case {out['case_id']} opened.")


def _settings(conn, who, outbox) -> None:
    for key in access.SETTINGS:
        print(f"  {key:<22} {access.setting(conn, key)[:70]}")
    key = ask("\nSetting to change (Enter to go back)")
    if key:
        access.set_setting(conn, who, key, ask("New value"))
        print("  Saved.")


def _records(conn, who, outbox) -> None:
    choice = ask("1 export a student's records  2 erase a student's records  "
                 "3 run the retention purge now")
    if choice == "1":
        student = choose("Student", choices.students(conn, who))
        if not student:
            return
        path = ask("Save to", f"integrity_{student}.json")
        print(f"  Saved {save_json(records.export(conn, who, student), path)}")
    elif choice == "2":
        student = choose("Student", choices.students(conn, who))
        if not student:
            return
        if ask(f"Type ERASE {student} to confirm") == f"ERASE {student}":
            print(f"  {records.erase(conn, who, student)}")
    elif choice == "3":
        access.require(access.is_officer(conn, who), "Only an integrity officer can do this")
        print(f"  Text removed from {records.purge(conn)} documents.")


def _roles(conn, who, outbox) -> None:
    table(access.roles(conn), ["username", "role", "granted_by", "granted_at"])
    choice = ask("\n1 grant  2 revoke  (Enter to go back)")
    if choice in ("1", "2"):
        username = choose("Member of staff", choices.staff(conn, who))
        role = choose("Role", [("reviewer", "Reviewer (any module)"),
                               ("officer", "Integrity officer")])
        if not username or not role:
            return
        (access.grant if choice == "1" else access.revoke)(conn, who, username, role)
        print("  Done.")


def _audit(conn, who, outbox) -> None:
    table(access.recent_audit(conn, who, 50), ["at", "actor", "entity", "entity_id", "action"])


def _import_external(conn, who, outbox) -> None:
    from education_system.systems.university.application.integrity import (
        external as integrity_external,
    )
    from education_system.systems.university.infrastructure.integrity import text_extract
    paths = [p.strip() for p in ask("Paths to the files (separate with ;)").split(";")
             if p.strip()]
    url = ask("Where they come from (web address, optional)") or None
    for path in paths:
        try:
            text = text_extract.extract(path)
        except ValueError as exc:
            print(f"  Skipped {path}: {exc}")
            continue
        doc_id = integrity_external.import_text(conn, who, title=path.rsplit("/", 1)[-1],
                                                content=text,
                                                file_type=text_extract.file_type(path),
                                                source_url=url)
        print(f"  {path} added as document {doc_id}.")


def _daily_jobs(conn, who, outbox) -> None:
    access.require(access.is_officer(conn, who), "Only an integrity officer can do this")
    if ask("Run the daily jobs now? Reminder e-mails may be sent. (y/n)").lower() != "y":
        return
    from education_system.systems.university.infrastructure.integrity import retention_worker
    print(f"  {retention_worker.run_once()}")


def _core_key(conn, who, outbox) -> None:
    access.require(who.is_admin, "Only an administrator can set the external search key")
    from education_system.systems.university.infrastructure.integrity import external_sources
    print(f"  CORE API key is {'set' if external_sources.configured() else 'not set'}.")
    key = ask("New key (Enter to leave it)")
    if key:
        print(f"  Saved to {external_sources.save_core_key(key)}.")
        access.audit(conn, who.username, "setting", "core_api_key", "changed")


def officer_menu(auth) -> None:
    actions = {"1": _cases, "2": _open_case, "3": _settings, "4": _records, "5": _roles,
               "6": _audit, "7": _import_external, "8": _daily_jobs, "9": _core_key}
    while True:
        print("\nAcademic integrity — officer")
        print("1. Cases and appeals")
        print("2. Open a case")
        print("3. Integrity settings")
        print("4. Export / erase / retention purge")
        print("5. Reviewer and officer roles (administrators)")
        print("6. Audit")
        print("7. Import external texts (essay-mill samples, copied articles)")
        print("8. Run the daily jobs now (purge, reminders, closing, retries)")
        print("9. External search key (administrators)")
        print("0. Back")
        choice = ask("Choose")
        if choice in ("0", ""):
            return
        if choice in actions:
            run(auth, actions[choice])
            pause()
