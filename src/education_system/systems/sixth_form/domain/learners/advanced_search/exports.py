"""Open handlers, result exports, mail-merge, cohort export and contact
sheets for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import json
from dataclasses import field
from typing import Any, Callable

from .models import (  # noqa: F401
    ALL_SCOPES,
    ValidationError,
)
from ._db import (  # noqa: F401
    logger,
)
from .sources import (  # noqa: F401
    student_group_index,
)
from .history import (  # noqa: F401
    _resolve_cohort_id,
    _student_ids_from_results,
    get_cohort,
)


# ══════════════════════════════════════════════════════════════════
# Drill-through + bulk export (items 45, 46)
# ══════════════════════════════════════════════════════════════════

# Scope → callable to open an entity in a GUI editor. GUI code calls
# ``register_open_handler('students', fn)`` at import time; the
# advanced-search view uses ``open_hit`` to dispatch.
OPEN_HANDLERS: dict[str, Callable[[Hit], Any]] = {}


def register_open_handler(scope: str,
                          fn: Callable[[Hit], Any]) -> None:
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unknown scope {scope!r}")
    OPEN_HANDLERS[scope] = fn


def open_hit(hit: Hit) -> Any:
    """Invoke the GUI handler registered for the hit's scope. Returns
    None when no handler is wired up — caller can show a default
    'no editor' message."""
    fn = OPEN_HANDLERS.get(hit.scope)
    if fn is None:
        logger.debug("open_hit: no handler for scope %s", hit.scope)
        return None
    try:
        return fn(hit)
    except Exception:
        logger.exception("open_hit handler for %s failed", hit.scope)
        return None


def audit_export(results: SearchResults, action: str, target: str = "",
                 count: int | None = None) -> None:
    """Record that results left the screen (export, mail-merge, contact
    sheet): in the search audit, the operator action log and, when the
    results include safeguarding/SEND/medical records, the sensitive-access
    log the DSL reviews. Never raises."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        from .annotations import log_action
        from .history import _record_search_audit
        from .matching import SENSITIVE_LOG_AREAS
        p = access.current()
        hits = results.ranked_hits or results.all_hits()
        n = len(hits) if count is None else count
        scopes = sorted({h.scope for h in hits})
        sensitive = [s for s in scopes if s in SENSITIVE_LOG_AREAS]
        _record_search_audit(p.username or None, p.role or None,
                             results.query or "", scopes, sensitive, False,
                             target or None, action=action, record_count=n)
        log_action(action, target, n)
        for scope in sensitive:
            access.log_sensitive_access(
                p, SENSITIVE_LOG_AREAS[scope], f"advanced search {action}",
                record_ref=(target or results.query or "")[:200])
    except Exception:
        logger.warning("could not audit advanced-search %s", action,
                       exc_info=True)


def export_results_csv(results: SearchResults) -> str:
    """Return a CSV string for the result set (one row per hit).

    Columns: scope, entity_id, score, label, sublabel, matched_fields.
    The caller writes it somewhere, so the export is audited here."""
    audit_export(results, "export", "csv")
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["scope", "entity_id", "score", "label", "sublabel",
                "matched_fields"])
    seq = results.ranked_hits or [
        h for hits in results.hits_by_scope.values() for h in hits]
    for h in seq:
        w.writerow([
            h.scope, h.entity_id, f"{h.score:.4f}",
            h.label, h.sublabel,
            "|".join(h.matched_fields),
        ])
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
# Multi-format export + column selection (item 36)
# ══════════════════════════════════════════════════════════════════

EXPORT_TEXT_FORMATS: tuple[str, ...] = ("csv", "tsv", "json", "html", "md")
EXPORT_FILE_FORMATS: tuple[str, ...] = EXPORT_TEXT_FORMATS + ("xlsx", "pdf")
EXPORT_COLUMNS: tuple[str, ...] = (
    "scope", "entity_id", "student_id", "score", "label", "sublabel",
    "matched_fields")
#: Student record fields that can be added to an export. For a students
#: hit they come from the record; for other student-keyed hits, from the
#: student the row is about.
STUDENT_EXPORT_COLUMNS: tuple[str, ...] = (
    "name", "preferred", "email", "personal_email", "phone", "status",
    "year", "tutor_group", "subject", "dob", "gender", "upn", "uln", "uci",
    "postcode", "start", "left")
ALL_EXPORT_COLUMNS: tuple[str, ...] = EXPORT_COLUMNS + STUDENT_EXPORT_COLUMNS


def _student_docs(seq: list[Hit]) -> dict[str, dict[str, Any]]:
    """The students-scope doc for every student the hits refer to, built
    once for the export (the hits themselves only carry their own row)."""
    from .query import _doc_student_id
    from .sources import _student_doc, student_group_index
    out: dict[str, dict[str, Any]] = {}
    want: set[str] = set()
    for h in seq:
        doc = (h.extra or {}).get("_doc") or {}
        if h.scope == "students" and doc.get("upn") is not None:
            out[h.entity_id] = doc
        elif doc.get("_sid"):
            want.add(_doc_student_id(h.scope, doc))
    want -= set(out)
    if not want:
        return out
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    groups = student_group_index()
    upns = sm.upns_by_student()
    for s in sm.list_students():
        if s.student_id in want:
            yr, tg = groups.get(s.student_id, (None, None))
            out[s.student_id] = _student_doc(
                s, ", ".join(s.subjects or []), yr, tg, upns.get(s.student_id))
    return out


def _export_rows(results: SearchResults,
                 columns: list[str] | None) -> tuple[list[str], list[list[str]]]:
    cols = [c for c in (columns or EXPORT_COLUMNS) if c in ALL_EXPORT_COLUMNS] \
        or list(EXPORT_COLUMNS)
    seq = results.ranked_hits or results.all_hits()
    students = (_student_docs(seq)
                if any(c in STUDENT_EXPORT_COLUMNS for c in cols) else {})

    def sid_of(h: Hit) -> str:
        doc = (h.extra or {}).get("_doc") or {}
        if h.scope == "students":
            return h.entity_id
        return str(doc.get("_sid") or "")

    def cell(h: Hit, c: str) -> str:
        if c == "score":
            return f"{h.score:.4f}"
        if c == "matched_fields":
            return "|".join(h.matched_fields)
        if c == "student_id":
            return sid_of(h)
        if c in STUDENT_EXPORT_COLUMNS:
            return str(students.get(sid_of(h), {}).get(c) or "")
        return str(getattr(h, c, "") or "")

    return cols, [[cell(h, c) for c in cols] for h in seq]


def export_results(results: SearchResults, *,
                   fmt: str = "csv",
                   columns: list[str] | None = None) -> str:
    """Serialise a result set to a text format (csv/tsv/json/html/md)."""
    fmt = (fmt or "csv").lower()
    cols, rows = _export_rows(results, columns)
    if fmt == "json":
        return json.dumps([dict(zip(cols, r)) for r in rows],
                          indent=2, ensure_ascii=False)
    if fmt in ("csv", "tsv"):
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf, delimiter="\t" if fmt == "tsv" else ",")
        w.writerow(cols)
        w.writerows(rows)
        return buf.getvalue()
    if fmt == "md":
        out = ["| " + " | ".join(cols) + " |",
               "| " + " | ".join("---" for _ in cols) + " |"]
        for r in rows:
            out.append("| " + " | ".join(
                x.replace("|", "\\|").replace("\n", " ") for x in r) + " |")
        return "\n".join(out)
    if fmt in ("html", "pdf"):
        return _results_html(results, cols, rows)
    raise ValidationError(
        f"Unknown export format {fmt!r}. One of: "
        f"{', '.join(EXPORT_FILE_FORMATS)}")


def _results_html(results: SearchResults, cols: list[str],
                  rows: list[list[str]]) -> str:
    import html as _h
    th = "".join(f"<th>{_h.escape(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{_h.escape(x)}</td>" for x in r) + "</tr>"
        for r in rows)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>body{font-family:sans-serif;margin:24px}"
        "table{border-collapse:collapse}"
        "td,th{border:1px solid #999;padding:4px 8px;font-size:12px}"
        "th{background:#eef}</style></head><body>"
        f"<h2>Advanced search — {_h.escape(results.query or '(all)')}</h2>"
        f"<p>{results.total} result(s)</p>"
        f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>")


def _path_fmt(path: str) -> str | None:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext if ext in EXPORT_FILE_FORMATS else None


def export_results_file(results: SearchResults, path: str, *,
                        fmt: str | None = None,
                        columns: list[str] | None = None) -> str:
    """Write a result set to ``path`` in any supported format. xlsx/pdf are
    produced when openpyxl/reportlab are installed (else raises)."""
    fmt = (fmt or _path_fmt(path) or "csv").lower()
    audit_export(results, "export", f"{fmt}: {path}")
    if fmt == "xlsx":
        _write_xlsx(results, path, columns)
    elif fmt == "pdf":
        _write_pdf(results, path, columns)
    else:
        text = export_results(results, fmt=fmt, columns=columns)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return path


def _write_xlsx(results: SearchResults, path: str,
                columns: list[str] | None) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise ValidationError(
            "xlsx export needs openpyxl (pip install openpyxl)") from None
    cols, rows = _export_rows(results, columns)
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(cols)
    for r in rows:
        ws.append(r)
    wb.save(path)


def _write_pdf(results: SearchResults, path: str,
               columns: list[str] | None) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError:
        raise ValidationError(
            "pdf export needs reportlab (pip install reportlab)") from None
    cols, rows = _export_rows(results, columns)
    styles = getSampleStyleSheet()
    data = [cols] + [[(x[:58] + "…") if len(x) > 58 else x for x in r]
                     for r in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    doc = SimpleDocTemplate(path, pagesize=landscape(A4))
    doc.build([
        Paragraph(f"Advanced search — {results.query or '(all)'}",
                  styles["Title"]),
        Spacer(1, 8), table])


# ══════════════════════════════════════════════════════════════════
# Mail-merge, cohort export, contact sheet (items 37–39)
# ══════════════════════════════════════════════════════════════════

def mailmerge_results(results: SearchResults, *,
                      subject: str, body: str,
                      sender_staff_id: str | None = None,
                      send: bool = False) -> dict[str, Any]:
    """Create (or send) one message per student in the result set via the
    messaging module's bulk_send (item 37). Needs the comms capability;
    the sender is the signed-in member of staff unless one is given."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if p.username:
        p.require(access.COMMS, "messaging students")
        sender_staff_id = sender_staff_id or p.staff_id
    ids = _student_ids_from_results(results)
    if not ids:
        raise ValidationError("No students in the results to message")
    if not (subject or "").strip():
        raise ValidationError("subject is required")
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as msg,
    )
    res = msg.bulk_send(
        subject=subject, body=body, student_ids=ids,
        sender_staff_id=sender_staff_id,
        status="Sent" if send else "Draft")
    audit_export(results, "message" if send else "message draft",
                 f"{subject!r} to {len(ids)} student(s)", len(ids))
    return {
        "recipients": len(ids),
        "created": len(getattr(res, "created", []) or []),
        "failed": len(getattr(res, "failed", []) or []),
        "thread_id": getattr(res, "thread_id", None),
        "status": "Sent" if send else "Draft",
    }


def export_cohort(name_or_id: str | int, *, fmt: str = "json") -> str:
    """Serialise a cohort (with student names/emails) for hand-off to the
    reports/UCAS/messaging modules (item 38)."""
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    c = get_cohort(cid)
    assert c is not None
    from .annotations import log_action
    log_action("cohort export", f"{c.name} ({fmt})", c.member_count)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    students = []
    for sid in c.members:
        s = sm.get_student(sid)
        students.append({
            "student_id": sid,
            "full_name": s.full_name if s else None,
            "email": s.email if s else None,
        })
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return json.dumps(
            {"cohort": c.name, "notes": c.notes, "count": c.member_count,
             "students": students}, indent=2, ensure_ascii=False)
    if fmt in ("csv", "tsv"):
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf, delimiter="\t" if fmt == "tsv" else ",")
        w.writerow(["student_id", "full_name", "email"])
        for st in students:
            w.writerow([st["student_id"], st["full_name"] or "",
                        st["email"] or ""])
        return buf.getvalue()
    raise ValidationError(f"Unknown cohort export format {fmt!r}")


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


def contact_sheet(results: SearchResults, *, fmt: str = "html") -> str:
    """Printable contact sheet (one card per student) for a result set —
    no photo field exists, so initials stand in for an avatar (item 39)."""
    ids = _student_ids_from_results(results)
    audit_export(results, "contact sheet", fmt, len(ids))
    idx = student_group_index()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    cards = []
    for sid in ids:
        s = sm.get_student(sid)
        if s is None:
            continue
        yr, tg = idx.get(sid, (None, None))
        cards.append({
            "id": sid, "name": s.full_name, "email": s.email or "",
            "phone": s.phone or "", "subjects": ", ".join(s.subjects or []),
            "year": yr, "tutor": tg, "initials": _initials(s.full_name),
        })
    if fmt == "text":
        lines = [f"Contact sheet — {len(cards)} student(s)", ""]
        for c in cards:
            lines += [
                f"{c['name']}  ({c['id']})",
                f"  {c['email']}  ·  {c['phone'] or '—'}",
                f"  {c['subjects'] or '—'}",
                f"  year {c['year'] or '—'} · tutor {c['tutor'] or '—'}",
                "",
            ]
        return "\n".join(lines)
    import html as _h
    cells = ""
    for c in cards:
        cells += (
            "<div class='card'>"
            f"<div class='av'>{_h.escape(c['initials'])}</div>"
            f"<div class='nm'>{_h.escape(c['name'])}</div>"
            f"<div class='id'>{_h.escape(c['id'])}</div>"
            f"<div>{_h.escape(c['email'])}</div>"
            f"<div>{_h.escape(c['phone'] or '—')}</div>"
            f"<div>{_h.escape(c['subjects'] or '—')}</div>"
            f"<div>year {c['year'] or '—'} · tutor "
            f"{_h.escape(str(c['tutor'] or '—'))}</div>"
            "</div>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{font-family:sans-serif;margin:18px}"
        ".grid{display:flex;flex-wrap:wrap;gap:10px}"
        ".card{border:1px solid #aaa;border-radius:8px;padding:10px;"
        "width:230px;font-size:12px}"
        ".av{width:42px;height:42px;border-radius:50%;background:#5577aa;"
        "color:#fff;display:flex;align-items:center;justify-content:center;"
        "font-weight:bold;margin-bottom:6px}"
        ".nm{font-weight:bold;font-size:14px}.id{color:#666}"
        "</style></head><body>"
        f"<h2>Contact sheet — {len(cards)} student(s)</h2>"
        f"<div class='grid'>{cells}</div></body></html>")
