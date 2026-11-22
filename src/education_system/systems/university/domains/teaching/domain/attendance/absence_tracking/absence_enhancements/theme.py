"""Tk theme palettes — #36 dark mode, #42 high contrast."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import ttk
from typing import Dict

from .log import logger
from .settings import EnhancementSettings


# ===========================================================================
# ThemeService — #36 dark mode, #42 high contrast
# ===========================================================================

THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#f0f4f8", "fg": "#0f172a", "header_bg": "#1e3a5f",
        "header_fg": "white", "tree_bg": "white", "tree_fg": "#0f172a",
        "sel_bg": "#2563eb", "sel_fg": "white", "accent": "#2563eb",
    },
    "dark": {
        "bg": "#0f172a", "fg": "#e2e8f0", "header_bg": "#020617",
        "header_fg": "#f1f5f9", "tree_bg": "#1e293b", "tree_fg": "#e2e8f0",
        "sel_bg": "#3b82f6", "sel_fg": "white", "accent": "#60a5fa",
    },
    "high_contrast": {
        "bg": "#000000", "fg": "#ffff00", "header_bg": "#000000",
        "header_fg": "#ffff00", "tree_bg": "#000000", "tree_fg": "#ffffff",
        "sel_bg": "#ffff00", "sel_fg": "#000000", "accent": "#00ffff",
    },
}


class ThemeService:
    """Apply / cycle Tk theme palettes; persists choice in absence_settings."""

    ORDER = ["light", "dark", "high_contrast"]

    def __init__(self, settings: EnhancementSettings) -> None:
        self.settings = settings

    def apply(self, root: tk.Misc, theme_name: str = "light") -> None:
        theme = THEMES.get(theme_name, THEMES["light"])
        try:
            root.configure(bg=theme["bg"])
        except tk.TclError:
            logger.debug("root.configure failed", exc_info=True)

        def walk(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Frame", "Labelframe", "Toplevel", "Tk"):
                    widget.configure(bg=theme["bg"])
                elif cls == "Label":
                    widget.configure(bg=theme["bg"], fg=theme["fg"])
                elif cls == "Entry":
                    widget.configure(bg=theme["tree_bg"], fg=theme["tree_fg"],
                                     insertbackground=theme["tree_fg"])
                elif cls == "Text":
                    widget.configure(bg=theme["tree_bg"], fg=theme["tree_fg"],
                                     insertbackground=theme["tree_fg"])
                elif cls == "Canvas":
                    widget.configure(bg=theme["tree_bg"])
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)
        walk(root)

        try:
            style = ttk.Style()
            style.configure("Treeview",
                            background=theme["tree_bg"],
                            foreground=theme["tree_fg"],
                            fieldbackground=theme["tree_bg"])
            style.configure("Treeview.Heading",
                            background=theme["header_bg"],
                            foreground=theme["header_fg"])
            style.map("Treeview",
                      background=[("selected", theme["sel_bg"])],
                      foreground=[("selected", theme["sel_fg"])])
        except tk.TclError:
            logger.debug("ttk.Style failed", exc_info=True)

    def cycle(self, root: tk.Misc) -> str:
        current = self.settings.get("theme", "light") or "light"
        try:
            nxt = self.ORDER[(self.ORDER.index(current) + 1) % len(self.ORDER)]
        except ValueError:
            nxt = "light"
        self.settings.set("theme", nxt)
        self.apply(root, nxt)
        logger.info("theme cycled %s -> %s", current, nxt)
        return nxt


# Module-level legacy aliases.
def apply_theme(root: tk.Misc, theme_name: str = "light") -> None:
    # No conn here — build a stand-alone settings shim that just no-ops.
    class _NoOpSettings:
        def get(self, *_a, **_k): return None
        def set(self, *_a, **_k): pass
    ThemeService(_NoOpSettings()).apply(root, theme_name)  # type: ignore[arg-type]


def cycle_theme(root: tk.Misc, conn: sqlite3.Connection) -> str:
    return ThemeService(EnhancementSettings(conn)).cycle(root)


__all__ = [
    "THEMES",
    "ThemeService",
    "apply_theme",
    "cycle_theme",
]
