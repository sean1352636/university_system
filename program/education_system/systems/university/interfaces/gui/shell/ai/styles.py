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

    THEMES = {
        "default": {
            "bg": "#F5F5F5",
            "surface": "#FFFFFF",
            "fg": "#212121",
            "select_bg": "#246B89",
            "select_fg": "#FFFFFF",
        },
        "dark": {
            "bg": "#2B2B2B",
            "surface": "#383838",
            "fg": "#FFFFFF",
            "select_bg": "#404040",
            "select_fg": "#FFFFFF",
        },
        "blue": {
            "bg": "#E3F2FD",
            "surface": "#FFFFFF",
            "fg": "#0D47A1",
            "select_bg": "#1976D2",
            "select_fg": "#FFFFFF",
        },
        "high_contrast": {
            "bg": "#000000",
            "surface": "#000000",
            "fg": "#FFFFFF",
            "select_bg": "#FFFF00",
            "select_fg": "#000000",
        },
    }

    def setup_styles(self):
        """Setup modern styling for the GUI"""
        self.style = ttk.Style()

        # Color scheme
        self.colors = {
            "primary": "#2E86AB",  # Blue
            "secondary": "#A23B72",  # Purple
            "accent": "#F18F01",  # Orange
            "success": "#C73E1D",  # Red-orange
            "background": "#F5F5F5",  # Light gray
            "surface": "#FFFFFF",  # White
            "text_primary": "#212121",  # Dark gray
            "text_secondary": "#757575",  # Medium gray
        }

        # Only set theme and root bg when running standalone (not embedded)
        if not hasattr(self, "_parent_window") or not self._parent_window:
            self.style.theme_use("clam")
            self.root.configure(bg=self.colors["background"])

        # Configure custom styles with CB. prefix to avoid polluting main GUI
        self.style.configure(
            "CB.Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.colors["primary"]
        )

        self.style.configure(
            "CB.Subtitle.TLabel", font=("Segoe UI", 10), foreground=self.colors["text_secondary"]
        )

        self.style.configure("CB.Primary.TButton", font=("Segoe UI", 10, "bold"))

        self.style.configure("CB.Secondary.TButton", font=("Segoe UI", 9))
        self.style.configure("CB.TFrame", background=self.colors["background"])
        self.style.configure(
            "CB.TLabel",
            background=self.colors["background"],
            foreground=self.colors["text_primary"],
        )
        self.style.configure("CB.TLabelframe", background=self.colors["background"])
        self.style.configure(
            "CB.TLabelframe.Label",
            background=self.colors["background"],
            foreground=self.colors["text_primary"],
        )
        self.style.configure("CB.TNotebook", background=self.colors["background"])
        self.style.configure("CB.TNotebook.Tab", padding=(10, 6))
        self.style.configure(
            "CB.Treeview", background=self.colors["surface"], foreground=self.colors["text_primary"]
        )
        self.style.configure(
            "CB.Accessible.TButton", padding=(10, 7), font=("Segoe UI", 10, "bold")
        )
        self.style.map(
            "CB.Accessible.TButton",
            focuscolor=[("focus", self.colors["accent"])],
            relief=[("focus", "solid")],
        )

        # Setup fonts - FIXED: Create proper font tuples instead of Font objects
        self.fonts = {
            "title": ("Segoe UI", 16, "bold"),
            "subtitle": ("Segoe UI", 12, "normal"),
            "body": ("Segoe UI", 10, "normal"),
            "small": ("Segoe UI", 9, "normal"),
            "chat": ("Segoe UI", 10, "normal"),
            "chat_bold": ("Segoe UI", 10, "bold"),  # Add bold variant
        }

    def create_theme_manager(self):
        """Create theme management functionality"""
        self.themes = dict(self.THEMES)

        def apply_theme(theme_name):
            """Apply a color theme to the interface"""
            if theme_name not in self.themes:
                return

            theme = self.themes[theme_name]

            # Apply to main window
            self.root.configure(bg=theme["bg"])
            self.current_theme = theme_name

            self.style.configure("CB.TFrame", background=theme["bg"])
            self.style.configure("CB.TLabel", background=theme["bg"], foreground=theme["fg"])
            self.style.configure(
                "CB.Title.TLabel", background=theme["bg"], foreground=theme["select_bg"]
            )
            self.style.configure(
                "CB.Subtitle.TLabel", background=theme["bg"], foreground=theme["fg"]
            )
            self.style.configure("CB.TLabelframe", background=theme["bg"])
            self.style.configure(
                "CB.TLabelframe.Label", background=theme["bg"], foreground=theme["fg"]
            )
            self.style.configure("CB.TNotebook", background=theme["bg"])
            self.style.configure(
                "CB.TNotebook.Tab", background=theme["surface"], foreground=theme["fg"]
            )
            self.style.configure(
                "CB.Treeview",
                background=theme["surface"],
                foreground=theme["fg"],
                fieldbackground=theme["surface"],
            )
            self.style.map(
                "CB.TNotebook.Tab",
                background=[("selected", theme["select_bg"])],
                foreground=[("selected", theme["select_fg"])],
            )
            for button_style in (
                "CB.Primary.TButton",
                "CB.Secondary.TButton",
                "CB.Accessible.TButton",
            ):
                self.style.configure(
                    button_style, background=theme["surface"], foreground=theme["fg"]
                )
                self.style.map(
                    button_style,
                    background=[("active", theme["select_bg"]), ("focus", theme["select_bg"])],
                    foreground=[("active", theme["select_fg"]), ("focus", theme["select_fg"])],
                )

            # Apply to chat display
            if hasattr(self, "chat_display"):
                self.chat_display.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"],
                )

            # Apply to message entry
            if hasattr(self, "message_entry"):
                self.message_entry.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"],
                )

            # Update color references
            self.colors["background"] = theme["bg"]
            self.colors["text_primary"] = theme["fg"]
            self.colors["text_secondary"] = theme["fg"]
            self.colors["surface"] = theme["surface"]

            # Apply scoped chatbot styles without changing the parent GUI's
            # global ttk defaults.
            def style_tree(widget):
                for child in widget.winfo_children():
                    cls = child.winfo_class()
                    try:
                        if cls in ("TFrame",):
                            child.configure(style="CB.TFrame")
                        elif cls == "TLabelframe":
                            child.configure(style="CB.TLabelframe")
                        elif cls == "TNotebook":
                            child.configure(style="CB.TNotebook")
                        elif cls == "Treeview":
                            child.configure(style="CB.Treeview")
                        elif cls == "TButton" and not str(child.cget("style")).startswith("CB."):
                            child.configure(style="CB.Secondary.TButton")
                        elif cls == "TLabel" and not str(child.cget("style")).startswith("CB."):
                            child.configure(style="CB.TLabel")
                        elif cls == "Menu":
                            child.configure(
                                background=theme["surface"],
                                foreground=theme["fg"],
                                activebackground=theme["select_bg"],
                                activeforeground=theme["select_fg"],
                            )
                    except Exception:
                        pass
                    style_tree(child)

            style_tree(self.root)

            if hasattr(self, "_refresh_message_card_theme"):
                self._refresh_message_card_theme()

        return apply_theme
