import tkinter as tk
from tkinter import messagebox, ttk

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class SettingsScreenMixin:
    """Mixin for settings/preferences screens."""

    def create_settings_screen(self):
        """Create settings/preferences screen"""
        self.settings_frame = ttk.Frame(self.main_frame)

        # Header
        header = ttk.Label(self.settings_frame,
                          text=_t("chatbot.settings_preferences", default="Settings & Preferences"),
                          style='CB.Title.TLabel')
        header.pack(pady=(0, 20))

        # Settings notebook
        notebook = ttk.Notebook(self.settings_frame, style='CB.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)

        # General settings tab
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text=_t("chatbot.tab_general", default="General"))

        # Voice settings tab
        voice_tab = ttk.Frame(notebook)
        notebook.add(voice_tab, text=_t("chatbot.tab_voice", default="Voice"))

        # About tab
        about_tab = ttk.Frame(notebook)
        notebook.add(about_tab, text=_t("chatbot.tab_about", default="About"))

        # General settings content
        self.create_general_settings(general_tab)
        self.create_voice_settings(voice_tab)
        self.create_about_tab(about_tab)

        # Back button
        back_button = ttk.Button(self.settings_frame,
                                text=_t("chatbot.back_to_chat", default="Back to Chat"),
                                style='CB.Primary.TButton',
                                command=self.show_chat_screen)
        back_button.pack(pady=(20, 0))

    def create_general_settings(self, parent):
        """Create general settings controls"""
        # Theme settings
        theme_frame = ttk.LabelFrame(parent, text=_t("chatbot.appearance", default="Appearance"), padding=10)
        theme_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(theme_frame, text=_t("chatbot.chat_font_size", default="Chat Font Size:")).pack(anchor=tk.W)
        self.font_size_var = tk.StringVar(value="10")
        font_size_combo = ttk.Combobox(theme_frame,
                                      textvariable=self.font_size_var,
                                      values=["8", "9", "10", "11", "12", "14", "16", "18", "20", "24"],
                                      state="readonly")
        font_size_combo.pack(anchor=tk.W, pady=(5, 10))
        font_size_combo.bind("<<ComboboxSelected>>", self.update_font_size)

        ttk.Label(theme_frame, text=_t("chatbot.theme", default="Colour theme:"))\
            .pack(anchor=tk.W)
        self.theme_var = tk.StringVar(value=getattr(self, 'current_theme', 'default'))
        theme_combo = ttk.Combobox(
            theme_frame, textvariable=self.theme_var,
            values=("default", "dark", "blue", "high_contrast"),
            state="readonly",
        )
        theme_combo.pack(anchor=tk.W, pady=(5, 10))
        theme_combo.bind("<<ComboboxSelected>>",
                         lambda _event: self.apply_theme(self.theme_var.get()))

        self.reduced_motion = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            theme_frame,
            text=_t("chatbot.reduced_motion", default="Reduce motion and animations"),
            variable=self.reduced_motion,
        ).pack(anchor=tk.W)

        # Notification settings
        notif_frame = ttk.LabelFrame(parent, text=_t("chatbot.notifications", default="Notifications"), padding=10)
        notif_frame.pack(fill=tk.X, padx=10, pady=10)

        self.sound_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame,
                       text=_t("chatbot.enable_notification_sounds", default="Enable notification sounds"),
                       variable=self.sound_enabled).pack(anchor=tk.W)

        self.auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame,
                       text=_t("chatbot.auto_scroll_chat", default="Auto-scroll chat"),
                       variable=self.auto_scroll).pack(anchor=tk.W)

        privacy_frame = ttk.LabelFrame(
            parent, text=_t('chatbot.privacy_history', default='Privacy & history'),
            padding=10,
        )
        privacy_frame.pack(fill=tk.X, padx=10, pady=10)
        self.history_enabled_var = tk.BooleanVar(
            value=getattr(self, 'history_enabled', True)
        )
        ttk.Checkbutton(
            privacy_frame,
            text=_t('chatbot.save_history', default='Save conversation history'),
            variable=self.history_enabled_var,
            command=self.apply_privacy_preferences,
        ).pack(anchor=tk.W)
        ttk.Label(
            privacy_frame,
            text=_t('chatbot.retention_days', default='Delete saved conversations after (days):'),
        ).pack(anchor=tk.W, pady=(8, 0))
        self.retention_days_var = tk.IntVar(
            value=getattr(self, 'history_retention_days', 90)
        )
        retention = ttk.Spinbox(
            privacy_frame, from_=1, to=3650,
            textvariable=self.retention_days_var, width=8,
            command=self.apply_privacy_preferences,
        )
        retention.pack(anchor=tk.W, pady=(4, 8))
        retention.bind('<FocusOut>', lambda _event: self.apply_privacy_preferences())
        ttk.Button(
            privacy_frame,
            text=_t('chatbot.delete_all_history', default='Delete all saved history'),
            style='CB.Secondary.TButton', command=self.delete_all_conversation_history,
        ).pack(anchor=tk.W)

        response_frame = ttk.LabelFrame(parent, text='Response preferences', padding=10)
        response_frame.pack(fill=tk.X, padx=10, pady=10)
        self.response_detail_var = tk.StringVar(value='balanced')
        self.response_language_var = tk.StringVar(value='Current interface language')
        self.reading_level_var = tk.StringVar(value='University')
        for label, variable, values in (
            ('Detail', self.response_detail_var, ('concise','balanced','detailed')),
            ('Language', self.response_language_var, ('Current interface language','English','French','Spanish','German')),
            ('Reading level', self.reading_level_var, ('Plain language','University','Expert')),
        ):
            ttk.Label(response_frame,text=label).pack(anchor=tk.W)
            box=ttk.Combobox(response_frame,textvariable=variable,values=values,state='readonly')
            box.pack(anchor=tk.W,pady=(2,6))
            box.bind('<<ComboboxSelected>>',lambda _e:self._apply_response_preferences())
        ttk.Button(response_frame,text='Quality dashboard',command=self.show_quality_dashboard,
                   style='CB.Secondary.TButton').pack(anchor=tk.W,pady=5)

    def _apply_response_preferences(self):
        self.response_detail=self.response_detail_var.get()
        self.response_language=self.response_language_var.get()
        self.reading_level=self.reading_level_var.get()

    def apply_privacy_preferences(self):
        if not hasattr(self, 'conversation_store'):
            return
        self.history_enabled = bool(self.history_enabled_var.get())
        try:
            self.history_retention_days = min(3650, max(1, int(self.retention_days_var.get())))
        except (ValueError, tk.TclError):
            self.history_retention_days = 90
        self.save_draft()
        username = self.current_user.get('username', 'unknown')
        self.conversation_store.purge_expired(username, self.history_retention_days)

    def delete_all_conversation_history(self):
        if not messagebox.askyesno(
            _t('chatbot.delete_all_history', default='Delete all saved history'),
            _t('chatbot.delete_all_history_confirm',
               default='Permanently delete every saved conversation?'),
            parent=self.root,
        ):
            return
        username = self.current_user.get('username', 'unknown')
        self.conversation_store.delete_all(username)
        self._start_new_conversation(clear=True)

    def create_voice_settings(self, parent):
        """Create voice settings controls"""
        if not self.chatbot.voice_interface.enabled:
            ttk.Label(parent,
                     text=_t("chatbot.voice_not_available", default="Voice interface is not available.\nPlease check your microphone and dependencies."),
                     foreground='red').pack(expand=True)
            return

        # Voice test
        test_frame = ttk.LabelFrame(parent, text=_t("chatbot.voice_test", default="Voice Test"), padding=10)
        test_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(test_frame,
                  text=_t("chatbot.test_microphone", default="Test Microphone"),
                  command=self.test_voice).pack(pady=5)

        self.voice_status_label = ttk.Label(test_frame, text=_t("chatbot.click_test_mic", default="Click 'Test Microphone' to check your setup"))
        self.voice_status_label.pack(pady=5)

        # Voice settings
        settings_frame = ttk.LabelFrame(parent, text=_t("chatbot.voice_settings", default="Voice Settings"), padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(settings_frame, text=_t("chatbot.recording_duration", default="Recording Duration (seconds):")).pack(anchor=tk.W)
        self.voice_duration_var = tk.StringVar(value="5")
        duration_spinbox = ttk.Spinbox(settings_frame,
                                      from_=1, to=10,
                                      textvariable=self.voice_duration_var,
                                      width=10)
        duration_spinbox.pack(anchor=tk.W, pady=(5, 10))

        self.voice_tts_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame,
                       text=_t("chatbot.enable_tts", default="Enable text-to-speech responses"),
                       variable=self.voice_tts_enabled).pack(anchor=tk.W)

    def create_about_tab(self, parent):
        """Create about/help tab"""
        # App info
        info_frame = ttk.LabelFrame(parent, text=_t("chatbot.app_information", default="Application Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_text = _t("chatbot.about_info", default="""University Chatbot v2.0
Student Support System

Features:
• Intelligent conversation processing
• Voice interaction support
• Multi-user authentication
• Course recommendations
• Grade tracking
• Financial aid information
• Technical support

Powered by advanced NLP and machine learning.""")

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        # Help
        help_frame = ttk.LabelFrame(parent, text=_t("chatbot.getting_help", default="Getting Help"), padding=10)
        help_frame.pack(fill=tk.X, padx=10, pady=10)

        help_text = _t("chatbot.help_info", default="""How to use the chatbot:
1. Type your questions in natural language
2. Use quick action buttons for common tasks
3. Try voice commands by clicking the Voice button
4. Access your conversation history
5. Click 'Exit to Main' to return to the main system

For technical support, contact IT Services.""")

        ttk.Label(help_frame, text=help_text, justify=tk.LEFT).pack(anchor=tk.W)
