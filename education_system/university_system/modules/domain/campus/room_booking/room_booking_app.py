"""Standalone Tk launcher for Room Booking (with clash detection)."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.campus.room_booking import (
    RoomBookingService,
    RoomBookingError,
)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = RoomBookingService()
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Room Booking", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)

        form = tk.LabelFrame(self, text="Book / Find / Manage", bg="#ecf0f1", padx=8, pady=4)
        form.pack(fill="x", padx=10, pady=6)
        labels = ["Room ID", "Start (YYYY-MM-DD HH:MM)", "End (YYYY-MM-DD HH:MM)",
                  "Booked by", "Purpose", "Equipment (CSV)"]
        self._vars = {l: tk.StringVar() for l in labels}
        for i, l in enumerate(labels):
            tk.Label(form, text=l + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2,
                                                            padx=4, pady=2, sticky="e")
            tk.Entry(form, textvariable=self._vars[l], width=22).grid(
                row=i // 3, column=(i % 3) * 2 + 1, padx=4, pady=2)
        btns = tk.Frame(form, bg="#ecf0f1"); btns.grid(row=2, column=0, columnspan=6, pady=4)
        tk.Button(btns, text="Book", command=self._book).pack(side="left", padx=4)
        tk.Button(btns, text="Find Available", command=self._find).pack(side="left", padx=4)
        tk.Button(btns, text="Cancel Selected", command=self._cancel).pack(side="left", padx=4)
        tk.Button(btns, text="Refresh", command=self._refresh).pack(side="left", padx=4)

        cols = ("id", "room", "start", "end", "by", "purpose", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c in cols: self._tree.heading(c, text=c.title()); self._tree.column(c, width=120)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _book(self):
        try:
            v = self._vars
            self._svc.create_booking(
                int(v["Room ID"].get()),
                v["Start (YYYY-MM-DD HH:MM)"].get().strip(),
                v["End (YYYY-MM-DD HH:MM)"].get().strip(),
                v["Booked by"].get().strip(),
                v["Purpose"].get().strip() or "(no purpose)",
                equipment_needed=v["Equipment (CSV)"].get().strip(),
            )
            messagebox.showinfo("OK", "Booked."); self._refresh()
        except (RoomBookingError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def _find(self):
        try:
            v = self._vars
            rooms = self._svc.find_available_rooms(
                v["Start (YYYY-MM-DD HH:MM)"].get().strip(),
                v["End (YYYY-MM-DD HH:MM)"].get().strip(),
                equipment_csv=v["Equipment (CSV)"].get().strip(),
            )
        except (RoomBookingError, ValueError) as e:
            messagebox.showerror("Error", str(e)); return
        ids = ", ".join(str(r.get("room_id")) for r in rooms) or "(none)"
        messagebox.showinfo("Available rooms", f"{len(rooms)} room(s): {ids}")

    def _cancel(self):
        sel = self._tree.focus()
        if not sel: messagebox.showwarning("Select", "Select a booking first."); return
        bid = int(self._tree.item(sel, "values")[0])
        try:
            self._svc.cancel_booking(bid); self._refresh()
        except RoomBookingError as e:
            messagebox.showerror("Error", str(e))

    def _refresh(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        try:
            for b in self._svc.list_bookings():
                self._tree.insert("", "end", values=(
                    b.get("booking_id"), b.get("room_id"),
                    b.get("start_datetime"), b.get("end_datetime"),
                    b.get("booked_by"), b.get("purpose"),
                    b.get("booking_status") or b.get("status", "-"),
                ))
        except RoomBookingError as e:
            messagebox.showerror("Error", str(e))


def main() -> None:
    root = tk.Tk()
    root.title("Room Booking"); root.geometry("980x620")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
