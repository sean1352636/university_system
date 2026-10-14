"""Small ``ttk.Treeview`` helpers for list+detail windows backed by dict rows."""

from __future__ import annotations

from tkinter import ttk
from typing import Any


def make_tree(parent, columns: list[str], width: int = 110) -> ttk.Treeview:
    """A headings-only Treeview with a vertical scrollbar, packed into *parent*."""
    tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
    for column in columns:
        tree.heading(column, text=column.replace("_", " ").title())
        tree.column(column, width=width, stretch=True)
    scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    return tree


def fill_tree(tree: ttk.Treeview, rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Replace the rows. When the first column is a ``*_id`` the row's id is its iid,
    so ``selected_id`` can read it back; otherwise Tk allocates one."""
    tree.delete(*tree.get_children())
    key = columns[0] if columns[0].endswith("_id") else None
    for row in rows:
        values = [row.get(c, "") if row.get(c) is not None else "" for c in columns]
        if key is not None and row.get(key) is not None:
            tree.insert("", "end", iid=str(row[key]), values=values)
        else:
            tree.insert("", "end", values=values)


def selected_id(tree: ttk.Treeview) -> int | None:
    """The iid of the selected row as an int, or ``None``."""
    selection = tree.selection()
    if not selection:
        return None
    try:
        return int(selection[0])
    except ValueError:
        return None


__all__ = ["make_tree", "fill_tree", "selected_id"]
