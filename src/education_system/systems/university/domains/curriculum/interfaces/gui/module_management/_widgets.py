"""Small Treeview helpers shared by the Module Management tabs."""

from __future__ import annotations

from tkinter import ttk

_PAD = {"padx": 8, "pady": 4}


def _tree(parent, columns, widths, height=12, selectmode="browse"):
    """A Treeview with a vertical scrollbar, packed to fill *parent*."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, **_PAD)
    tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show="headings",
                        height=height, selectmode=selectmode)
    for (key, title), width in zip(columns, widths):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w", stretch=True)
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def _clear(tree):
    tree.delete(*tree.get_children())


def _code_of(choice: str) -> str:
    """'CS101 - Intro' -> 'CS101'."""
    return (choice or "").split(" - ", 1)[0].strip()
