"""Shared CLI plumbing for the integrity menus."""

from __future__ import annotations

import json
import textwrap
from contextlib import contextmanager

from education_system.systems.university.application.integrity import access


def ask(prompt, default="") -> str:
    try:
        value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return value or str(default)


def ask_int(prompt):
    value = ask(prompt)
    return int(value) if value.isdigit() else None


LIST_LIMIT = 25


def choose(prompt, options, default=None, optional=False):
    """Pick from ``options`` (``[(value, label)]``): a numbered list, the
    number or the value itself, or some text to narrow a long list. Returns
    the value, or ``None`` when left blank (``optional``) or nothing fits."""
    options = list(options or [])
    if not options:
        print(f"  (nothing to choose for {prompt.lower()})")
        return None
    shown = options
    while True:
        if len(shown) > LIST_LIMIT:
            print(f"  {len(shown)} to choose from — type part of a name or number to "
                  f"narrow the list, or the value itself.")
        else:
            for n, (_value, label) in enumerate(shown, 1):
                print(f"  {n:>3}. {label}")
        hint = " (Enter to skip)" if optional else ""
        answer = ask(f"{prompt}{hint}", "" if default is None else default)
        if not answer:
            return None if optional or default is None else default
        if answer.isdigit() and len(shown) <= LIST_LIMIT and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1][0]
        exact = [v for v, _label in options if str(v).lower() == answer.lower()]
        if exact:
            return exact[0]
        narrowed = [o for o in options if answer.lower() in o[1].lower()]
        if len(narrowed) == 1:
            return narrowed[0][0]
        if not narrowed:
            print("  Nothing matches; try again.")
            continue
        shown = narrowed


def pause() -> None:
    ask("\nPress Enter to continue")


@contextmanager
def session(auth):
    """``(conn, who)`` for the signed-in user; commits on success and then
    sends any e-mails collected in ``conn.integrity_emails``."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    outbox: list = []
    try:
        access.ensure(conn)
        who = access.from_user(conn, getattr(auth, "current_user", None) if auth else None)
        if who is None:
            raise PermissionError("Please sign in first")
        yield conn, who, outbox
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if outbox:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(outbox)


def run(auth, action, *args) -> None:
    """Run ``action(conn, who, outbox, *args)`` and report refusals plainly."""
    try:
        with session(auth) as (conn, who, outbox):
            action(conn, who, outbox, *args)
    except (PermissionError, ValueError) as exc:
        print(f"\n{exc}")


def table(rows, columns) -> None:
    if not rows:
        print("  (none)")
        return
    widths = [max(len(str(c)), *(len(str(r.get(c, "") if r.get(c) is not None else ""))
                                  for r in rows)) for c in columns]
    widths = [min(w, 40) for w in widths]
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(columns, widths)))
    for r in rows:
        print("  " + "  ".join(str(r.get(c) if r.get(c) is not None else "")[:w].ljust(w)
                               for c, w in zip(columns, widths)))


def wrap(text, indent="    ") -> str:
    return textwrap.fill(str(text or ""), 90, initial_indent=indent, subsequent_indent=indent)


def pct(value) -> str:
    return f"{float(value or 0):.0%}"


def save_json(data, path) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    return path


def print_case_parts(case) -> None:
    """The statement deadline, statements and evidence of a case."""
    if case.get("response_due"):
        print(f"  Statement due by {case['response_due']}")
    for st in case.get("statements") or []:
        print(wrap(f"Statement {st['submitted_at'][:16]}: {st['statement']}", "  "))
    for e in case.get("evidence") or []:
        marks = [m for m, on in (("withdrawn", e.get("removed_at")),
                                 ("internal", not e.get("visible_to_student")),
                                 (f"file {e.get('file_name')}", e.get("file_name"))) if on]
        print(wrap(f"Evidence #{e['evidence_id']} {e['added_at'][:10]} {e['kind']}: {e['title']}"
                   + (f" [{', '.join(marks)}]" if marks else "")
                   + (f" — {e['detail']}" if e.get("detail") else ""), "  "))


def show_evidence_file(conn, who) -> None:
    from education_system.systems.university.application.integrity import evidence
    evidence_id = ask_int("Evidence number")
    if not evidence_id:
        return
    found = evidence.evidence_file(conn, who, evidence_id)
    state = "" if found["intact"] else " (WARNING: it no longer matches the attached copy)"
    print(f"  {found['name']}: {found['path']}{state}")


def add_case_evidence(conn, who, case_id, officer) -> None:
    from education_system.systems.university.application.integrity import evidence
    kind = {"1": "note", "2": "meeting_record", "3": "file"}.get(
        ask("1 note  2 meeting record  3 file"))
    if not kind:
        return
    title = ask("Title")
    path = ask("Path to the file") if kind == "file" else None
    detail = ask("Note / record" if kind != "file" else "What it shows (optional)")
    visible, reason = True, ""
    if officer and ask("Can the student see it? (y/n)", "y").lower() != "y":
        visible, reason = False, ask("Why not")
    evidence.add_evidence(conn, who, case_id, kind=kind, title=title, detail=detail,
                          file_path=path, visible_to_student=visible, internal_reason=reason)
    print("  Evidence added.")
