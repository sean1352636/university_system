import tkinter as tk
import threading
import queue
import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)


class MessagingMixin:
    """Mixin for chat messaging and display."""

    def send_message(self):
        """Send user message to chatbot"""
        if not self.conversation_active:
            return

        # Ignore new sends while a previous message is still being processed,
        # so overlapping process_message() calls can't race on the session.
        if getattr(self, '_processing_message', False):
            return

        message = self.message_entry.get("1.0", tk.END).strip()
        if not message:
            return

        # Clear input
        self.message_entry.delete("1.0", tk.END)

        # Add user message to chat
        self.add_chat_message(self.current_user.get("username", "User"), message, "user")

        # Update session stats
        if hasattr(self, 'update_session_stats'):
            self.update_session_stats("text")

        # Update status and lock input until the response comes back
        self._processing_message = True
        self.status_label.config(text="Processing...")
        if hasattr(self, 'send_button'):
            self.send_button.config(state=tk.DISABLED)
        self._show_typing_indicator()

        # Process the message on a background thread so the Tk main loop stays
        # responsive. The worker only touches a thread-safe queue; the reply is
        # picked up and rendered by _poll_response(), which runs on the Tk main
        # thread (Tk widgets must never be touched from another thread).
        self._response_queue = queue.Queue()
        threading.Thread(
            target=self._process_message,
            args=(message,),
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

    def add_chat_message(self, sender, message, msg_type="user"):
        """Add message to chat display"""
        self.chat_display.config(state=tk.NORMAL)

        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M")

        # Add message with styling
        if msg_type == "user":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{sender}: ", "user")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        elif msg_type == "bot":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{sender}: ", "bot")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        elif msg_type == "system":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{message}\n\n", "system")

        self.chat_display.config(state=tk.DISABLED)

        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll') and self.auto_scroll.get():
            self.chat_display.see(tk.END)

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
        if not getattr(self, '_processing_message', False):
            return
        if getattr(self, '_typing_start', None) is None:
            return
        self._typing_dots = (self._typing_dots % 3) + 1
        label = "Chatbot is typing" + ("." * self._typing_dots)
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete(self._typing_start, f"{self._typing_start} lineend")
            self.chat_display.insert(self._typing_start, label, "system")
            self.chat_display.config(state=tk.DISABLED)
        except Exception as e:
            logger.debug(f"Typing indicator animate failed: {e}")
            return
        self._typing_after_id = self.root.after(400, self._animate_typing)

    def _hide_typing_indicator(self):
        """Cancel the animation and remove the typing line from the transcript."""
        after_id = getattr(self, '_typing_after_id', None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
            self._typing_after_id = None
        start = getattr(self, '_typing_start', None)
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

    def _handle_bot_response(self, response):
        """Handle bot response (runs in main thread)"""
        # Remove the "typing..." placeholder before showing the real reply
        self._hide_typing_indicator()

        # Add bot response to chat
        self.add_chat_message("Chatbot", response, "bot")

        # Response received - unlock input and reset status
        self._processing_message = False
        self.status_label.config(text="Ready")
        if hasattr(self, 'send_button'):
            self.send_button.config(state=tk.NORMAL)

        # Text-to-speech if enabled. `response` is the text actually shown in
        # the chat (a bot reply or an error message), so this is always bound.
        if (hasattr(self, 'voice_tts_enabled') and
            self.voice_tts_enabled.get() and
            LIBRARIES_AVAILABLE.get('pyttsx3', False)):
            threading.Thread(target=self.chatbot.text_to_speech,
                           args=(response,), daemon=True).start()

    def _process_message(self, message):
        """Process message with chatbot (runs in a background thread).

        Must not touch any Tk widget — it only computes the reply and hands it
        back to the main thread through the response queue.
        """
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(
                message,
                user_id,
                session_id=self.session_id
            )

            # Log activity
            log_activity('chat', 'chatbot_message', None,
                        details={'user': user_id, 'message_length': len(message)})

        except Exception as e:
            response = f"I apologize, but I encountered an error: {e}"

        self._response_queue.put(response)

    def _poll_response(self, event=None):
        """Poll the worker's queue on the Tk main thread and render the reply."""
        try:
            response = self._response_queue.get_nowait()
        except queue.Empty:
            # Still working; check again shortly.
            self.root.after(50, self._poll_response)
            return

        self._handle_bot_response(response)
