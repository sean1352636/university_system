import tkinter as tk
from tkinter import ttk, scrolledtext
import logging

from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

logger = logging.getLogger(__name__)


class ChatScreenMixin:
    """Mixin for the main chat screen and display."""

    def create_chat_screen(self):
        """Create main chat interface - with fixed font handling"""
        self.chat_frame = ttk.Frame(self.main_frame)

        # Header
        header_frame = ttk.Frame(self.chat_frame, style='CB.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        self.chat_header_frame = header_frame

        # User info
        self.user_info_label = ttk.Label(header_frame,
                                        text=_t("chatbot.welcome", default="Welcome to University Chatbot"),
                                        style='CB.Title.TLabel')
        self.user_info_label.pack(side=tk.LEFT)

        # Header buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)
        self.chat_header_buttons = button_frame

        self.voice_button = ttk.Button(button_frame,
                                      text=_t("chatbot.voice_btn", default="Voice input"),
                                      style='CB.Secondary.TButton',
                                      command=self.toggle_voice_mode)
        self.voice_button.pack(side=tk.LEFT, padx=(0, 5))

        self.clear_button = ttk.Button(button_frame,
                                      text=_t("chatbot.clear_btn", default="Clear conversation"),
                                      style='CB.Secondary.TButton',
                                      command=self.clear_chat_history)
        self.clear_button.pack(side=tk.LEFT, padx=(0, 5))

        self.settings_button = ttk.Button(button_frame,
                                         text=_t("chatbot.settings_btn", default="Settings"),
                                         style='CB.Secondary.TButton',
                                         command=self.show_settings_screen)
        self.settings_button.pack(side=tk.LEFT, padx=(0, 5))

        self.exit_button = ttk.Button(button_frame,
                                     text=_t("chatbot.exit_to_main", default="Exit to Main"),
                                     style='CB.Secondary.TButton',
                                     command=self.handle_exit)
        self.exit_button.pack(side=tk.LEFT)
        self.new_conversation_button = ttk.Button(
            button_frame, text=_t("chatbot.new_conversation", default="New conversation"),
            style='CB.Secondary.TButton', command=self.new_conversation,
        )
        self.new_conversation_button.pack(side=tk.LEFT, padx=(0, 5))
        self.conversations_button = ttk.Button(
            button_frame, text=_t("chatbot.saved_conversations", default="Saved conversations"),
            style='CB.Secondary.TButton', command=self.show_conversation_manager,
        )
        self.conversations_button.pack(side=tk.LEFT, padx=(0, 5))
        self.memory_button = ttk.Button(button_frame,text='Memory',style='CB.Secondary.TButton',command=self.show_memory_controls)
        self.memory_button.pack(side=tk.LEFT,padx=(0,5))
        self.notifications_button = ttk.Button(button_frame,text='Updates',style='CB.Secondary.TButton',command=self.show_chat_notifications)
        self.notifications_button.pack(side=tk.LEFT,padx=(0,5))
        self.chat_header_action_buttons = (
            self.new_conversation_button, self.conversations_button,
            self.memory_button, self.notifications_button,
            self.voice_button, self.clear_button,
            self.settings_button, self.exit_button,
        )

        # Keep contextual suggestions above the expanding transcript so they
        # remain visible even on short laptop displays.
        self._create_command_palette()

        # Chat area
        chat_container = ttk.Frame(self.chat_frame)
        chat_container.pack(fill=tk.BOTH, expand=True)

        # Chat display. Message cards are embedded into this text widget so we
        # retain its mature scrolling behaviour while presenting a modern,
        # clearly separated conversation.
        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            font=self.fonts['chat'],
            state=tk.DISABLED,
            height=20,
            bg='white',
            relief=tk.FLAT,
            borderwidth=1
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.chat_display.configure(cursor="arrow", padx=8, pady=8)
        self.unread_button = ttk.Button(
            chat_container,
            text=_t('chatbot.new_message', default='New message — jump to latest'),
            style='CB.Primary.TButton', command=self.jump_to_latest_message,
        )

        # Right-click context menu so users can copy bot replies out of the
        # read-only transcript (the widget is DISABLED, so normal selection
        # copy shortcuts don't always fire).
        self._create_chat_context_menu(chat_container)

        # Configure chat display tags for styling - FIXED: Use proper font tuples
        self.chat_display.tag_configure("user",
                                       foreground=self.colors['primary'],
                                       font=self.fonts['chat_bold'])  # Use pre-defined bold font
        self.chat_display.tag_configure("bot",
                                       foreground=self.colors['secondary'],
                                       font=self.fonts['chat'])
        self.chat_display.tag_configure("system",
                                       foreground=self.colors['text_secondary'],
                                       font=self.fonts['small'])
        self.chat_display.tag_configure("timestamp",
                                       foreground=self.colors['text_secondary'],
                                       font=self.fonts['small'])

        # Input area
        input_frame = ttk.Frame(chat_container)
        self.input_frame = input_frame

        # Message input
        self.message_entry = tk.Text(input_frame,
                                    height=3,
                                    font=self.fonts['body'],
                                    wrap=tk.WORD,
                                    relief=tk.FLAT,
                                    borderwidth=1)

        self.attach_button = ttk.Button(
            input_frame, text=_t('chatbot.attach_files', default='Attach files'),
            style='CB.Secondary.TButton', command=self.show_attachment_manager,
        )

        # Generation controls
        controls = ttk.Frame(input_frame)
        self.generation_controls = controls
        self.send_button = ttk.Button(controls,
                                text=_t("chatbot.send_btn", default="Send"),
                                style='CB.Primary.TButton',
                                command=self.send_message)
        self.send_button.pack(fill=tk.X)
        self.stop_button = ttk.Button(
            controls,
            text=_t("chatbot.stop_btn", default="Stop generating"),
            style='CB.Secondary.TButton',
            command=self.stop_generating,
            state=tk.DISABLED,
        )
        self.stop_button.pack(fill=tk.X, pady=(5, 0))

        # Reserve the composer at the bottom before allowing the transcript to
        # expand. A grid gives Send its own non-shrinking column, so neither a
        # tall transcript nor translated labels can push it off-screen.
        self.chat_display.pack_forget()
        input_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        input_frame.columnconfigure(0, weight=1, minsize=180)
        self.message_entry.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.attach_button.grid(row=0, column=1, sticky='ns', padx=(0, 8))
        controls.grid(row=0, column=2, sticky='nsew')

        self._responsive_width = None
        self.root.bind('<Configure>', self._schedule_responsive_layout, add='+')
        self.root.after_idle(self._apply_responsive_layout)

    def _create_command_palette(self):
        """Create searchable commands, favourites and contextual suggestions."""
        panel = ttk.LabelFrame(
            self.chat_frame,
            text=_t("chatbot.commands", default="Commands"),
            padding=8,
        )
        panel.pack(fill=tk.X, pady=(10, 0))

        search_row = ttk.Frame(panel)
        search_row.pack(fill=tk.X)
        ttk.Label(search_row, text=_t("chatbot.search_commands", default="Search:"))\
            .pack(side=tk.LEFT, padx=(0, 6))
        self.command_search_var = tk.StringVar()
        self.command_search_entry = ttk.Entry(
            search_row, textvariable=self.command_search_var
        )
        self.command_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.command_search_var.trace_add("write", self._on_command_search)

        self._favourite_commands = set()
        self._command_specs = self._flatten_commands(self._quick_action_tabs())

        self.suggested_commands_frame = ttk.Frame(panel)
        self.suggested_commands_frame.pack(fill=tk.X, pady=(8, 3))
        self.command_results_frame = ttk.Frame(panel)
        self.command_results_frame.pack(fill=tk.X)
        self._render_command_palette()

    @staticmethod
    def _flatten_commands(tabs):
        """Return de-duplicated ``(category, label, callback)`` commands."""
        commands = []
        seen = set()
        for category, buttons in tabs:
            for label, callback in buttons:
                key = str(label).casefold()
                if key not in seen:
                    commands.append((category, label, callback))
                    seen.add(key)
        return commands

    def _on_command_search(self, *_args):
        self._render_command_palette()

    def _schedule_responsive_layout(self, event=None):
        """Debounce layout work while a window is actively being resized."""
        if event is not None and event.widget is not self.root:
            return
        pending = getattr(self, '_responsive_after_id', None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        self._responsive_after_id = self.root.after(80, self._apply_responsive_layout)

    @staticmethod
    def _command_column_count(width):
        """Return a readable command-column count for the available width."""
        if width < 760:
            return 1
        if width < 1050:
            return 2
        return 4

    def _apply_responsive_layout(self):
        """Reflow the header and command palette at compact breakpoints."""
        self._responsive_after_id = None
        width = max(1, self.root.winfo_width())
        compact = width < 820
        self.user_info_label.configure(wraplength=max(280, width - 40))
        self.user_info_label.pack_forget()
        self.chat_header_buttons.pack_forget()
        for button in self.chat_header_action_buttons:
            button.pack_forget()
            button.grid_forget()
        if compact:
            self.user_info_label.pack(side=tk.TOP, anchor=tk.W, fill=tk.X)
            self.chat_header_buttons.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
            for index, button in enumerate(self.chat_header_action_buttons):
                button.grid(row=index // 2, column=index % 2,
                            padx=3, pady=2, sticky='ew')
            self.chat_header_buttons.columnconfigure(0, weight=1)
            self.chat_header_buttons.columnconfigure(1, weight=1)
        else:
            self.user_info_label.pack(side=tk.LEFT)
            self.chat_header_buttons.pack(side=tk.RIGHT)
            for button in self.chat_header_action_buttons:
                button.pack(side=tk.LEFT, padx=(0, 5))
        columns = self._command_column_count(width)
        if columns != getattr(self, '_command_columns', None):
            self._command_columns = columns
            self._render_command_palette()
        self._update_message_wraplengths(width)

    def _suggested_commands(self):
        """Choose a compact, role-aware set, refined by the latest question."""
        commands = list(getattr(self, '_command_specs', []))
        role = (self._current_role() or '').lower()
        preferred = {
            'alumni': ('Transcripts', 'Events', 'Staff Directory'),
            'staff': ('Timetable', 'Staff Directory', 'Room Booking'),
            'admin': ('Support Tickets', 'Staff Directory', 'Announcements'),
        }.get(role, ('Timetable', 'Deadlines', 'Assignments'))
        latest = getattr(self, '_last_user_message', '').casefold()
        keyword_hits = [c for c in commands if any(
            word in latest for word in str(c[1]).casefold().split()
        )]
        ordered = keyword_hits + sorted(
            commands,
            key=lambda c: preferred.index(str(c[1]))
            if str(c[1]) in preferred else len(preferred),
        )
        result = []
        for command in ordered:
            if command not in result:
                result.append(command)
            if len(result) == 3:
                break
        return result

    def _render_command_palette(self):
        """Refresh suggestions and filtered/favourite command results."""
        if not hasattr(self, 'command_results_frame'):
            return
        for frame in (self.suggested_commands_frame, self.command_results_frame):
            for child in frame.winfo_children():
                child.destroy()

        ttk.Label(
            self.suggested_commands_frame,
            text=_t("chatbot.suggested", default="Suggested for you"),
            style='CB.Subtitle.TLabel',
        ).grid(row=0, column=0, sticky='w', padx=(0, 8), pady=2)
        suggested_columns = max(1, getattr(self, '_command_columns', 2))
        for index, (_category, label, callback) in enumerate(self._suggested_commands()):
            ttk.Button(
                self.suggested_commands_frame, text=label,
                style='CB.Secondary.TButton', command=callback,
            ).grid(row=1 + index // suggested_columns,
                   column=index % suggested_columns, padx=3, pady=2, sticky='ew')
        for column in range(suggested_columns):
            self.suggested_commands_frame.columnconfigure(column, weight=1)

        query = self.command_search_var.get().strip().casefold()
        favourites = getattr(self, '_favourite_commands', set())
        matches = [c for c in self._command_specs if not query or query in
                   f"{c[0]} {c[1]}".casefold()]
        matches.sort(key=lambda c: (str(c[1]) not in favourites, str(c[1])))
        columns = max(1, getattr(self, '_command_columns', 2))
        # With no search, show only favourites; the three role-aware
        # suggestions above are the useful default. This avoids an eight-row
        # command wall on narrow windows. Searching expands a bounded result
        # set appropriate to the current width.
        if not query:
            matches = [c for c in matches if str(c[1]) in favourites]
        result_limit = {1: 4, 2: 6}.get(columns, 8)
        for row, (category, label, callback) in enumerate(matches[:result_limit]):
            group = row % columns
            ttk.Button(
                self.command_results_frame,
                text=(_t("chatbot.remove_favourite", default="Remove favourite")
                      if str(label) in favourites else
                      _t("chatbot.add_favourite", default="Add favourite")),
                command=lambda name=str(label): self._toggle_command_favourite(name),
                style='CB.Secondary.TButton',
            ).grid(row=row // columns, column=group * 2, padx=(2, 0), pady=2)
            ttk.Button(
                self.command_results_frame,
                text=f"{label} · {category}",
                style='CB.Secondary.TButton', command=callback,
            ).grid(row=row // columns, column=group * 2 + 1,
                   padx=(0, 5), pady=2, sticky='ew')
        for column in range(columns):
            self.command_results_frame.columnconfigure(column * 2 + 1, weight=1)
        if not query and not matches:
            ttk.Label(
                self.command_results_frame,
                text=_t(
                    'chatbot.search_commands_hint',
                    default='Search to browse all commands. Favourites appear here.',
                ),
                style='CB.Subtitle.TLabel',
            ).grid(row=0, column=0, columnspan=max(2, columns * 2),
                   sticky='w', padx=3, pady=2)

    def _toggle_command_favourite(self, label):
        if label in self._favourite_commands:
            self._favourite_commands.remove(label)
        else:
            self._favourite_commands.add(label)
        self._render_command_palette()

    def _current_role(self):
        """Best-effort current-user role (auth is set before current_user is)."""
        auth = getattr(self, 'auth_system', None)
        if auth is not None and getattr(auth, 'current_user', None):
            return auth.current_user.get('role')
        if getattr(self, 'current_user', None):
            return self.current_user.get('role')
        return None

    def _quick_action_tabs(self):
        """Return the (tab_title, buttons) specs for the user's role."""
        if self._current_role() == 'alumni':
            return self._alumni_quick_action_tabs()
        return self._default_quick_action_tabs()

    def _alumni_quick_action_tabs(self):
        """Quick actions relevant to alumni — no courses/grades/timetable/fees."""
        return [
            (_t("chatbot.tab_alumni_services", default="Alumni Services"), [
                (_t("chatbot.transcript_request", default="Transcripts"), self.show_transcript_request),
                (_t("chatbot.staff_directory", default="Staff Directory"), self.show_staff_directory),
                (_t("chatbot.support_tickets", default="Support Tickets"), self.show_my_tickets),
                (_t("chatbot.quick_help", default="Quick Help"), self.show_quick_help),
            ]),
            (_t("chatbot.tab_community", default="Community"), [
                (_t("chatbot.events", default="Events"), self.show_upcoming_events),
                (_t("chatbot.announcements", default="Announcements"), self.show_announcements),
                (_t("chatbot.clubs", default="Clubs & Societies"), self.show_clubs_societies),
                (_t("chatbot.mental_health", default="Wellbeing"), self.show_mental_health_resources),
            ]),
            (_t("chatbot.tab_facilities", default="Facilities"), [
                (_t("chatbot.room_booking", default="Room Booking"), self.show_room_bookings),
                (_t("chatbot.book_room", default="Book a Room"), self.show_book_room_dialog),
                (_t("chatbot.library_search", default="Library Search"), self.show_library_search),
                (_t("chatbot.transport", default="Transport"), self.show_transport_schedule),
            ]),
        ]

    def _default_quick_action_tabs(self):
        """Quick actions for students / staff."""
        return [
            (_t("chatbot.tab_services", default="Student Services"), [
                (_t("chatbot.my_courses", default="My Courses"), self.show_my_courses),
                (_t("chatbot.my_grades", default="My Grades"), self.show_my_grades),
                (_t("chatbot.view_schedule", default="Timetable"), self.show_my_schedule),
                (_t("chatbot.check_financial_aid", default="Financial Aid"), self.show_financial_aid),
                (_t("chatbot.fee_balance", default="Fee Balance"), self.show_fee_balance),
                (_t("chatbot.transcript_request", default="Transcripts"), self.show_transcript_request),
            ]),
            (_t("chatbot.tab_academic", default="Academic Support"), [
                (_t("chatbot.assignments", default="Assignments"), self.show_my_assignments),
                (_t("chatbot.deadlines", default="Deadlines"), self.show_deadlines),
                (_t("chatbot.exam_schedule", default="Exam Schedule"), self.show_exam_schedule),
                (_t("chatbot.library_search", default="Library Search"), self.show_library_search),
                (_t("chatbot.academic_calendar", default="Academic Calendar"), self.show_academic_calendar),
                (_t("chatbot.attendance", default="Attendance"), self.show_my_attendance),
            ]),
            (_t("chatbot.tab_admin", default="Admin & Admissions"), [
                (_t("chatbot.application_status", default="Application Status"), self.show_application_status),
                (_t("chatbot.staff_directory", default="Staff Directory"), self.show_staff_directory),
                (_t("chatbot.room_booking", default="Room Booking"), self.show_room_bookings),
                (_t("chatbot.book_room", default="Book a Room"), self.show_book_room_dialog),
                (_t("chatbot.id_card", default="ID Card Help"), self.show_id_card_help),
                (_t("chatbot.leave_absence", default="Leave/Deferral"), self.show_leave_guidance),
                (_t("chatbot.support_tickets", default="Support Tickets"), self.show_my_tickets),
            ]),
            (_t("chatbot.tab_campus", default="Campus Life"), [
                (_t("chatbot.events", default="Events"), self.show_upcoming_events),
                (_t("chatbot.clubs", default="Clubs & Societies"), self.show_clubs_societies),
                (_t("chatbot.mental_health", default="Wellbeing"), self.show_mental_health_resources),
                (_t("chatbot.lost_found", default="Lost & Found"), self.show_lost_found),
                (_t("chatbot.transport", default="Transport"), self.show_transport_schedule),
                (_t("chatbot.notifications_btn", default="Notifications"), self.show_my_notifications),
            ]),
            (_t("chatbot.tab_info", default="Help & Info"), [
                (_t("chatbot.announcements", default="Announcements"), self.show_announcements),
                (_t("chatbot.library_books", default="My Library Books"), self.show_my_library_books),
                (_t("chatbot.quick_help", default="Quick Help"), self.show_quick_help),
            ]),
        ]

    def _create_chat_context_menu(self, parent):
        """Attach a right-click Copy / Select All menu to the chat transcript."""
        menu = tk.Menu(parent, tearoff=0)
        menu.add_command(label=_t("chatbot.copy", default="Copy"),
                         command=self._copy_chat_selection)
        menu.add_command(label=_t("chatbot.select_all", default="Select All"),
                         command=self._select_all_chat)
        menu.add_command(label=_t('chatbot.copy_conversation', default='Copy conversation'),
                         command=self.copy_conversation)
        menu.add_command(label=_t('chatbot.copy_markdown', default='Copy conversation as Markdown'),
                         command=lambda: self.copy_conversation(markdown=True))
        self._chat_context_menu = menu

        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # Button-3 on X11/Windows; Button-2 is the right button on macOS.
        self.chat_display.bind('<Button-3>', _show_menu)
        self.chat_display.bind('<Button-2>', _show_menu)

    def _copy_chat_selection(self):
        """Copy the current chat selection to the clipboard."""
        try:
            text = self.chat_display.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return  # nothing selected
        self.chat_display.clipboard_clear()
        self.chat_display.clipboard_append(text)

    def _select_all_chat(self):
        """Select the entire chat transcript."""
        self.chat_display.tag_add(tk.SEL, "1.0", tk.END)

    def update_font_size(self, event=None):
        """Update chat font size - FIXED: Handle both Font objects and tuples properly"""
        try:
            size = int(self.font_size_var.get())

            # Preserve whatever font family the theme actually resolved to
            # instead of hardcoding a Windows-only face ('Segoe UI' silently
            # falls back to a Tk default on Linux/macOS).
            family = self.fonts.get('chat', ('TkDefaultFont',))[0]

            # Create new font tuples with updated size
            new_chat_font = (family, size, 'normal')
            new_body_font = (family, size, 'normal')
            new_bold_font = (family, size, 'bold')

            # Update the fonts dictionary
            self.fonts['chat'] = new_chat_font
            self.fonts['body'] = new_body_font
            self.fonts['chat_bold'] = new_bold_font

            # Apply to widgets
            self.chat_display.config(font=new_chat_font)
            self.message_entry.config(font=new_body_font)

            # Update text tags
            self.chat_display.tag_configure("user", font=new_bold_font)
            self.chat_display.tag_configure("bot", font=new_chat_font)
            self.style.configure('CB.Primary.TButton', font=(family, max(9, size - 1), 'bold'))
            self.style.configure('CB.Secondary.TButton', font=(family, max(9, size - 1)))
            self.style.configure('CB.TLabel', font=(family, size))
            self.style.configure('CB.Subtitle.TLabel', font=(family, size))
            self.style.configure('CB.Title.TLabel', font=(family, size + 5, 'bold'))
            self.style.configure('CB.TNotebook.Tab', font=(family, max(9, size - 1)))
            for card, _msg_type in getattr(self, '_message_cards', []):
                for child in card.winfo_children():
                    for widget in ([child] + list(child.winfo_children())):
                        if widget.winfo_class() == 'Label':
                            widget.configure(font=new_chat_font)
                card._sender_label.configure(font=new_bold_font)
                card._time_label.configure(font=(family, max(8, size - 1)))
            self._update_message_wraplengths(self.root.winfo_width())

        except (ValueError, AttributeError) as e:
            logger.debug(f"Font size update error: {e}")

    def _update_message_wraplengths(self, width):
        wrap = max(260, width - (70 if width < 820 else 150))
        for card, _msg_type in getattr(self, '_message_cards', []):
            body = getattr(card, '_message_body', None)
            if body is not None:
                body.configure(wraplength=wrap)

    def show_chat_screen(self):
        """Show the main chat screen"""
        self.hide_all_screens()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = True
        self.message_entry.focus()

        # Update user info
        if self.current_user:
            self.user_info_label.config(text=f"Welcome, {self.current_user['username']} ({self.current_user['role']})")

        # Add personalized welcome summary
        if not hasattr(self, '_welcome_shown'):
            welcome = self._build_welcome_summary()
            self.add_chat_message("System", welcome, "system")
            self._welcome_shown = True

    def create_widgets(self):
        """Create and layout all GUI widgets"""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create different screens (no login screen - use central auth)
        self.create_chat_screen()
        self.create_settings_screen()

        # Create status bar
        self.create_status_bar()
