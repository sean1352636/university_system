"""DSL admissions queue (needs the ``safeguarding`` capability).

Applicants the safeguarding team should look at: a referee asked for
the DSL to be contacted, or the previous school handed over
safeguarding information. The DSL can read and record that handover
here. It is a page in the Admissions window and also its own window
("Admissions DSL Queue" in the main menu), because the DSL usually has
no admissions access. Every view of the list and of the text is logged
by the domain.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as details,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "DSL Queue"
_BLURB = ("Applicants with a referee asking for the DSL to be contacted, or "
          "safeguarding information from their previous school. Opening the "
          "list and the information is recorded in the sensitive-access log.")


class DslQueuePanel:
    COLS = [("id", "ID", 90), ("name", "Name", 190), ("status", "Status", 130),
            ("school", "Previous school", 200), ("reasons", "Why", 480)]

    def __init__(self, frame: ttk.Frame) -> None:
        self.frame = frame
        self.allowed = pc.can(access.SAFEGUARDING)
        if not self.allowed:
            pc.denied(frame, "the DSL admissions queue (needs safeguarding)")
            return
        bar = ttk.Frame(frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        ttk.Button(bar, text="Safeguarding information…",
                   command=self._open).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(frame)
        self.tree = pc.make_tree(frame, self.COLS, height=18)
        self.tree.bind("<Double-1>", lambda _e: self._open())
        self._rows: dict[str, details.DslItem] = {}
        self._loaded = False

    def refresh(self) -> None:
        """Load the queue. Called when the page is shown (not when the
        Admissions window opens), so the access log records real views."""
        if not self.allowed:
            return
        self._loaded = True
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, TITLE, details.dsl_queue)
        if not ok:
            return
        self._rows = {r.applicant_id: r for r in rows}
        for r in rows:
            self.tree.insert("", "end", iid=r.applicant_id, values=(
                r.applicant_id, r.name, r.status, r.previous_school or "",
                "; ".join(r.reasons)))
        self.status.set(f"{len(rows)} applicant(s) for the DSL to review.")

    def on_show(self) -> None:
        if not self._loaded:
            self.refresh()

    def _open(self) -> None:
        aid = pc.selected(self.tree, TITLE)
        if aid:
            item = self._rows.get(aid)
            SafeguardingDialog(self.frame, aid, item.name if item else "",
                               on_save=self.refresh)


class SafeguardingDialog:
    """Read and record the safeguarding handover for one applicant."""

    def __init__(self, parent: tk.Misc, applicant_id: str, name: str,
                 on_save=None) -> None:
        self.aid = applicant_id
        self.on_save = on_save
        ok, view = pc.run(parent, TITLE, details.get_sensitive, applicant_id)
        if not ok:
            return
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title(f"Safeguarding information — {applicant_id} {name}")
        self.win.geometry("760x520")
        grab_when_viewable(self.win)
        body = ttk.Frame(self.win, padding=10)
        body.pack(fill="both", expand=True)
        held = [details.SENSITIVE_AREAS[a][2] for a, h in view.held.items()
                if h and a != "safeguarding"]
        if held:
            ttk.Label(body, text="Also held (shown to the relevant staff "
                      "only): " + ", ".join(held), foreground=pc.MUTED,
                      wraplength=700, justify="left").pack(anchor="w")
        top = ttk.Frame(body)
        top.pack(fill="x", pady=(6, 4))
        ttk.Label(top, text="Received from:").pack(side="left")
        self.received = ttk.Entry(top, width=50)
        self.received.pack(side="left", padx=4)
        if view.received_from:
            self.received.insert(0, view.received_from)
        foot = ttk.Frame(body)
        foot.pack(side="bottom", fill="x", pady=(6, 0))
        can_edit = pc.can(access.SAFEGUARDING)
        ttk.Button(foot, text="Save", command=self._save,
                   state="normal" if can_edit else "disabled").pack(
            side="left")
        ttk.Button(foot, text="Close", command=self.win.destroy).pack(
            side="left", padx=6)
        ttk.Label(body, text=details.SENSITIVE_AREAS["safeguarding"][2] + ":"
                  ).pack(anchor="w")
        self.text = tk.Text(body, wrap="word", height=16)
        self.text.pack(fill="both", expand=True)
        current = view.visible.get("safeguarding")
        if current:
            self.text.insert("1.0", current)
        self._original = (current or "").strip()

    def _save(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text and self._original and not messagebox.askyesno(
                TITLE, "Clear the safeguarding information for this "
                "applicant?", parent=self.win):
            return
        ok, _ = pc.run(self.win, TITLE, details.set_sensitive, self.aid,
                       "safeguarding", text,
                       received_from=self.received.get().strip())
        if not ok:
            return
        self.win.destroy()
        if self.on_save:
            self.on_save()


class DslQueuePage:
    """The queue as a page of the Admissions window."""

    def __init__(self, nb: Any) -> None:
        # The queue loads the first time the page is shown, not when the
        # Admissions window opens, so the access log records real views.
        self.panel: DslQueuePanel | None = None
        self.frame = pc.new_page(nb, TITLE, "DSL admissions queue", _BLURB,
                                 on_show=self._shown)
        self.panel = DslQueuePanel(self.frame)
        if nb.select() == str(self.frame):
            self.panel.on_show()

    def _shown(self) -> None:
        if self.panel is not None:
            self.panel.on_show()

    def refresh(self) -> None:
        self.panel.refresh()


def open_dsl_queue_window(parent=None) -> None:
    """Stand-alone window for the DSL (main menu: Admissions DSL Queue)."""
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Admissions — DSL queue")
    window_sizing.fit(win, "1400x900", (1200, 800))
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)
    from education_system.systems.sixth_form.interfaces.gui._sidebar import (
        page_header,
    )
    page_header(frame, "DSL admissions queue", _BLURB)
    panel = DslQueuePanel(frame)
    panel.refresh()
