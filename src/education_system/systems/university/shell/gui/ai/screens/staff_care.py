"""Chatbot staff screens: the case queue (agents), answers and unanswered
questions (editors), settings and roles (administrators) and usage stats.

Every action runs a rule from ``university/application/chatbot/care`` or
``chatbot_knowledge`` through ``record_screens.call``, which checks the
person's permission again, so a tab being shown is a convenience only.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.ui import record_screens as rs

ADMIN_ROLES = ("admin", "administrator", "superadmin")


def _rules():
    from education_system.systems.university.application.chatbot import (
        care as chatbot_care,
        knowledge as chatbot_knowledge,
    )
    return chatbot_care, chatbot_knowledge


def _who(app):
    user = getattr(app, "current_user", None) or {}
    return str(user.get("username") or ""), str(user.get("role") or "").lower()


def permitted_tabs(app) -> list[str]:
    """Which staff tabs this person may open."""
    care, _knowledge = _rules()
    username, role = _who(app)
    if not username:
        return []
    agent = rs.call(app.root, care.holds, username, "agent", role, quiet=True) or False
    editor = rs.call(app.root, care.holds, username, "editor", role, quiet=True) or False
    tabs = []
    if agent is True:
        tabs.append("cases")
    if editor is True:
        tabs += ["answers", "unanswered"]
    if role in ADMIN_ROLES:
        tabs += ["settings", "roles"]
    if tabs:
        tabs.append("stats")
    return tabs


def _bar(parent):
    bar = ttk.Frame(parent)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)      # before the list: stays visible
    return bar


# ── cases ───────────────────────────────────────────────────────────────


def build_cases_tab(parent, app):
    care, _knowledge = _rules()
    username, role = _who(app)
    frame = ttk.Frame(parent)
    top = ttk.Frame(frame)
    top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
    status = tk.StringVar(value="open")
    ttk.Label(top, text="Show").pack(side=tk.LEFT)
    combo = ttk.Combobox(top, textvariable=status, values=("open", "answered", "closed", "all"),
                         state="readonly", width=12)
    combo.pack(side=tk.LEFT, padx=4)
    bar = _bar(frame)
    panes = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
    panes.pack(fill=tk.BOTH, expand=True, padx=8)
    left, right = ttk.Frame(panes), ttk.Frame(panes)
    panes.add(left, weight=2)
    panes.add(right, weight=3)
    tree = rs.make_tree(left, [("case", "Case", 60), ("kind", "Kind", 90), ("who", "From", 110),
                               ("status", "Status", 90), ("at", "Asked", 140)])
    detail = rs.Detail(right)
    detail.pack(fill=tk.BOTH, expand=True)
    rows = {}

    def refresh():
        wanted = None if status.get() == "all" else status.get()
        found = rs.call(frame, care.cases, username, role, wanted) or []
        rows.clear()
        rows.update({str(r["case_id"]): r for r in found})
        rs.fill(tree, found, lambda r: r["case_id"], lambda r: (
            r["case_id"], "CRISIS" if r["kind"] == "crisis" else "help", r["username"],
            r["status"], r["created_at"]))
        detail.clear("Select a case.")

    def show(_event=None):
        row = rows.get(rs.selected(tree) or "")
        if not row:
            return
        sections = [("Question", row["message"]),
                    ("", [("From", row["username"]), ("Status", row["status"]),
                          ("Assigned to", row.get("assigned_to"))])]
        if row["kind"] == "crisis":
            sections.insert(0, ("Crisis", "The safeguarding team owns this case "
                                f"(safeguarding case {row.get('safeguarding_case_id') or '—'}). "
                                "Follow up there; close it here when they have."))
        if row.get("answer"):
            sections.append(("Answer", f"{row['answer']}\n— {row.get('answered_by')}, "
                                       f"{row.get('answered_at')}"))
        detail.show(f"Case {row['case_id']}", sections)

    def chosen():
        cid = rs.selected(tree)
        if not cid:
            rs.info(frame, "Select a case first.")
        return int(cid) if cid else None

    def do_assign():
        cid = chosen()
        if cid is None:
            return
        got = rs.ask(frame, "Assign case", [rs.Field("to", "Assign to (username)", required=True)],
                     {"to": username})
        if got and rs.call(frame, care.assign, username, role, cid, got["to"],
                           write=True) is not None:
            refresh()

    def do_answer():
        cid = chosen()
        if cid is None:
            return
        got = rs.ask(frame, "Answer", [rs.Field("text", "Your answer (sent to their inbox)",
                                                "multiline", required=True)])
        if got and rs.call(frame, care.answer, username, role, cid, got["text"],
                           write=True) is not None:
            refresh()

    def do_close():
        cid = chosen()
        if cid is None or not rs.confirm(frame, "Close this case?"):
            return
        if rs.call(frame, care.close, username, role, cid, write=True) is not None:
            refresh()

    for label, cmd in (("Refresh", refresh), ("Assign…", do_assign), ("Answer…", do_answer),
                       ("Close", do_close)):
        ttk.Button(bar, text=label, command=cmd).pack(side=tk.LEFT, padx=3)
    tree.bind("<<TreeviewSelect>>", show)
    combo.bind("<<ComboboxSelected>>", lambda _e: refresh())
    refresh()
    return frame


# ── answers (FAQ) ───────────────────────────────────────────────────────


def _faq_fields(categories):
    return [rs.Field("question", "Question", required=True),
            rs.Field("answer", "Answer", "multiline", required=True),
            rs.Field("category", "Category", "combo", choices=categories),
            rs.Field("status", "Status", "combo", choices=["published", "draft", "retired"])]


CATEGORIES = ["academic", "financial", "technical", "wellbeing", "admissions", "general"]


def build_answers_tab(parent, app):
    _care, knowledge = _rules()
    username, role = _who(app)
    frame = ttk.Frame(parent)
    top = ttk.Frame(frame)
    top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
    status, search = tk.StringVar(value=""), tk.StringVar()
    ttk.Label(top, text="Status").pack(side=tk.LEFT)
    combo = ttk.Combobox(top, textvariable=status, values=("", "published", "draft", "retired"),
                         state="readonly", width=12)
    combo.pack(side=tk.LEFT, padx=4)
    ttk.Label(top, text="Search").pack(side=tk.LEFT, padx=(8, 0))
    entry = ttk.Entry(top, textvariable=search, width=28)
    entry.pack(side=tk.LEFT, padx=4)
    bar = _bar(frame)
    tree = rs.make_tree(frame, [("q", "Question", 360), ("cat", "Category", 90),
                                ("status", "Status", 80), ("views", "Shown", 60),
                                ("up", "Helpful", 70), ("down", "Not helpful", 85)])
    rows = {}

    def refresh(_event=None):
        found = rs.call(frame, knowledge.faqs, status.get() or None,
                        search.get().strip() or None) or []
        rows.clear()
        rows.update({str(r["faq_id"]): r for r in found})
        rs.fill(tree, found, lambda r: r["faq_id"], lambda r: (
            r["question"], r["category"], r.get("status") or "published", r.get("view_count") or 0,
            r.get("helpful_votes") or 0, r.get("not_helpful_votes") or 0))

    def save(row=None, **override):
        values = dict(row or {"status": "published", "category": "general"})
        values.update(override)
        if not override:
            got = rs.ask(frame, "Answer" if row else "New answer", _faq_fields(CATEGORIES), values)
            if not got:
                return
            values.update(got)
        if rs.call(frame, knowledge.save_faq, username, role, values["question"],
                   values["answer"], values.get("category") or "general",
                   values.get("status") or "published", (row or {}).get("faq_id"),
                   write=True) is not None:
            refresh()

    def current():
        row = rows.get(rs.selected(tree) or "")
        if not row:
            rs.info(frame, "Select an answer first.")
        return row

    ttk.Button(bar, text="New…", command=save).pack(side=tk.LEFT, padx=3)
    ttk.Button(bar, text="Edit…", command=lambda: (r := current()) and save(r)).pack(
        side=tk.LEFT, padx=3)
    ttk.Button(bar, text="Publish", command=lambda: (r := current()) and save(
        r, status="published")).pack(side=tk.LEFT, padx=3)
    ttk.Button(bar, text="Retire", command=lambda: (r := current()) and save(
        r, status="retired")).pack(side=tk.LEFT, padx=3)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=3)
    combo.bind("<<ComboboxSelected>>", refresh)
    entry.bind("<Return>", refresh)
    tree.bind("<Double-1>", lambda _e: (r := current()) and save(r))
    refresh()
    return frame


# ── unanswered questions ────────────────────────────────────────────────


def build_unanswered_tab(parent, app):
    _care, knowledge = _rules()
    username, role = _who(app)
    frame = ttk.Frame(parent)
    bar = _bar(frame)
    tree = rs.make_tree(frame, [("q", "Question", 460), ("n", "Times asked", 90),
                                ("last", "Last asked", 150)])
    rows = {}

    def refresh():
        found = rs.call(frame, knowledge.unanswered) or []
        rows.clear()
        rows.update({str(r["question_id"]): r for r in found})
        rs.fill(tree, found, lambda r: r["question_id"],
                lambda r: (r["question"], r["times_asked"], r["last_asked_at"]))

    def current():
        qid = rs.selected(tree)
        if not qid:
            rs.info(frame, "Select a question first.")
        return int(qid) if qid else None

    def answer():
        qid = current()
        if qid is None:
            return
        got = rs.ask(frame, "Answer this question",
                     [rs.Field("answer", "Answer (published as an FAQ)", "multiline",
                               required=True),
                      rs.Field("category", "Category", "combo", choices=CATEGORIES)],
                     {"category": "general"})
        if got and rs.call(frame, knowledge.resolve_unanswered, username, role, qid,
                           answer=got["answer"], category=got.get("category") or "general",
                           write=True) is not None:
            refresh()

    def dismiss():
        qid = current()
        if qid is not None and rs.call(frame, knowledge.resolve_unanswered, username, role, qid,
                                       dismiss=True, write=True) is not None:
            refresh()

    for label, cmd in (("Answer…", answer), ("Dismiss", dismiss), ("Refresh", refresh)):
        ttk.Button(bar, text=label, command=cmd).pack(side=tk.LEFT, padx=3)
    refresh()
    return frame


# ── settings, roles, stats ──────────────────────────────────────────────

SETTING_LABELS = {
    "counselling_contact": "University counselling contact",
    "wellbeing_contact": "Student wellbeing contact",
    "out_of_hours_number": "Out-of-hours support number",
    "security_number": "Campus security number",
    "reply_promise": "What people are told when they ask for a person",
    "retention_days": "Keep conversations for (days)",
}


def build_settings_tab(parent, app):
    care, knowledge = _rules()
    username, role = _who(app)
    frame = ttk.Frame(parent)
    bar = _bar(frame)
    body = ttk.Frame(frame, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text="These contacts appear in crisis and wellbeing answers. Leave a field "
                         "blank rather than guess — placeholders are refused.",
              wraplength=760, justify=tk.LEFT).grid(row=0, column=0, columnspan=2, sticky="w",
                                                    pady=(0, 8))
    current = rs.call(frame, care.settings) or {}
    vars_ = {}
    for n, (key, label) in enumerate(SETTING_LABELS.items(), 1):
        ttk.Label(body, text=label).grid(row=n, column=0, sticky="w", pady=3, padx=(0, 8))
        var = tk.StringVar(value=current.get(key, ""))
        ttk.Entry(body, textvariable=var, width=70).grid(row=n, column=1, sticky="ew", pady=3)
        vars_[key] = var
    body.columnconfigure(1, weight=1)

    def save():
        changed = 0
        for key, var in vars_.items():
            if var.get().strip() != str(current.get(key, "")).strip():
                if rs.call(frame, care.set_setting, username, role, key, var.get(),
                           write=True) is None:
                    return
                current[key] = var.get().strip()
                changed += 1
        rs.info(frame, f"Saved {changed} setting(s).")

    def purge():
        if not rs.confirm(frame, "Delete conversations older than the retention period now?"):
            return
        gone = rs.call(frame, knowledge.purge, write=True)
        if gone is not None:
            rs.info(frame, f"Deleted {0 if gone is True else gone} old conversation turn(s).")

    ttk.Button(bar, text="Save settings", command=save).pack(side=tk.LEFT, padx=3)
    ttk.Button(bar, text="Delete old conversations now", command=purge).pack(side=tk.LEFT,
                                                                              padx=3)
    return frame


def build_roles_tab(parent, app):
    care, _knowledge = _rules()
    username, role = _who(app)
    frame = ttk.Frame(parent)
    bar = _bar(frame)
    tree = rs.make_tree(frame, [("user", "Username", 160), ("role", "Role", 100),
                                ("by", "Granted by", 140), ("at", "Granted", 160)])

    def refresh():
        found = rs.call(frame, care.roles) or []
        rs.fill(tree, found, lambda r: f"{r['username']}|{r['role']}",
                lambda r: (r["username"], r["role"], r.get("granted_by"), r["granted_at"]))

    def grant():
        got = rs.ask(frame, "Give a chatbot role",
                     [rs.Field("user", "Member of staff", "staff",
                               choices=rs.staff_choices(frame), required=True),
                      rs.Field("role", "Role", "combo", choices=["agent", "editor"],
                               required=True)], {"role": "agent"})
        if got and rs.call(frame, care.grant, username, role, got["user"], got["role"],
                           write=True) is not None:
            refresh()

    def revoke():
        key = rs.selected(tree)
        if not key:
            rs.info(frame, "Select a role first.")
            return
        who, held = key.split("|", 1)
        if rs.confirm(frame, f"Remove {held} from {who}?") and rs.call(
                frame, care.revoke, username, role, who, held, write=True) is not None:
            refresh()

    for label, cmd in (("Give role…", grant), ("Remove role", revoke), ("Refresh", refresh)):
        ttk.Button(bar, text=label, command=cmd).pack(side=tk.LEFT, padx=3)
    refresh()
    return frame


def build_stats_tab(parent, app):
    _care, knowledge = _rules()
    frame = ttk.Frame(parent)
    bar = _bar(frame)
    detail = rs.Detail(frame)
    detail.pack(fill=tk.BOTH, expand=True, padx=8)

    def refresh():
        s = rs.call(frame, knowledge.stats) or {}
        detail.show("Chatbot usage", [("", [
            ("Conversation turns kept", s.get("turns")),
            ("Answered without falling back", f"{s.get('answered_pct')}%"
             if s.get("answered_pct") is not None else None),
            ("Ratings given", s.get("ratings")),
            ("Rated helpful", f"{s.get('helpful_pct')}%" if s.get("helpful_pct") is not None
             else None),
            ("Open cases", s.get("open_cases")),
            ("Unanswered questions waiting", s.get("open_unanswered"))])])

    ttk.Button(bar, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=3)
    refresh()
    return frame


BUILDERS = {"cases": ("Cases", build_cases_tab), "answers": ("Answers (FAQ)", build_answers_tab),
            "unanswered": ("Unanswered questions", build_unanswered_tab),
            "settings": ("Chatbot settings", build_settings_tab),
            "roles": ("Chatbot roles", build_roles_tab), "stats": ("Usage", build_stats_tab)}


def add_tabs(notebook, app, tabs=None) -> int:
    """Add the permitted staff tabs to ``notebook``. Returns how many."""
    tabs = permitted_tabs(app) if tabs is None else tabs
    for key in tabs:
        title, builder = BUILDERS[key]
        notebook.add(builder(notebook, app), text=f"  {title}  ")
    return len(tabs)


def open_staff_desk(app):
    """A window with the tabs this person may use (agents, editors)."""
    tabs = permitted_tabs(app)
    if not tabs:
        rs.info(app.root, "The chatbot staff desk is for chatbot agents, editors and "
                          "administrators.")
        return None
    win = tk.Toplevel(app.root)
    win.title("Chatbot staff desk")
    win.geometry("1100x680")
    notebook = ttk.Notebook(win)
    notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    add_tabs(notebook, app, tabs)
    return win
