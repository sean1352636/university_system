
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import messagebox
import threading

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
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
            if hasattr(self, 'set_backend_status'):
                self.set_backend_status(getattr(self, '_backend_state', 'online'))
            messagebox.showwarning(
                _t("chatbot.voice_unavailable", default="Voice Unavailable"),
                _t("chatbot.voice_unavailable_msg", default="Voice interface is not available. Please check your microphone setup.")
            )
            return

        if not self.conversation_active:
            return

        # Change button state
        self.voice_button.config(state='disabled', text=_t('gui.shell.ai.features.voice.text.recording', default="Recording"))
        self.set_activity_status('listening')

        # Record voice in thread
        duration = float(getattr(self, 'voice_duration_var', tk.StringVar(value="5")).get())
        start_thread(self.root, self._record_voice, duration)

    def _record_voice(self, duration):
        """Record voice input (runs in separate thread)"""
        try:
            # Record audio
            text = self.chatbot.process_voice_input(duration)

            # Update UI in main thread
            if text:
                ui(self.root, self._handle_voice_result, text)
            else:
                ui(self.root, self._handle_voice_error, "No speech detected")

        except Exception:
            ui(self.root, self._handle_voice_error, None)

    def _handle_voice_result(self, text):
        """Handle successful voice recognition"""
        # Reset voice button
        self.voice_button.config(state='normal', text=_t('gui.shell.ai.features.voice.text.voice', default="Voice input"))
        self.status_label.config(text=_t('gui.shell.ai.features.voice.text.voice_recognized', default="Voice recognized"))

        # Add recognized text to input and send
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", text)
        self.send_message()

    def _handle_voice_error(self, error):
        """Handle voice recognition error"""
        # Reset voice button
        self.voice_button.config(state='normal', text=_t('gui.shell.ai.features.voice.text.voice', default="Voice input"))
        self.set_activity_status('ready')

        # Show error
        messagebox.showerror(
            _t("chatbot.voice_error", default="Voice Error"),
            _t("chatbot.voice_recognition_failed", default="Voice recognition failed. Please try again.")
        )

    def test_voice(self):
        """Test voice interface"""
        if not self.chatbot.voice_interface.enabled:
            self.voice_status_label.config(text=_t('gui.shell.ai.features.voice.text.voice_interface_not_available', default="Voice interface not available"), foreground='red')
            return

        self.voice_status_label.config(text=_t('gui.shell.ai.features.voice.text.testing_microphone', default="Testing microphone..."), foreground='blue')

        # Run test in thread
        start_thread(self.root, self._run_voice_test)

    def _run_voice_test(self):
        """Run voice test (in separate thread)"""
        try:
            result = self.chatbot.test_voice_interface()
            ui(self.root, self._handle_voice_test_result, result)
        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            ui(self.root, self._handle_voice_test_result, error_result)

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
