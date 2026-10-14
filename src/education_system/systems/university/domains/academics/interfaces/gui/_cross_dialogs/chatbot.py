"""The embedded university chatbot panel."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk


class ChatbotPanel(ttk.Frame):
    """Inline chatbot side-panel for any GUI.

    Wraps the existing ``UniversityChatbot`` instance and adds two
    integration touches:

    * ``scope`` is auto-attached to every prompt the user types, so
      "what's the timetable?" inside Module Scheduling becomes
      "what's the timetable for module {scope}?" — no need to retype
      context.
    * Reads/writes use the canonical ``chatbot_tools.call_tool``
      surface via the chatbot's normal message pipeline.

    Heavy by Tk standards; lazy-loads the chatbot on first message
    so embedding the panel doesn't spin it up unless needed.
    """

    def __init__(self, master: tk.Misc, *,
                 scope: str | None = None,
                 user_id: str = "anonymous",
                 height: int = 14) -> None:
        super().__init__(master)
        self._scope = scope
        self._user_id = user_id
        self._chatbot = None  # lazy

        self._heading_var = tk.StringVar(value=self._heading_text())
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        from tkinter import scrolledtext
        self._log = scrolledtext.ScrolledText(
            self, height=height, wrap="word", state="disabled",
            font=("Helvetica", 9),
        )
        self._log.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._entry = ttk.Entry(entry_frame)
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<Return>", lambda _e: self._send())
        ttk.Button(entry_frame, text=_t('gui.academics.cross_dialogs.buttons.send', default="Send"), command=self._send).pack(
            side="left", padx=(4, 0),
        )

        self._append("Chatbot ready. Ask anything about your scope.\n")

    def set_scope(self, scope: str | None) -> None:
        self._scope = scope
        self._heading_var.set(self._heading_text())

    def _heading_text(self) -> str:
        return f"Assistant — {self._scope}" if self._scope else "Assistant"

    def _append(self, text: str) -> None:
        try:
            self._log.configure(state="normal")
            self._log.insert("end", text)
            self._log.see("end")
            self._log.configure(state="disabled")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _ensure_chatbot(self):
        if self._chatbot is not None:
            return self._chatbot
        try:
            from education_system.systems.university.infrastructure.ai.university_chatbot import (
                UniversityChatbot,
            )
            self._chatbot = UniversityChatbot()
        except Exception as exc:
            self._append(f"[chatbot unavailable: {exc}]\n")
            self._chatbot = False  # sentinel to avoid retrying on every send
        return self._chatbot

    def _send(self) -> None:
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, "end")
        if self._scope:
            text = f"[scope: {self._scope}] {text}"
        self._append(f"You: {text}\n")
        bot = self._ensure_chatbot()
        if not bot:
            return
        try:
            reply = bot.process_message(text, user_id=self._user_id)
        except Exception as exc:
            reply = f"[error: {exc}]"
        self._append(f"Bot: {reply}\n\n")


__all__ = [
    "ChatbotPanel",
]
