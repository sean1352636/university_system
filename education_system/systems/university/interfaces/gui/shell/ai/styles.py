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


class StylesMixin:
    """Mixin for GUI styling and theme management."""

    def setup_styles(self):
        """Setup modern styling for the GUI"""
        self.style = ttk.Style()

        # Color scheme
        self.colors = {
            'primary': '#2E86AB',      # Blue
            'secondary': '#A23B72',    # Purple
            'accent': '#F18F01',       # Orange
            'success': '#C73E1D',      # Red-orange
            'background': '#F5F5F5',   # Light gray
            'surface': '#FFFFFF',      # White
            'text_primary': '#212121', # Dark gray
            'text_secondary': '#757575' # Medium gray
        }

        # Only set theme and root bg when running standalone (not embedded)
        if not hasattr(self, '_parent_window') or not self._parent_window:
            self.style.theme_use('clam')
            self.root.configure(bg=self.colors['background'])

        # Configure custom styles with CB. prefix to avoid polluting main GUI
        self.style.configure('CB.Title.TLabel',
                           font=('Segoe UI', 16, 'bold'),
                           foreground=self.colors['primary'])

        self.style.configure('CB.Subtitle.TLabel',
                           font=('Segoe UI', 10),
                           foreground=self.colors['text_secondary'])

        self.style.configure('CB.Primary.TButton',
                           font=('Segoe UI', 10, 'bold'))

        self.style.configure('CB.Secondary.TButton',
                           font=('Segoe UI', 9))

        # Setup fonts - FIXED: Create proper font tuples instead of Font objects
        self.fonts = {
            'title': ('Segoe UI', 16, 'bold'),
            'subtitle': ('Segoe UI', 12, 'normal'),
            'body': ('Segoe UI', 10, 'normal'),
            'small': ('Segoe UI', 9, 'normal'),
            'chat': ('Segoe UI', 10, 'normal'),
            'chat_bold': ('Segoe UI', 10, 'bold')  # Add bold variant
        }

    def create_theme_manager(self):
        """Create theme management functionality"""
        self.themes = {
            "default": {
                "bg": "#F5F5F5",
                "fg": "#212121",
                "select_bg": "#2E86AB",
                "select_fg": "#FFFFFF"
            },
            "dark": {
                "bg": "#2B2B2B",
                "fg": "#FFFFFF",
                "select_bg": "#404040",
                "select_fg": "#FFFFFF"
            },
            "blue": {
                "bg": "#E3F2FD",
                "fg": "#0D47A1",
                "select_bg": "#1976D2",
                "select_fg": "#FFFFFF"
            }
        }

        def apply_theme(theme_name):
            """Apply a color theme to the interface"""
            if theme_name not in self.themes:
                return

            theme = self.themes[theme_name]

            # Apply to main window
            self.root.configure(bg=theme["bg"])

            # Apply to chat display
            if hasattr(self, 'chat_display'):
                self.chat_display.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"]
                )

            # Apply to message entry
            if hasattr(self, 'message_entry'):
                self.message_entry.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"]
                )

            # Update color references
            self.colors['background'] = theme["bg"]
            self.colors['text_primary'] = theme["fg"]

        return apply_theme
