"""Tkinter building blocks shared by every Secondary School screen.

* :func:`tree` - a table with a scrollbar (and row colour tags).
* :func:`problems` - the text for a refused action.
* :func:`text_window` - a read-only text window (summaries, history), with
  an optional Save button.
* :func:`dialog` - a parented pop-up window with a padded frame.
* :func:`form_dialog` - a pop-up form built from a list of fields, which
  shows the domain's problems and stays open until Save succeeds.

Every pop-up is parented with :mod:`platform.delivery.gui.parented_dialogs`
so it opens over the main window.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable, Mapping

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.core.exceptions import errors

#: What a domain call raises when it refuses (every module shares these).
ERRORS = (errors.ValidationError, errors.PermissionDenied, errors.NotFound)

#: The usual row colours: tree.insert(..., tags=("good",)).
STANDARD_TAGS: dict[str, dict[str, str]] = {
    "good": {"background": "#e7f6ea"},
    "bad": {"background": "#fde2e2"},
    "warn": {"background": "#fff4d6"},
    "muted": {"foreground": "#777"},
}


def problems(e: Exception, heading: str | None = None) -> str:
    """Each validation problem as a bullet (under *heading*), else the
    message."""
    probs = getattr(e, "problems", None)
    if not probs:
        return str(e)
    text = "\n".join(f"• {p}" for p in probs)
    return f"{heading}\n{text}" if heading else text


def tree(parent: tk.Misc, columns: Iterable[tuple[str, str, int]], *, height: int = 10,
         select: str = "browse", stretch: Iterable[str] = (),
         tags: Mapping[str, str | Mapping[str, str]] | None = None,
         minwidth: int | None = None, xscroll: bool = False) -> ttk.Treeview:
    """A headings-only table packed into *parent* with a vertical scrollbar.

    *columns* are ``(key, heading, width)``; columns named in *stretch* take
    up spare width. *tags* maps a tag to a background colour, or to tag
    options (``{"foreground": "#999"}``). *minwidth* (e.g. 0) lets columns
    shrink below their width; *xscroll* adds a horizontal scrollbar."""
    columns = list(columns)
    wide = set(stretch)
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    t = ttk.Treeview(frame, columns=[c for c, _h, _w in columns], show="headings",
                     selectmode=select, height=height)
    for col, heading, width in columns:
        t.heading(col, text=heading)
        opts: dict[str, Any] = {"width": width, "anchor": "w", "stretch": col in wide}
        if minwidth is not None:
            opts["minwidth"] = minwidth
        t.column(col, **opts)
    sb = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    if xscroll:
        xs = ttk.Scrollbar(frame, orient="horizontal", command=t.xview)
        t.configure(xscrollcommand=xs.set)
        xs.pack(side="bottom", fill="x")
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    for tag, style in (tags or {}).items():
        if isinstance(style, str):
            t.tag_configure(tag, background=style)
        else:
            t.tag_configure(tag, **style)
    return t


def dialog(owner: tk.Misc, title: str, *, size: str | None = None,
           resizable: bool | None = None, padding: int = 12
           ) -> tuple[tk.Toplevel, ttk.Frame]:
    """A pop-up over *owner*'s window: ``(window, padded frame)``."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    if size:
        win.geometry(size)
    if resizable is not None:
        win.resizable(resizable, resizable)
    frm = ttk.Frame(win, padding=padding)
    frm.pack(fill="both", expand=True)
    return win, frm


def text_window(owner: tk.Misc, title: str, text: str, *, size: str = "720x480",
                save_name: str | None = None,
                on_save: Callable[[str], None] | None = None) -> tk.Toplevel:
    """Read-only text in a pop-up with Close (and Save… when *save_name* is
    given; *on_save(path)* runs after the file is written)."""
    win, frm = dialog(owner, title, size=size, padding=10)
    t = tk.Text(frm, wrap="word", font=("TkFixedFont", 10))
    t.insert("1.0", text)
    t.configure(state="disabled")
    t.pack(fill="both", expand=True)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    if save_name:
        def save() -> None:
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".txt",
                                                initialfile=save_name,
                                                filetypes=[("Text", "*.txt")])
            if path:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                if on_save:
                    on_save(path)
        ttk.Button(bar, text="Save…", command=save).pack(side="right", padx=6)
    return win


def form_dialog(owner: tk.Misc, title: str, fields: list[tuple[str, str, Any, Any]],
                on_save: Callable[[dict[str, Any]], None], note: str | None = None, *,
                errors: tuple[type[BaseException], ...] = ERRORS) -> tk.Toplevel:
    """A pop-up form. Each field is ``(key, label, initial, kind)`` where
    *kind* is:

    * ``None`` - a one-line entry;
    * ``"text"`` - several lines;
    * ``"check"`` - a tick box (gives True / False);
    * a list - a read-only drop-down;
    * ``("edit", list)`` - a drop-down you can also type in;
    * ``("pupils", [(id, label)])`` - a list to tick several from (gives the
      ids; *initial* is the ids already chosen).

    Save calls ``on_save({key: value})``; if that raises one of *errors* the
    problems are shown and the form stays open, otherwise it closes."""
    win, frm = dialog(owner, title)
    if note:
        ttk.Label(frm, text=note, foreground="#555", wraplength=460, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    getters: dict[str, Callable[[], Any]] = {}
    for i, (key, label, initial, kind) in enumerate(fields, start=1):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw", padx=(0, 8), pady=2)
        init = "" if initial is None else str(initial)
        if kind == "text":
            t = tk.Text(frm, width=50, height=3, wrap="word")
            t.insert("1.0", init)
            t.grid(row=i, column=1, sticky="w", pady=2)
            getters[key] = lambda t=t: t.get("1.0", "end").strip()
        elif kind == "check":
            bv = tk.BooleanVar(value=bool(initial))
            ttk.Checkbutton(frm, variable=bv).grid(row=i, column=1, sticky="w")
            getters[key] = bv.get
        elif isinstance(kind, tuple) and kind and kind[0] == "pupils":
            box = tk.Listbox(frm, selectmode="multiple", height=10, width=44,
                             exportselection=False)
            ids = [pid for pid, _l in kind[1]]
            for pid, lab in kind[1]:
                box.insert("end", lab)
                if pid in (initial or ()):
                    box.selection_set(ids.index(pid))
            box.grid(row=i, column=1, sticky="w", pady=2)
            getters[key] = lambda box=box, ids=ids: [ids[j] for j in box.curselection()]
        elif isinstance(kind, tuple) and kind and kind[0] == "edit":
            sv = tk.StringVar(value=init)
            ttk.Combobox(frm, textvariable=sv, values=list(kind[1]), width=40).grid(
                row=i, column=1, sticky="w")
            getters[key] = sv.get
        elif kind:
            sv = tk.StringVar(value=init)
            ttk.Combobox(frm, textvariable=sv, values=list(kind), state="readonly",
                         width=30).grid(row=i, column=1, sticky="w")
            getters[key] = sv.get
        else:
            sv = tk.StringVar(value=init)
            ttk.Entry(frm, textvariable=sv, width=42).grid(row=i, column=1, sticky="w")
            getters[key] = sv.get

    def save() -> None:
        try:
            on_save({k: g() for k, g in getters.items()})
        except errors as e:
            messagebox.showerror(title, problems(e), parent=win)
            return
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(bar, text="Save", command=save).pack(side="right")
    return win
