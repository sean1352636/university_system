import tkinter as tk
from tkinter import ttk, scrolledtext
import logging

from education_system.post_18.university_system.core.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
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
        header_frame = ttk.Frame(self.chat_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # User info
        self.user_info_label = ttk.Label(header_frame,
                                        text=_t("chatbot.welcome", default="Welcome to University Chatbot"),
                                        style='CB.Title.TLabel')
        self.user_info_label.pack(side=tk.LEFT)

        # Header buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)

        self.voice_button = ttk.Button(button_frame,
                                      text=_t("chatbot.voice_btn", default="\U0001f3a4 Voice"),
                                      style='CB.Secondary.TButton',
                                      command=self.toggle_voice_mode)
        self.voice_button.pack(side=tk.LEFT, padx=(0, 5))

        self.clear_button = ttk.Button(button_frame,
                                      text=_t("chatbot.clear_btn", default="\U0001f5d1 Clear"),
                                      style='CB.Secondary.TButton',
                                      command=self.clear_chat_history)
        self.clear_button.pack(side=tk.LEFT, padx=(0, 5))

        self.settings_button = ttk.Button(button_frame,
                                         text=_t("chatbot.settings_btn", default="\u2699\ufe0f Settings"),
                                         style='CB.Secondary.TButton',
                                         command=self.show_settings_screen)
        self.settings_button.pack(side=tk.LEFT, padx=(0, 5))

        self.exit_button = ttk.Button(button_frame,
                                     text=_t("chatbot.exit_to_main", default="Exit to Main"),
                                     style='CB.Secondary.TButton',
                                     command=self.handle_exit)
        self.exit_button.pack(side=tk.LEFT)

        # Chat area
        chat_container = ttk.Frame(self.chat_frame)
        chat_container.pack(fill=tk.BOTH, expand=True)

        # Chat display
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
        input_frame.pack(fill=tk.X)

        # Message input
        self.message_entry = tk.Text(input_frame,
                                    height=3,
                                    font=self.fonts['body'],
                                    wrap=tk.WORD,
                                    relief=tk.FLAT,
                                    borderwidth=1)
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Send button (kept on self so messaging can disable it while a
        # message is in flight)
        self.send_button = ttk.Button(input_frame,
                                text=_t("chatbot.send_btn", default="Send"),
                                style='CB.Primary.TButton',
                                command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)

        # Quick actions frame with role-appropriate notebook tabs
        quick_actions_notebook = ttk.Notebook(self.chat_frame)
        quick_actions_notebook.pack(fill=tk.X, pady=(10, 0))

        for tab_title, buttons in self._quick_action_tabs():
            self._add_quick_action_tab(quick_actions_notebook, tab_title, buttons)

    def _add_quick_action_tab(self, notebook, title, buttons):
        """Render one quick-action tab as a 3-column grid of buttons."""
        frame = ttk.Frame(notebook, padding=5)
        notebook.add(frame, text=title)
        for i, (text, cmd) in enumerate(buttons):
            ttk.Button(frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky='ew')
        for c in range(3):
            frame.columnconfigure(c, weight=1)

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

        except (ValueError, AttributeError) as e:
            logger.debug(f"Font size update error: {e}")

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
