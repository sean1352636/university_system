import tkinter as tk
from tkinter import ttk

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
        notebook = ttk.Notebook(self.settings_frame)
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
                                      values=["8", "9", "10", "11", "12", "14"],
                                      state="readonly")
        font_size_combo.pack(anchor=tk.W, pady=(5, 10))
        font_size_combo.bind("<<ComboboxSelected>>", self.update_font_size)

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
