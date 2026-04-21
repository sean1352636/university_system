import tkinter as tk
import threading
import logging
from datetime import datetime

from education_system.university_system.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class MessagingMixin:
    """Mixin for chat messaging and display."""

    def send_message(self):
        """Send user message to chatbot"""
        if not self.conversation_active:
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

        # Update status
        self.status_label.config(text="Processing...")

        # Process message directly to avoid threading issues
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(
                message,
                user_id,
                session_id=self.session_id
            )

            # Add bot response to chat
            self.add_chat_message("Chatbot", response, "bot")

            # Log activity
            log_activity('chat', 'chatbot_message', None,
                        details={'user': user_id, 'message_length': len(message)})

        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {e}"
            self.add_chat_message("Chatbot", error_response, "bot")

        # Update status
        self.status_label.config(text="Ready")

        # Text-to-speech if enabled
        if (hasattr(self, 'voice_tts_enabled') and
            self.voice_tts_enabled.get() and
            LIBRARIES_AVAILABLE.get('pyttsx3', False)):
            threading.Thread(target=self.chatbot.text_to_speech,
                           args=(response,), daemon=True).start()

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

    def _handle_bot_response(self, response):
        """Handle bot response (runs in main thread)"""
        # Add bot response to chat
        self.add_chat_message("Chatbot", response, "bot")

        # Update status
        self.status_label.config(text="Ready")

        # Text-to-speech if enabled
        if (hasattr(self, 'voice_tts_enabled') and
            self.voice_tts_enabled.get() and
            LIBRARIES_AVAILABLE.get('pyttsx3', False)):
            threading.Thread(target=self.chatbot.text_to_speech,
                           args=(response,), daemon=True).start()

    def _process_message(self, message):
        """Process message with chatbot (runs in separate thread)"""
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(
                message,
                user_id,
                session_id=self.session_id
            )

            # Update UI in main thread
            self.root.after(0, self._handle_bot_response, response)

        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {e}"
            self.root.after(0, self._handle_bot_response, error_response)
