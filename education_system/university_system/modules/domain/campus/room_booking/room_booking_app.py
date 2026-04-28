"""Standalone Tk launcher for Room Booking (with clash detection).

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user, and
the "Booked by" field is pre-filled with their name.

Persistence: data lives in the central `student_records.db` (room and
booking tables managed by `RoomBookingService`). Any stray *.db files
alongside this module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import tkinter as tk
from tkinter import ttk, messagebox

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


from education_system.university_system.modules.domain.campus.room_booking import (  # noqa: E402
    RoomBookingService,
    RoomBookingError,
)


def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, with a
    fallback to the in-process global auth singleton."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


def _remove_legacy_db():
    """Sweep any stray local SQLite files left alongside this module
    by earlier iterations. Data lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(here):
        return
    for fname in os.listdir(here):
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy room-booking DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class _Frame(tk.Frame):
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = RoomBookingService()
        self._user = user
        self._user_display = _user_display_name(user)
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Room Booking", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)
        role = (self._user or {}).get('role') or ('—' if self._user else 'not signed in')
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({role})",
                 font=("Helvetica", 9), bg="#2c3e50",
                 fg="#bdc3c7").pack(side="right", padx=20, pady=14)

        form = tk.LabelFrame(self, text="Book / Find / Manage", bg="#ecf0f1", padx=8, pady=4)
        form.pack(fill="x", padx=10, pady=6)
        labels = ["Room ID", "Start (YYYY-MM-DD HH:MM)", "End (YYYY-MM-DD HH:MM)",
                  "Booked by", "Purpose", "Equipment (CSV)"]
        self._vars = {l: tk.StringVar() for l in labels}
        # Pre-fill "Booked by" with the signed-in user.
        if self._user:
            self._vars["Booked by"].set(self._user_display)
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
            room_id = int(v["Room ID"].get())
            start = v["Start (YYYY-MM-DD HH:MM)"].get().strip()
            end = v["End (YYYY-MM-DD HH:MM)"].get().strip()
            booked_by = v["Booked by"].get().strip() or self._user_display
            purpose = v["Purpose"].get().strip() or "(no purpose)"
            self._svc.create_booking(
                room_id, start, end, booked_by, purpose,
                equipment_needed=v["Equipment (CSV)"].get().strip(),
            )
            logger.info("Room booked room_id=%s start=%s end=%s by=%s purpose=%r logged_by=%s",
                        room_id, start, end, booked_by, purpose, self._user_display)
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
            self._svc.cancel_booking(bid)
            logger.info("Room booking cancelled booking_id=%s by=%s",
                        bid, self._user_display)
            self._refresh()
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
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("Room Booking starting user=%s role=%s",
                _user_display_name(user),
                (user or {}).get('role') or 'none')
    root = tk.Tk()
    root.title("Room Booking"); root.geometry("980x620")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
