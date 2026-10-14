"""Behavioural tests for the university chatbot interaction helpers."""

from types import SimpleNamespace

from education_system.systems.university.shell.gui.ai.features.messaging import (
    MessagingMixin,
)
from education_system.systems.university.shell.gui.ai.features.conversations import (
    ConversationsMixin,
)
from education_system.systems.university.shell.gui.ai.screens.chat import (
    ChatScreenMixin,
)
from education_system.systems.university.shell.gui.ai.conversation_store import (
    ConversationStore,
)
from education_system.systems.university.shell.gui.ai.styles import StylesMixin


def test_flatten_commands_removes_duplicate_labels_case_insensitively():
    first = lambda: None
    second = lambda: None
    commands = ChatScreenMixin._flatten_commands(
        [
            ("Study", [("Timetable", first)]),
            ("More", [("timetable", second), ("Deadlines", second)]),
        ]
    )

    assert [(category, label) for category, label, _ in commands] == [
        ("Study", "Timetable"),
        ("More", "Deadlines"),
    ]


def test_student_suggestions_prioritise_common_study_commands():
    gui = SimpleNamespace(
        _command_specs=[
            ("Campus", "Events", lambda: None),
            ("Study", "Assignments", lambda: None),
            ("Study", "Timetable", lambda: None),
            ("Study", "Deadlines", lambda: None),
        ],
        _current_role=lambda: "student",
        _last_user_message="",
    )

    suggestions = ChatScreenMixin._suggested_commands(gui)

    assert [label for _, label, _ in suggestions] == [
        "Timetable",
        "Deadlines",
        "Assignments",
    ]


def test_late_response_from_stopped_generation_is_discarded():
    scheduled = []
    gui = SimpleNamespace(
        _response_queue=SimpleNamespace(get_nowait=lambda: (1, "late", "bot", None, None)),
        _generation_token=2,
        _processing_message=False,
        root=SimpleNamespace(after=lambda *args: scheduled.append(args)),
        handled=[],
    )
    gui._handle_bot_response = gui.handled.append

    MessagingMixin._poll_response(gui)

    assert gui.handled == []
    assert scheduled == []


def test_responsive_command_breakpoints():
    assert ChatScreenMixin._command_column_count(600) == 1
    assert ChatScreenMixin._command_column_count(900) == 2
    assert ChatScreenMixin._command_column_count(1200) == 4


def test_conversation_store_create_search_rename_delete(tmp_path):
    store = ConversationStore(tmp_path / "conversations.db")
    conversation_id = store.create("student-1")
    store.add_message(conversation_id, "Student", "When is my exam?", "user")
    store.add_message(conversation_id, "Assistant", "Monday at 10.", "bot")
    store.title_from_first_message(conversation_id, "When is my exam?")

    assert store.list("student-1", "exam")[0]["message_count"] == 2
    assert store.messages(conversation_id)[1]["message"] == "Monday at 10."

    store.rename(conversation_id, "Exam planning")
    assert store.list("student-1")[0]["title"] == "Exam planning"
    store.delete(conversation_id)
    assert store.list("student-1") == []


def test_conversation_store_is_user_scoped(tmp_path):
    store = ConversationStore(tmp_path / "conversations.db")
    store.create("alice", "Alice only")
    store.create("bob", "Bob only")

    assert [item["title"] for item in store.list("alice")] == ["Alice only"]


def test_all_accessibility_themes_have_required_colours():
    assert {"default", "dark", "blue", "high_contrast"} <= StylesMixin.THEMES.keys()
    for theme in StylesMixin.THEMES.values():
        assert {"bg", "surface", "fg", "select_bg", "select_fg"} <= theme.keys()


def test_alumni_actions_do_not_include_student_records():
    class GUI(ChatScreenMixin):
        def __getattr__(self, _name):
            return lambda: None

    gui = GUI()
    labels = {
        label
        for _category, commands in gui._alumni_quick_action_tabs()
        for label, _callback in commands
    }
    assert "My Grades" not in labels
    assert "Timetable" not in labels
    assert "Transcripts" in labels


def test_conversation_store_preferences_feedback_folders_and_drafts(tmp_path):
    store = ConversationStore(tmp_path / "conversations.db")
    conversation_id = store.create("student")
    message_id = store.add_message(conversation_id, "Assistant", "Answer", "bot")
    store.save_feedback(message_id, False, "Needs a source")
    store.set_organisation(conversation_id, pinned=True, folder="Assessments")
    store.save_draft(conversation_id, "unfinished question")
    store.save_preferences(
        "student", history_enabled=False, retention_days=30, draft="legacy draft"
    )

    item = store.list("student")[0]
    assert item["pinned"] == 1
    assert item["folder"] == "Assessments"
    assert store.draft(conversation_id) == "unfinished question"
    assert store.preferences("student")["history_enabled"] == 0


def test_mutating_requests_require_confirmation_but_questions_do_not():
    assert MessagingMixin._requires_confirmation("Book room A for tomorrow")
    assert MessagingMixin._requires_confirmation("Delete my booking")
    assert not MessagingMixin._requires_confirmation("How do I book a room?")
    assert MessagingMixin._is_read_only_request("Show my timetable")


def test_follow_up_suggestions_are_contextual():
    assert "Show my grades" in MessagingMixin._suggest_followups("Your exam grade is available.")
    assert "Show financial aid" in MessagingMixin._suggest_followups("Your fee payment is pending.")


def test_conversation_store_backup_has_version(tmp_path):
    store = ConversationStore(tmp_path / "live.db")
    backup = store.backup(tmp_path / "backup.db")
    assert backup.exists()
    assert ConversationStore(backup).schema_version() == 2


def test_user_scroll_position_is_respected_when_new_reply_arrives():
    gui = SimpleNamespace(auto_scroll=SimpleNamespace(get=lambda: True))
    assert MessagingMixin._should_follow_latest(gui, near_bottom=False) is False
    assert MessagingMixin._should_follow_latest(gui, near_bottom=True) is True


def test_stop_immediately_invalidates_pending_response():
    states = []
    gui = SimpleNamespace(
        _processing_message=True,
        _generation_token=7,
        _hide_typing_indicator=lambda: states.append("hidden"),
        set_activity_status=states.append,
        send_button=SimpleNamespace(config=lambda **kw: states.append(kw["state"])),
        stop_button=SimpleNamespace(config=lambda **kw: states.append(kw["state"])),
        add_chat_message=lambda *_args: states.append("message"),
    )
    MessagingMixin.stop_generating(gui)
    assert gui._generation_token == 8
    assert gui._processing_message is False
    assert states == ["hidden", "stopped", "normal", "disabled", "message"]


def test_retry_after_partial_stream_reuses_original_request():
    sent = []
    entry = SimpleNamespace(
        value="partial",
        delete=lambda *_args: setattr(entry, "value", ""),
        insert=lambda _index, value: setattr(entry, "value", value),
    )
    gui = SimpleNamespace(
        _last_request_message="Original question",
        _processing_message=False,
        message_entry=entry,
        send_message=lambda: sent.append(entry.value),
    )
    MessagingMixin.retry_last_message(gui)
    assert sent == ["Original question"]


def test_edit_and_resend_preserves_pending_attachments():
    attachment = {"filename": "evidence.pdf"}
    entry = SimpleNamespace(
        value="",
        delete=lambda *_args: setattr(entry, "value", ""),
        insert=lambda _index, value: setattr(entry, "value", value),
        focus_set=lambda: None,
    )
    gui = SimpleNamespace(
        _processing_message=False,
        message_entry=entry,
        pending_attachments=[attachment],
    )
    MessagingMixin.edit_and_resend(gui, "Edited question")
    assert entry.value == "Edited question"
    assert gui.pending_attachments == [attachment]


def relative_luminance(hex_colour):
    channels = [int(hex_colour[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    channels = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first, second):
    bright, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def test_theme_text_contrast_meets_wcag_aa():
    for theme in StylesMixin.THEMES.values():
        assert contrast_ratio(theme["bg"], theme["fg"]) >= 4.5
        assert contrast_ratio(theme["select_bg"], theme["select_fg"]) >= 4.5


def test_switching_conversation_stops_active_generation():
    calls = []
    gui = SimpleNamespace(
        _processing_message=True,
        stop_generating=lambda: calls.append("stopped"),
        _start_new_conversation=lambda clear: calls.append(("new", clear)),
    )
    ConversationsMixin.new_conversation(gui)
    assert calls == ["stopped", ("new", True)]


def test_streamed_reply_updates_screen_reader_status():
    status = SimpleNamespace(configure=lambda **options: setattr(status, "text", options["text"]))
    gui = SimpleNamespace(screen_reader_status=status)
    MessagingMixin._announce_message(gui, "Assistant", "Your answer is ready")
    assert status.text == "Assistant: Your answer is ready"


def test_reduced_motion_disables_word_by_word_streaming():
    body = SimpleNamespace(configure=lambda **options: setattr(body, "text", options["text"]))
    card = SimpleNamespace(_message_body=body)
    gui = SimpleNamespace(reduced_motion=SimpleNamespace(get=lambda: True))
    MessagingMixin._stream_card_text(gui, card, "Complete response", True)
    assert body.text == "Complete response"


def test_theme_propagates_to_dynamic_widget_types():
    class Widget:
        def __init__(self, widget_class, children=()):
            self.widget_class = widget_class
            self.children = list(children)
            self.options = {"style": ""}

        def winfo_children(self):
            return self.children

        def winfo_class(self):
            return self.widget_class

        def configure(self, **options):
            self.options.update(options)

        def cget(self, option):
            return self.options.get(option, "")

    notebook = Widget("TNotebook")
    tree = Widget("Treeview")
    button = Widget("TButton")
    menu = Widget("Menu")
    status = Widget("TFrame", [button])
    root = Widget("Tk", [notebook, tree, menu, status])
    configured = []
    gui = SimpleNamespace(
        root=root,
        style=SimpleNamespace(
            configure=lambda name, **options: configured.append((name, options)),
            map=lambda *_args, **_kwargs: None,
        ),
        colors={"background": "", "text_primary": "", "text_secondary": "", "surface": ""},
        THEMES=StylesMixin.THEMES,
        themes=dict(StylesMixin.THEMES),
    )

    StylesMixin.create_theme_manager(gui)("high_contrast")

    assert notebook.options["style"] == "CB.TNotebook"
    assert tree.options["style"] == "CB.Treeview"
    assert button.options["style"] == "CB.Secondary.TButton"
    assert menu.options["background"] == "#000000"
    assert status.options["style"] == "CB.TFrame"
    assert any(name == "CB.Treeview" for name, _options in configured)
