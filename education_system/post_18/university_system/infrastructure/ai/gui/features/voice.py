import tkinter as tk
from tkinter import messagebox
import threading

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class VoiceMixin:
    """Mixin for voice recording and text-to-speech."""

    def toggle_voice_mode(self):
        """Toggle voice recording mode"""
        if not self.chatbot.voice_interface.enabled:
            messagebox.showwarning(
                _t("chatbot.voice_unavailable", default="Voice Unavailable"),
                _t("chatbot.voice_unavailable_msg", default="Voice interface is not available. Please check your microphone setup.")
            )
            return

        if not self.conversation_active:
            return

        # Change button state
        self.voice_button.config(state='disabled', text="\U0001f3a4 Recording...")
        self.status_label.config(text="Listening...")

        # Record voice in thread
        duration = float(getattr(self, 'voice_duration_var', tk.StringVar(value="5")).get())
        threading.Thread(target=self._record_voice, args=(duration,), daemon=True).start()

    def _record_voice(self, duration):
        """Record voice input (runs in separate thread)"""
        try:
            # Record audio
            text = self.chatbot.process_voice_input(duration)

            # Update UI in main thread
            if text:
                self.root.after(0, self._handle_voice_result, text)
            else:
                self.root.after(0, self._handle_voice_error, "No speech detected")

        except Exception as e:
            self.root.after(0, self._handle_voice_error, str(e))

    def _handle_voice_result(self, text):
        """Handle successful voice recognition"""
        # Reset voice button
        self.voice_button.config(state='normal', text="\U0001f3a4 Voice")
        self.status_label.config(text="Voice recognized")

        # Add recognized text to input and send
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", text)
        self.send_message()

    def _handle_voice_error(self, error):
        """Handle voice recognition error"""
        # Reset voice button
        self.voice_button.config(state='normal', text="\U0001f3a4 Voice")
        self.status_label.config(text="Ready")

        # Show error
        messagebox.showerror(
            _t("chatbot.voice_error", default="Voice Error"),
            _t("chatbot.voice_recognition_failed", default="Voice recognition failed: {error}").format(error=error)
        )

    def test_voice(self):
        """Test voice interface"""
        if not self.chatbot.voice_interface.enabled:
            self.voice_status_label.config(text="Voice interface not available", foreground='red')
            return

        self.voice_status_label.config(text="Testing microphone...", foreground='blue')

        # Run test in thread
        threading.Thread(target=self._run_voice_test, daemon=True).start()

    def _run_voice_test(self):
        """Run voice test (in separate thread)"""
        try:
            result = self.chatbot.test_voice_interface()
            self.root.after(0, self._handle_voice_test_result, result)
        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            self.root.after(0, self._handle_voice_test_result, error_result)

    def _handle_voice_test_result(self, result):
        """Handle voice test result"""
        if result["status"] == "success":
            devices = len(result.get("devices", []))
            test_text = result.get("test_recording", "No test recording")
            message = f"\u2713 Voice test successful!\nFound {devices} audio devices\nTest: '{test_text}'"
            self.voice_status_label.config(text=message, foreground='green')
        else:
            message = f"\u2717 Voice test failed: {result.get('message', 'Unknown error')}"
            self.voice_status_label.config(text=message, foreground='red')
