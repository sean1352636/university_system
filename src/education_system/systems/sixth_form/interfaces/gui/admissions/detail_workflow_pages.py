"""Applicant detail dialog pages: interview booking, open-event history,
re-applications and communications."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)

from . import _admissions_ui as ui
from . import applicant_actions as act
from .detail_pages import Page

logger = logging.getLogger(__name__)


def _interviews():
    from education_system.systems.sixth_form.domain.admissions import (
        interviews,
    )
    return interviews


# ── Interview booking ──────────────────────────────────────────────

class InterviewPage(Page):
    SLOT_COLS = [("id", "#", 45), ("when", "When", 230),
                 ("panel", "Panel", 200), ("left", "Places left", 80)]
    HIST_COLS = [("id", "#", 45), ("slot", "Slot", 260),
                 ("status", "Status", 90), ("by", "Booked by", 100),
                 ("at", "Booked", 140), ("reason", "Reason", 200)]

    def build(self) -> None:
        iv = _interviews()
        f = self.frame
        a = data.get_applicant(self.aid)
        cur = iv.active_booking(self.aid)
        head = ttk.LabelFrame(f, text="Current interview")
        head.pack(fill="x", padx=10, pady=(8, 4))
        if cur is not None:
            where = cur.slot.label if cur.slot else f"slot #{cur.slot_id}"
            panel = cur.slot.panel_label if cur.slot else ""
            ttk.Label(head, text=f"Booked: {where}"
                      + (f" — panel {panel}" if panel else "")).pack(
                anchor="w", padx=6, pady=2)
        elif a is not None and a.interview_date:
            ttk.Label(head, text=f"Interview date {a.interview_date} "
                      f"({a.interviewer or 'no interviewer'}) — not booked "
                      "into a slot").pack(anchor="w", padx=6, pady=2)
        else:
            ttk.Label(head, text="No interview booked.").pack(
                anchor="w", padx=6, pady=2)
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=10, pady=4)
        ok = act.can_admissions()
        act.gate(ttk.Button(bar, text="Book selected slot",
                            command=self._book), ok and cur is None
                 ).pack(side="left")
        act.gate(ttk.Button(bar, text="Move to selected slot…",
                            command=self._move), ok and cur is not None
                 ).pack(side="left", padx=4)
        act.gate(ttk.Button(bar, text="Cancel booking…",
                            command=lambda: self._cancel(cur)),
                 ok and cur is not None).pack(side="left")
        ttk.Label(f, text="Available slots",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w",
                                                           padx=10)
        h1 = ttk.Frame(f)
        h1.pack(fill="both", expand=True, padx=10, pady=(2, 6))
        self.slots = ui.make_tree(h1, self.SLOT_COLS, height=7)
        for s in iv.list_slots(available_only=True):
            self.slots.insert("", "end", iid=str(s.slot_id), values=(
                s.slot_id, s.label, s.panel_label, s.places_left))
        ttk.Label(f, text="Booking history",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w",
                                                           padx=10)
        h2 = ttk.Frame(f)
        h2.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        hist = ui.make_tree(h2, self.HIST_COLS, height=6)
        for b in iv.booking_history(self.aid):
            hist.insert("", "end", values=(
                b.booking_id, b.slot.label if b.slot else f"#{b.slot_id}",
                b.status, b.booked_by or "", b.booked_at, b.reason or ""))

    def _slot(self) -> int | None:
        iid = ui.require_iid(self.slots, "Interview slot")
        return int(iid) if iid else None

    def _book(self) -> None:
        sid = self._slot()
        if sid is None:
            return
        ok, _ = act.attempt(self.frame, "Book interview",
                            data.schedule_interview, self.aid, slot_id=sid)
        if ok:
            self.notify()

    def _move(self) -> None:
        sid = self._slot()
        if sid is None:
            return
        reason = act.ask_text(self.frame, "Move interview",
                              "Reason (optional):", required=False)
        if reason is None:
            return
        ok, _ = act.attempt(self.frame, "Move interview",
                            data.reschedule_interview, self.aid, slot_id=sid,
                            reason=reason or None)
        if ok:
            self.notify()

    def _cancel(self, cur) -> None:
        if cur is None:
            return
        reason = act.ask_text(self.frame, "Cancel interview",
                              "Reason (optional):", required=False)
        if reason is None:
            return
        ok, _ = act.attempt(self.frame, "Cancel interview",
                            data.cancel_interview, self.aid,
                            reason=reason or None)
        if ok:
            self.notify()


# ── Open events ────────────────────────────────────────────────────

class OpenEventsPage(Page):
    COLS = [("event", "Event", 320), ("who", "Booked as", 170),
            ("party", "Party", 50), ("attended", "Attended", 75),
            ("follow", "Follow-up", 90), ("booked", "Booked", 140)]

    def build(self) -> None:
        from education_system.systems.sixth_form.domain.admissions import (
            open_events,
        )
        f = self.frame
        rows = open_events.bookings_for_applicant(self.aid)
        ttk.Label(f, foreground="#555", text=(
            f"{len(rows)} open-event booking(s) linked to this applicant.")
        ).pack(anchor="w", padx=10, pady=(8, 2))
        holder = ttk.Frame(f)
        holder.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        tree = ui.make_tree(holder, self.COLS, height=10)
        events: dict[int, str] = {}
        for b in rows:
            if b.event_id not in events:
                ev = open_events.get_event(b.event_id)
                events[b.event_id] = ev.label if ev else f"#{b.event_id}"
            tree.insert("", "end", values=(
                events[b.event_id], b.attendee_name, b.party_size,
                {True: "Yes", False: "No"}.get(b.attended, "—"),
                b.follow_up_status, b.booked_at or ""))


# ── Re-applications ────────────────────────────────────────────────

class ReapplicationsPage(Page):
    def __init__(self, frame: tk.Misc, aid: str,
                 notify: Callable[[], None],
                 open_applicant: Callable[[str], None]) -> None:
        super().__init__(frame, aid, notify)
        self.open_applicant = open_applicant

    def build(self) -> None:
        from education_system.systems.sixth_form.domain.admissions import (
            cycles,
        )
        f = self.frame
        a = data.get_applicant(self.aid)
        earlier = cycles.reapplied_from(self.aid)
        later = cycles.reapplications_of(self.aid)
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        can = (act.can_admissions() and a is not None
               and a.status in cycles.REAPPLY_FROM
               and not a.converted_student_id)
        act.gate(ttk.Button(bar, text="Reapply in another cycle…",
                            command=self._reapply), can).pack(side="left")
        act.gate(ttk.Button(bar, text="Open selected",
                            command=self._open), True).pack(side="left",
                                                            padx=4)
        ttk.Label(f, foreground="#555", wraplength=760, justify="left", text=(
            "Reapplying copies details, profile, contacts, choices and GCSEs "
            "into a new application; sensitive information, references and "
            "the ID check must be gathered again. Possible from: "
            + ", ".join(cycles.REAPPLY_FROM) + ".")).pack(fill="x", padx=10)
        holder = ttk.Frame(f)
        holder.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree = ui.make_tree(holder, [
            ("link", "Link", 160), ("id", "Applicant", 100),
            ("name", "Name", 200), ("cycle", "Intake", 80),
            ("status", "Status", 140)], height=8)
        self.tree.bind("<Double-1>", lambda _e: self._open())
        for kind, ids in (("Re-applies from", [earlier] if earlier else []),
                          ("Re-applied as", later)):
            for other in ids:
                o = data.get_applicant(other)
                self.tree.insert("", "end", iid=other, values=(
                    kind, other, o.full_name if o else "(removed)",
                    (o.intake_year or "") if o else "",
                    o.status if o else ""))
        if not earlier and not later:
            ttk.Label(f, text="No linked applications.").pack(anchor="w",
                                                             padx=10)

    def _open(self) -> None:
        iid = ui.require_iid(self.tree, "Re-applications")
        if iid:
            self.open_applicant(iid)

    def _reapply(self) -> None:
        from education_system.systems.sixth_form.domain.admissions import (
            cycles,
        )
        a = data.get_applicant(self.aid)
        if a is None:
            return
        try:
            suggest = cycles.next_cycle_name(a.intake_year
                                             or data.default_intake_year())
        except Exception:  # noqa: BLE001 — just no suggestion
            suggest = ""
        to = act.ask_text(self.frame, "Reapply",
                          "New application in which cycle (YYYY/YY)?",
                          initial=suggest)
        if not to:
            return
        note = act.ask_text(self.frame, "Reapply", "Note (optional):",
                            required=False)
        if note is None:
            return
        ok, new = act.attempt(self.frame, "Reapply", cycles.reapply,
                              self.aid, to, note=note or None)
        if not ok:
            return
        self.notify()
        if messagebox.askyesno("Reapply", f"New application {new.applicant_id}"
                               f" created for {to}. Open it?",
                               parent=self.frame.winfo_toplevel()):
            self.open_applicant(new.applicant_id)


# ── Communications ─────────────────────────────────────────────────

class CommunicationsPage(Page):
    COLS = [("at", "When", 140), ("kind", "Kind", 120),
            ("role", "To", 80), ("addr", "Address", 200),
            ("subject", "Subject", 240), ("state", "Delivery", 230)]

    def __init__(self, frame: tk.Misc, aid: str,
                 notify: Callable[[], None],
                 compose: Callable[[], None]) -> None:
        super().__init__(frame, aid, notify)
        self.compose = compose

    def build(self) -> None:
        from education_system.systems.sixth_form.domain.admissions import (
            admissions_comms,
        )
        f = self.frame
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        act.gate(ttk.Button(bar, text="New e-mail…", command=self.compose),
                 act.can_admissions()).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        rows = admissions_comms.communications_log(self.aid)
        ttk.Label(f, foreground="#555", text=(
            f"{len(rows)} admissions e-mail(s). Delivery shows the outbox "
            "state: a message held by the delivery mode has not been sent.")
        ).pack(anchor="w", padx=10)
        holder = ttk.Frame(f)
        holder.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        tree = ui.make_tree(holder, self.COLS, height=14)
        for r in rows:
            tree.insert("", "end", values=(
                r.get("created_at") or "", r.get("kind") or "",
                r.get("recipient_role") or "",
                r.get("to_address") or "", r.get("subject") or "",
                r.get("label") or ""))
