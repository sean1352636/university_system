"""Shared table tools for the At-Risk, Eligibility and Deferred tabs.

Those three tabs were each a Treeview, a refresh button and nothing else: you
could see the rows but not search them, sort them, take them out of the
program, or look at one in detail. They also gave no sense of scale — twelve
rows and twelve hundred rows looked the same until you scrolled.

The helpers here are deliberately generic and hold no exam knowledge, so each
tab keeps its own queries and its own meaning; they only supply the table
behaviour all three were missing.
"""
from __future__ import annotations

import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk


def enable_column_sort(tree: ttk.Treeview, numeric: tuple = ()) -> None:
    """Make every column heading sort the rows, alternating direction.

    Columns named in *numeric* sort by value rather than as text, so 10 comes
    after 9 instead of between 1 and 2.
    """
    state: dict[str, bool] = {}

    def sort_by(column: str) -> None:
        descending = state.get(column, False)
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]

        def key(pair):
            raw = (pair[0] or "").strip()
            if column in numeric:
                try:
                    return (0, float(raw.rstrip("%")))
                except ValueError:
                    # Blanks and placeholders sort together, after the numbers.
                    return (1, 0.0)
            return (0, raw.lower())

        rows.sort(key=key, reverse=descending)
        for index, (_value, item) in enumerate(rows):
            tree.move(item, "", index)
        state[column] = not descending

    for column in tree["columns"]:
        tree.heading(column, command=lambda c=column: sort_by(c))


def row_matches(values, needle: str) -> bool:
    """True when any cell contains *needle* (case-insensitive)."""
    needle = (needle or "").strip().lower()
    if not needle:
        return True
    return any(needle in str(value).lower() for value in values)


def export_tree_to_csv(tree: ttk.Treeview, parent, default_stem: str,
                       headings: dict | None = None) -> None:
    """Write what is currently displayed to a CSV file.

    Exports the *visible* rows, so a filtered view exports the filtered set —
    the alternative (always exporting everything) makes the filter feel
    ignored.
    """
    items = tree.get_children("")
    if not items:
        messagebox.showinfo("Export", "There is nothing to export.",
                            parent=parent)
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".csv",
        initialfile=f"{default_stem}_{stamp}.csv",
        filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
    if not path:
        return

    columns = list(tree["columns"])
    header = [(headings or {}).get(c, c) for c in columns]
    try:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            for item in items:
                writer.writerow([tree.set(item, c) for c in columns])
    except OSError as exc:
        messagebox.showerror("Export", f"Could not write the file: {exc}",
                             parent=parent)
        return
    messagebox.showinfo("Export", f"{len(items)} row(s) written to:\n{path}",
                        parent=parent)


def show_row_details(parent, title: str, headings: dict, columns, values) -> None:
    """A read-only field-per-line view of one row.

    Table cells truncate; a reason or a student name is often the thing you
    actually need to read in full.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("560x420")
    try:
        dialog.transient(parent)
    except tk.TclError:
        pass

    frame = ttk.Frame(dialog, padding=15)
    frame.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(frame, wrap=tk.WORD, height=18)
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)

    for column, value in zip(columns, values):
        text.insert(tk.END, f"{headings.get(column, column)}:\n", "label")
        text.insert(tk.END, f"{value if str(value).strip() else '—'}\n\n")
    text.tag_configure("label", font=("Helvetica", 9, "bold"))
    text.configure(state=tk.DISABLED)

    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 12))


def bind_row_details(tree: ttk.Treeview, parent, title: str,
                     headings: dict) -> None:
    """Double-click a row to open :func:`show_row_details` for it."""
    def _open(_event=None):
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        show_row_details(parent, title, headings, list(tree["columns"]), values)

    tree.bind("<Double-1>", _open)


def show_text_dialog(parent, title: str, body: str) -> None:
    """A scrollable, monospaced, read-only text window.

    For pre-formatted output — column-aligned histories and the like — where
    a Treeview would fight the formatting.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("720x460")
    try:
        dialog.transient(parent)
    except tk.TclError:
        pass

    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(frame, wrap=tk.NONE, font=("Courier", 9))
    y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    x_scroll = ttk.Scrollbar(dialog, orient=tk.HORIZONTAL, command=text.xview)
    text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    x_scroll.pack(fill=tk.X)

    text.insert("1.0", body)
    text.configure(state=tk.DISABLED)

    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 10))


__all__ = ["enable_column_sort", "row_matches", "export_tree_to_csv",
           "show_row_details", "bind_row_details", "show_text_dialog"]
