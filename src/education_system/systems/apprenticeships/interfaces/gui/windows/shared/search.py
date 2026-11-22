"""Search everything you can see — people, employers, reviews, evidence.

Results come through the same scoped reads as each screen, so a search
never shows more than the screens would. Double-click a result to open
the screen it belongs to.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.workspace import search_service

logger = logging.getLogger(__name__)

COLUMNS = (
    ("kind", "Kind", 130),
    ("title", "Match", 320),
    ("details", "Details", 520),
)


def render(gui: Any, query: str = "") -> None:
    frame = gui.clear()
    widgets.heading(
        frame, "Search",
        subtitle="Apprentices, employers, programmes, reviews, evidence and messages you "
                 "can see.",
    )
    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(0, 8))
    text = tk.StringVar(value=query)
    entry = ttk.Entry(bar, textvariable=text, width=50)
    entry.pack(side="left")
    entry.focus_set()
    entry.bind("<Return>", lambda _event: render(gui, text.get()))
    ttk.Button(bar, text="Search", command=lambda: render(gui, text.get())).pack(
        side="left", padx=6
    )

    if not query.strip():
        widgets.empty_state(frame, "Type a name, reference or phrase, then press Enter.")
        return
    ok, results = widgets.guard(lambda: search_service.search(gui.actor, query))
    if not ok:
        return
    if not results:
        widgets.empty_state(frame, f"Nothing you can see matches “{query.strip()}”.")
        return

    by_index = dict(enumerate(results))

    def open_result(ident: Any) -> None:
        result = by_index.get(int(ident))
        if result is not None and result.opens:
            gui.show(*result.opens)

    table = widgets.DataTable(frame, COLUMNS, on_activate=open_result)
    table.populate(
        list(by_index.items()),
        lambda pair: (pair[1].kind, pair[1].title, pair[1].subtitle),
        identity=lambda pair: pair[0],
        noun="result",
    )
