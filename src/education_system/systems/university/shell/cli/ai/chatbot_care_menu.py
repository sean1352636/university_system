"""Chatbot support, privacy and staff tools for the CLI.

People chatting can rate answers, ask for a person, see their questions to
staff, and download or delete their conversations. Staff get the menus
their chatbot role allows (``chatbot_care.holds``): agents work the case
queue, editors manage FAQ answers and unanswered questions, admins also
change settings, roles and run the retention purge. Crisis cases are for
admins only and show the linked safeguarding case.

Every action runs in one transaction; refusals are printed; e-mails go out
after the commit.
"""

from __future__ import annotations

import json

from education_system.systems.university.application.chatbot import care
from education_system.systems.university.application.chatbot import knowledge
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.ui.record_screens import send_emails

_SHOWN_NOTICE: set[str] = set()


def _run(fn, *args, **kwargs):
    """Run a rule in one transaction. ``None`` when refused."""
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
    except (ValueError, PermissionError) as exc:
        conn.rollback()
        print(f"  {exc}")
        return None
    except Exception as exc:
        conn.rollback()
        print(f"  That did not work: {exc}")
        return None
    finally:
        conn.close()
    emails = result.get("emails") if isinstance(result, dict) else (
        result if isinstance(result, list) and result and isinstance(result[0], tuple) else None)
    if emails:
        send_emails(emails)
    return True if result is None else result


def _ask(prompt, default=""):
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _menu(title, items):
    """``items``: [(label, fn)]; runs until 0."""
    while True:
        print(f"\n{title}\n" + "=" * len(title))
        for n, (label, _fn) in enumerate(items, 1):
            print(f"  {n}. {label}")
        print("  0. Back")
        choice = input("Choose: ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            items[int(choice) - 1][1]()
        else:
            print("  Invalid choice.")


def _user(auth):
    user = getattr(auth, "current_user", None) or {}
    return str(user.get("username") or ""), str(user.get("role") or "").lower()


# ── for the person chatting ─────────────────────────────────────────────


def show_privacy_notice(username):
    """Print the privacy notice once per person per run."""
    if username in _SHOWN_NOTICE:
        return
    _SHOWN_NOTICE.add(username)
    notice = _run(lambda conn: knowledge.privacy_notice(conn))
    if notice and notice is not True:
        print(f"\nPrivacy: {notice}\n")


def ask_feedback(chatbot, username):
    """After an answer: 'Was that helpful?' (y/n/skip)."""
    row_id = getattr(chatbot, "last_turn_id", None)
    if not row_id:
        return
    answer = input("  Was that helpful? (y/n/skip): ").strip().lower()
    if answer not in ("y", "n", "yes", "no"):
        return
    helpful = answer.startswith("y")
    comment = "" if helpful else input("  What was missing? (optional): ").strip()
    if _run(knowledge.give_feedback, username, row_id, helpful, comment):
        print("  Thank you.")


def speak_to_person(chatbot, username):
    question = _ask("What do you need help with")
    if not question:
        return
    if chatbot is not None and hasattr(chatbot, "escalate_to_human"):
        print(f"Chatbot: {chatbot.escalate_to_human(question, username)}")
        return
    result = _run(care.open_case, username, question)
    if result and result is not True:
        print(f"Chatbot: {result['reply']}")


def my_questions(username):
    rows = _run(care.my_cases, username) or []
    if rows is True or not rows:
        print("  You have no questions with staff.")
        return
    for c in rows:
        print(f"\n  Case {c['case_id']} [{c['status']}] {c['created_at']}")
        print(f"    You asked: {c['message'][:200]}")
        if c.get("answer"):
            print(f"    Reply ({c['answered_at']}): {c['answer']}")


def download_my_conversations(username):
    data = _run(knowledge.export, username)
    if not data or data is True:
        return
    path = _ask("Save to file", f"chatbot_{username}.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        print(f"  Saved {len(data['conversations'])} conversation turn(s) to {path}")
    except OSError as exc:
        print(f"  Could not save: {exc}")


def delete_my_conversations(username, role):
    if _ask("Delete all your chatbot conversations? Type DELETE to confirm") != "DELETE":
        print("  Nothing deleted.")
        return
    result = _run(knowledge.erase, username, role, username)
    if result and result is not True:
        print(f"  Deleted {result['conversations']} conversation turn(s) and "
              f"{result['feedback']} rating(s). Messages tied to a safeguarding concern are kept.")


def self_service_menu(chatbot, auth):
    username, role = _user(auth)
    _menu("Chatbot support & privacy", [
        ("Speak to a person", lambda: speak_to_person(chatbot, username)),
        ("My questions to staff", lambda: my_questions(username)),
        ("Download my conversations", lambda: download_my_conversations(username)),
        ("Delete my conversations", lambda: delete_my_conversations(username, role)),
        ("Privacy notice", lambda: (_SHOWN_NOTICE.discard(username),
                                    show_privacy_notice(username))),
    ])


# ── staff: cases ────────────────────────────────────────────────────────


def _list_cases(username, role):
    status = _ask("Status (open/answered/closed, blank = open)", "open")
    rows = _run(care.cases, username, role, status if status != "all" else None)
    if not rows or rows is True:
        print("  No cases.")
        return
    for c in rows:
        extra = (f" safeguarding case {c['safeguarding_case_id']}"
                 if c["kind"] == "crisis" else "")
        print(f"  {c['case_id']:>4} {c['kind']:<10} {c['status']:<9} {c['username']:<12} "
              f"{c['created_at']}{extra}")
        print(f"       {c['message'][:150]}")


def _case_id():
    value = _ask("Case id")
    return int(value) if value.isdigit() else None


def _assign(username, role):
    cid = _case_id()
    if cid:
        if _run(care.assign, username, role, cid, _ask("Assign to (username)", username)):
            print("  Assigned.")


def _answer(username, role):
    cid = _case_id()
    if cid:
        text = _ask("Answer (sent to the person's inbox)")
        if _run(care.answer, username, role, cid, text):
            print("  Answered.")


def _close(username, role):
    cid = _case_id()
    if cid and _run(care.close, username, role, cid, _ask("Note (optional)")):
        print("  Closed.")


def cases_menu(username, role):
    _menu("Chatbot cases", [
        ("List cases", lambda: _list_cases(username, role)),
        ("Assign a case", lambda: _assign(username, role)),
        ("Answer a case", lambda: _answer(username, role)),
        ("Close a case", lambda: _close(username, role)),
    ])


# ── staff: FAQ answers and unanswered questions ─────────────────────────


def _list_faqs():
    status = _ask("Status (published/draft/retired, blank = all)")
    search = _ask("Search (blank = all)")
    rows = _run(knowledge.faqs, status or None, search or None) or []
    if rows is True or not rows:
        print("  No answers.")
        return
    for f in rows:
        print(f"  {f['faq_id']:>4} [{f.get('status') or 'published'}] ({f['category']}) "
              f"{f['question']}")
        print(f"       {f['answer'][:150]}  (helpful {f.get('helpful_votes') or 0} / not "
              f"{f.get('not_helpful_votes') or 0})")


def _save_faq(username, role, existing=False):
    faq_id = None
    current = {}
    if existing:
        value = _ask("Answer id")
        if not value.isdigit():
            return
        faq_id = int(value)
        found = [f for f in (_run(knowledge.faqs) or []) if f["faq_id"] == faq_id]
        if not found:
            print("  No such answer.")
            return
        current = found[0]
    question = _ask("Question", current.get("question", ""))
    answer = _ask("Answer", current.get("answer", ""))
    category = _ask("Category", current.get("category", "general"))
    status = _ask("Status (published/draft/retired)", current.get("status") or "published")
    saved = _run(knowledge.save_faq, username, role, question, answer, category, status, faq_id)
    if saved:
        print(f"  Saved answer {saved}.")


def _list_unanswered():
    rows = _run(knowledge.unanswered) or []
    if rows is True or not rows:
        print("  Nothing waiting.")
        return
    for q in rows:
        print(f"  {q['question_id']:>4} asked {q['times_asked']}x (last {q['last_asked_at']}): "
              f"{q['question'][:150]}")


def _resolve_unanswered(username, role):
    value = _ask("Question id")
    if not value.isdigit():
        return
    if _ask("Answer it (a) or dismiss it (d)", "a").lower().startswith("d"):
        if _run(knowledge.resolve_unanswered, username, role, int(value), dismiss=True):
            print("  Dismissed.")
        return
    answer = _ask("Answer")
    faq = _run(knowledge.resolve_unanswered, username, role, int(value), answer=answer,
               category=_ask("Category", "general"))
    if faq:
        print(f"  Published as answer {faq}.")


def knowledge_menu(username, role):
    _menu("Chatbot answers", [
        ("List / search answers", _list_faqs),
        ("Add an answer", lambda: _save_faq(username, role)),
        ("Edit, publish or retire an answer", lambda: _save_faq(username, role, True)),
        ("Unanswered questions", _list_unanswered),
        ("Answer or dismiss an unanswered question", lambda: _resolve_unanswered(username, role)),
    ])


# ── admin: settings, roles, retention, stats ────────────────────────────


def _show_settings():
    s = _run(care.settings) or {}
    for key, value in (s.items() if isinstance(s, dict) else []):
        print(f"  {key}: {value or '(not set)'}")


def _set_setting(username, role):
    print("  Settings: " + ", ".join(care.SETTINGS))
    key = _ask("Setting")
    if key and _run(care.set_setting, username, role, key, _ask("Value")):
        print("  Saved.")


def _purge():
    gone = _run(knowledge.purge)
    if gone is not None:
        print(f"  Deleted {0 if gone is True else gone} old conversation turn(s).")


def _roles(username, role):
    for r in _run(care.roles) or []:
        print(f"  {r['username']:<14} {r['role']}")
    action = _ask("Give (g), remove (r) or back (enter)").lower()
    if action in ("g", "r"):
        who, which = _ask("Username"), _ask("Role (agent/editor)")
        fn = care.grant if action == "g" else care.revoke
        if _run(fn, username, role, who, which):
            print("  Done.")


def _stats():
    s = _run(knowledge.stats) or {}
    for key, value in (s.items() if isinstance(s, dict) else []):
        print(f"  {key.replace('_', ' ')}: {value if value is not None else '—'}")


def staff_menu(auth):
    """The chatbot staff tools this person's role allows (None if none)."""
    username, role = _user(auth)
    items = []
    conn = get_connection(row_factory=False)
    try:
        agent = care.holds(conn, username, "agent", role)
        editor = care.holds(conn, username, "editor", role)
    finally:
        conn.close()
    if agent:
        items.append(("Cases (people asking for help)", lambda: cases_menu(username, role)))
    if editor:
        items.append(("Answers and unanswered questions", lambda: knowledge_menu(username, role)))
    if role in care.ADMIN_ROLES:
        items += [("Show settings", _show_settings),
                  ("Change a setting", lambda: _set_setting(username, role)),
                  ("Staff roles", lambda: _roles(username, role)),
                  ("Delete conversations past retention now", _purge)]
    if agent or editor:
        items.append(("Statistics", _stats))
    if not items:
        print("  You have no chatbot staff role. Ask an administrator.")
        return
    _menu("Chatbot staff tools", items)


def has_staff_role(auth) -> bool:
    username, role = _user(auth)
    if not username:
        return False
    conn = get_connection(row_factory=False)
    try:
        return care.holds(conn, username, "agent", role) or care.holds(conn, username, "editor",
                                                                        role)
    finally:
        conn.close()


__all__ = ["show_privacy_notice", "ask_feedback", "self_service_menu", "staff_menu",
           "has_staff_role", "speak_to_person", "my_questions", "download_my_conversations",
           "delete_my_conversations"]
