"""What a student can do: read the notice, see their own work and released
reports, check a draft, follow their cases (send a statement, see the
evidence) and appeal, and see and comment on their AI-writing readings."""

from __future__ import annotations

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.application.integrity import ai as integrity_ai
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
    ask, ask_int, choose, pause, pct, print_case_parts, run, show_evidence_file, table, wrap,
)


def _notice(conn, who, outbox) -> None:
    notice = access.notice(conn)
    print("\nAcademic integrity notice\n")
    print(wrap(notice["text"]))
    if access.has_acknowledged(conn, who):
        print("\n  You have acknowledged this notice.")
    elif ask("\nType YES to acknowledge it").upper() == "YES":
        access.acknowledge(conn, who)
        print("  Thank you.")


def _my_work(conn, who, outbox) -> None:
    print("\nMy submitted work")
    table(checks.documents(conn, who), ["id", "title", "module_code", "academic_year",
                                        "word_count", "submission_date"])
    print("\nMy similarity reports (released)")
    rows = review.results(conn, who)
    for r in rows:
        r["score"] = pct(r["similarity_score"])
    table(rows, ["id", "title", "module_code", "score", "status", "review_status"])
    result_id = ask_int("\nReport number to open (Enter to go back)")
    if result_id:
        show_own_report(review.result_detail(conn, who, result_id))
        from education_system.systems.university.domains.integrity.interfaces.cli.integrity.tools import (  # noqa: E501
            report_actions,
        )
        report_actions(conn, who, outbox, result_id)


def show_own_report(detail) -> None:
    print(f"\n{detail['title']} — {pct(detail['similarity_score'])} ({detail['status']})")
    print(wrap(detail["report"]))
    if detail.get("review_note") and detail.get("review_status") in ("no_concern",
                                                                     "false_positive"):
        print(f"\n  Reviewed: {detail['review_status'].replace('_', ' ')}")
    if detail.get("paraphrase_score"):
        print(f"\n  Reworded from a source: {pct(detail['paraphrase_score'])}")
    if detail.get("obfuscated_chars"):
        print(f"  Disguised characters (look-alike letters / hidden characters): "
              f"{detail['obfuscated_chars']}")
    for m in detail["matches"]:
        if not m.get("counted", True):
            print(f"\n  {pct(m['score'])} with a classmate on this assignment — collaboration "
                  "allowed, not counted")
            continue
        print(f"\n  {pct(m['score'])} also found in {m['source']}")
        for p in m["passages"][:10]:
            label = " (reworded)" if p.get("kind") == "paraphrase" else ""
            print(wrap(f"“{p['text'][:300]}”{label}", "      "))


def _draft(conn, who, outbox) -> None:
    from education_system.systems.university.infrastructure.integrity import text_extract
    path = ask("Path to your draft file")
    if not path:
        return
    text = text_extract.extract(path)
    module = choose("Module", choices.modules(conn, who), optional=True)
    result = checks.self_check(conn, who, text=text, file_type=text_extract.file_type(path),
                               module_code=module)
    print(f"\n{pct(result['score'])} of {result['words_checked']} words also appear elsewhere "
          f"({result['words_excluded']} quoted / reference-list words left out).")
    if result.get("paraphrase_score"):
        print(f"{pct(result['paraphrase_score'])} is reworded from a source (marked below).")
    if result.get("obfuscated"):
        print(f"{result['obfuscated']} disguised character(s) found — retype any text pasted "
              "from elsewhere.")
    for p in result["passages"][:15]:
        label = " (reworded)" if p.get("kind") == "paraphrase" else ""
        print(wrap(f"“{p['text'][:300]}”{label}"))
    print("\nNothing from a draft check is kept. Cite your sources and use quotation marks.")


def _my_cases(conn, who, outbox) -> None:
    rows = review.cases(conn, who)
    table(rows, ["id", "case_type", "stage", "status", "penalty", "appeal_deadline"])
    case_id = ask_int("\nCase number to open (Enter to go back)")
    if not case_id:
        return
    case = review.case(conn, who, case_id)
    print(wrap(case["description"]))
    print_case_parts(case)
    for e in case["events"]:
        print(f"  {e['at']}  {e['stage']:<13} {e['note'] or ''}")
    for a in case["appeals"]:
        print(f"  Appeal {a['appeal_id']}: {a['status']} {a['decision_note'] or ''}")
    if any(e.get("file_name") for e in case["evidence"]) and \
            ask("\nSee where an evidence file is? (y/n)").lower() == "y":
        show_evidence_file(conn, who)
    if case["stage"] in evidence.OPEN_STAGES and \
            ask("\nSend your statement (your account of what happened)? (y/n)").lower() == "y":
        outbox += evidence.submit_statement(conn, who, case_id, ask("Your statement"))
        print("  Statement sent.")
    if case["stage"] == "decided" and ask("\nAppeal this decision? (y/n)").lower() == "y":
        grounds = ask("Your grounds for appeal")
        outbox += review.lodge_appeal(conn, who, case_id, grounds)
        print("  Appeal lodged.")


def _my_readings(conn, who, outbox) -> None:
    from education_system.systems.university.domains.integrity.interfaces.cli.integrity.staff import (  # noqa: E501
        print_reading,
    )
    table(integrity_ai.results(conn, who), ["id", "title", "course_code", "level", "decision"])
    reading = ask_int("\nReading number to open (Enter to go back)")
    if not reading:
        return
    print_reading(integrity_ai.result_detail(conn, who, reading))
    print("\nIf you think a reading is wrong, say so: the module's staff see your comment.")
    if ask("Add a comment? (y/n)").lower() == "y":
        outbox += integrity_ai.comment(conn, who, reading, ask("Your comment"))
        print("  Sent.")


def student_menu(auth) -> None:
    actions = {"1": _notice, "2": _my_work, "3": _draft, "4": _my_cases, "5": _my_readings}
    while True:
        print("\nAcademic integrity")
        print("1. Read the academic integrity notice")
        print("2. My work and similarity reports")
        print("3. Check a draft before submitting")
        print("4. My integrity cases and appeals")
        print("5. My AI-writing readings")
        print("0. Back")
        choice = ask("Choose")
        if choice in ("0", ""):
            return
        if choice in actions:
            run(auth, actions[choice])
            pause()
