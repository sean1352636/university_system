"""Real-event-loop regression tests for chatbot attachment windows."""

import tkinter as tk
from tkinter import ttk

import pytest

from education_system.systems.university.shell.gui.ai.features.attachments import (
    AttachmentsMixin,
)
from education_system.systems.university.shell.gui.ai.events import EventsMixin
from education_system.systems.university.shell.gui.ai.features.messaging import (
    MessagingMixin,
)

pytestmark = pytest.mark.gui


class AttachmentHarness(AttachmentsMixin):
    def __init__(self, root):
        self.root = root
        self.pending_attachments = []

    def _update_attachment_button(self):
        pass


@pytest.fixture
def root():
    window = tk.Tk()
    window.withdraw()
    yield window
    try:
        if window.winfo_exists():
            window.destroy()
    except tk.TclError:
        pass


def attachment_window(root):
    return next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))


def add_files_button(window):
    return next(child for child in window.winfo_children() if isinstance(child, ttk.Button))


def test_file_picker_return_after_manager_close_is_safe(root):
    harness = AttachmentHarness(root)
    harness.show_attachment_manager()
    manager = attachment_window(root)

    harness.choose_attachment = manager.destroy

    # Regression: refresh used to access the destroyed body after this callback.
    add_files_button(manager).invoke()
    root.update_idletasks()

    assert not manager.winfo_exists()


def test_attachment_manager_can_be_reopened_after_close(root):
    harness = AttachmentHarness(root)

    for _ in range(3):
        harness.show_attachment_manager()
        manager = attachment_window(root)
        manager.destroy()
        root.update_idletasks()

    assert not root.winfo_children()


def test_multiple_attachment_managers_close_independently(root):
    harness = AttachmentHarness(root)
    harness.show_attachment_manager()
    harness.show_attachment_manager()
    managers = list(root.winfo_children())

    managers[0].destroy()
    root.update_idletasks()

    assert not managers[0].winfo_exists()
    assert managers[1].winfo_exists()


class EventsHarness(EventsMixin):
    def __init__(self, root):
        self.root = root
        self.message_entry = tk.Text(root)
        self.message_entry.pack()
        self.conversation_active = True
        self.current_user = {"role": "student"}
        self.chatbot = type(
            "Chatbot",
            (),
            {"voice_interface": type("Voice", (), {"enabled": False})()},
        )()
        self.sent = 0

    def send_message(self):
        self.sent += 1


def test_enter_key_sends_once_and_shift_enter_does_not(root):
    harness = EventsHarness(root)
    harness.setup_event_handlers()
    harness.message_entry.focus_force()

    harness.message_entry.event_generate("<Return>")
    root.update()
    harness.message_entry.event_generate("<Shift-Return>")
    root.update()

    assert harness.sent == 1


def test_close_during_background_work_invalidates_and_cancels_callbacks(root):
    harness = EventsHarness(root)
    callback_ran = []
    harness._processing_message = True
    harness._generation_token = 4
    harness._typing_after_id = root.after(1, lambda: callback_ran.append(True))

    harness.handle_exit()

    assert harness._generation_token == 5
    assert harness._processing_message is False
    assert callback_ran == []


class MessagingHarness(MessagingMixin):
    def __init__(self, root):
        self.root = root
        self.message_entry = tk.Text(root)
        self.message_entry.insert("1.0", "Explain my balance")
        self.conversation_active = True
        self.current_user = {"username": "student"}
        self.messages = []
        self.processed = []

    def add_chat_message(self, sender, message, kind, **_kwargs):
        self.messages.append((sender, message, kind))

    def confirm_sensitive_access(self, _message):
        return True

    def set_activity_status(self, _status):
        pass

    def _show_typing_indicator(self):
        pass

    def _poll_response(self):
        pass

    def _process_message(self, message, token):
        self.processed.append((message, token))


def test_rapid_double_send_starts_only_one_request(root, monkeypatch):
    harness = MessagingHarness(root)

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(
        "education_system.systems.university.shell.gui.ai.features.messaging.threading.Thread",
        ImmediateThread,
    )

    harness.send_message()
    harness.message_entry.insert("1.0", "Send this twice")
    harness.send_message()

    assert len(harness.processed) == 1
    assert harness._processing_message is True
