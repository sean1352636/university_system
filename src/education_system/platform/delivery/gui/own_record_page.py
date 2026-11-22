"""Page parts shared by the student and parent own-record screens.

These screens render into a school system's content area like its other screens.
Nothing here reads data: every page is handed rows that the system's own-record
read layer has already checked, and an :class:`OwnRecordError` becomes a plain
message with no records.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Sequence

from education_system.platform.cross_system.own_record_access import OwnRecordError

logger = logging.getLogger(__name__)

LOAD_FAILED = ("These records could not be loaded just now. Please try again, or "
               "contact the school office if it keeps happening.")


def start_page(host: Any, title: str) -> ttk.Frame:
    """Clear the content area and title it; returns the area to draw in."""
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text=title, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    host.status_var.set(f"Opened: {title}")
    return root


def show_message(parent: tk.Misc, message: str) -> None:
    ttk.Label(parent, text=message, wraplength=720, justify="left").pack(
        anchor="w", pady=(4, 8))


def show_table(parent: tk.Misc, columns: Sequence[tuple[str, int]],
               rows: Sequence[Sequence[Any]], *, empty: str,
               height: int = 14) -> ttk.Treeview | None:
    """A read-only table of ``(heading, width)`` columns, or *empty* if no rows.

    The row's position is its tree id, so a caller can find what was selected.
    """
    if not rows:
        show_message(parent, empty)
        return None
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, pady=(0, 8))
    ids = [f"c{i}" for i in range(len(columns))]
    tree = ttk.Treeview(frame, columns=ids, show="headings", height=height,
                        selectmode="browse")
    for cid, (heading, width) in zip(ids, columns):
        tree.heading(cid, text=heading)
        tree.column(cid, width=width, anchor="w")
    for i, row in enumerate(rows):
        tree.insert("", "end", iid=str(i),
                    values=["" if v is None else v for v in row])
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="left", fill="y")
    return tree


def guarded_page(host: Any, title: str, draw: Callable[[ttk.Frame], None]) -> None:
    """Draw a page; a refused or unlinked record shows its message and nothing else."""
    root = start_page(host, title)
    body = ttk.Frame(root)
    body.pack(fill="both", expand=True)
    try:
        draw(body)
    except OwnRecordError as refused:
        for widget in body.winfo_children():
            widget.destroy()
        show_message(body, str(refused))
    except Exception:
        logger.exception("Own-record page %s failed", title)
        for widget in body.winfo_children():
            widget.destroy()
        show_message(body, LOAD_FAILED)


def child_picker(parent: tk.Misc, children: Sequence[Any],
                 on_change: Callable[[str], None]) -> str:
    """A parent's choice between their own children; returns the first child's id.

    The list is built only from the read layer's linked children, and the id it
    hands back is checked again by the read layer on every read. With one child
    there is nothing to choose, so it only names them.
    """
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    if len(children) == 1:
        ttk.Label(bar, text=f"Child: {children[0].name}",
                  font=("", 10, "bold")).pack(side="left")
        return children[0].pupil_id
    labels = [f"{c.name} (Year {c.year_group})" for c in children]
    ttk.Label(bar, text="Child:").pack(side="left", padx=(0, 6))
    choice = ttk.Combobox(bar, values=labels, state="readonly", width=40)
    choice.current(0)
    choice.pack(side="left")
    choice.bind("<<ComboboxSelected>>",
                lambda _e: on_change(children[choice.current()].pupil_id))
    return children[0].pupil_id
