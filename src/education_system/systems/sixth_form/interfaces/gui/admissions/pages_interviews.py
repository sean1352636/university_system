"""Admissions window pages: interview slots and interview rooms.

* **Interview Slots** — dated slots with a room, a panel and a capacity.
  Creating or changing one refuses a past time, a room already in use
  (including room-booking bookings, lessons and exams for a linked room)
  and a panel member on an overlapping slot; the table flags any clash
  that has crept in since. Bookings per slot and the day sheet for a
  date.
* **Interview Rooms** — the rooms admissions interviews in, optionally
  linked to a room-booking room, and a one-off import of the room names
  kept in the old CLI side file.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    interviews,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

SLOTS = "Interview Slots"
ROOMS = "Interview Rooms"
#: The side file the CLI kept interview rooms in (applicant id → room name).
OLD_ROOMS_FILE = "admissions_interview_rooms.json"
_NO_ROOM = "(no room)"


def old_rooms_path() -> Path:
    return Path(adm.DB_PATH).parent / OLD_ROOMS_FILE


def old_room_names() -> list[str]:
    """Room names in the old side file (empty when there is none)."""
    p = old_rooms_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        values = list(data.values())
    elif isinstance(data, list):
        values = data
    else:
        return []
    return sorted({str(v).strip() for v in values
                   if isinstance(v, str) and v.strip()})


def _room_choices() -> dict[str, int | None]:
    out: dict[str, int | None] = {_NO_ROOM: None}
    for r in interviews.list_rooms():
        cap = f", holds {r.capacity}" if r.capacity else ""
        out[f"{r.name} (#{r.room_id}{cap})"] = r.room_id
    return out


# ── Slots ─────────────────────────────────────────────────────────

class SlotsPage:
    COLS = [("id", "#", 45), ("date", "Date", 90), ("start", "Start", 55),
            ("end", "End", 55), ("room", "Room", 140), ("panel", "Panel", 200),
            ("cap", "Capacity", 65), ("booked", "Booked", 60),
            ("left", "Left", 45), ("status", "Status", 75),
            ("clash", "Clash", 260), ("notes", "Notes", 180)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, SLOTS, "Interview slots",
            "Each slot has a date, a time, a room, a panel and how many "
            "applicants it takes. Book applicants into slots from the "
            "Interviews page. Cancelling a slot cancels its bookings with the "
            "reason.")
        self.editable = pc.can(access.ADMISSIONS)
        st = "normal" if self.editable else "disabled"
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 2))
        for text, cmd in (("New slot…", self._new), ("Edit…", self._edit),
                          ("Cancel slot…", self._cancel)):
            ttk.Button(bar, text=text, command=cmd, state=st).pack(
                side="left", padx=(0, 4))
        ttk.Button(bar, text="Bookings…", command=self._bookings).pack(
            side="left", padx=(8, 4))
        ttk.Button(bar, text="Day sheet…", command=self._day_sheet).pack(
            side="left", padx=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        bar2 = ttk.Frame(self.frame)
        bar2.pack(side="top", fill="x", pady=(0, 4))
        ttk.Label(bar2, text="From:").pack(side="left")
        self.d_from = ttk.Entry(bar2, width=11)
        self.d_from.insert(0, pc.today())
        self.d_from.pack(side="left", padx=(2, 8))
        ttk.Label(bar2, text="To:").pack(side="left")
        self.d_to = ttk.Entry(bar2, width=11)
        self.d_to.pack(side="left", padx=(2, 8))
        for e in (self.d_from, self.d_to):
            e.bind("<Return>", lambda _e: self.refresh())
        self.cancelled = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show cancelled", variable=self.cancelled,
                        command=self.refresh).pack(side="left", padx=6)
        self.free = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Places left only", variable=self.free,
                        command=self.refresh).pack(side="left", padx=6)
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=16)
        self.tree.tag_configure("clash", background="#ffd6d6")
        self.tree.tag_configure("full", background="#eeeeee")
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._bookings())
        self._rows: dict[str, interviews.Slot] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, SLOTS, interviews.list_slots,
                           date_from=self.d_from.get().strip() or None,
                           date_to=self.d_to.get().strip() or None,
                           include_cancelled=self.cancelled.get(),
                           available_only=self.free.get())
        if not ok:
            return
        self._rows = {str(s.slot_id): s for s in rows}
        clashes = 0
        for s in rows:
            clash = ""
            if s.status == "Open":
                try:
                    rep = interviews.find_clashes(
                        slot_date=s.slot_date, start_time=s.start_time,
                        end_time=s.end_time, room_id=s.room_id, panel=s.panel,
                        exclude_slot_id=s.slot_id)
                    clash = rep.message() if rep else ""
                except Exception as e:  # noqa: BLE001 — shown in the row
                    clash = f"(clash check failed: {e})"
            tag = ("clash" if clash else "Cancelled" if s.status != "Open"
                   else "full" if s.is_full else "")
            clashes += bool(clash)
            notes = s.cancel_reason if s.status != "Open" else s.notes
            self.tree.insert("", "end", iid=str(s.slot_id), tags=(tag,),
                             values=(s.slot_id, s.slot_date, s.start_time,
                                     s.end_time, s.room_name or "",
                                     s.panel_label, s.capacity, s.booked,
                                     s.places_left, s.status, clash,
                                     (notes or "").replace("\n", " ")))
        places = sum(s.places_left for s in rows if s.status == "Open")
        self.status.set(f"{len(rows)} slot(s) · {places} place(s) left"
                        + (f" · {clashes} with a clash" if clashes else ""))

    def _slot(self) -> interviews.Slot | None:
        iid = pc.selected(self.tree, SLOTS)
        return self._rows.get(iid) if iid else None

    def _form(self, title: str, initial: dict[str, Any], submit) -> bool:
        ok, rooms = pc.run(self.frame, SLOTS, _room_choices)
        if not ok:
            return False

        def go(v: dict[str, Any]) -> None:
            data = dict(v)
            data["room_id"] = rooms.get(v["room"])
            data.pop("room")
            submit(data)

        return pc.ask_form(self.frame, title, [
            ("slot_date", "Date (YYYY-MM-DD)", "entry", None),
            ("start_time", "Start (HH:MM)", "entry", None),
            ("end_time", "End (HH:MM)", "entry", None),
            ("room", "Room", "readonly", list(rooms)),
            ("panel", "Panel (comma-separated)", "entry", None),
            ("capacity", "Applicants in the slot", "entry", None),
            ("notes", "Notes", "text", None)], initial, on_submit=go,
            intro="A clash with another slot's room or panel, or a "
                  "room-booking booking, lesson or exam, is refused."
        ) is not None

    def _new(self) -> None:
        last = self._rows.get(pc.selected(self.tree, SLOTS, quiet=True) or "")
        initial = {"slot_date": last.slot_date if last else pc.today(),
                   "start_time": last.end_time if last else "09:00",
                   "end_time": "", "capacity": 1, "room": _NO_ROOM,
                   "panel": last.panel_label if last else
                   pc.username()}
        if last and last.room_id:
            for label, rid in _room_choices().items():
                if rid == last.room_id:
                    initial["room"] = label
        if self._form("New interview slot", initial, interviews.create_slot):
            self.refresh()

    def _edit(self) -> None:
        s = self._slot()
        if s is None:
            return
        room = _NO_ROOM
        for label, rid in _room_choices().items():
            if rid is not None and rid == s.room_id:
                room = label
        initial = {"slot_date": s.slot_date, "start_time": s.start_time,
                   "end_time": s.end_time, "room": room,
                   "panel": s.panel_label, "capacity": s.capacity,
                   "notes": s.notes}
        if self._form(f"Edit slot #{s.slot_id} ({s.booked} booked)", initial,
                      lambda d: interviews.update_slot(s.slot_id, d)):
            self.refresh()

    def _cancel(self) -> None:
        s = self._slot()
        if s is None or s.status != "Open":
            return
        reason = pc.ask_text(
            self.frame, f"Cancel slot #{s.slot_id}",
            f"Reason ({s.booked} booked applicant(s) will have their interview "
            "cancelled)", required=True)
        if reason is None:
            return
        ok, affected = pc.run(self.frame, SLOTS, interviews.cancel_slot,
                              s.slot_id, reason=reason)
        if ok:
            if affected:
                messagebox.showinfo(
                    SLOTS, "Interview cancelled for: " + ", ".join(affected)
                    + "\nRebook them from the Interviews page.",
                    parent=self.frame.winfo_toplevel())
            self.refresh()

    def _bookings(self) -> None:
        s = self._slot()
        if s is None:
            return
        ok, rows = pc.run(self.frame, SLOTS, interviews.slot_bookings,
                          s.slot_id, active_only=False)
        if not ok:
            return
        names = _names()
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title(f"Bookings — slot #{s.slot_id} {s.label}")
        win.geometry("1000x480")
        ttk.Label(win, text=f"{s.label} · panel: {s.panel_label} · "
                  f"{s.booked} of {s.capacity} booked", padding=8).pack(
            side="top", anchor="w")
        foot = ttk.Frame(win, padding=8)
        foot.pack(side="bottom", fill="x")
        ttk.Button(foot, text="Close", command=win.destroy).pack(side="left")
        holder = ttk.Frame(win, padding=(8, 0))
        holder.pack(fill="both", expand=True)
        tree = pc.make_tree(holder, [
            ("id", "#", 45), ("aid", "Applicant", 85), ("name", "Name", 170),
            ("status", "Status", 85), ("by", "Booked by", 100),
            ("at", "Booked", 140), ("ended", "Ended", 140),
            ("reason", "Reason", 240)], height=12)
        for b in rows:
            tree.insert("", "end", iid=str(b.booking_id), values=(
                b.booking_id, b.applicant_id, names.get(b.applicant_id, ""),
                b.status, b.booked_by or "", b.booked_at,
                f"{b.ended_at or ''} {b.ended_by or ''}".strip(),
                b.reason or ""))

    def _day_sheet(self) -> None:
        s = self._rows.get(pc.selected(self.tree, SLOTS, quiet=True) or "")
        day = pc.ask_form(self.frame, "Day sheet",
                          [("date", "Date (YYYY-MM-DD)", "entry", None)],
                          {"date": s.slot_date if s else pc.today()})
        if not day:
            return
        ok, sheet = pc.run(self.frame, "Day sheet", interviews.day_sheet,
                           day["date"])
        if not ok:
            return
        names = _names()
        lines = [f"Interview day sheet — {day['date']}", ""]
        if not sheet:
            lines.append("No open interview slots on this day.")
        for slot, bookings in sheet:
            lines.append(f"{slot.start_time}–{slot.end_time}  "
                         f"{slot.room_name or '(no room)'}  ·  panel: "
                         f"{slot.panel_label}  ·  {len(bookings)}/"
                         f"{slot.capacity}")
            for b in bookings:
                lines.append(f"    {b.applicant_id}  "
                             f"{names.get(b.applicant_id, '')}")
            if not bookings:
                lines.append("    (no one booked)")
            lines.append("")
        pc.show_text(self.frame, f"Day sheet {day['date']}", "\n".join(lines),
                     save_name=f"interview_day_sheet_{day['date']}.txt")


def _names() -> dict[str, str]:
    try:
        return {a.applicant_id: a.full_name for a in adm.list_applicants()}
    except Exception:  # noqa: BLE001 — ids are still shown
        return {}


# ── Rooms ─────────────────────────────────────────────────────────

class RoomsPage:
    COLS = [("name", "Room", 220), ("cap", "Holds", 60),
            ("linked", "Room-booking room", 220), ("active", "Active", 60),
            ("notes", "Notes", 360)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, ROOMS, "Interview rooms",
            "A room linked to a room-booking room also counts that room's "
            "bookings, lessons and exams as clashes. A room added with the "
            "same name as a room-booking room is linked automatically. "
            "Removing a room keeps it for history; it is refused while "
            "upcoming slots use it.")
        self.editable = pc.can(access.ADMISSIONS)
        st = "normal" if self.editable else "disabled"
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 2))
        ttk.Button(bar, text="Add room…", command=self._add,
                   state=st).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Remove", command=self._remove,
                   state=st).pack(side="left", padx=(0, 4))
        self.inactive = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show removed", variable=self.inactive,
                        command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.old_names = old_room_names()
        if self.old_names:
            bar2 = ttk.Frame(self.frame)
            bar2.pack(side="top", fill="x", pady=(0, 4))
            ttk.Button(bar2, text="Import old room list", command=self._import,
                       state=st).pack(side="left")
            ttk.Label(bar2, text=f"{len(self.old_names)} room name(s) in the "
                      f"old CLI file {old_rooms_path().name}",
                      foreground=pc.MUTED).pack(side="left", padx=8)
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=16)
        self.tree.tag_configure("removed", foreground="#888")
        self._rows: dict[str, interviews.Room] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, ROOMS, interviews.list_rooms,
                           active_only=not self.inactive.get())
        if not ok:
            return
        linked = dict(interviews.room_booking_rooms())
        self._rows = {str(r.room_id): r for r in rows}
        for r in rows:
            link = ""
            if r.resource_id:
                link = linked.get(r.resource_id, f"#{r.resource_id} (inactive)")
            self.tree.insert("", "end", iid=str(r.room_id),
                             tags=() if r.active else ("removed",), values=(
                                 r.name, pc.fmt(r.capacity), link,
                                 "Yes" if r.active else "No", r.notes or ""))
        if self.old_names:
            have = {r.name.lower() for r in rows}
            todo = [n for n in self.old_names
                    if n.lower() not in have and n.upper() != "TBC"]
            self.status.set(f"{len(rows)} room(s)" + (
                f" · {len(todo)} old room name(s) not imported yet"
                if todo else ""))
        else:
            self.status.set(f"{len(rows)} room(s)")

    def _add(self) -> None:
        rb = interviews.room_booking_rooms()
        links = {"(link by name, if one matches)": None}
        links.update({f"{name} (#{rid})": rid for rid, name in rb})

        def submit(v: dict[str, Any]) -> None:
            interviews.add_room(v["name"], capacity=v["capacity"] or None,
                                resource_id=links.get(v["link"]),
                                notes=v["notes"] or None)

        if pc.ask_form(self.frame, "Add interview room", [
                ("name", "Room name", "entry", None),
                ("capacity", "Holds (applicants)", "entry", None),
                ("link", "Room-booking room", "readonly", list(links)),
                ("notes", "Notes", "entry", None)],
                {"link": next(iter(links))}, on_submit=submit):
            self.refresh()

    def _remove(self) -> None:
        iid = pc.selected(self.tree, ROOMS)
        if not iid:
            return
        r = self._rows[iid]
        if not r.active:
            return
        if not messagebox.askyesno(ROOMS, f"Remove {r.name} from the "
                                   "interview rooms?",
                                   parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, ROOMS, interviews.remove_room, r.room_id)
        if ok:
            self.refresh()

    def _import(self) -> None:
        names = old_room_names()
        if not messagebox.askyesno(
                ROOMS, f"Add these rooms from the old list?\n\n"
                + ", ".join(names) + "\n\nNames already listed (and TBC) are "
                "skipped.", parent=self.frame.winfo_toplevel()):
            return
        ok, n = pc.run(self.frame, ROOMS, interviews.import_room_names, names)
        if ok:
            messagebox.showinfo(ROOMS, f"{n} room(s) added.",
                                parent=self.frame.winfo_toplevel())
            self.refresh()
