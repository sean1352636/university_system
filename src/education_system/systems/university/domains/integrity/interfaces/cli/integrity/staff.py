"""What module staff and reviewers can do: work through the review queue,
read reports side by side, run checks, add reference and template
documents, set a module's options and see statistics; deal with failed
automatic checks and AI-writing readings, search published sources for a
document, and add evidence to the cases they raised."""

from __future__ import annotations

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import ai as integrity_ai
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
    add_case_evidence, ask, ask_int, choose, pause, pct, print_case_parts, run,
    show_evidence_file, table, wrap,
)


def _queue(conn, who, outbox) -> None:
    rows = review.results(conn, who, review_status="pending")
    for r in rows:
        r["score"] = pct(r["similarity_score"])
        r["reworded"] = pct(r.get("paraphrase_score"))
        r["disguised"] = r.get("obfuscated_chars") or 0
    print("\nWaiting for review")
    table(rows, ["id", "title", "student_id", "module_code", "score", "reworded", "disguised",
                 "status", "check_date"])
    result_id = ask_int("\nReport number to open (Enter to go back)")
    if result_id:
        _report(conn, who, outbox, result_id)


def _report(conn, who, outbox, result_id=None) -> None:
    result_id = result_id or ask_int("Report number")
    if not result_id:
        return
    d = review.result_detail(conn, who, result_id)
    print(f"\n{d['title']} — student {d['student_id']} — {d['module_code']}")
    print(f"{pct(d['similarity_score'])} ({d['status']}), review: {d['review_status']}")
    if d.get("paraphrase_score"):
        print(f"Reworded from a source: {pct(d['paraphrase_score'])}")
    if d.get("obfuscated_chars"):
        print(f"Disguised characters: {d['obfuscated_chars']}")
    if d.get("ai_signal"):
        a = d["ai_signal"]
        print(f"AI-writing reading {a['id']} for this work: {a.get('level') or 'recorded'} "
              "(indicators, not evidence; open it from menu 8)")
    print(wrap(d["report"]))
    for m in d["matches"]:
        how = ("NOT COUNTED — classmate on this assignment, collaboration allowed"
               if not m.get("counted", True) else
               {"paraphrase": "reworded"}.get(m.get("match_kind"), "word for word"))
        print(f"\n  {pct(m['score'])} with {m['source']} (document {m['source_document_id']}, "
              f"student {m['source_student_id'] or '-'}) — {how}")
        for p in m["passages"][:8]:
            label = "THIS (reworded):" if p.get("kind") == "paraphrase" else "THIS:  "
            print(wrap(f"{label} {p['text'][:250]}", "      "))
            print(wrap(f"SOURCE: {p.get('source_text', '')[:250]}", "      "))
    if d["review_status"] == "pending" or (d["review_status"] == "not_needed"
                                           and not d["case_id"]):
        _decide(conn, who, outbox, result_id)
    from education_system.systems.university.domains.integrity.interfaces.cli.integrity.tools import (  # noqa: E501
        report_actions,
    )
    report_actions(conn, who, outbox, result_id)


def _decide(conn, who, outbox, result_id) -> None:
    print("\nDecision: 1 no concern  2 false positive  3 refer to an integrity case  "
          "(Enter to leave it)")
    decision = {"1": "no_concern", "2": "false_positive", "3": "refer"}.get(ask("Choose"))
    if not decision:
        return
    note = ask("Reason (recorded and shown to the student)")
    case_type = "plagiarism"
    if decision == "refer":
        case_type = ask(f"Case type ({', '.join(review.CASE_TYPES)})", "plagiarism")
    out = review.review(conn, who, result_id, decision, note, case_type=case_type)
    outbox += out["emails"]
    opened = f"; case {out['case_id']} opened" if out["case_id"] else ""
    print(f"  Recorded{opened}.")


def _run_check(conn, who, outbox) -> None:
    table(checks.documents(conn, who, limit=50), ["id", "title", "student_id", "module_code",
                                                  "kind", "academic_year"])
    doc_id = ask_int("\nDocument number to check")
    if doc_id:
        result_id = checks.run_check(conn, doc_id, who=who)
        _report(conn, who, outbox, result_id)


def _add_document(conn, who, outbox) -> None:
    from education_system.systems.university.infrastructure.integrity import text_extract
    kind = {"1": "reference", "2": "template"}.get(ask("1 reference source  2 template / "
                                                      "starter code"))
    if not kind:
        return
    path = ask("Path to the file")
    module = choose("Module (Enter for any module)", choices.modules(conn, who), optional=True)
    assignment = choose("Assignment (Enter for the whole module)",
                        choices.assignments(conn, who, module), optional=True)
    doc_id = checks.add_document(conn, who, title=ask("Title", path.rsplit("/", 1)[-1]),
                                 content=text_extract.extract(path),
                                 file_type=text_extract.file_type(path), module_code=module,
                                 kind=kind, assignment_id=assignment)
    print(f"  Added as document {doc_id}.")


def _module_settings(conn, who, outbox) -> None:
    module = choose("Module", choices.modules(conn, who))
    if not module:
        return
    print(f"  Current review threshold: {pct(access.module_threshold(conn, module))}")
    enabled = ask("Check submissions automatically? (y/n)", "y").lower() == "y"
    threshold = float(ask("Review threshold (0-1)", access.module_threshold(conn, module)))
    collab = ask("Is collaboration allowed? (y/n)", "n").lower() == "y"
    access.set_module_settings(conn, who, module, enabled=enabled, threshold=threshold,
                               allow_collaboration=collab, notes=ask("Notes"))
    print("  Saved.")


def _stats(conn, who, outbox) -> None:
    s = review.statistics(conn, who)
    print(f"\n  Checks: {s['checks']}   waiting review: {s['waiting_review']}   "
          f"referred: {s['referred']}   open cases: {s['open_cases']}")
    print("  " + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print(f"  Largely reworded: {s.get('reworded', 0)}   with disguised characters: "
          f"{s.get('disguised', 0)}   failed automatic checks: {s.get('failed_checks', 0)}")


def _failed(conn, who, outbox) -> None:
    rows = checks.failures(conn, who)
    table(rows, ["submission_id", "assignment_title", "student_id", "module_code", "attempts",
                 "last_error"])
    sid = ask_int("\nSubmission number to deal with (Enter to go back)")
    if not sid:
        return
    choice = ask("1 check the text by hand (from a readable file)  2 won't be checked")
    if choice == "1":
        from education_system.systems.university.infrastructure.integrity import text_extract
        path = ask("Path to a readable copy (typed up or run through OCR)")
        result_id = checks.check_by_hand(conn, who, sid, text_extract.extract(path),
                                         text_extract.file_type(path))
        _report(conn, who, outbox, result_id)
    elif choice == "2":
        checks.dismiss_failure(conn, who, sid, ask("Why it will not be checked"))
        print("  Recorded.")


def print_reading(d) -> None:
    """One AI-writing reading: the notice, indicators, passages, comments."""
    print(f"\n{d['title']} — {d.get('course_code') or '-'} — student {d['student_id']}")
    print(wrap(d["notice"]))
    level = str(d.get("level") or "")
    shown = "-" if level.startswith("not ") else d.get("ai_score")
    print(f"  {level} (strength {shown}), {d.get('words_checked') or 0} words read")
    for i in d.get("indicators") or []:
        print(wrap(f"{i['label']}: {i['shown']} — {i['meaning']}"))
    if d.get("note"):
        print(wrap(d["note"]))
    for p in (d.get("passages") or [])[:15]:
        label = {"artefact": "chat text", "stock": "stock phrase",
                 "opener": "opening"}.get(p.get("kind"), p.get("kind"))
        print(wrap(f"[{label}] “{p['text'][:200]}”", "      "))
    if d.get("decision"):
        print(f"  Reviewed: {d['decision']} by {d.get('reviewed_by')} — {d.get('note') or ''}")
    for c in d.get("comments") or []:
        print(f"  {c['at'][:16]} {c['author']}: {c['comment']}")


def _ai_writing(conn, who, outbox) -> None:
    choice = ask("1 waiting review  2 all readings  3 read a submission  4 read text for a "
                 "student", "1")
    if choice in ("1", "2"):
        rows = (integrity_ai.flags(conn, who) if choice == "1"
                else integrity_ai.results(conn, who))
        table(rows, ["id", "title", "student_id", "course_code", "level", "ai_score",
                     "decision"])
        reading = ask_int("\nReading number to open (Enter to go back)")
    elif choice == "3":
        from education_system.systems.university.infrastructure.integrity import text_extract
        sid = choose("Submission", choices.submissions(conn, who))
        if not sid:
            return
        text, kind = text_extract.submission_text(conn, sid)
        reading = integrity_ai.run_check(conn, who, text=text, module_code=None,
                                         submission_id=sid, file_type=kind)
    elif choice == "4":
        from education_system.systems.university.infrastructure.integrity import text_extract
        path = ask("Path to the file")
        if not path:
            return
        module = choose("Module", choices.modules(conn, who))
        if not module:
            return
        student = choose("Student", choices.students(conn, who, module))
        if not student:
            return
        reading = integrity_ai.run_check(
            conn, who, text=text_extract.extract(path), module_code=module, student_id=student,
            assignment_id=choose("Assignment", choices.assignments(conn, who, module),
                                 optional=True),
            title=ask("Title", path.rsplit("/", 1)[-1]), file_type=text_extract.file_type(path))
    else:
        return
    if not reading:
        return
    d = integrity_ai.result_detail(conn, who, reading)
    print_reading(d)
    options = "1 reply" + ("  2 no concern  3 refer as a case" if not d.get("decision") else "")
    pick = ask(f"\n{options}  (Enter to go back)")
    if pick == "1":
        integrity_ai.comment(conn, who, reading, ask("Your reply (seen by the student)"))
        print("  Sent.")
    elif pick in ("2", "3") and not d.get("decision"):
        out = integrity_ai.review_flag(conn, who, reading,
                                       "no_concern" if pick == "2" else "refer",
                                       ask("Reason (for a referral: the concern, sent to the "
                                           "student)"))
        outbox += out["emails"]
        print(f"  Recorded{'; case ' + str(out['case_id']) + ' opened' if out['case_id'] else ''}.")


def _external(conn, who, outbox) -> None:
    from education_system.systems.university.application.integrity import (
        external as integrity_external,
    )
    doc_id = choose("Document", choices.documents(conn, who))
    if not doc_id:
        return
    found = integrity_external.search_external(conn, who, doc_id)
    print(f"  {found['queries']} phrase(s) searched; {found['sources_added']} new source(s).")
    for error in found["errors"]:
        print(f"  {error}")
    _report(conn, who, outbox, found["result_id"])


def _my_cases(conn, who, outbox) -> None:
    table(review.cases(conn, who), ["id", "student_id", "case_type", "stage", "created_at"])
    case_id = ask_int("\nCase number to open (Enter to go back)")
    if not case_id:
        return
    c = review.case(conn, who, case_id)
    print(wrap(c["description"]))
    print_case_parts(c)
    choice = ask("1 add evidence  2 evidence file  (Enter to go back)")
    if choice == "1":
        add_case_evidence(conn, who, case_id, officer=False)
    elif choice == "2":
        show_evidence_file(conn, who)


_DOC_FILTERS = (("module_code", "Module code"), ("kind", "Kind (submission / reference / "
                                                 "template / external)"),
                ("file_type", "File type (e.g. pdf, docx, py)"), ("min_words", "Minimum words"),
                ("max_words", "Maximum words"), ("date_from", "Submitted from (YYYY-MM-DD)"),
                ("date_to", "Submitted to (YYYY-MM-DD)"),
                ("student", "Student / candidate (as listed)"),
                ("author", "Added by (username)"), ("search", "Text in the title or document"))


def _documents(conn, who, outbox) -> None:
    """Search the repository with filters; optionally export the list as CSV."""
    print("\nFilter documents (Enter to skip any filter)")
    filters = {key: ask(label) for key, label in _DOC_FILTERS}
    filters = {k: v for k, v in filters.items() if v}
    rows = checks.documents(conn, who, limit=200, **filters)
    table(rows, ["id", "title", "kind", "student_id", "module_code", "file_type", "word_count",
                 "submission_date"])
    print(f"  {len(rows)} document(s){' (first 200)' if len(rows) == 200 else ''}")
    if rows and ask("Export the full filtered list to CSV? (y/n)", "n").lower() == "y":
        path = ask("Save to", "integrity_documents.csv")
        text = checks.export_documents(conn, who, **filters)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print(f"  Saved {max(0, text.count(chr(10)) - 1)} document(s) to {path}")


def _is_officer(auth) -> bool:
    from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
        session,
    )
    try:
        with session(auth) as (conn, who, _outbox):
            return access.is_officer(conn, who)
    except (PermissionError, ValueError):
        return False


def staff_menu(auth) -> None:
    actions = {"1": _queue, "2": _report, "3": _run_check, "4": _add_document,
               "5": _module_settings, "6": _stats, "7": _failed, "8": _ai_writing,
               "9": _external, "10": _my_cases, "11": _documents}
    officer = _is_officer(auth)
    while True:
        print("\nAcademic integrity — staff")
        print("1. Review queue")
        print("2. Open a similarity report")
        print("3. Run a check on a document")
        print("4. Add a reference or template document")
        print("5. Module integrity settings")
        print("6. Statistics")
        print("7. Failed automatic checks")
        print("8. AI-writing readings")
        print("9. Search published sources for a document")
        print("10. Cases I raised (add evidence)")
        print("11. Search and export documents")
        print("12. Tools: compare, import, bulk check, history, statistics, reports")
        print("0. Back")
        choice = ask("Choose")
        if choice in ("0", ""):
            return
        if choice == "12":
            from education_system.systems.university.domains.integrity.interfaces.cli.integrity.tools import (  # noqa: E501
                tools_menu,
            )
            tools_menu(auth, officer=officer)
            continue
        if choice in actions:
            run(auth, actions[choice])
            pause()
