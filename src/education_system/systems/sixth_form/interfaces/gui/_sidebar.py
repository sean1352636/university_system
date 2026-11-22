"""A button sidebar that stands in for a ``ttk.Notebook``.

Windows with many tabs read better as a list of sections down the left,
one shown at a time. :class:`SidebarBook` speaks the parts of the
``ttk.Notebook`` API the sixth form windows use (``add``, ``select``,
``index``, ``tabs``, ``tab``, ``hide``, ``forget`` and the
``<<NotebookTabChanged>>`` event), so a window converts by swapping the
class: tab classes keep building ``ttk.Frame(nb)`` and calling
``nb.add(frame, text=...)``.

Sections can be grouped under headings, either per ``add`` call
(``group=``) or for a whole window with ``groups={"Tab text": "Group"}``.
Headings are shown in the order the groups are first listed; a section's
index (what ``select(2)`` means) stays the order it was added in.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

_MUTED = "#7f8c8d"


def _styles(widget: tk.Misc) -> None:
    style = ttk.Style(widget)
    style.configure("SideNav.TButton", anchor="w", padding=(10, 5))
    style.configure("SideNavOn.TButton", anchor="w", padding=(10, 5),
                    font=("TkDefaultFont", 10, "bold"))
    style.map("SideNavOn.TButton",
              background=[("!active", "#dfe8f1"), ("active", "#d0dceb")])
    style.configure("SideNavHead.TLabel", foreground=_MUTED,
                    font=("TkDefaultFont", 9, "bold"))
    style.configure("SidePageTitle.TLabel",
                    font=("TkDefaultFont", 14, "bold"))
    style.configure("SidePageBlurb.TLabel", foreground=_MUTED)


class SidebarBook(ttk.Frame):
    """A ``ttk.Notebook`` look-alike with the tabs as a left sidebar."""

    def __init__(self, master: tk.Misc, *, nav_width: int = 210,
                 groups: dict[str, str] | None = None,
                 title: str | None = None, fit_pages: bool = True,
                 **kw) -> None:
        # Notebook-only options (a notebook's own size, style, padding)
        # mean nothing to a frame; the sections size themselves.
        for opt in ("padding", "style", "width", "height", "takefocus"):
            kw.pop(opt, None)
        super().__init__(master, **kw)
        width = nav_width
        self._fit_pages = fit_pages
        _styles(self)
        self._groups = dict(groups or {})
        self._group_order: list[str] = []
        for g in self._groups.values():
            if g not in self._group_order:
                self._group_order.append(g)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        side = ttk.Frame(self, width=width)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.pack_propagate(False)
        ttk.Separator(self, orient="vertical").grid(row=0, column=0,
                                                    sticky="nse")
        if title:
            ttk.Label(side, text=title, font=("TkDefaultFont", 12, "bold")
                      ).pack(side="top", anchor="w", padx=4, pady=(0, 6))
        self._extras = ttk.Frame(side)
        self._extras.pack(side="bottom", fill="x", pady=(6, 0), padx=(0, 8))

        # The section list scrolls when there are more than fit.
        self._canvas = tk.Canvas(side, highlightthickness=0, bd=0,
                                 width=width - 10)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll = ttk.Scrollbar(side, orient="vertical",
                                     command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._on_scroll)
        self._nav = ttk.Frame(self._canvas)
        self._nav_id = self._canvas.create_window((0, 0), window=self._nav,
                                                  anchor="nw")
        self._nav.bind("<Configure>", self._on_nav_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        for w in (self._canvas, self._nav):
            w.bind("<Enter>", lambda _e: self._bind_wheel(True))
            w.bind("<Leave>", lambda _e: self._bind_wheel(False))
        self._sync_canvas_bg()

        # One record per section, in add order.
        self._pages: list[dict] = []
        self._current: tk.Misc | None = None
        self.after_idle(self._keep_on_screen)

    def _keep_on_screen(self) -> None:
        """Shrink the window to the screen if it was opened larger."""
        try:
            from education_system.platform.delivery.gui import window_sizing
            top = self.winfo_toplevel()
            top.update_idletasks()
            w, h = top.winfo_width(), top.winfo_height()
            cw, ch = window_sizing.clamp(top, w, h)
            if (cw, ch) != (w, h) and w > 1:
                top.geometry(f"{cw}x{ch}")
        except tk.TclError:
            pass

    # ── Scrolling ─────────────────────────────────────────────────

    def _sync_canvas_bg(self) -> None:
        try:
            bg = ttk.Style(self).lookup("TFrame", "background") or None
            if bg:
                self._canvas.configure(bg=bg)
        except tk.TclError:
            pass

    def _on_nav_configure(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self._canvas.itemconfigure(self._nav_id, width=e.width)

    def _on_scroll(self, first, last) -> None:
        self._scroll.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scroll.pack_forget()
        elif not self._scroll.winfo_ismapped():
            self._scroll.pack(side="right", fill="y", before=self._canvas)

    def _bind_wheel(self, on: bool) -> None:
        if on:
            self._canvas.bind_all("<MouseWheel>", self._wheel)
            self._canvas.bind_all("<Button-4>", self._wheel)
            self._canvas.bind_all("<Button-5>", self._wheel)
        else:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self._canvas.unbind_all(seq)

    def _wheel(self, e) -> None:
        if self._scroll.winfo_ismapped():
            step = -1 if (getattr(e, "num", 0) == 4 or e.delta > 0) else 1
            self._canvas.yview_scroll(step, "units")

    # ── Notebook API ──────────────────────────────────────────────

    def add(self, child: tk.Misc, text: str = "", *, group: str | None = None,
            on_show=None, state: str = "normal", **_kw) -> None:
        if any(p["frame"] is child for p in self._pages):
            self.tab(child, text=text or None, state=state)
            return
        group = group or self._groups.get(text) or (
            self._pages[-1]["group"] if self._pages and not self._groups
            else ("More" if self._groups else None))
        if group and group not in self._group_order:
            self._group_order.append(group)
        btn = ttk.Button(self._nav, text=text, style="SideNav.TButton",
                         command=lambda f=child: self.select(f))
        self._pages.append({"frame": child, "text": text, "group": group,
                            "button": btn, "on_show": on_show,
                            "state": state, "fitted": False,
                            "holder": None})
        self._layout_nav()
        if self._current is None and state == "normal":
            self.select(child)

    def insert(self, pos, child: tk.Misc, **kw) -> None:
        self.add(child, **kw)
        page = self._pages.pop()
        index = len(self._pages) if pos == "end" else self.index(pos)
        self._pages.insert(index, page)
        self._layout_nav()

    def _layout_nav(self) -> None:
        for w in self._nav.winfo_children():
            if isinstance(w, ttk.Label):
                w.destroy()
            else:
                w.pack_forget()
        groups = [g for g in self._group_order
                  if any(p["group"] == g for p in self._pages)]
        if any(p["group"] is None for p in self._pages):
            groups = [None] + groups
        first = True
        for g in groups:
            pages = [p for p in self._pages
                     if p["group"] == g and p["state"] != "hidden"]
            if not pages:
                continue
            if g:
                ttk.Label(self._nav, text=g.upper(),
                          style="SideNavHead.TLabel").pack(
                    anchor="w", padx=4, pady=(0 if first else 10, 2))
            for p in pages:
                p["button"].configure(
                    state="disabled" if p["state"] == "disabled" else "normal")
                p["button"].pack(fill="x", pady=1, padx=(0, 8))
            first = False

    def _resolve(self, tab_id) -> dict:
        if isinstance(tab_id, int):
            return self._pages[tab_id]
        if tab_id == "current":
            for p in self._pages:
                if p["frame"] is self._current:
                    return p
            raise tk.TclError("no current tab")
        for p in self._pages:
            if p["frame"] is tab_id or str(p["frame"]) == str(tab_id):
                return p
        raise tk.TclError(f"bad tab id {tab_id!r}")

    def select(self, tab_id=None):
        if tab_id is None:
            return str(self._current) if self._current is not None else ""
        page = self._resolve(tab_id)
        if page["state"] != "normal":
            return None
        changed = page["frame"] is not self._current
        for p in self._pages:
            shown = p["holder"] or p["frame"]
            if p is page:
                shown.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
                p["button"].configure(style="SideNavOn.TButton")
            else:
                shown.grid_remove()
                p["button"].configure(style="SideNav.TButton")
        self._current = page["frame"]
        if page["on_show"] is not None:
            page["on_show"]()
        if self._fit_pages and not page["fitted"]:
            # Sections were laid out for a full-width notebook; the first
            # time each is shown, fit it to the space beside the sidebar.
            page["fitted"] = True
            from education_system.systems.sixth_form.interfaces.gui._ui import (
                fit_when_shown,
            )
            fit_when_shown(page["frame"])
            self.after_idle(lambda p=page: self._scroll_if_tall(p))
        if changed:
            self.event_generate("<<NotebookTabChanged>>")
        return None

    def _scroll_if_tall(self, page: dict) -> None:
        """Give a section taller than the window a vertical scrollbar.

        The section stays a child of this widget (callers hold it and its
        tab id); it is shown as a window item on a canvas, which Tk allows
        for any descendant of the canvas's ancestors.
        """
        frame = page["frame"]
        try:
            if page["holder"] is not None or frame is not self._current:
                return
            frame.update_idletasks()
            avail = self.winfo_height()
            need = frame.winfo_reqheight()
        except tk.TclError:
            return
        if avail <= 1:
            # Not sized yet (the first section is shown while the window
            # is still being built): look again once it has a size.
            def _later(_e=None) -> None:
                if self.winfo_height() > 1:
                    self.unbind("<Configure>", bind_id)
                    self._scroll_if_tall(page)
            bind_id = self.bind("<Configure>", _later, add="+")
            return
        if need <= avail + 2:
            return
        holder = ttk.Frame(self)
        canvas = tk.Canvas(holder, highlightthickness=0, bd=0)
        try:
            canvas.configure(bg=ttk.Style(self).lookup("TFrame", "background"))
        except tk.TclError:
            pass
        bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame.grid_remove()
        item = canvas.create_window(0, 0, window=frame, anchor="nw")
        frame.lift(holder)

        def _resize(e) -> None:
            canvas.itemconfigure(item, width=e.width,
                                 height=max(e.height, frame.winfo_reqheight()))

        def _region(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _wheel(e) -> None:
            # Tables and text areas scroll themselves.
            if e.widget.winfo_class() in ("Treeview", "Listbox", "Text"):
                return
            step = -1 if (getattr(e, "num", 0) == 4 or e.delta > 0) else 1
            canvas.yview_scroll(step, "units")

        def _hover(on: bool) -> None:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                if on:
                    canvas.bind_all(seq, _wheel)
                else:
                    canvas.unbind_all(seq)

        canvas.bind("<Configure>", _resize)
        frame.bind("<Configure>", _region, add="+")
        holder.bind("<Enter>", lambda _e: _hover(True))
        holder.bind("<Leave>", lambda _e: _hover(False))
        page["holder"] = holder
        holder.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

    def index(self, tab_id) -> int:
        if tab_id == "end":
            return len(self._pages)
        return self._pages.index(self._resolve(tab_id))

    def tabs(self) -> tuple[str, ...]:
        return tuple(str(p["frame"]) for p in self._pages)

    def tab(self, tab_id, option: str | None = None, **kw):
        page = self._resolve(tab_id)
        if option is not None:
            return page.get(option, "")
        if not kw:
            return {"text": page["text"], "state": page["state"]}
        if kw.get("text"):
            page["text"] = kw["text"]
            page["button"].configure(text=kw["text"])
        if kw.get("state"):
            page["state"] = kw["state"]
            if page["state"] != "normal" and page["frame"] is self._current:
                (page["holder"] or page["frame"]).grid_remove()
                self._current = None
        self._layout_nav()
        return None

    def hide(self, tab_id) -> None:
        self.tab(tab_id, state="hidden")

    def forget(self, tab_id) -> None:
        page = self._resolve(tab_id)
        page["frame"].grid_remove()
        if page["holder"] is not None:
            page["holder"].destroy()
        page["button"].destroy()
        self._pages.remove(page)
        if page["frame"] is self._current:
            self._current = None
        self._layout_nav()

    # ── Extras ────────────────────────────────────────────────────

    def add_action(self, text: str, command) -> None:
        """A button at the foot of the sidebar that runs *command*."""
        ttk.Button(self._extras, text=text, style="SideNav.TButton",
                   command=command).pack(fill="x", pady=1)


def page_header(page: tk.Misc, title: str, blurb: str = "") -> None:
    """Title and one-line explanation at the top of a sidebar page."""
    _styles(page)
    head = ttk.Frame(page)
    head.pack(fill="x", pady=(2, 8))
    ttk.Label(head, text=title, style="SidePageTitle.TLabel").pack(anchor="w")
    if blurb:
        ttk.Label(head, text=blurb, style="SidePageBlurb.TLabel",
                  wraplength=900, justify="left").pack(anchor="w", pady=(2, 0))


def action_list(parent: tk.Misc, title: str,
                items: "list[tuple[str, str, object]]") -> ttk.LabelFrame:
    """A titled box of buttons, each with a short description beside it."""
    box = ttk.LabelFrame(parent, text=title, padding=8)
    box.pack(fill="x", pady=(0, 8))
    box.columnconfigure(1, weight=1)
    for row, (label, desc, command) in enumerate(items):
        ttk.Button(box, text=label, width=24, command=command).grid(
            row=row, column=0, sticky="w", pady=2)
        ttk.Label(box, text=desc, foreground=_MUTED).grid(
            row=row, column=1, sticky="w", padx=(10, 0))
    return box
