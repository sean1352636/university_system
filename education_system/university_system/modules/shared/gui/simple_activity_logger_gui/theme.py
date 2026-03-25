"""
Theme configuration for the Activity Logger GUI.
"""

from tkinter import ttk

from education_system.university_system.modules.shared.gui.simple_activity_logger_gui._imports import tk


class LoggerGUITheme:
    """Modern light theme for the logger GUI"""

    # Color scheme - Light Theme
    DARK_BG = "#f0f0f0"  # Light gray background
    DARKER_BG = "#e0e0e0"  # Slightly darker gray
    LIGHT_BG = "#ffffff"  # White
    ACCENT_BLUE = "#0066cc"
    ACCENT_GREEN = "#4CAF50"
    ACCENT_RED = "#f44336"
    ACCENT_ORANGE = "#ff9800"
    ACCENT_YELLOW = "#ffc107"

    TEXT_PRIMARY = "#000000"  # Black text
    TEXT_SECONDARY = "#333333"  # Dark gray text
    TEXT_MUTED = "#666666"  # Medium gray text

    BORDER = "#cccccc"  # Light gray border

    @classmethod
    def apply_theme(cls, root, standalone=True):
        """Apply the light theme to the root window.

        Args:
            root: The root or toplevel window.
            standalone: If False (embedded mode), skip theme_use and root bg
                        changes that would affect the main application.
        """
        # Configure ttk styles
        style = ttk.Style()

        if standalone:
            # Only change the base theme when running standalone
            try:
                style.theme_use('clam')
            except Exception:
                pass

        # Configure namespaced styles (AL.* prefix avoids collisions)
        style.configure('AL.Title.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 14, 'bold'))

        style.configure('AL.Heading.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 10, 'bold'))

        style.configure('AL.Info.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_SECONDARY,
                       font=('Segoe UI', 9))

        style.configure('AL.Success.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_GREEN,
                       font=('Segoe UI', 9, 'bold'))

        style.configure('AL.Error.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_RED,
                       font=('Segoe UI', 9, 'bold'))

        style.configure('AL.Warning.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_ORANGE,
                       font=('Segoe UI', 9, 'bold'))

        # Button styles
        style.configure('AL.Accent.TButton',
                       background=cls.ACCENT_BLUE,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))

        style.configure('AL.Success.TButton',
                       background=cls.ACCENT_GREEN,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))

        style.configure('AL.Danger.TButton',
                       background=cls.ACCENT_RED,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))

        # Frame styles
        style.configure('AL.Card.TFrame',
                       background=cls.LIGHT_BG,
                       relief='flat',
                       borderwidth=1)

        # Notebook styles
        style.configure('AL.TNotebook',
                       background=cls.DARK_BG,
                       borderwidth=0)

        style.configure('AL.TNotebook.Tab',
                       background=cls.LIGHT_BG,
                       foreground=cls.TEXT_SECONDARY,
                       padding=[12, 8],
                       font=('Segoe UI', 9))

        if standalone:
            # Only change root background in standalone mode
            root.configure(bg=cls.DARK_BG)
