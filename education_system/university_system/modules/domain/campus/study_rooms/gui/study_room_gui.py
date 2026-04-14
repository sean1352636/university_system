import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


class StudyRoomBookingGUI:
    """Student self-service study room and facility booking system."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Study Room Booking")
        self.window.geometry("1000x650")

        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        try:
            from education_system.university_system.modules.shared.utils.i18n import get_text as _t
            self._t = _t
        except ImportError:
            self._t = lambda key, **kw: key

        self._init_db()
        self._build_ui()
        self._load_data()

    def _init_db(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS study_rooms (
                    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_number TEXT NOT NULL,
                    building TEXT DEFAULT '',
                    capacity INTEGER DEFAULT 4,
                    room_type TEXT DEFAULT 'study',
                    equipment TEXT DEFAULT '',
                    has_whiteboard INTEGER DEFAULT 0,
                    has_projector INTEGER DEFAULT 0,
                    has_power_outlets INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'available'
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS study_room_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    booked_by TEXT NOT NULL,
                    booking_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    purpose TEXT DEFAULT 'study',
                    group_size INTEGER DEFAULT 1,
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'confirmed',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (room_id) REFERENCES study_rooms(room_id)
                )""")
                # Seed sample rooms if empty
                count = conn.execute("SELECT COUNT(*) FROM study_rooms").fetchone()[0]
                if count == 0:
                    rooms = [
                        ("SR-101", "Library", 4, "study", "Quiet study room", 1, 0, 1),
                        ("SR-102", "Library", 6, "group_study", "Group study room", 1, 1, 1),
                        ("SR-103", "Library", 2, "study", "Individual study pod", 0, 0, 1),
                        ("SR-201", "Student Center", 8, "group_study", "Large group room", 1, 1, 1),
                        ("SR-202", "Student Center", 4, "study", "Quiet room", 1, 0, 1),
                        ("SR-301", "Science Building", 6, "lab_study", "Study room with lab access", 1, 1, 1),
                        ("SR-302", "Science Building", 4, "study", "Science study room", 1, 0, 1),
                        ("SR-401", "Engineering Block", 8, "group_study", "Engineering project room", 1, 1, 1),
                    ]
                    for r in rooms:
                        conn.execute(
                            "INSERT INTO study_rooms (room_number, building, capacity, room_type, equipment, has_whiteboard, has_projector, has_power_outlets) VALUES (?,?,?,?,?,?,?,?)",
                            r
                        )
                    conn.commit()
        except Exception as e:
            logger.error(f"DB init error: {e}")

    def _get_user_id(self):
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                return user.get('student_id', user.get('username', 'unknown'))
            return getattr(user, 'student_id', getattr(user, 'username', 'unknown'))
        return 'unknown'

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_available_rooms_tab()
        self._build_book_room_tab()
        self._build_my_bookings_tab()

    def _build_available_rooms_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Available Rooms")

        # Filters
        filt_frame = ttk.LabelFrame(tab, text="Filter", padding=5)
        filt_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filt_frame, text="Date:").pack(side=tk.LEFT, padx=2)
        self.filter_date = ttk.Entry(filt_frame, width=12)
        self.filter_date.pack(side=tk.LEFT, padx=2)
        self.filter_date.insert(0, date.today().isoformat())

        ttk.Label(filt_frame, text="Building:").pack(side=tk.LEFT, padx=(10, 2))
        self.filter_building = ttk.Combobox(filt_frame, values=["All"], state="readonly", width=15)
        self.filter_building.set("All")
        self.filter_building.pack(side=tk.LEFT, padx=2)

        ttk.Label(filt_frame, text="Type:").pack(side=tk.LEFT, padx=(10, 2))
        self.filter_type = ttk.Combobox(filt_frame, values=["All", "study", "group_study", "lab_study"], state="readonly", width=12)
        self.filter_type.set("All")
        self.filter_type.pack(side=tk.LEFT, padx=2)

        ttk.Button(filt_frame, text="Search", command=self._load_rooms).pack(side=tk.LEFT, padx=10)

        # Room list
        cols = ("room_id", "room_number", "building", "capacity", "type", "whiteboard", "projector", "status")
        self.room_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (50, 90, 120, 70, 90, 80, 70, 80)):
            self.room_tree.heading(c, text=c.replace("_", " ").title())
            self.room_tree.column(c, width=w, minwidth=40)
        self.room_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Button(tab, text="Book Selected Room", command=self._quick_book).pack(pady=5)

    def _build_book_room_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Book a Room")

        form = ttk.LabelFrame(tab, text="Booking Details", padding=15)
        form.pack(fill=tk.X, padx=10, pady=10)

        row = 0
        ttk.Label(form, text="Room:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_room_combo = ttk.Combobox(form, state="readonly", width=30)
        self.book_room_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_date = ttk.Entry(form, width=15)
        self.book_date.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)
        self.book_date.insert(0, date.today().isoformat())

        row += 1
        ttk.Label(form, text="Start Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_start = ttk.Combobox(form, values=[f"{h:02d}:00" for h in range(8, 22)], width=10)
        self.book_start.set("09:00")
        self.book_start.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="End Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_end = ttk.Combobox(form, values=[f"{h:02d}:00" for h in range(9, 23)], width=10)
        self.book_end.set("11:00")
        self.book_end.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Group Size:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_group = ttk.Spinbox(form, from_=1, to=20, width=5)
        self.book_group.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Purpose:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.book_purpose = ttk.Combobox(form, values=["study", "group_project", "exam_prep", "tutoring", "meeting"], state="readonly", width=15)
        self.book_purpose.set("study")
        self.book_purpose.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Notes:").grid(row=row, column=0, sticky=tk.NW, pady=3)
        self.book_notes = tk.Text(form, width=30, height=3)
        self.book_notes.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Button(form, text="Book Room", command=self._book_room).grid(row=row, column=1, sticky=tk.W, pady=10, padx=5)

    def _build_my_bookings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Bookings")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_my_bookings).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Cancel Selected", command=self._cancel_booking).pack(side=tk.LEFT, padx=2)

        cols = ("booking_id", "room", "date", "start", "end", "purpose", "group_size", "status")
        self.booking_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (60, 100, 100, 70, 70, 100, 70, 80)):
            self.booking_tree.heading(c, text=c.replace("_", " ").title())
            self.booking_tree.column(c, width=w, minwidth=40)
        self.booking_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _load_data(self):
        self._load_rooms()
        self._load_room_combos()
        self._load_my_bookings()

    def _load_rooms(self):
        for item in self.room_tree.get_children():
            self.room_tree.delete(item)
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                query = "SELECT * FROM study_rooms WHERE status = 'available'"
                params = []
                building = self.filter_building.get()
                if building and building != "All":
                    query += " AND building = ?"
                    params.append(building)
                rtype = self.filter_type.get()
                if rtype and rtype != "All":
                    query += " AND room_type = ?"
                    params.append(rtype)
                query += " ORDER BY building, room_number"
                rows = conn.execute(query, params).fetchall()
                buildings = set()
                for r in rows:
                    self.room_tree.insert("", tk.END, values=(
                        r["room_id"], r["room_number"], r["building"],
                        r["capacity"], r["room_type"],
                        "Yes" if r["has_whiteboard"] else "No",
                        "Yes" if r["has_projector"] else "No",
                        r["status"]
                    ))
                    buildings.add(r["building"])
                self.filter_building['values'] = ["All"] + sorted(buildings)
        except Exception as e:
            logger.debug(f"Load rooms: {e}")

    def _load_room_combos(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute("SELECT room_id, room_number, building, capacity FROM study_rooms WHERE status='available' ORDER BY building, room_number").fetchall()
                vals = [f"{r['room_id']} - {r['room_number']} ({r['building']}, cap:{r['capacity']})" for r in rows]
                self.book_room_combo['values'] = vals
                if vals:
                    self.book_room_combo.current(0)
        except Exception as e:
            logger.debug(f"Load room combos: {e}")

    def _load_my_bookings(self):
        for item in self.booking_tree.get_children():
            self.booking_tree.delete(item)
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            user_id = self._get_user_id()
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT b.*, r.room_number FROM study_room_bookings b
                    JOIN study_rooms r ON b.room_id = r.room_id
                    WHERE b.booked_by = ? ORDER BY b.booking_date DESC, b.start_time DESC
                """, (user_id,)).fetchall()
                for r in rows:
                    self.booking_tree.insert("", tk.END, values=(
                        r["booking_id"], r["room_number"], r["booking_date"],
                        r["start_time"], r["end_time"], r["purpose"],
                        r["group_size"], r["status"]
                    ))
        except Exception as e:
            logger.debug(f"Load bookings: {e}")

    def _quick_book(self):
        sel = self.room_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a room first.")
            return
        vals = self.room_tree.item(sel[0])['values']
        room_id = vals[0]
        room_label = f"{room_id} - {vals[1]} ({vals[2]}, cap:{vals[3]})"
        # Set in booking tab
        idx = None
        for i, v in enumerate(self.book_room_combo['values']):
            if v.startswith(str(room_id) + " -"):
                idx = i
                break
        if idx is not None:
            self.book_room_combo.current(idx)
        self.notebook.select(1)  # Switch to booking tab

    def _book_room(self):
        room_val = self.book_room_combo.get()
        if not room_val:
            messagebox.showwarning("Warning", "Select a room.")
            return
        room_id = int(room_val.split(" - ")[0])
        bdate = self.book_date.get().strip()
        start = self.book_start.get().strip()
        end = self.book_end.get().strip()

        try:
            datetime.strptime(bdate, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format.")
            return
        if start >= end:
            messagebox.showerror("Error", "End time must be after start time.")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            user_id = self._get_user_id()
            with get_connection() as conn:
                # Check conflicts
                conflict = conn.execute("""
                    SELECT COUNT(*) FROM study_room_bookings
                    WHERE room_id = ? AND booking_date = ? AND status = 'confirmed'
                    AND start_time < ? AND end_time > ?
                """, (room_id, bdate, end, start)).fetchone()[0]
                if conflict > 0:
                    messagebox.showerror("Error", "Room is already booked for that time slot.")
                    return

                conn.execute("""INSERT INTO study_room_bookings
                    (room_id, booked_by, booking_date, start_time, end_time, purpose, group_size, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (room_id, user_id, bdate, start, end,
                     self.book_purpose.get(), int(self.book_group.get()),
                     self.book_notes.get("1.0", tk.END).strip()))
                conn.commit()
            messagebox.showinfo("Success", "Room booked successfully!")
            self._load_my_bookings()
            self.notebook.select(2)  # Switch to my bookings
        except Exception as e:
            messagebox.showerror("Error", f"Booking failed: {e}")

    def _cancel_booking(self):
        sel = self.booking_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a booking to cancel.")
            return
        vals = self.booking_tree.item(sel[0])['values']
        if vals[7] == 'cancelled':
            messagebox.showinfo("Info", "Already cancelled.")
            return
        if messagebox.askyesno("Confirm", "Cancel this booking?"):
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    conn.execute("UPDATE study_room_bookings SET status='cancelled' WHERE booking_id=?", (vals[0],))
                    conn.commit()
                self._load_my_bookings()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")


def launch_study_room_gui(parent=None):
    return StudyRoomBookingGUI(parent=parent)
