"""A drop-in replacement for ``ttk.Notebook`` that renders its tabs as a
scrollable vertical sidebar of buttons instead of a horizontal tab strip.

Why: the Course Management GUI has ~20 top-level tabs. A horizontal tab strip
truncates/stacks the labels and is hard to scan. A left sidebar shows each
section name in full, scrolls cleanly, and reads like a navigation menu.

It implements the subset of the Notebook API the GUI actually uses so it can be
swapped in with a one-line change and every existing ``create_*_tab`` method
keeps working unchanged:

    add(child, text=...)        select() / select(index|widget|pathname)
    index("end") / index(w)     tab(index|widget, "text")
    forget(child)               bind("<<NotebookTabChanged>>", cb, add=...)
    pack(...)                   (inherited — it is a real Frame)

Selecting a tab raises its content frame and fires the virtual
``<<NotebookTabChanged>>`` event, matching ttk.Notebook semantics that callers
(e.g. the lazy Course Planning loader) depend on.
"""

import tkinter as tk
from tkinter import ttk


class SidebarNotebook(ttk.Frame):
    """Notebook-compatible widget with a scrollable button sidebar."""

    # Colours for the section buttons (selected vs idle).
    _SEL_BG = '#2c3e50'
    _SEL_FG = '#ffffff'
    _IDLE_BG = '#ecf0f1'
    _IDLE_FG = '#2c3e50'
    _HOVER_BG = '#d6e4f0'

    def __init__(self, master, sidebar_width=230, **kwargs):
        super().__init__(master, **kwargs)

        # Each entry: {"child": Frame, "text": str, "button": tk.Button}
        self._tabs = []
        self._current = None  # currently shown child Frame

        # The notebook lays out three grid columns: sidebar | divider | content.
        self.rowconfigure(0, weight=1)
        self.columnconfigure(2, weight=1)  # content column takes the slack

        # ── Left: scrollable sidebar (fixed width) ────────────────────
        side = ttk.Frame(self, width=sidebar_width)
        side.grid(row=0, column=0, sticky='ns')
        side.grid_propagate(False)

        ttk.Label(side, text="Sections", font=('Arial', 12, 'bold')
                  ).pack(fill=tk.X, padx=10, pady=(8, 6))
        ttk.Separator(side, orient='horizontal').pack(fill=tk.X, padx=6)

        canvas = tk.Canvas(side, width=sidebar_width, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(side, orient=tk.VERTICAL, command=canvas.yview)
        self._btn_frame = ttk.Frame(canvas)
        self._btn_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=self._btn_frame, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=vsb.set)
        # Pack the scrollbar FIRST so it always reserves its width; packing the
        # expanding canvas first would squeeze the scrollbar to zero width and
        # leave the lower buttons unreachable.
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._sidebar_canvas = canvas
        self._bind_mousewheel(canvas)
        self._bind_mousewheel(self._btn_frame)

        # ── Divider between sidebar and content ───────────────────────
        ttk.Separator(self, orient='vertical').grid(row=0, column=1, sticky='ns')

        # ── Right: content column ─────────────────────────────────────
        # Section frames are direct children of this notebook (callers do
        # ttk.Frame(self.notebook)); each is gridded straight into column 2, so
        # the column sizes to them and they fill the available space. (The
        # earlier 'in_' reparenting left the content area unsized — a blank
        # page — so we grid directly into the notebook instead.)

    def _bind_mousewheel(self, widget):
        # Cross-platform mouse-wheel: Windows/macOS deliver <MouseWheel> with
        # event.delta; X11/Linux delivers <Button-4>/<Button-5>.
        def _on_wheel(event):
            if getattr(event, 'num', None) == 4:
                delta = -1
            elif getattr(event, 'num', None) == 5:
                delta = 1
            else:
                delta = int(-1 * (event.delta / 120)) if event.delta else 0
            if delta:
                self._sidebar_canvas.yview_scroll(delta, "units")
        widget.bind("<MouseWheel>", _on_wheel)
        widget.bind("<Button-4>", _on_wheel)
        widget.bind("<Button-5>", _on_wheel)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _index_of_child(self, child):
        for i, t in enumerate(self._tabs):
            if t["child"] is child:
                return i
        return -1

    def _resolve(self, item):
        """Map an index / widget / Tk-pathname to a child Frame (or None)."""
        if item is None:
            return self._current
        if isinstance(item, int):
            if 0 <= item < len(self._tabs):
                return self._tabs[item]["child"]
            return None
        # A widget instance?
        for t in self._tabs:
            if t["child"] is item:
                return t["child"]
        # A Tk pathname string (what ttk.Notebook.select() returns)?
        s = str(item)
        for t in self._tabs:
            if str(t["child"]) == s:
                return t["child"]
        return None

    def _style_button(self, btn, selected):
        if selected:
            btn.configure(bg=self._SEL_BG, fg=self._SEL_FG,
                          activebackground=self._SEL_BG, activeforeground=self._SEL_FG)
        else:
            btn.configure(bg=self._IDLE_BG, fg=self._IDLE_FG,
                          activebackground=self._HOVER_BG, activeforeground=self._IDLE_FG)

    # ------------------------------------------------------------------
    # ttk.Notebook-compatible API
    # ------------------------------------------------------------------
    def add(self, child, text="", **kwargs):
        """Register *child* as a section with sidebar label *text*."""
        btn = tk.Button(
            self._btn_frame, text=text or f"Section {len(self._tabs) + 1}",
            anchor='w', justify=tk.LEFT, relief=tk.FLAT, bd=0,
            padx=12, pady=8, font=('Arial', 10), cursor='hand2',
            wraplength=200,
            command=lambda c=child: self.select(c))
        btn.pack(fill=tk.X, padx=4, pady=1)
        self._style_button(btn, selected=False)
        # Wheel over a button should still scroll the sidebar.
        self._bind_mousewheel(btn)

        # Hover feedback (skipped for the selected button).
        def _enter(_e, b=btn):
            if self._current is None or self._tab_for_button(b) is not self._current:
                b.configure(bg=self._HOVER_BG)

        def _leave(_e, b=btn):
            if self._current is None or self._tab_for_button(b) is not self._current:
                b.configure(bg=self._IDLE_BG)
        btn.bind("<Enter>", _enter)
        btn.bind("<Leave>", _leave)

        # Place the content frame in the notebook's content column, hidden.
        child.grid(row=0, column=2, sticky='nsew')
        child.grid_remove()

        self._tabs.append({"child": child, "text": text, "button": btn})

        # First tab becomes the active one, mirroring ttk.Notebook.
        if self._current is None:
            self.select(child)

    def _tab_for_button(self, btn):
        for t in self._tabs:
            if t["button"] is btn:
                return t["child"]
        return None

    def select(self, item=None):
        """No-arg: return the current child's Tk pathname (like ttk.Notebook).
        With an arg (index / widget / pathname): show that section."""
        if item is None:
            return str(self._current) if self._current is not None else ""

        target = self._resolve(item)
        if target is None or target is self._current:
            return None

        if self._current is not None:
            self._current.grid_remove()
        self._current = target
        target.grid()

        for t in self._tabs:
            self._style_button(t["button"], selected=(t["child"] is target))

        # Mirror ttk.Notebook: notify listeners a tab change happened.
        self.event_generate("<<NotebookTabChanged>>")
        return None

    def index(self, which):
        """``index('end')`` → tab count; ``index(widget)`` → its position."""
        if which == "end":
            return len(self._tabs)
        if isinstance(which, int):
            return which
        idx = self._index_of_child(self._resolve(which))
        return idx if idx >= 0 else 0

    def tab(self, item, option=None):
        """Return tab options; supports ``tab(i, "text")`` like ttk.Notebook."""
        child = self._resolve(item)
        entry = next((t for t in self._tabs if t["child"] is child), None)
        if entry is None:
            return "" if option else {}
        if option in ("text", "-text"):
            return entry["text"]
        if option:
            return ""
        return {"text": entry["text"]}

    def forget(self, item):
        """Remove a section (its button + content)."""
        child = self._resolve(item)
        idx = self._index_of_child(child)
        if idx < 0:
            return
        entry = self._tabs.pop(idx)
        entry["button"].destroy()
        try:
            entry["child"].grid_forget()
        except tk.TclError:
            pass
        if self._current is child:
            self._current = None
            # Fall back to the nearest remaining tab, if any.
            if self._tabs:
                self.select(self._tabs[min(idx, len(self._tabs) - 1)]["child"])

    def tabs(self):
        """Return the child pathnames, like ttk.Notebook.tabs()."""
        return tuple(str(t["child"]) for t in self._tabs)
