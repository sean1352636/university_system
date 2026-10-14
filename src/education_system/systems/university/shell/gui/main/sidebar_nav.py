"""Shared sidebar navigation for the student and staff portals.

Brings both portals in line with the admin layout built by
``core/gui_setup_parts/create_navigation_panel.py``: a search box at the top
that filters every action, a ★ Pinned shortcuts block, and collapsible
("drop down") category groups instead of one long flat list of buttons.

The portals keep their existing ``_build_sidebar()`` bodies untouched. This
mixin redefines ``_add_heading`` / ``_add_button`` so that those calls *collect*
a declarative spec rather than packing widgets immediately; ``_render_sidebar``
then draws the spec in the admin style. Every button a portal declares is still
rendered — headings become collapsible groups, and buttons declared before the
first heading stay pinned to the top of the sidebar as direct shortcuts.
"""

import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk

logger = logging.getLogger(__name__)

_SEARCH_PLACEHOLDER = "🔍 Search features..."
_MAX_SEARCH_RESULTS = 25


class SidebarNavMixin:
    """Search + pinned + accordion sidebar, shared by the role portals.

    Host requirements: ``self.root``, ``self._sidebar`` (the scrollable inner
    frame), ``self._sidebar_canvas``, a ``_build_sidebar()`` that declares the
    menu via ``_add_heading``/``_add_button``, and ``_nav_pin_key`` naming the
    portal so each role keeps its own pin file.
    """

    _nav_pin_key = "portal"

    # ------------------------------------------------------------------
    # Declarative collection (called by the portal's _build_sidebar)
    # ------------------------------------------------------------------

    def _add_heading(self, text):
        """Start a new collapsible group."""
        self._nav_groups.append((text, []))

    def _add_button(self, text, command):
        """Add an action to the current group, or to the top shortcuts."""
        if self._nav_groups:
            self._nav_groups[-1][1].append((text, command))
        else:
            self._nav_top_buttons.append((text, command))

    # ------------------------------------------------------------------
    # Pinned shortcuts
    # ------------------------------------------------------------------

    def _pin_file(self):
        return (Path.home() / ".config" / "edu_system"
                / f"university_pinned_{self._nav_pin_key}.json")

    def _load_pins(self):
        try:
            path = self._pin_file()
            if path.exists():
                data = json.loads(path.read_text())
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.debug(f"Could not load pinned: {e}")
        return []

    def _save_pins(self, pins):
        try:
            path = self._pin_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(list(pins)))
        except Exception as e:
            logger.warning(f"Could not save pinned: {e}")

    def _toggle_pin(self, label):
        pins = self._load_pins()
        if label in pins:
            pins.remove(label)
        else:
            pins.append(label)
        self._save_pins(pins)
        self._render_sidebar()

    def _bind_pin_menu(self, widget, label):
        """Right-click a button to pin/unpin it, as in the admin sidebar."""
        def _show_menu(event):
            menu = tk.Menu(widget, tearoff=0)
            pinned = label in self._load_pins()
            menu.add_command(
                label="Unpin from sidebar" if pinned else "Pin to sidebar",
                command=lambda: self._toggle_pin(label),
            )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        widget.bind('<Button-3>', _show_menu)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _configure_nav_styles(self):
        """Group toggles are heavier than leaf buttons, as in the admin nav."""
        try:
            self.style.configure('SidebarGroup.TButton',
                                 font=('Arial', 10, 'bold'), padding=(8, 5))
        except Exception:
            logger.debug("Could not configure sidebar styles", exc_info=True)

    def _refresh_nav_scrollregion(self):
        try:
            self._sidebar.update_idletasks()
            self._sidebar_canvas.configure(
                scrollregion=self._sidebar_canvas.bbox('all'))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _focus_nav_search(self, *_args):
        """Ctrl+K focuses the search box from anywhere in the portal."""
        try:
            entry = getattr(self, 'nav_search_entry', None)
            if entry is None or not entry.winfo_exists():
                return "break"
            entry.focus_set()
            try:
                entry.select_range(0, 'end')
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        except tk.TclError:
            pass
        return "break"

    def _render_sidebar(self):
        """Collect the portal's menu spec, then draw it admin-style."""
        # Collect. Re-run on every render so a pin change picks up any
        # conditional buttons the portal decides at build time.
        self._nav_groups = []
        self._nav_top_buttons = []
        self._build_sidebar()

        self._configure_nav_styles()

        for child in self._sidebar.winfo_children():
            child.destroy()

        # Flat index of every action, for search and for pin lookup. Labels
        # are the identity here (the portals declare no button names).
        all_actions = list(self._nav_top_buttons)
        for _label, buttons in self._nav_groups:
            all_actions.extend(buttons)

        self._render_search(all_actions)
        self._render_pinned(all_actions)
        self._render_top_buttons()
        self._render_groups()

        self._refresh_nav_scrollregion()

    def _render_search(self, all_actions):
        search_var = tk.StringVar()
        entry = ttk.Entry(self._sidebar, textvariable=search_var)
        entry.pack(fill='x', padx=6, pady=(6, 4))
        self.nav_search_entry = entry

        try:
            self.root.bind('<Control-k>', self._focus_nav_search, add="+")
            self.root.bind('<Control-K>', self._focus_nav_search, add="+")
        except Exception:
            logger.debug("Ctrl+K binding failed", exc_info=True)

        def _set_placeholder():
            entry.delete(0, tk.END)
            entry.insert(0, _SEARCH_PLACEHOLDER)
            try:
                entry.config(foreground='gray')
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        def _on_focus_in(_e):
            if search_var.get() == _SEARCH_PLACEHOLDER:
                entry.delete(0, tk.END)
                try:
                    entry.config(foreground='black')
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

        def _on_focus_out(_e):
            if not search_var.get().strip():
                _set_placeholder()

        entry.bind('<FocusIn>', _on_focus_in)
        entry.bind('<FocusOut>', _on_focus_out)
        _set_placeholder()

        # Created unpacked so it takes no layout slot until there are hits.
        results = ttk.Frame(self._sidebar)

        def _on_search_change(*_):
            for widget in results.winfo_children():
                widget.destroy()
            query = search_var.get().strip().lower()
            if not query or query == _SEARCH_PLACEHOLDER.lower():
                try:
                    results.pack_forget()
                except tk.TclError:
                    pass
                self._refresh_nav_scrollregion()
                return

            seen = set()
            matches = []
            for text, command in all_actions:
                if text in seen or query not in text.lower():
                    continue
                matches.append((text, command))
                seen.add(text)

            if not matches:
                try:
                    results.pack_forget()
                except tk.TclError:
                    pass
                self._refresh_nav_scrollregion()
                return

            try:
                results.pack(fill='x', padx=6, pady=(0, 4), after=entry)
            except tk.TclError:
                results.pack(fill='x', padx=6, pady=(0, 4))
            for text, command in matches[:_MAX_SEARCH_RESULTS]:
                btn = ttk.Button(results, text=text, command=command,
                                 style='Sidebar.TButton')
                btn.pack(fill='x', pady=1)
                self._bind_pin_menu(btn, text)
            self._refresh_nav_scrollregion()

        search_var.trace_add('write', _on_search_change)

    def _render_pinned(self, all_actions):
        pins = self._load_pins()
        if not pins:
            return
        by_label = dict(all_actions)
        visible = [(label, by_label[label]) for label in pins if label in by_label]
        if not visible:
            return

        frame = ttk.LabelFrame(self._sidebar, text="★ Pinned", padding=3)
        frame.pack(fill='x', padx=6, pady=(4, 6))
        for label, command in visible:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=1)
            ttk.Button(row, text=label, command=command,
                       style='Sidebar.TButton').pack(side='left', fill='x',
                                                     expand=True)
            ttk.Button(row, text="✕", width=2,
                       command=lambda n=label: self._toggle_pin(n)
                       ).pack(side='right', padx=(2, 0))

    def _render_top_buttons(self):
        """Buttons declared before the first heading — always visible."""
        for text, command in self._nav_top_buttons:
            btn = ttk.Button(self._sidebar, text=text, command=command,
                             style='Sidebar.TButton')
            btn.pack(fill='x', padx=6, pady=1)
            self._bind_pin_menu(btn, text)

    def _render_groups(self):
        """One collapsible container per heading, populated on first expand."""
        for label, buttons in self._nav_groups:
            if not buttons:
                continue

            container = ttk.Frame(self._sidebar)
            container.pack(fill='x', padx=6, pady=2)
            container._expanded = False
            container._sub = None

            toggle = ttk.Button(container, text=f"{label}  ▶",
                                style='SidebarGroup.TButton')
            toggle.pack(fill='x')
            toggle.configure(
                command=self._make_group_toggle(container, toggle, label,
                                                buttons))

    def _make_group_toggle(self, container, toggle, label, buttons):
        def _toggle():
            if container._expanded:
                if container._sub is not None:
                    container._sub.pack_forget()
                toggle.configure(text=f"{label}  ▶")
                container._expanded = False
            else:
                if container._sub is None:
                    sub = ttk.Frame(container)
                    for text, command in buttons:
                        btn = ttk.Button(sub, text=text, command=command,
                                         style='Sidebar.TButton')
                        btn.pack(fill='x', padx=(14, 2), pady=1)
                        self._bind_pin_menu(btn, text)
                    container._sub = sub
                container._sub.pack(fill='x', pady=(2, 4))
                toggle.configure(text=f"{label}  ▼")
                container._expanded = True
            self._refresh_nav_scrollregion()
        return _toggle
