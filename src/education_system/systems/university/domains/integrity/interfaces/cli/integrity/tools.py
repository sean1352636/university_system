"""The integrity tools in the CLI (``application/integrity/tools``): compare
two documents, import files or a folder, check / export / delete several
documents, history, statistics, reports, repository health, and exporting or
e-mailing a similarity report."""

from __future__ import annotations

import os

from education_system.systems.university.application.integrity import choices
from education_system.systems.university.application.integrity import tools
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
    ask, ask_int, choose, pause, pct, run, table, wrap,
)


def _ids(prompt) -> list[int]:
    raw = ask(prompt)
    return [int(x) for x in raw.replace(",", " ").split() if x.isdigit()]


def _compare(conn, who, outbox) -> None:
    docs = choices.documents(conn, who)
    a = choose("First document", docs)
    b = choose("Second document", docs) if a else None
    if not a or not b:
        return
    result = tools.compare(conn, who, a, b)
    for side, other in (("a", "b"), ("b", "a")):
        d = result[side]
        print(f"\n{d['id']}: {d['title']} ({d['module_code'] or 'no module'}, {d['student'] or ''})")
        print(f"  {pct(d['score'])} also in document {result[other]['id']}; a further "
              f"{pct(d['paraphrase_score'])} reworded ({d['words']} words)")
    for p in result["a"]["passages"][:20]:
        print(wrap(f"[{p.get('kind', 'exact')}] {p['text'][:240]}", "    "))
        print(wrap(f"   ↔ {p['source_text'][:240]}", "    "))
    path = ask("Save the comparison as (.html or .txt, Enter to skip)")
    if path:
        text = tools.comparison_html(result) if path.lower().endswith(".html") \
            else tools.comparison_text(result)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"  Saved {path}")


def _import(conn, who, outbox) -> None:
    from education_system.systems.university.infrastructure.integrity import text_extract
    where = ask("File(s) separated by ';', or a folder")
    if not where:
        return
    if os.path.isdir(where):
        paths = [os.path.join(b, n) for b, _d, names in os.walk(where) for n in sorted(names)
                 if text_extract.file_type(n) in text_extract.SUPPORTED]
    else:
        paths = [p.strip() for p in where.split(";") if p.strip()]
    kind = ask(f"Kind ({', '.join(tools.IMPORT_KINDS)})", "submission")
    module = choose("Module", choices.modules(conn, who), optional=True)
    assignment = choose("Assignment", choices.assignments(conn, who, module), optional=True)
    check = ask("Check submissions as they are added? (y/n)", "y").lower() == "y"
    out = tools.import_files(conn, who, paths, kind=kind, module_code=module,
                             assignment_id=assignment, check=check)
    table(out, ["file", "student", "status", "document_id", "result_id", "error"])


def _bulk_check(conn, who, outbox) -> None:
    ids = _ids("Document numbers (space or comma separated)")
    if ids:
        out = tools.bulk_check(conn, who, ids)
        for r in out:
            r["score"] = pct(r["score"]) if r["score"] is not None else ""
        table(out, ["document_id", "result_id", "score", "band", "error"])


def _export(conn, who, outbox) -> None:
    ids = _ids("Document numbers to export")
    if not ids:
        return
    fmt = ask("Format (txt / md / html)", "txt")
    path = ask("Save the ZIP as", f"documents_{tools.today()}.zip")
    done = tools.export_texts(conn, who, ids, path, fmt)
    print(f"  Exported {done['written']} of {done['documents']} to {done['path']}")


def _doc_history(conn, who, outbox) -> None:
    doc_id = choose("Document", choices.documents(conn, who))
    if doc_id:
        data = tools.document_history(conn, who, doc_id)
        print(f"\n{data['title']} — {data['module_code'] or 'no module'}, {data['student'] or ''}")
        for r in data["results"]:
            r["score"] = pct(r["similarity_score"])
        table(data["results"], ["id", "check_date", "checked_by", "score", "status",
                                "review_status", "sources", "case_id"])


def _student_history(conn, who, outbox) -> None:
    student = choose("Student", choices.students(conn, who))
    if not student:
        return
    data = tools.student_history(conn, who, student)
    rows = [{**d, "latest_score": pct((d["latest"] or {}).get("similarity_score")),
             "review": (d["latest"] or {}).get("review_status")} for d in data["documents"]]
    table(rows, ["id", "title", "module_code", "submitted", "checks", "latest_score", "review"])
    if data["cases"]:
        print("\nCases")
        table(data["cases"], ["id", "case_type", "stage", "outcome", "module_code", "created_at"])


def _statistics(conn, who, outbox) -> None:
    stats = tools.statistics_detail(conn, who, ask("From (YYYY-MM-DD, optional)") or None,
                                    ask("To (YYYY-MM-DD, optional)") or None)
    o = stats["overview"]
    print(f"\n  Checks {o['checks'] or 0}, documents {o['documents'] or 0}, average "
          f"{pct(o['average'])}, waiting {o['waiting'] or 0}, referred {o['referred'] or 0}")
    print("\nBy month")
    top = max([m["checks"] for m in stats["by_month"]] or [1])
    for m in stats["by_month"]:
        print(f"  {m['month']}  {'█' * max(1, round(30 * m['checks'] / top))} {m['checks']} "
              f"({m['needing_review'] or 0} needing review)")
    print("\nBy module")
    for m in stats["by_module"]:
        m["average"] = pct(m["average"])
    table(stats["by_module"], ["module", "checks", "documents", "average", "high", "waiting",
                               "referred"])


def _report(conn, who, outbox) -> None:
    kind = choose("Report", list(tools.REPORTS.items()), default="summary")
    fmt = choose("Format", [("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV")], default="pdf")
    rep = tools.report(conn, who, kind, ask("From (YYYY-MM-DD, optional)") or None,
                       ask("To (YYYY-MM-DD, optional)") or None)
    path = ask("Save as", f"integrity_{kind}_{tools.today()}.{fmt}")
    with open(path, "wb") as fh:
        fh.write(tools.render(rep, fmt))
    print(f"  Saved {path}")


def _health(conn, who, outbox) -> None:
    found = tools.repository_health(conn, who)
    for key, items in found.items():
        if key != "checked_at":
            print(f"  {key.replace('_', ' '):<18} {len(items)}")
    if any(found[k] for k in ("orphaned_results", "orphaned_matches", "dangling_sources",
                              "empty_documents")) and ask("Fix what can be fixed? (y/n)",
                                                          "n").lower() == "y":
        print(f"  {tools.fix_repository(conn, who)}")


def _bulk_delete(conn, who, outbox) -> None:
    ids = _ids("Document numbers to delete")
    if not ids:
        return
    reason = ask("Reason")
    if ask(f"Type DELETE to delete {len(ids)} document(s)") != "DELETE":
        return
    table(tools.bulk_delete(conn, who, ids, reason), ["document_id", "deleted", "error"])


def report_actions(conn, who, outbox, result_id) -> None:
    """Export or e-mail one similarity report (staff and students)."""
    choice = ask("1 export to a file  2 e-mail it  (Enter to skip)")
    if choice == "1":
        fmt = ask("Format (pdf / html / csv)", "pdf")
        path = ask("Save as", f"similarity_report_{result_id}.{fmt}")
        with open(path, "wb") as fh:
            fh.write(tools.export_report(conn, who, result_id, fmt))
        print(f"  Saved {path}")
    elif choice == "2":
        recipient = "me"
        if who.is_staff and ask("Send to the student instead of you? (y/n)", "n") == "y":
            recipient = "student"
        outbox += tools.email_report(conn, who, result_id, recipient, ask("Note (optional)"))
        print("  Sent.")


def _report_file(conn, who, outbox) -> None:
    result_id = choose("Similarity report", choices.results(conn, who))
    if result_id:
        report_actions(conn, who, outbox, result_id)


def tools_menu(auth, officer=False) -> None:
    actions = {"1": _compare, "2": _import, "3": _bulk_check, "4": _export, "5": _doc_history,
               "6": _student_history, "7": _statistics, "8": _report, "9": _report_file}
    if officer:
        actions.update({"10": _health, "11": _bulk_delete})
    while True:
        print("\nAcademic integrity — tools")
        print("1. Compare two documents")
        print("2. Import files or a folder")
        print("3. Check several documents")
        print("4. Export documents (text, Markdown or HTML, as a ZIP)")
        print("5. Document history")
        print("6. Student history")
        print("7. Statistics")
        print("8. Reports (PDF, HTML, CSV)")
        print("9. Export or e-mail a similarity report")
        if officer:
            print("10. Repository health")
            print("11. Delete several documents")
        print("0. Back")
        choice = ask("Choose")
        if choice in ("0", ""):
            return
        if choice in actions:
            run(auth, actions[choice])
            pause()
