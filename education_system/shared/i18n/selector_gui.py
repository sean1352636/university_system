"""Tkinter language selector dialog for the shared i18n system.

Provides a modal dialog that lists all 13 supported languages with their
native names and allows the user to choose one.

Usage::

    from education_system.shared.i18n.selector_gui import show_language_selector

    selected = show_language_selector()  # returns e.g. "es"
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

from education_system.shared.i18n.core import (
    get_available_language_list,
    get_current_language,
    get_english_name,
    set_language,
    SUPPORTED_LANGUAGES,
)

_HEADER_BG = "#2c3e50"
_HEADER_FG = "#ffffff"
_SELECT_BG = "#4a90d9"
_SELECT_FG = "#ffffff"
_WIDTH = 400
_HEIGHT = 500


def _build_language_ui(window, languages, current_code, on_ok, on_cancel):
    """Build the language selector UI inside *window*."""
    # --- Dark header ---
    header = tk.Frame(window, bg=_HEADER_BG, height=60)
    header.pack(fill=tk.X)
    header.pack_propagate(False)

    header_font = tkfont.Font(family="Arial", size=16, weight="bold")
    tk.Label(
        header, text="Select Language",
        bg=_HEADER_BG, fg=_HEADER_FG, font=header_font,
    ).pack(expand=True)

    # --- Language list ---
    list_frame = tk.Frame(window)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))

    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(
        list_frame, yscrollcommand=scrollbar.set,
        font=("Arial", 13), selectmode=tk.SINGLE, activestyle="dotbox",
        selectbackground=_SELECT_BG, selectforeground=_SELECT_FG, height=12,
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    select_idx = 0
    for idx, (code, native_name) in enumerate(languages):
        english = get_english_name(code)
        display = f"  {native_name}" if native_name == english else f"  {native_name} ({english})"
        listbox.insert(tk.END, display)
        if code == current_code:
            select_idx = idx

    listbox.selection_set(select_idx)
    listbox.see(select_idx)
    listbox.activate(select_idx)
    listbox.bind("<Double-Button-1>", lambda _e: on_ok())

    # --- Button bar ---
    btn_frame = tk.Frame(window)
    btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
    tk.Button(btn_frame, text="OK", width=12, command=on_ok).pack(side=tk.LEFT, padx=(0, 10))
    tk.Button(btn_frame, text="Cancel", width=12, command=on_cancel).pack(side=tk.LEFT)

    window.bind("<Return>", lambda _e: on_ok())
    window.bind("<Escape>", lambda _e: on_cancel())
    listbox.focus_set()

    return listbox


class LanguageSelectorDialog(tk.Toplevel):
    """Modal dialog for selecting the application language.

    Use this when you already have a tk root / parent window.
    """

    def __init__(self, parent: tk.Misc):
        self._selected: Optional[str] = None
        super().__init__(parent)
        self.title("Select Language")
        self.resizable(False, False)
        self.geometry(f"{_WIDTH}x{_HEIGHT}")
        self.update_idletasks()
        x = (self.winfo_screenwidth() - _WIDTH) // 2
        y = (self.winfo_screenheight() - _HEIGHT) // 2
        self.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        languages = get_available_language_list()
        self._languages = languages
        self._listbox = _build_language_ui(
            self, languages, get_current_language(), self._on_ok, self._on_cancel,
        )

    def _on_ok(self) -> None:
        sel = self._listbox.curselection()
        if sel:
            code, _ = self._languages[sel[0]]
            self._selected = code
            set_language(code)
        else:
            self._selected = get_current_language()
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self._selected = get_current_language()
        self.grab_release()
        self.destroy()

    @property
    def result(self) -> Optional[str]:
        return self._selected

    def show(self) -> str:
        self.wait_window()
        return self._selected or get_current_language()


def show_language_selector(parent: Optional[tk.Misc] = None) -> str:
    """Show the language selector and return the chosen language code.

    If *parent* is provided the dialog opens as a modal child of that window.
    Otherwise a standalone tk.Tk window is used — it is cleanly destroyed
    before returning so that a fresh Tk root can be created afterwards.
    """
    if parent is not None:
        dlg = LanguageSelectorDialog(parent)
        return dlg.show()

    # Standalone mode — use a tk.Tk as the window itself (not a Toplevel)
    # so that destroying it leaves no lingering Tcl interpreter issues.
    selected = get_current_language()
    root = tk.Tk()
    root.title("Select Language")
    root.resizable(False, False)
    root.geometry(f"{_WIDTH}x{_HEIGHT}")
    root.update_idletasks()
    x = (root.winfo_screenwidth() - _WIDTH) // 2
    y = (root.winfo_screenheight() - _HEIGHT) // 2
    root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")

    languages = get_available_language_list()

    def on_ok():
        nonlocal selected
        sel = listbox.curselection()
        if sel:
            code, _ = languages[sel[0]]
            selected = code
            set_language(code)
        root.destroy()

    def on_cancel():
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    listbox = _build_language_ui(root, languages, selected, on_ok, on_cancel)
    root.mainloop()
    return selected


__all__ = [
    "LanguageSelectorDialog",
    "show_language_selector",
]
