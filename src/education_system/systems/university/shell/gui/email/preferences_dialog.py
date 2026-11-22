"""E-mail preferences: which kinds of e-mail the signed-in person gets.

Rows are the e-mail bus's notification events, the categories bulk mail
has been sent under, and ``all_bulk`` (every mailing list). Turning one off
stops bulk and marketing mail in that category and the matching
notification; transactional mail (password resets, decisions, receipts)
always arrives. Stored by ``email_outbox.set_preference``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.mail import outbox
from education_system.systems.university.infrastructure.ui import record_screens as rs
from education_system.systems.university.shell.gui.email import hub_access

ALL_BULK = "all_bulk"


def _bus_events() -> list[str]:
    """``email_bus._TRACKED_EVENTS``, read from the source: importing the bus
    registers its subscribers, which a preferences dialog must not do."""
    import ast
    import importlib.util
    try:
        spec = importlib.util.find_spec(
            "education_system.systems.university.services.bus.email_bus")
        tree = ast.parse(open(spec.origin, encoding="utf-8").read())
    except Exception:
        return []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", "") == "_TRACKED_EVENTS"):
            return [str(v) for v in ast.literal_eval(node.value)]
    return []


def categories(conn) -> list[str]:
    """Every category a person can turn off, ``all_bulk`` first."""
    outbox.ensure(conn)
    used = [r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM email_bulk_sends ORDER BY category")]
    rest = sorted((set(_bus_events()) | set(used)) - {ALL_BULK})
    return [ALL_BULK, *rest]


def _load(conn, username):
    return categories(conn), outbox.preferences(conn, username)


def _save(conn, username, choices):
    current = outbox.preferences(conn, username)
    for category, enabled in choices.items():
        if current.get(category, True) != enabled:
            outbox.set_preference(conn, username, category, enabled)


class EmailPreferencesDialog:
    def __init__(self, parent, auth):
        self.username, _role = hub_access.user_of(auth)
        self.window = None
        if not self.username:
            rs.info(parent, "Sign in to change your e-mail preferences.")
            return
        loaded = rs.call(parent, _load, self.username)
        if loaded is None:
            return
        names, prefs = loaded
        self.window = tk.Toplevel(parent)
        self.window.title("E-mail preferences")
        self.window.geometry(f"520x{min(640, self.window.winfo_screenheight() - 120)}")
        self.window.transient(parent)
        bar = ttk.Frame(self.window, padding=(10, 6))
        bar.pack(side="bottom", fill="x")                  # packed first: always visible
        ttk.Button(bar, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(bar, text="Close", command=self.window.destroy).pack(side="right", padx=4)
        ttk.Label(self.window, padding=10, wraplength=480, justify="left",
                  text="Untick what you don't want by e-mail. Messages you must receive "
                       "(password resets, decisions, receipts) are always sent.").pack(
            side="top", anchor="w")
        canvas = tk.Canvas(self.window, highlightthickness=0)
        scroll = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=(10, 0))
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.vars = {}
        for name in names:
            var = tk.BooleanVar(value=prefs.get(name, True))
            label = ("All mailing lists and announcements" if name == ALL_BULK
                     else name.replace(".", " › ").replace("_", " "))
            ttk.Checkbutton(inner, text=label, variable=var).pack(anchor="w", pady=1)
            self.vars[name] = var

    def save(self):
        choices = {name: bool(var.get()) for name, var in self.vars.items()}
        if rs.call(self.window, _save, self.username, choices, write=True) is not None:
            rs.info(self.window, "Your e-mail preferences are saved.")
            self.window.destroy()
