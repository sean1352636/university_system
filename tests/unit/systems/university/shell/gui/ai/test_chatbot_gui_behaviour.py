"""Headless behavioural checks for chatbot GUI state transitions."""

from types import SimpleNamespace

from education_system.systems.university.shell.gui.ai.events import EventsMixin
from education_system.systems.university.shell.gui.ai.status_bar import StatusBarMixin
from education_system.systems.university.shell.gui.ai.features.messaging import (
    MessagingMixin,
)


class Label:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)

    config = configure


class Text:
    def __init__(self, value=""):
        self.value = value

    def get(self, *_args):
        return self.value

    def delete(self, *_args):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


def test_status_transitions_are_not_static(monkeypatch):
    monkeypatch.setattr(
        "education_system.systems.university.shell.gui.ai.status_bar._t",
        lambda _key, default=None, **_kwargs: default,
    )
    gui = SimpleNamespace(status_label=Label())
    StatusBarMixin.set_activity_status(gui, "processing")
    assert gui.status_label.options["text"] == "Processing"
    StatusBarMixin.set_activity_status(gui, "listening")
    assert gui.status_label.options["text"] == "Listening"


def test_backend_status_reports_voice_unavailable(monkeypatch):
    monkeypatch.setattr(
        "education_system.systems.university.shell.gui.ai.status_bar._t",
        lambda _key, default=None, **_kwargs: default,
    )
    gui = SimpleNamespace(
        chatbot=SimpleNamespace(voice_interface=SimpleNamespace(enabled=False)),
        connection_label=Label(),
    )
    StatusBarMixin.set_backend_status(gui, "offline")
    assert gui.connection_label.options["text"] == ("Assistant: Offline | Voice: Unavailable")


def test_closing_invalidates_processing_and_cancels_callbacks():
    cancelled = []
    root = SimpleNamespace(
        after_cancel=cancelled.append,
        destroy=lambda: None,
    )
    gui = SimpleNamespace(
        root=root,
        chatbot=SimpleNamespace(),
        _processing_message=True,
        _generation_token=4,
        _typing_after_id="typing",
        _responsive_after_id="layout",
        _status_after_id="status",
        _restore_dialog_parenting=lambda: None,
    )
    EventsMixin.handle_exit(gui)
    assert gui._processing_message is False
    assert gui._generation_token == 5
    assert set(cancelled) == {"typing", "layout", "status"}


def test_closing_during_voice_capture_cleans_up_microphone():
    cleaned = []
    voice = SimpleNamespace(enabled=True, cleanup=lambda: cleaned.append(True))
    gui = SimpleNamespace(
        root=SimpleNamespace(destroy=lambda: None),
        chatbot=SimpleNamespace(voice_interface=voice),
        _processing_message=False,
    )
    EventsMixin.handle_exit(gui)
    assert cleaned == [True]


def test_reconnect_state_recovers_to_online():
    states = []
    gui = SimpleNamespace(
        chatbot=SimpleNamespace(
            process_message=lambda _message: None,
            get_system_status=lambda: {"status": "ok"},
        ),
        root=SimpleNamespace(after=lambda *_args: None),
        set_backend_status=states.append,
        retry_offline_queue=lambda: states.append("retried"),
    )
    StatusBarMixin.schedule_reconnect_check(gui)
    StatusBarMixin.refresh_service_status(gui)
    assert states == ["reconnecting", "online", "retried"]


def test_enter_sends_only_during_active_conversation():
    calls = []
    gui = SimpleNamespace(conversation_active=True, send_message=lambda: calls.append(1))
    assert EventsMixin._on_return_key(gui, None) == "break"
    assert calls == [1]


def test_translated_status_text_is_used(monkeypatch):
    monkeypatch.setattr(
        "education_system.systems.university.shell.gui.ai.status_bar._t",
        lambda key, default=None, **_kwargs: (
            "Traitement" if key.endswith("processing") else default
        ),
    )
    gui = SimpleNamespace(status_label=Label())
    StatusBarMixin.set_activity_status(gui, "processing")
    assert gui.status_label.options["text"] == "Traitement"


def test_send_enters_disabled_loading_state(monkeypatch):
    class Thread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(
        "education_system.systems.university.shell.gui.ai.features.messaging.threading.Thread",
        Thread,
    )
    scheduled = []
    gui = SimpleNamespace(
        conversation_active=True,
        _processing_message=False,
        message_entry=Text("Where is my class?"),
        current_user={"username": "student"},
        session_id="session",
        send_button=Label(),
        stop_button=Label(),
        root=SimpleNamespace(after=lambda *args: scheduled.append(args)),
        add_chat_message=lambda *_args: None,
        update_session_stats=lambda *_args: None,
        set_activity_status=lambda state: setattr(gui, "activity", state),
        _show_typing_indicator=lambda: None,
        _render_command_palette=lambda: None,
        _process_message=lambda *_args: None,
        _poll_response=lambda *_args: None,
        _requires_confirmation=MessagingMixin._requires_confirmation,
        _is_read_only_request=MessagingMixin._is_read_only_request,
    )
    MessagingMixin.send_message(gui)
    assert gui._processing_message is True
    assert gui.activity == "processing"
    assert gui.send_button.options["state"] == "disabled"
    assert gui.stop_button.options["state"] == "normal"
    assert scheduled


def test_failed_response_uses_safe_card_and_reconnect_state():
    diagnostic = {"reference": "ABC123", "component": "RuntimeError"}
    shown = []
    gui = SimpleNamespace(
        _response_queue=SimpleNamespace(
            get_nowait=lambda: (3, "Friendly failure", "error", diagnostic, None)
        ),
        _generation_token=3,
        _processing_message=True,
        send_button=Label(),
        stop_button=Label(),
        status=[],
        _hide_typing_indicator=lambda: None,
        add_chat_message=lambda *args: shown.append(args),
        set_activity_status=lambda state: gui.status.append(state),
        schedule_reconnect_check=lambda: gui.status.append("reconnecting"),
    )
    MessagingMixin._poll_response(gui)
    assert shown == [("Assistant", "Friendly failure", "error")]
    assert gui._last_diagnostic == diagnostic
    assert gui.status == ["failed", "reconnecting"]
    assert gui.send_button.options["state"] == "normal"


def test_new_message_scroll_waits_for_card_layout():
    calls = []
    display = SimpleNamespace(
        winfo_exists=lambda: True,
        update_idletasks=lambda: calls.append("layout"),
        see=lambda index: calls.append(("see", index)),
    )
    root = SimpleNamespace(after_idle=lambda callback: (calls.append("scheduled"), callback()))
    gui = SimpleNamespace(chat_display=display, root=root)

    MessagingMixin._scroll_to_message(gui, "4.0")

    assert calls == ["scheduled", "layout", ("see", "4.0")]


def test_offline_read_only_request_is_queued():
    shown = []
    gui = SimpleNamespace(
        conversation_active=True,
        _processing_message=False,
        _backend_state="offline",
        message_entry=Text("Show my timetable"),
        _requires_confirmation=MessagingMixin._requires_confirmation,
        _is_read_only_request=MessagingMixin._is_read_only_request,
        add_chat_message=lambda *args: shown.append(args),
    )
    MessagingMixin.send_message(gui)
    assert gui._offline_queue == ["Show my timetable"]
    assert "queued" in shown[0][1]


def test_offline_mutation_is_not_queued():
    shown = []
    gui = SimpleNamespace(
        conversation_active=True,
        _processing_message=False,
        _backend_state="offline",
        message_entry=Text("Delete my booking"),
        _requires_confirmation=lambda _message: False,
        _is_read_only_request=MessagingMixin._is_read_only_request,
        add_chat_message=lambda *args: shown.append(args),
    )
    MessagingMixin.send_message(gui)
    assert not hasattr(gui, "_offline_queue")
    assert shown[0][2] == "error"
