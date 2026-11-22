"""What the person chatting can do about their own conversations and
questions: the privacy notice, rating answers, asking for a person, seeing
staff replies, downloading or deleting what the chatbot holds.

Rules live in ``university/application/chatbot/care`` and
``chatbot_knowledge``; each action runs one of them through
``record_screens.call``.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.infrastructure.ui import record_screens as rs


def _rules():
    from education_system.systems.university.application.chatbot import (
        care as chatbot_care,
        knowledge as chatbot_knowledge,
    )
    return chatbot_care, chatbot_knowledge


class CareMixin:
    """Privacy, feedback, human help and data rights for the chat window."""

    def initialize_care(self):
        self._turn_ids = {}            # rating key -> chatbot_conversations row id
        self._turn_by_token = {}       # worker token -> logged turn id
        self._pending_turn_id = None
        self._apply_retention()

    def _care_user(self):
        user = getattr(self, "current_user", None) or {}
        return str(user.get("username") or ""), str(user.get("role") or "").lower()

    # ── privacy ─────────────────────────────────────────────────────────
    def show_privacy_notice_once(self):
        """Shown in the chat once per session; Help ▸ Privacy notice repeats it."""
        if getattr(self, "_privacy_shown", False):
            return
        _care, knowledge = _rules()
        notice = rs.call(self.root, knowledge.privacy_notice, quiet=True)
        if notice and hasattr(self, "add_chat_message"):
            self.add_chat_message("Privacy", notice, "system")
        self._privacy_shown = True

    def show_privacy_notice(self):
        _care, knowledge = _rules()
        notice = rs.call(self.root, knowledge.privacy_notice)
        if notice:
            rs.info(self.root, notice)

    def _apply_retention(self):
        """The window's own conversation list follows the university's
        retention period too."""
        care, _knowledge = _rules()
        settings = rs.call(self.root, care.settings, quiet=True) or {}
        store = getattr(self, "conversation_store", None)
        try:
            days = int(settings.get("retention_days") or 0)
        except (TypeError, ValueError):
            days = 0
        if store is not None and days and hasattr(store, "purge_older_than"):
            try:
                store.purge_older_than(days)
            except Exception:
                pass

    # ── feedback ────────────────────────────────────────────────────────
    def remember_turn(self, message_id):
        """The key the rating buttons use for this bot answer: the saved
        message id, or ``turn:<id>`` when history is switched off."""
        turn = getattr(self, "_pending_turn_id", None)
        self._pending_turn_id = None
        if not turn:
            return message_id
        key = message_id if message_id is not None else f"turn:{turn}"
        self.__dict__.setdefault("_turn_ids", {})[key] = turn
        return key

    def send_turn_feedback(self, message_id, helpful, comment=""):
        """Record the rating against the logged turn (feeds the FAQ counts)."""
        turn = self.__dict__.get("_turn_ids", {}).get(message_id)
        if not turn:
            return
        _care, knowledge = _rules()
        username, _role = self._care_user()
        rs.call(self.root, knowledge.give_feedback, username, turn, helpful, comment,
                write=True, quiet=True)

    # ── a person ────────────────────────────────────────────────────────
    def speak_to_person(self):
        """Open a real case in the chatbot agents' queue."""
        last = getattr(self, "_last_user_message", "") or ""
        got = rs.ask(self.root, "Speak to a person",
                     [rs.Field("question", "What do you need help with?", "multiline",
                               required=True)], {"question": last})
        if not got:
            return
        username, _role = self._care_user()
        reply = self.chatbot.escalate_to_human(got["question"], username)
        self.add_chat_message("Chatbot", reply, "system")

    def show_my_cases(self):
        care, _knowledge = _rules()
        username, _role = self._care_user()
        cases = rs.call(self.root, care.my_cases, username) or []
        win = tk.Toplevel(self.root)
        win.title("My questions to staff")
        win.geometry("820x480")
        bar = ttk.Frame(win)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        tree = rs.make_tree(win, [("case", "Case", 60), ("asked", "Asked", 150),
                                  ("status", "Status", 90), ("q", "Question", 420)], height=8)
        detail = rs.Detail(win)
        detail.pack(fill=tk.BOTH, expand=True, padx=8)
        rows = {str(c["case_id"]): c for c in cases}
        rs.fill(tree, cases, lambda c: c["case_id"],
                lambda c: (c["case_id"], c["created_at"], c["status"], c["message"][:120]))

        def show(_event=None):
            c = rows.get(rs.selected(tree) or "")
            if c:
                detail.show(f"Case {c['case_id']}", [
                    ("You asked", c["message"]),
                    ("Reply", c.get("answer") or "No reply yet — you'll get it in your inbox.")])

        tree.bind("<<TreeviewSelect>>", show)
        if not cases:
            detail.clear("You haven't asked staff anything through the chatbot.")

    # ── data rights ─────────────────────────────────────────────────────
    def download_my_conversations(self):
        _care, knowledge = _rules()
        username, _role = self._care_user()
        data = rs.call(self.root, knowledge.export, username)
        if data is None:
            return
        store = getattr(self, "conversation_store", None)
        if store is not None:
            try:
                data["window_conversations"] = [
                    {**c, "messages": store.messages(c["id"])}
                    for c in store.list(username, limit=10000)]
            except Exception:
                pass
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                            initialfile=f"chatbot_{username}.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        rs.info(self.root, f"Saved to {path}")

    def delete_my_conversations(self):
        if not rs.confirm(self.root, "Delete all your chatbot conversations? Questions you sent "
                                     "to staff, and anything passed to the safeguarding team, "
                                     "are kept."):
            return
        _care, knowledge = _rules()
        username, role = self._care_user()
        result = rs.call(self.root, knowledge.erase, username, role, username, write=True)
        if result is None:
            return
        store = getattr(self, "conversation_store", None)
        if store is not None:
            try:
                store.delete_all(username)
            except Exception:
                pass
        rs.info(self.root, f"Deleted {result.get('conversations', 0)} conversation turn(s).")

    def open_staff_desk(self):
        from education_system.systems.university.shell.gui.ai.screens import staff_care
        staff_care.open_staff_desk(self)
