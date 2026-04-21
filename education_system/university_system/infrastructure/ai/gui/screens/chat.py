import tkinter as tk
from tkinter import ttk, scrolledtext
import logging

from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
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

        # Send button
        send_button = ttk.Button(input_frame,
                                text=_t("chatbot.send_btn", default="Send"),
                                style='CB.Primary.TButton',
                                command=self.send_message)
        send_button.pack(side=tk.RIGHT)

        # Quick actions frame with scrollable notebook tabs
        quick_actions_notebook = ttk.Notebook(self.chat_frame)
        quick_actions_notebook.pack(fill=tk.X, pady=(10, 0))

        # --- Student Services tab ---
        services_frame = ttk.Frame(quick_actions_notebook, padding=5)
        quick_actions_notebook.add(services_frame, text=_t("chatbot.tab_services", default="Student Services"))
        services_buttons = [
            (_t("chatbot.my_courses", default="My Courses"), self.show_my_courses),
            (_t("chatbot.my_grades", default="My Grades"), self.show_my_grades),
            (_t("chatbot.view_schedule", default="Timetable"), self.show_my_schedule),
            (_t("chatbot.check_financial_aid", default="Financial Aid"), self.show_financial_aid),
            (_t("chatbot.fee_balance", default="Fee Balance"), self.show_fee_balance),
            (_t("chatbot.transcript_request", default="Transcripts"), self.show_transcript_request),
        ]
        for i, (text, cmd) in enumerate(services_buttons):
            ttk.Button(services_frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky='ew')
        for c in range(3):
            services_frame.columnconfigure(c, weight=1)

        # --- Academic Support tab ---
        academic_frame = ttk.Frame(quick_actions_notebook, padding=5)
        quick_actions_notebook.add(academic_frame, text=_t("chatbot.tab_academic", default="Academic Support"))
        academic_buttons = [
            (_t("chatbot.assignments", default="Assignments"), self.show_my_assignments),
            (_t("chatbot.deadlines", default="Deadlines"), self.show_deadlines),
            (_t("chatbot.exam_schedule", default="Exam Schedule"), self.show_exam_schedule),
            (_t("chatbot.library_search", default="Library Search"), self.show_library_search),
            (_t("chatbot.academic_calendar", default="Academic Calendar"), self.show_academic_calendar),
            (_t("chatbot.attendance", default="Attendance"), self.show_my_attendance),
        ]
        for i, (text, cmd) in enumerate(academic_buttons):
            ttk.Button(academic_frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky='ew')
        for c in range(3):
            academic_frame.columnconfigure(c, weight=1)

        # --- Admissions & Admin tab ---
        admin_frame = ttk.Frame(quick_actions_notebook, padding=5)
        quick_actions_notebook.add(admin_frame, text=_t("chatbot.tab_admin", default="Admin & Admissions"))
        admin_buttons = [
            (_t("chatbot.application_status", default="Application Status"), self.show_application_status),
            (_t("chatbot.staff_directory", default="Staff Directory"), self.show_staff_directory),
            (_t("chatbot.room_booking", default="Room Booking"), self.show_room_bookings),
            (_t("chatbot.id_card", default="ID Card Help"), self.show_id_card_help),
            (_t("chatbot.leave_absence", default="Leave/Deferral"), self.show_leave_guidance),
            (_t("chatbot.support_tickets", default="Support Tickets"), self.show_my_tickets),
        ]
        for i, (text, cmd) in enumerate(admin_buttons):
            ttk.Button(admin_frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky='ew')
        for c in range(3):
            admin_frame.columnconfigure(c, weight=1)

        # --- Campus Life tab ---
        campus_frame = ttk.Frame(quick_actions_notebook, padding=5)
        quick_actions_notebook.add(campus_frame, text=_t("chatbot.tab_campus", default="Campus Life"))
        campus_buttons = [
            (_t("chatbot.events", default="Events"), self.show_upcoming_events),
            (_t("chatbot.clubs", default="Clubs & Societies"), self.show_clubs_societies),
            (_t("chatbot.mental_health", default="Wellbeing"), self.show_mental_health_resources),
            (_t("chatbot.lost_found", default="Lost & Found"), self.show_lost_found),
            (_t("chatbot.transport", default="Transport"), self.show_transport_schedule),
            (_t("chatbot.notifications_btn", default="Notifications"), self.show_my_notifications),
        ]
        for i, (text, cmd) in enumerate(campus_buttons):
            ttk.Button(campus_frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky='ew')
        for c in range(3):
            campus_frame.columnconfigure(c, weight=1)

        # --- Info tab ---
        info_frame = ttk.Frame(quick_actions_notebook, padding=5)
        quick_actions_notebook.add(info_frame, text=_t("chatbot.tab_info", default="Help & Info"))
        info_buttons = [
            (_t("chatbot.announcements", default="Announcements"), self.show_announcements),
            (_t("chatbot.library_books", default="My Library Books"), self.show_my_library_books),
            (_t("chatbot.quick_help", default="Quick Help"), self.show_quick_help),
        ]
        for i, (text, cmd) in enumerate(info_buttons):
            ttk.Button(info_frame, text=text, style='CB.Secondary.TButton',
                       command=cmd).grid(row=0, column=i, padx=5, pady=4, sticky='ew')
        for c in range(3):
            info_frame.columnconfigure(c, weight=1)

    def update_font_size(self, event=None):
        """Update chat font size - FIXED: Handle both Font objects and tuples properly"""
        try:
            size = int(self.font_size_var.get())

            # Create new font tuples with updated size
            new_chat_font = ('Segoe UI', size, 'normal')
            new_body_font = ('Segoe UI', size, 'normal')
            new_bold_font = ('Segoe UI', size, 'bold')

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
