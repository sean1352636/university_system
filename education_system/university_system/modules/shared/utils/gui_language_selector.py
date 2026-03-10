"""
GUI Language Selector - Tkinter-based language selection dialog.

This module provides a graphical language selection dialog that appears
before the main GUI starts. It allows users to choose their preferred
language for the application.

Usage:
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector
    )

    # Show language selector before GUI starts
    selected_language = show_gui_language_selector()
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_language_list,
    SUPPORTED_LANGUAGES,
)


class LanguageSelectorDialog:
    """Tkinter dialog for selecting application language."""

    def __init__(self, parent: Optional[tk.Tk] = None):
        """
        Initialize the language selector dialog.

        Args:
            parent: Optional parent window. If None, creates a new root.
        """
        self.selected_language: Optional[str] = None
        self.parent = parent

        # Create window
        if parent:
            self.root = tk.Toplevel(parent)
            self.root.transient(parent)
        else:
            self.root = tk.Tk()

        self.root.title(_t("language_selector.title"))
        self.root.geometry("450x550")
        self.root.resizable(False, False)

        # Center the window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"450x550+{x}+{y}")

        # Make it modal
        self.root.grab_set()

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Build the UI
        self._build_ui()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        """Build the dialog UI."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title with icon/emoji
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))

        title_label = ttk.Label(
            title_frame,
            text=_t("language_selector.title"),
            font=('Arial', 16, 'bold')
        )
        title_label.pack()

        # Current language info
        current_lang = get_current_language_name()
        current_frame = ttk.Frame(main_frame)
        current_frame.pack(fill=tk.X, pady=(0, 15))

        current_label = ttk.Label(
            current_frame,
            text=_t("language_selector.current", language=current_lang),
            font=('Arial', 10, 'italic')
        )
        current_label.pack()

        # Prompt
        prompt_label = ttk.Label(
            main_frame,
            text=_t("language_selector.prompt"),
            font=('Arial', 11)
        )
        prompt_label.pack(pady=(0, 10))

        # Language listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.lang_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=('Arial', 12),
            height=10,
            selectmode=tk.SINGLE,
            activestyle='dotbox',
            selectbackground='#4a90d9',
            selectforeground='white'
        )
        self.lang_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.lang_listbox.yview)

        # Populate languages
        self.languages = get_available_language_list()
        current_code = get_current_language()
        selected_idx = 0

        for i, (code, name) in enumerate(self.languages):
            display_text = f"  {name}"
            if code == current_code:
                display_text += " *"
                selected_idx = i
            self.lang_listbox.insert(tk.END, display_text)

        # Select current language
        self.lang_listbox.selection_set(selected_idx)
        self.lang_listbox.see(selected_idx)
        self.lang_listbox.activate(selected_idx)

        # Double-click to select
        self.lang_listbox.bind('<Double-Button-1>', lambda e: self._on_ok())

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        # OK button (primary)
        self.ok_btn = ttk.Button(
            btn_frame,
            text=_t("common.ok"),
            command=self._on_ok,
            width=15
        )
        self.ok_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Cancel button
        self.cancel_btn = ttk.Button(
            btn_frame,
            text=_t("common.cancel"),
            command=self._on_cancel,
            width=15
        )
        self.cancel_btn.pack(side=tk.LEFT)

        # Bind Enter key to OK
        self.root.bind('<Return>', lambda e: self._on_ok())
        self.root.bind('<Escape>', lambda e: self._on_cancel())

    def _on_ok(self):
        """Handle OK button click."""
        selection = self.lang_listbox.curselection()
        if selection:
            idx = selection[0]
            code, name = self.languages[idx]
            self.selected_language = code
            set_language(code)
        else:
            # Keep current language if nothing selected
            self.selected_language = get_current_language()

        self.root.destroy()

    def _on_cancel(self):
        """Handle Cancel button click."""
        # Keep current language
        self.selected_language = get_current_language()
        self.root.destroy()

    def show(self) -> str:
        """
        Show the dialog and wait for user selection.

        Returns:
            The selected language code.
        """
        # Focus on the listbox
        self.lang_listbox.focus_set()

        # Wait for window to close
        if self.parent:
            self.root.wait_window()
        else:
            self.root.mainloop()

        return self.selected_language or get_current_language()


def show_gui_language_selector(parent: Optional[tk.Tk] = None) -> str:
    """
    Show the GUI language selector dialog.

    Args:
        parent: Optional parent window.

    Returns:
        The selected language code.
    """
    # Initialize i18n first
    init_i18n()

    # Show dialog
    dialog = LanguageSelectorDialog(parent)
    return dialog.show()


def create_language_menu_button(parent: tk.Widget, callback=None) -> ttk.Button:
    """
    Create a language selection button for use in GUI menus.

    Args:
        parent: Parent widget.
        callback: Optional callback function to call after language change.

    Returns:
        The created button widget.
    """
    def on_click():
        old_lang = get_current_language()
        show_gui_language_selector(parent.winfo_toplevel())
        new_lang = get_current_language()
        if callback and old_lang != new_lang:
            callback(new_lang)

    btn = ttk.Button(
        parent,
        text=f"{_t('gui.change_language')} [{get_current_language_name()}]",
        command=on_click
    )
    return btn


__all__ = [
    "LanguageSelectorDialog",
    "show_gui_language_selector",
    "create_language_menu_button",
]
