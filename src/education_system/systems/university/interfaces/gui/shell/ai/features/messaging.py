from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk
import threading
import queue
import logging
import time
from datetime import datetime
from uuid import uuid4

from education_system.systems.university.infrastructure.ai.university_chatbot import (
    LIBRARIES_AVAILABLE,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)


class MessagingMixin:
    """Mixin for chat messaging and display."""

    def send_message(self):
        """Send user message to chatbot"""
        if not self.conversation_active:
            return

        # Ignore new sends while a previous message is still being processed,
        # so overlapping process_message() calls can't race on the session.
        if getattr(self, "_processing_message", False):
            return

        message = self.message_entry.get("1.0", tk.END).strip()
        if not message:
            return
        if hasattr(self, "security_policy"):
            try:
                self.security_policy.validate_request(message)
            except Exception as error:
                self.add_chat_message("Security", str(error), "error")
                return

        confirmed = message == getattr(self, "_confirmed_message", None)
        if not confirmed and self._requires_confirmation(message):
            self.message_entry.delete("1.0", tk.END)
            self._pending_confirmation = message
            if hasattr(self, "security_policy"):
                self._pending_action_token = self.security_policy.issue_action_token(message)
            self.add_chat_message(
                "System",
                f"Please confirm this action before I continue:\n{message}",
                "confirmation",
            )
            return
        self._confirmed_message = None
        if hasattr(self, "confirm_sensitive_access") and not self.confirm_sensitive_access(message):
            return

        if getattr(self, "_backend_state", "online") != "online":
            self.message_entry.delete("1.0", tk.END)
            if self._is_read_only_request(message):
                if not hasattr(self, "_offline_queue"):
                    self._offline_queue = []
                self._offline_queue.append(message)
                self.add_chat_message(
                    "System",
                    "The assistant is offline. Your read-only request is queued and will retry automatically.",
                    "system",
                )
            else:
                self.add_chat_message(
                    "Error",
                    "This action cannot be queued while the assistant is offline. Please retry when online.",
                    "error",
                )
            return

        attachment_context = (
            self.consume_attachment_context() if hasattr(self, "consume_attachment_context") else ""
        )
        preference_context = (
            self.response_instruction() if hasattr(self, "response_instruction") else ""
        )
        request_message = message + attachment_context + preference_context
        self._last_user_message = message
        self._last_request_message = message

        # Clear input
        self.message_entry.delete("1.0", tk.END)

        # Add user message to chat
        self.add_chat_message(self.current_user.get("username", "User"), message, "user")

        # Update session stats
        if hasattr(self, "update_session_stats"):
            self.update_session_stats("text")

        # Update status and lock input until the response comes back
        self._processing_message = True
        self.set_activity_status("processing")
        if hasattr(self, "send_button"):
            self.send_button.config(state=tk.DISABLED)
        if hasattr(self, "stop_button"):
            self.stop_button.config(state=tk.NORMAL)
        if hasattr(self, "_render_command_palette"):
            self._render_command_palette()
        self._show_typing_indicator()

        # Process the message on a background thread so the Tk main loop stays
        # responsive. The worker only touches a thread-safe queue; the reply is
        # picked up and rendered by _poll_response(), which runs on the Tk main
        # thread (Tk widgets must never be touched from another thread).
        if not hasattr(self, "_response_queue"):
            self._response_queue = queue.Queue()
        self._generation_token = getattr(self, "_generation_token", 0) + 1
        token = self._generation_token
        if not hasattr(self, "_request_started"):
            self._request_started = {}
        self._request_started[token] = time.monotonic()
        threading.Thread(
            target=self._process_message,
            args=(request_message, token),
            daemon=True,
        ).start()
        self.root.after(50, self._poll_response)

    def quick_message(self, message):
        """Send a quick action message"""
        if not self.conversation_active:
            return

        # Set message in input and send
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.send_message()

    @staticmethod
    def _requires_confirmation(message):
        text = " ".join(message.casefold().split())
        risky_prefixes = (
            "book ",
            "reserve ",
            "send ",
            "submit ",
            "delete ",
            "cancel ",
            "change ",
            "update ",
            "pay ",
            "purchase ",
            "create ticket",
        )
        return text.startswith(risky_prefixes)

    @classmethod
    def _is_read_only_request(cls, message):
        return not cls._requires_confirmation(message)

    def _confirm_pending_request(self):
        message = getattr(self, "_pending_confirmation", None)
        if not message:
            return
        if hasattr(self, "security_policy"):
            try:
                self.security_policy.consume_action_token(
                    getattr(self, "_pending_action_token", ""), message
                )
            except Exception as error:
                self.add_chat_message("Security", str(error), "error")
                return
        self._pending_confirmation = None
        self._confirmed_message = message
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.send_message()

    def _cancel_pending_request(self):
        self._pending_confirmation = None
        self.add_chat_message("System", "Action cancelled. No changes were made.", "system")

    def add_chat_message(self, sender, message, msg_type="user", *, sources=None, stream=False):
        """Add a visually distinct message card to the conversation."""
        # Older quick actions historically passed raw ``Error ...: <exception>``
        # strings as normal bot messages. Contain those details at this shared
        # boundary so no exception text can leak into the transcript.
        if msg_type == "bot" and str(message).lower().startswith("error"):
            logger.error("Chatbot GUI action failed: %s", message)
            self._last_diagnostic = {
                "reference": uuid4().hex[:10].upper(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "component": "chatbot-action",
            }
            message = _t(
                "chatbot.request_failed",
                default="I couldn't complete that request. Please retry or contact support if the problem continues.",
            )
            sender = "Error"
            msg_type = "error"
        try:
            near_bottom = self.chat_display.yview()[1] >= 0.98
        except (tk.TclError, IndexError, AttributeError):
            near_bottom = True
        self.chat_display.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M")

        palette = self._message_palette()
        bg, fg, default_sender = palette.get(msg_type, palette["system"])
        card = tk.Frame(self.chat_display, bg=bg, bd=1, relief=tk.SOLID, padx=10, pady=7)
        heading = tk.Frame(card, bg=bg)
        heading.pack(fill=tk.X)
        display_sender = sender if msg_type == "bot" else default_sender
        sender_label = tk.Label(
            heading,
            text=display_sender,
            bg=bg,
            fg=fg,
            font=self.fonts["chat_bold"],
        )
        sender_label.pack(side=tk.LEFT)
        time_label = tk.Label(
            heading,
            text=timestamp,
            bg=bg,
            fg=self.colors["text_secondary"],
            font=self.fonts["small"],
        )
        time_label.pack(side=tk.RIGHT)
        display_message = (
            self.render_rich_text(message) if hasattr(self, "render_rich_text") else message
        )
        body_label = tk.Label(
            card,
            text="" if stream else display_message,
            bg=bg,
            fg=self.colors["text_primary"],
            font=self.fonts["chat"],
            justify=tk.LEFT,
            anchor="w",
            wraplength=max(420, self.chat_display.winfo_width() - 100),
        )
        body_label.pack(fill=tk.X, pady=(4, 0))
        card._message_body = body_label
        card._sender_label = sender_label
        card._time_label = time_label

        actions = tk.Frame(card, bg=bg)
        if msg_type == "user":
            actions.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(
                actions,
                text=_t("chatbot.edit_resend", default="Edit & resend"),
                command=lambda value=message: self.edit_and_resend(value),
            ).pack(side=tk.RIGHT)
        elif msg_type in ("bot", "error") and getattr(self, "_last_request_message", None):
            actions.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(
                actions,
                text=_t("chatbot.retry", default="Retry"),
                command=self.retry_last_message,
            ).pack(side=tk.RIGHT)
        if msg_type == "error":
            if not actions.winfo_manager():
                actions.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(
                actions,
                text=_t("chatbot.copy_diagnostics", default="Copy diagnostics"),
                command=self.copy_diagnostics,
            ).pack(side=tk.RIGHT, padx=4)
            ttk.Button(
                actions,
                text=_t("chatbot.contact_support", default="Contact support"),
                command=self.contact_support,
            ).pack(side=tk.RIGHT)
        if msg_type == "confirmation":
            actions.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(
                actions,
                text="Confirm",
                style="CB.Primary.TButton",
                command=self._confirm_pending_request,
            ).pack(side=tk.RIGHT)
            ttk.Button(
                actions,
                text="Cancel",
                style="CB.Secondary.TButton",
                command=self._cancel_pending_request,
            ).pack(side=tk.RIGHT, padx=4)
        if msg_type == "bot":
            if not actions.winfo_manager():
                actions.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(
                actions,
                text=_t("chatbot.copy_message", default="Copy"),
                command=lambda value=message: self.copy_message(value),
            ).pack(side=tk.LEFT)
            ttk.Button(
                actions,
                text=_t("chatbot.copy_markdown", default="Copy as Markdown"),
                command=lambda value=message: self.copy_message(f"**Assistant**\n\n{value}"),
            ).pack(side=tk.LEFT, padx=4)

            source_items = list(sources or [])
            if source_items:
                ttk.Button(
                    actions,
                    text=_t("chatbot.sources", default=f"Sources ({len(source_items)})"),
                    command=lambda items=source_items: self.show_sources(items),
                ).pack(side=tk.LEFT, padx=4)
            else:
                tk.Label(
                    actions,
                    text="Evidence not supplied — verify important details",
                    bg=bg,
                    fg=fg,
                    font=self.fonts["small"],
                ).pack(side=tk.LEFT, padx=4)

        card_index = self.chat_display.index(tk.END)
        self.chat_display.window_create(tk.END, window=card, padx=8, pady=5)
        self.chat_display.insert(tk.END, "\n")
        if not hasattr(self, "_message_cards"):
            self._message_cards = []
        self._message_cards.append((card, msg_type))
        if len(self._message_cards) > 200:
            self.chat_display.delete("1.0", "2.0")
            self._message_cards.pop(0)
        message_id = None
        if hasattr(self, "_save_conversation_message"):
            message_id = self._save_conversation_message(sender, message, msg_type)
        if msg_type == "bot" and message_id:
            ttk.Button(
                actions,
                text=_t("chatbot.helpful", default="Helpful"),
                command=lambda mid=message_id: self.record_feedback(mid, True),
            ).pack(side=tk.LEFT, padx=(8, 2))
            ttk.Button(
                actions,
                text=_t("chatbot.not_helpful", default="Not helpful"),
                command=lambda mid=message_id: self.record_feedback(mid, False),
            ).pack(side=tk.LEFT, padx=2)

        if msg_type == "bot":
            followups = self._suggest_followups(message)
            if followups:
                followup_frame = tk.Frame(card, bg=bg)
                followup_frame.pack(fill=tk.X, pady=(5, 0))
                tk.Label(
                    followup_frame,
                    text="You could also ask:",
                    bg=bg,
                    fg=fg,
                    font=self.fonts["small"],
                ).pack(side=tk.LEFT)
                for question in followups:
                    ttk.Button(
                        followup_frame,
                        text=question,
                        command=lambda q=question: self.quick_message(q),
                    ).pack(side=tk.LEFT, padx=3)

        self.chat_display.config(state=tk.DISABLED)

        self._announce_message(display_sender, message)

        # Auto-scroll if enabled
        follow_latest = self._should_follow_latest(near_bottom)
        if follow_latest:
            self._scroll_to_message(card_index)
        elif msg_type in ("bot", "error"):
            self._show_unread_marker()
        if stream:
            self._stream_card_text(card, display_message, follow_latest)
        return card

    def _should_follow_latest(self, near_bottom):
        """Follow new messages only when enabled and the reader is at the end."""
        return (not hasattr(self, "auto_scroll") or self.auto_scroll.get()) and near_bottom

    def _announce_message(self, sender, message):
        """Update the text-only live status used by assistive technology."""
        if hasattr(self, "screen_reader_status"):
            self.screen_reader_status.configure(text=f"{sender}: {message}")

    def _stream_card_text(self, card, message, follow_latest=True):
        words = message.split()
        if not words or (hasattr(self, "reduced_motion") and self.reduced_motion.get()):
            card._message_body.configure(text=message)
            return
        state = {"offset": 0}

        def append_chunk():
            if not card.winfo_exists():
                return
            state["offset"] += 4
            card._message_body.configure(text=" ".join(words[: state["offset"]]))
            if follow_latest:
                try:
                    self.chat_display.see(tk.END)
                except tk.TclError:
                    return
            if state["offset"] < len(words):
                self.root.after(25, append_chunk)

        append_chunk()

    def _show_unread_marker(self):
        if hasattr(self, "unread_button"):
            self.unread_button.place(relx=1.0, rely=1.0, x=-24, y=-110, anchor="se")
            self.unread_button.lift()

    def jump_to_latest_message(self):
        self.chat_display.see(tk.END)
        if hasattr(self, "unread_button"):
            self.unread_button.place_forget()

    def copy_message(self, message):
        self.root.clipboard_clear()
        self.root.clipboard_append(message)
        self.set_activity_status("Message copied")

    def copy_conversation(self, markdown=False):
        store = getattr(self, "conversation_store", None)
        conversation_id = getattr(self, "conversation_id", None)
        messages = store.messages(conversation_id) if store and conversation_id else []
        if messages:
            if markdown:
                text = "\n\n".join(f"## {item['sender']}\n\n{item['message']}" for item in messages)
            else:
                text = "\n\n".join(f"{item['sender']}: {item['message']}" for item in messages)
        else:
            text = "\n\n".join(
                card._message_body.cget("text")
                for card, _kind in getattr(self, "_message_cards", [])
                if card.winfo_exists()
            )
        self.copy_message(text)

    def record_feedback(self, message_id, helpful):
        comment = ""
        if not helpful:
            from tkinter import simpledialog

            comment = (
                simpledialog.askstring(
                    "Improve this answer", "What could be improved?", parent=self.root
                )
                or ""
            )
        self.conversation_store.save_feedback(message_id, helpful, comment)
        self.set_activity_status("Feedback saved")

    def show_sources(self, sources):
        import webbrowser
        from urllib.parse import urlparse

        window = tk.Toplevel(self.root)
        window.title("Sources and evidence")
        window.transient(self.root)
        ttk.Label(window, text="Evidence used for this answer:", style="CB.Title.TLabel").pack(
            anchor=tk.W, padx=12, pady=12
        )
        for source in sources:
            if isinstance(source, dict):
                title = source.get("title", "Source")
                url = source.get("url", "")
            else:
                title, url = str(source), ""
            safe_url = url if urlparse(url).scheme in ("http", "https") else ""
            if safe_url:
                ttk.Button(
                    window,
                    text=title,
                    style="CB.Secondary.TButton",
                    command=lambda value=safe_url: webbrowser.open(value),
                ).pack(fill=tk.X, padx=12, pady=4)
                ttk.Label(window, text=safe_url, style="CB.Subtitle.TLabel").pack(
                    anchor=tk.W, padx=16
                )
            else:
                ttk.Label(window, text=title, style="CB.TLabel").pack(anchor=tk.W, padx=12, pady=4)

    @staticmethod
    def _suggest_followups(message):
        text = message.casefold()
        if any(word in text for word in ("exam", "assessment", "grade")):
            return ["Show my deadlines", "Show my grades"]
        if any(word in text for word in ("course", "module", "class")):
            return ["Show my timetable", "Show my assignments"]
        if any(word in text for word in ("fee", "finance", "payment")):
            return ["Show my fee balance", "Show financial aid"]
        return ["What else can you help with?"]

    def _scroll_to_message(self, index):
        """Reveal a new card after Tk has calculated its embedded-window size."""

        def reveal():
            try:
                if self.chat_display.winfo_exists():
                    self.chat_display.update_idletasks()
                    self.chat_display.see(index)
                    if hasattr(self, "unread_button"):
                        self.unread_button.place_forget()
            except (tk.TclError, AttributeError):
                return

        try:
            self.root.after_idle(reveal)
        except (tk.TclError, AttributeError):
            reveal()

    def _message_palette(self):
        """Return accessible card colours for the active theme."""
        theme = getattr(self, "current_theme", "default")
        if theme == "high_contrast":
            return {
                "user": ("#000000", "#00FFFF", "You"),
                "bot": ("#000000", "#FFFF00", "Assistant"),
                "system": ("#000000", "#FFFFFF", "System"),
                "error": ("#000000", "#FF8080", "Error"),
            }
        if theme == "dark":
            return {
                "user": ("#163A52", "#8ED0FF", "You"),
                "bot": ("#452744", "#F0A8EA", "Assistant"),
                "system": ("#3E3828", "#FFE082", "System"),
                "error": ("#4A2020", "#FFABAB", "Error"),
            }
        return {
            "user": ("#E3F2FD", "#0D47A1", "You"),
            "bot": ("#F3E5F5", "#6A1B9A", "Assistant"),
            "system": ("#FFF8E1", "#795548", "System"),
            "error": ("#FFEBEE", "#B71C1C", "Error"),
        }

    def _refresh_message_card_theme(self):
        palette = self._message_palette()
        for card, msg_type in getattr(self, "_message_cards", []):
            bg, fg, _label = palette.get(msg_type, palette["system"])
            card.configure(bg=bg)
            for child in card.winfo_children():
                if child.winfo_class() in ("Frame", "Label"):
                    child.configure(bg=bg)
                for grandchild in child.winfo_children():
                    if grandchild.winfo_class() in ("Frame", "Label"):
                        grandchild.configure(bg=bg)
            card._sender_label.configure(fg=fg)
            card._time_label.configure(fg=self.colors["text_secondary"])
            card._message_body.configure(fg=self.colors["text_primary"])

    def edit_and_resend(self, message):
        """Load an earlier user message into the composer for editing."""
        if getattr(self, "_processing_message", False):
            self.stop_generating()
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.message_entry.focus_set()

    def retry_last_message(self):
        """Run the most recent request again."""
        message = getattr(self, "_last_request_message", "")
        if not message or getattr(self, "_processing_message", False):
            return
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.send_message()

    def copy_diagnostics(self):
        diagnostic = getattr(self, "_last_diagnostic", {})
        text = (
            f"Reference: {diagnostic.get('reference', 'unavailable')}\n"
            f"Time: {diagnostic.get('timestamp', 'unavailable')}\n"
            f"Component: {diagnostic.get('component', 'chatbot')}"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_activity_status(_t("chatbot.diagnostics_copied", default="Diagnostics copied"))

    def contact_support(self):
        if hasattr(self, "create_support_handoff"):
            self.create_support_handoff()
            return
        diagnostic = getattr(self, "_last_diagnostic", {})
        reference = diagnostic.get("reference", "unavailable")
        from tkinter import messagebox

        messagebox.showinfo(
            _t("chatbot.contact_support", default="Contact support"),
            _t(
                "chatbot.support_details",
                default=("Contact IT Services and include diagnostic reference {reference}."),
            ).format(reference=reference),
            parent=self.root,
        )

    def stop_generating(self):
        """Stop waiting for the active generation and discard its late reply."""
        if not getattr(self, "_processing_message", False):
            return
        self._generation_token = getattr(self, "_generation_token", 0) + 1
        self._processing_message = False
        self._hide_typing_indicator()
        self.set_activity_status("stopped")
        self.send_button.config(state=tk.NORMAL)
        if hasattr(self, "stop_button"):
            self.stop_button.config(state=tk.DISABLED)
        self.add_chat_message(
            "System",
            _t("chatbot.generation_stopped", default="Response generation was stopped."),
            "system",
        )

    def _show_typing_indicator(self):
        """Show an animated 'Chatbot is typing…' line while awaiting a reply."""
        try:
            self.chat_display.config(state=tk.NORMAL)
            # Insert just before Tk's implicit trailing newline and remember the
            # start as a concrete index. Nothing else touches the buffer between
            # here and _hide_typing_indicator (all on the Tk main thread), so the
            # index stays valid.
            self._typing_start = self.chat_display.index("end-1c")
            self.chat_display.insert("end-1c", "Chatbot is typing\n", "system")
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)
        except Exception as e:
            logger.debug(f"Typing indicator show failed: {e}")
            self._typing_start = None
            return
        self._typing_dots = 0
        self._animate_typing()

    def _animate_typing(self):
        """Cycle the trailing dots of the typing indicator."""
        if not getattr(self, "_processing_message", False):
            return
        if getattr(self, "_typing_start", None) is None:
            return
        reduced_motion = hasattr(self, "reduced_motion") and self.reduced_motion.get()
        self._typing_dots = 1 if reduced_motion else (self._typing_dots % 3) + 1
        label = "Chatbot is typing" + ("." * self._typing_dots)
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete(self._typing_start, f"{self._typing_start} lineend")
            self.chat_display.insert(self._typing_start, label, "system")
            self.chat_display.config(state=tk.DISABLED)
        except Exception as e:
            logger.debug(f"Typing indicator animate failed: {e}")
            return
        if not reduced_motion:
            self._typing_after_id = self.root.after(400, self._animate_typing)

    def _hide_typing_indicator(self):
        """Cancel the animation and remove the typing line from the transcript."""
        after_id = getattr(self, "_typing_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
            self._typing_after_id = None
        start = getattr(self, "_typing_start", None)
        if start is None:
            return
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete(start, tk.END)
            self.chat_display.config(state=tk.DISABLED)
        except Exception as e:
            logger.debug(f"Typing indicator hide failed: {e}")
        finally:
            self._typing_start = None

    def _handle_bot_response(self, response, sources=None):
        """Handle bot response (runs in main thread)"""
        # Remove the "typing..." placeholder before showing the real reply
        self._hide_typing_indicator()

        # Add bot response to chat
        self.add_chat_message("Chatbot", response, "bot", sources=sources, stream=True)

        # Response received - unlock input and reset status
        self._processing_message = False
        self.set_activity_status("ready")
        self.set_backend_status("online")
        started = getattr(self, "_request_started", {}).pop(
            getattr(self, "_generation_token", None), None
        )
        if started and hasattr(self, "conversation_store"):
            self.conversation_store.metric(
                self.current_user.get("username", "unknown"),
                "response",
                (time.monotonic() - started) * 1000,
            )
        if hasattr(self, "send_button"):
            self.send_button.config(state=tk.NORMAL)
        if hasattr(self, "stop_button"):
            self.stop_button.config(state=tk.DISABLED)

        # Text-to-speech if enabled. `response` is the text actually shown in
        # the chat (a bot reply or an error message), so this is always bound.
        if (
            hasattr(self, "voice_tts_enabled")
            and self.voice_tts_enabled.get()
            and LIBRARIES_AVAILABLE.get("pyttsx3", False)
        ):
            threading.Thread(
                target=self.chatbot.text_to_speech, args=(response,), daemon=True
            ).start()

    def _process_message(self, message, token):
        """Process message with chatbot (runs in a background thread).

        Must not touch any Tk widget — it only computes the reply and hands it
        back to the main thread through the response queue.
        """
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(message, user_id, session_id=self.session_id)

            # Log activity
            log_activity(
                "chat",
                "chatbot_message",
                None,
                details={"user": user_id, "message_length": len(message)},
            )

            sources = None
            if isinstance(response, dict):
                sources = response.get("sources") or response.get("evidence") or []
                response = (
                    response.get("answer")
                    or response.get("response")
                    or response.get("message")
                    or ""
                )
            if hasattr(self, "security_policy"):
                response = self.security_policy.sanitize_output(response)
            result_type = "bot"
        except Exception as error:
            reference = uuid4().hex[:10].upper()
            logger.exception("Chatbot request failed [reference=%s]", reference)
            response = _t(
                "chatbot.request_failed",
                default="I couldn't complete that request. Please retry or contact support if the problem continues.",
            )
            result_type = "error"
            diagnostic = {
                "reference": reference,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "component": type(error).__name__,
            }
            sources = None
        else:
            diagnostic = None

        self._response_queue.put((token, response, result_type, diagnostic, sources))

    def _poll_response(self, event=None):
        """Poll the worker's queue on the Tk main thread and render the reply."""
        try:
            token, response, result_type, diagnostic, sources = self._response_queue.get_nowait()
        except queue.Empty:
            # Still working; check again shortly.
            if getattr(self, "_processing_message", False):
                self.root.after(50, self._poll_response)
            return

        if token != getattr(self, "_generation_token", None):
            if getattr(self, "_processing_message", False):
                self.root.after(50, self._poll_response)
            return
        if result_type == "error":
            self._last_diagnostic = diagnostic or {}
            self._hide_typing_indicator()
            self.add_chat_message("Assistant", response, "error")
            self._processing_message = False
            self.set_activity_status("failed")
            self.schedule_reconnect_check()
            if hasattr(self, "conversation_store"):
                self.conversation_store.metric(
                    self.current_user.get("username", "unknown"),
                    "failure",
                    0,
                    (diagnostic or {}).get("reference", ""),
                )
            self.send_button.config(state=tk.NORMAL)
            if hasattr(self, "stop_button"):
                self.stop_button.config(state=tk.DISABLED)
            return
        self._handle_bot_response(response, sources=sources)

    def retry_offline_queue(self):
        if (
            getattr(self, "_processing_message", False)
            or getattr(self, "_backend_state", "offline") != "online"
        ):
            return
        queue_items = getattr(self, "_offline_queue", [])
        if not queue_items:
            return
        message = queue_items.pop(0)
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.send_message()
