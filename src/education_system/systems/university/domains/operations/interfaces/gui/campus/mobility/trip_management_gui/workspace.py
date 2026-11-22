"""Trip Workspace: one trip at a time, with a sub-tab per part of running it.

The workspace is a tab of the main Trip Management window. A picker at the
top chooses the trip; each sub-tab (a :class:`Panel`) loads only when it is
shown, so switching trips stays quick. Sub-tabs are found by their stable
``key`` (never by their translated title).
"""

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, run_async, show_error, trip_label, parse_trip_id, trips_for, title_case,
)

logger = logging.getLogger(__name__)
_K = 'gui.operations.campus.mobility.trip_management_gui.workspace'

# Residual-risk band colours, shared by the risk screens.
BAND_COLOURS = {'low': '#d6f0d6', 'medium': '#fff1bf', 'high': '#f7cccc'}


class Panel(ttk.Frame):
    """One workspace sub-tab. Subclasses set ``key`` / ``title`` and
    implement :meth:`build` (widgets) and :meth:`load` (data for a trip)."""

    key = ''
    title = ''

    def __init__(self, master, workspace):
        super().__init__(master, padding=8)
        self.ws = workspace
        self.auth = workspace.auth
        self.trip_id = None
        self.trip = None
        self.build()

    # -- to implement --------------------------------------------------------
    def build(self):
        raise NotImplementedError

    def load(self, trip_id):
        raise NotImplementedError

    # -- helpers -------------------------------------------------------------
    def show(self, trip_id):
        """Load ``trip_id`` (or clear when ``None``)."""
        self.trip_id = trip_id
        self.trip = None
        if trip_id is None:
            self.clear()
            return
        try:
            self.trip = tm('trips').get_trip(trip_id)
            self.load(trip_id)
        except Exception as exc:
            show_error(self, exc)

    def clear(self):
        """Empty the panel when no trip is chosen (override when needed)."""

    def reload(self):
        if self.trip_id is not None:
            self.show(self.trip_id)

    def changed(self):
        """Something was written: refresh this panel and the rest of the window."""
        self.reload()
        self.ws.changed()

    def need_trip(self):
        if self.trip_id is None:
            from tkinter import messagebox
            messagebox.showwarning(_t(f"{_K}.no_trip", default="No Trip Selected"),
                                   _t(f"{_K}.pick_trip", default="Choose a trip at the top of the workspace first."),
                                   parent=self.winfo_toplevel())
            return False
        return True

    def bar(self, side=tk.TOP):
        frame = ttk.Frame(self)
        frame.pack(side=side, fill=tk.X, pady=(0, 6))
        return frame

    def button(self, parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        b.pack(side=tk.LEFT, padx=(0, 5))
        return b

    def async_call(self, work, done=None, message=None):
        """Run ``work`` off the Tk thread, then refresh; ``message(result)`` → info box."""
        from tkinter import messagebox

        def finished(result):
            if message:
                text = message(result)
                if text:
                    messagebox.showinfo(_t(f"{_K}.done", default="Done"), text,
                                        parent=self.winfo_toplevel())
            if done:
                done(result)
            self.changed()

        run_async(self, work, finished, status=self.ws.status)


class TripWorkspace(ttk.Frame):
    """The workspace tab: trip picker, gate status and the sub-tab notebook."""

    def __init__(self, master, gui, panels):
        super().__init__(master, padding=6)
        self.gui = gui
        self.auth = gui.auth
        self.trip_id = None
        self.trips = []
        self.panels = {}
        # Panels loaded for the current trip since the last change.
        self._fresh = set()

        top = ttk.Frame(self)
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(top, text=_t(f"{_K}.trip", default="Trip:")).pack(side=tk.LEFT)
        self.trip_var = tk.StringVar()
        self.picker = ttk.Combobox(top, textvariable=self.trip_var, state='readonly', width=70)
        self.picker.pack(side=tk.LEFT, padx=5)
        self.picker.bind('<<ComboboxSelected>>', lambda _e: self.select_trip(parse_trip_id(self.trip_var.get())))
        self.archived_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=_t(f"{_K}.show_archived", default="Include archived"),
                        variable=self.archived_var, command=self.refresh_trips).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t("common.refresh", default="Refresh"), command=self.refresh_all).pack(side=tk.LEFT, padx=5)

        self.gate_var = tk.StringVar()
        self.gate_label = ttk.Label(self, textvariable=self.gate_var, foreground='#7a4b00',
                                    wraplength=1200, justify=tk.LEFT)
        self.gate_label.pack(fill=tk.X, pady=(0, 4))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        for cls in panels:
            panel = cls(self.notebook, self)
            self.notebook.add(panel, text=cls.title)
            self.panels[cls.key] = panel
        self.notebook.bind('<<NotebookTabChanged>>', lambda _e: self._load_current())
        self.refresh_trips()

    # -- trips ---------------------------------------------------------------
    def refresh_trips(self):
        try:
            self.trips = trips_for(self.auth, 'view', include_archived=self.archived_var.get())
        except Exception as exc:
            show_error(self, exc)
            self.trips = []
        values = [trip_label(t) for t in self.trips]
        self.picker['values'] = values
        current = next((v for v in values if parse_trip_id(v) == self.trip_id), None)
        if current:
            self.trip_var.set(current)
        elif self.trip_id is not None:
            self.trip_var.set('')
            self.select_trip(None)

    def select_trip(self, trip_id):
        self.trip_id = trip_id
        match = next((trip_label(t) for t in self.trips if t['id'] == trip_id), None)
        if match:
            self.trip_var.set(match)
        self._fresh.clear()
        self._load_current(force=True)
        self.update_gate()

    def current_panel(self):
        try:
            widget = self.nametowidget(self.notebook.select())
        except (KeyError, tk.TclError):
            return None
        return widget if isinstance(widget, Panel) else None

    def _load_current(self, force=False):
        panel = self.current_panel()
        if panel is None:
            return
        if force or panel.key not in self._fresh or panel.trip_id != self.trip_id:
            panel.show(self.trip_id)
            self._fresh.add(panel.key)

    def select(self, key, trip_id=None):
        """Show sub-tab ``key`` (optionally for ``trip_id``)."""
        if trip_id is not None and trip_id != self.trip_id:
            if not any(t['id'] == trip_id for t in self.trips):
                self.archived_var.set(True)
                self.refresh_trips()
            self.trip_id = trip_id
            self.select_trip(trip_id)
        panel = self.panels.get(key)
        if panel is not None:
            self.notebook.select(panel)
            self._load_current()

    # -- status --------------------------------------------------------------
    def status(self, text):
        try:
            self.gui.update_status(text)
        except Exception:
            logger.debug("status bar update failed", exc_info=True)

    def update_gate(self):
        """Show what still stands between the trip and opening for registration."""
        trip_id = self.trip_id
        if trip_id is None:
            self.gate_var.set('')
            return
        trip = next((t for t in self.trips if t['id'] == trip_id), None)
        status = (trip or {}).get('status')
        if status in ('open', 'in_progress', 'completed', 'cancelled', 'archived'):
            text = tf(f"{_K}.status_only", "{name}: {status}.", name=(trip or {}).get('trip_name', ''),
                      status=title_case(status))
            self.gate_var.set(text)
            self.status(text)
            return

        def done(problems):
            if self.trip_id != trip_id:
                return
            name = (trip or {}).get('trip_name', '')
            if problems:
                text = tf(f"{_K}.gate_problems", "{name} ({status}) — before it can open: {problems}",
                          name=name, status=title_case(status), problems="; ".join(problems))
            else:
                text = tf(f"{_K}.gate_clear", "{name} ({status}) — ready to open for registration.",
                          name=name, status=title_case(status))
            self.gate_var.set(text)
            self.status(text)

        run_async(self, lambda: tm('approvals').gate_problems(trip_id, 'open'), done,
                  lambda exc: logger.warning("gate check failed: %s", exc))

    # -- refresh -------------------------------------------------------------
    def refresh_all(self):
        self.refresh_trips()
        self._load_current(force=True)
        self.update_gate()

    def changed(self):
        """A panel wrote something: refresh the window's lists and the gate."""
        current = self.current_panel()
        self._fresh = {current.key} if current is not None else set()
        try:
            self.gui.after_change(source=self)
        except Exception:
            logger.debug("after_change failed", exc_info=True)
        self.refresh_trips()
        self.update_gate()
