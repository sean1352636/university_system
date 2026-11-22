"""Shared prompts and printing for the AI Content Detector's CLI menus.

Pickers offer real ids (module code, student number, assignment id) for the
modules the signed-in person reviews; readings are printed as level,
strength, whether they wait for review, how much text they rest on, the
indicators with their meaning, and the notice that they are indicators, not
evidence."""

from __future__ import annotations

import json

NOTICE = ("These are indicators, not evidence: no tool can tell reliably whether a person or a "
          "model wrote a text. Review it with the student.")


def detector():
    import education_system.systems.university.shell.cli.ai.ai_detector.interface as iface
    return iface.ai_detector


def ask(prompt, default="") -> str:
    try:
        value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return value or str(default)


def pause() -> None:
    ask("\nPress Enter to continue")


def read_text(prompt="Paste the text (finish with two empty lines), or give a file path"):
    """Text typed/pasted, or read from a file path."""
    print(f"\n{prompt}:")
    lines, empty = [], 0
    while empty < 2:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        empty = empty + 1 if not line.strip() else 0
        lines.append(line)
    text = "\n".join(lines).strip()
    if text and "\n" not in text and text.lower().endswith((".txt", ".md", ".pdf", ".docx")):
        from education_system.systems.university.infrastructure.integrity import text_extract
        try:
            return text_extract.extract(text), text_extract.file_type(text)
        except ValueError as exc:
            print(f"  {exc}")
            return "", "txt"
    return text, "txt"


def _connect():
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(row_factory=False)


def who():
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    user = getattr(detector(), "current_user", None)
    conn = _connect()
    try:
        return integrity_access.from_user(conn, user) if user else None
    finally:
        conn.close()


def is_officer() -> bool:
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    person = who()
    if person is None:
        return False
    conn = _connect()
    try:
        return integrity_access.is_officer(conn, person)
    finally:
        conn.close()


def require_officer() -> bool:
    if is_officer():
        return True
    print("  Only an integrity officer can do this.")
    return False


def _choose(rows, title, allow_blank=False):
    if not rows:
        print(f"  No {title} to choose from.")
        return None
    for i, (_id, label) in enumerate(rows, 1):
        print(f"  {i:3}. {label}")
    value = ask(f"Choose {title}" + (" (Enter for none)" if allow_blank else ""))
    if not value:
        return None
    if value.isdigit() and 1 <= int(value) <= len(rows):
        return rows[int(value) - 1][0]
    for item_id, _label in rows:
        if str(item_id) == value:
            return item_id
    print("  Not in the list.")
    return None


def pick_module():
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    person = who()
    conn = _connect()
    try:
        allowed = integrity_access.taught_modules(conn, person) if person else []
        rows = conn.execute("SELECT module_code, module_name FROM modules WHERE module_code IS "
                            "NOT NULL ORDER BY module_code").fetchall()
    finally:
        conn.close()
    return _choose([(c, f"{c} - {n or ''}") for c, n in rows if allowed is None or c in allowed],
                   "a module")


def pick_student(module_code):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT s.student_id, s.first_name, s.last_name FROM students s JOIN "
            "student_modules sm ON sm.student_id = s.student_id WHERE sm.module_code = ? ORDER "
            "BY s.last_name, s.first_name", (module_code,)).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    if not rows:
        value = ask("Student number")
        return value or None
    return _choose([(r[0], f"{r[1] or ''} {r[2] or ''} ({r[0]})") for r in rows], "a student")


def pick_assignment(module_code):
    conn = _connect()
    try:
        rows = conn.execute("SELECT id, title, due_date FROM assignments WHERE module_code = ? "
                            "ORDER BY due_date DESC", (module_code,)).fetchall()
    finally:
        conn.close()
    return _choose([(r[0], f"{r[1]} (due {str(r[2] or '')[:10]})") for r in rows],
                   "an assignment", allow_blank=True)


def summary(result) -> str:
    reading = result.get("detailed_results") if isinstance(result.get("detailed_results"),
                                                           dict) else result
    strength = result.get("strength", reading.get("strength"))
    words = result.get("words_checked") or reading.get("words_checked") or 0
    level = result.get("level") or reading.get("level") or "—"
    if strength is None:
        return f"{level} (based on {words} words)"
    review = "waits for review" if result.get("needs_review") else "below the review level"
    return f"{level} — strength {float(strength):.2f}, {review}, based on {words} words"


def print_reading(result) -> None:
    if result.get("skipped"):
        print(f"\n  Not read: {result.get('reason')}")
        return
    print("\n" + "=" * 70)
    print(f"Reading {result.get('result_id')} (submission {result.get('submission_id')}) — "
          f"student {result.get('student_id')}, module {result.get('course_code')}")
    print(summary(result))
    print(NOTICE)
    for title, rows in (("Indicators", result.get("indicators") or []),
                        ("Informational", result.get("informational") or [])):
        if rows:
            print(f"\n{title}:")
            for i in rows:
                print(f"  • {i.get('label')}: {i.get('shown')}")
                print(f"      {i.get('meaning')}")
    passages = result.get("passages") or []
    if passages:
        print(f"\nPassages behind the indicators: {len(passages)}")
    for rec in result.get("recommendations") or []:
        print(f"  → {rec}")
    print("=" * 70)


def print_sentences(text, passages) -> None:
    """The text sentence by sentence with the indicator passages in each."""
    from education_system.systems.university.shared.ai.ai_detector.detector import (
        reading,
    )
    names = {"artefact": "leftover chat text", "stock": "stock phrasing",
             "opener": "formulaic opening"}
    rows = reading.sentence_breakdown(text, passages)
    print(f"\nSentence by sentence ({len(rows)}) — where the indicator passages fall:")
    for r in rows:
        kinds = ", ".join(f"{names.get(k, k)} x{n}" for k, n in r["kinds"].items()) or "—"
        mark = "*" if r["kinds"] else " "
        print(f" {mark}{r['index']:>3}. [{r['share']:>4.0%}] {kinds}")
        print(f"       {r['text'][:160]}")


def offer_sentences(result, text) -> None:
    """Ask whether to show the sentence-by-sentence view of a reading."""
    if text and result.get("indicators") and \
            ask("Show it sentence by sentence? (y/n)", "n").lower() == "y":
        print_sentences(text, result.get("passages") or [])


def show(value, title=None) -> None:
    """Print a backend result readably."""
    if title:
        print(f"\n{title}\n" + "-" * len(title))
    if isinstance(value, dict) and value.get("success") is False:
        print(f"  Not done: {value.get('error')}")
        return
    if isinstance(value, dict) and value.get("error"):
        print(f"  {value['error']}")
        return
    print(json.dumps(value, indent=2, default=str))


def run(fn, *args, title=None, **kwargs):
    """Call ``fn`` and print the result; refusals print plainly."""
    try:
        out = fn(*args, **kwargs)
    except (PermissionError, ValueError) as exc:
        print(f"  {exc}")
        return None
    show(out, title)
    return out
