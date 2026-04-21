"""Cinema — Staff and Student portals.

The repo's existing `CinemaApp` manages its showings internally (no
dedicated `cinema_showings` / `cinema_bookings` tables in the base
schema). To give staff + students working portals we create those two
tables on first open — idempotent `CREATE TABLE IF NOT EXISTS`s safe to
run on every portal launch.

Staff: add / edit / cancel showings.
Student: browse upcoming showings + book a ticket.
Admins retain the full CinemaApp.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


def ensure_cinema_tables():
    """Create cinema_showings and cinema_bookings if missing."""
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS cinema_showings ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  movie_title TEXT NOT NULL,"
                "  showing_date TEXT NOT NULL,"
                "  showing_time TEXT NOT NULL,"
                "  screen TEXT,"
                "  price REAL DEFAULT 0,"
                "  total_seats INTEGER DEFAULT 100,"
                "  booked_seats INTEGER DEFAULT 0,"
                "  rating TEXT,"
                "  duration_minutes INTEGER,"
                "  genre TEXT,"
                "  status TEXT DEFAULT 'scheduled',"
                "  created_at TEXT DEFAULT (datetime('now'))"
                ")"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS cinema_bookings ("
                "  booking_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  showing_id INTEGER NOT NULL,"
                "  user_id TEXT NOT NULL,"
                "  seats INTEGER DEFAULT 1,"
                "  total_price REAL,"
                "  booking_date TEXT DEFAULT (datetime('now')),"
                "  status TEXT DEFAULT 'booked',"
                "  FOREIGN KEY (showing_id) REFERENCES cinema_showings (id)"
                ")"
            )
            conn.commit()
    except Exception:
        pass


class CinemaStaffPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        ensure_cinema_tables()

        self.window = tk.Toplevel(parent)
        self.window.title("Cinema — Staff Portal")
        self.window.geometry("1080x680")
        self.window.minsize(900, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.info_var = tk.StringVar(value="")
        self._build_ui()
        self._load_showings()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#1f3a5f', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="Cinema — Staff",
                 font=('Arial', 14, 'bold'), bg='#1f3a5f', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Button(bar, text="+ New Showing",
                   command=self._new_showing).pack(side='left')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel_showing).pack(side='left', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_showings).pack(side='right')

        cols = ('date', 'time', 'title', 'screen', 'price',
                'seats', 'status')
        self.tree = ttk.Treeview(self.window, columns=cols,
                                 show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'Date', 110), ('time', 'Time', 80),
            ('title', 'Movie', 280), ('screen', 'Screen', 100),
            ('price', 'Price £', 90), ('seats', 'Seats', 120),
            ('status', 'Status', 110),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(self.window, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True,
                       padx=(10, 0), pady=4)
        vsb.pack(side='right', fill='y', padx=(0, 10), pady=4)
        self.tree.tag_configure('cancelled', foreground='#888')
        self.tree.tag_configure('full', background='#fde5e0')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _load_showings(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, showing_date, showing_time, movie_title, "
                    "       screen, price, total_seats, booked_seats, status "
                    "FROM cinema_showings "
                    "ORDER BY showing_date DESC, showing_time DESC LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for sid, date, time_, title, screen, price, total, booked, status in rows:
            seats = f"{booked or 0}/{total or 0}"
            tag = ()
            if status == 'cancelled':
                tag = ('cancelled',)
            elif (total or 0) > 0 and (booked or 0) >= (total or 0):
                tag = ('full',)
            price_str = f"{price:.2f}" if price is not None else ''
            self.tree.insert('', 'end', iid=str(sid), values=(
                (date or '')[:10], (time_ or '')[:5], title or '',
                screen or '', price_str, seats, status or ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} showing(s).")

    def _new_showing(self):
        ShowingDialog(self.window, showing=None,
                      on_save=self._load_showings)

    def _cancel_showing(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a showing to cancel.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Cancel Showing",
                                   "Cancel this showing? "
                                   "Existing bookings will be cancelled.",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE cinema_showings SET status = 'cancelled' "
                    "WHERE id = ?", (int(sel[0]),)
                )
                cur.execute(
                    "UPDATE cinema_bookings SET status = 'cancelled' "
                    "WHERE showing_id = ? AND status = 'booked'",
                    (int(sel[0]),)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Cancel Failed", str(e),
                                 parent=self.window)
            return
        self._load_showings()


class ShowingDialog:
    def __init__(self, parent, showing, on_save):
        self.showing = showing
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Showing")
        self.dialog.geometry("440x360")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        self.title_var = tk.StringVar()
        default_date = (datetime.now() + timedelta(days=1)).date().isoformat()
        self.date_var = tk.StringVar(value=default_date)
        self.time_var = tk.StringVar(value='19:30')
        self.screen_var = tk.StringVar(value='Screen 1')
        self.price_var = tk.StringVar(value='8.00')
        self.seats_var = tk.StringVar(value='100')
        self.rating_var = tk.StringVar(value='12A')

        for i, (label, var) in enumerate([
            ("Movie title:", self.title_var),
            ("Date (YYYY-MM-DD):", self.date_var),
            ("Time (HH:MM):", self.time_var),
            ("Screen:", self.screen_var),
            ("Price £:", self.price_var),
            ("Total seats:", self.seats_var),
            ("Rating:", self.rating_var),
        ]):
            ttk.Label(frame, text=label).grid(row=i, column=0,
                                                sticky='w', pady=4)
            ttk.Entry(frame, textvariable=var, width=26).grid(
                row=i, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=7, column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        title = self.title_var.get().strip()
        date = self.date_var.get().strip()
        time_ = self.time_var.get().strip()
        if not (title and date and time_):
            messagebox.showerror("Missing",
                                 "Title, date, and time are required.",
                                 parent=self.dialog)
            return
        try:
            datetime.strptime(date, '%Y-%m-%d')
            datetime.strptime(time_, '%H:%M')
        except ValueError:
            messagebox.showerror("Invalid",
                                 "Date must be YYYY-MM-DD, time HH:MM.",
                                 parent=self.dialog)
            return
        try:
            price = float(self.price_var.get() or 0)
            seats = int(self.seats_var.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid",
                                 "Price and seats must be numbers.",
                                 parent=self.dialog)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO cinema_showings "
                    "(movie_title, showing_date, showing_time, screen, "
                    " price, total_seats, booked_seats, rating, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'scheduled')",
                    (title, date, time_, self.screen_var.get().strip(),
                     price, seats, self.rating_var.get().strip())
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed", str(e),
                                 parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


class CinemaStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        ensure_cinema_tables()

        user = (auth.current_user if auth else None) or {}
        self.user_id = str(user.get('username') or user.get('user_id')
                           or user.get('id') or '')

        self.window = tk.Toplevel(parent)
        self.window.title("Cinema — My Portal")
        self.window.geometry("1040x680")
        self.window.minsize(880, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.info_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#1f3a5f', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Cinema — {display}",
                 font=('Arial', 14, 'bold'), bg='#1f3a5f', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#14253a', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#14253a', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_browse_tab(nb)
        self._build_mine_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_browse_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Upcoming Showings")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Book Selected",
                   command=self._book).pack(side='right')

        cols = ('date', 'time', 'title', 'screen', 'price', 'avail')
        self.show_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'Date', 110), ('time', 'Time', 80),
            ('title', 'Movie', 320), ('screen', 'Screen', 100),
            ('price', 'Price £', 100), ('avail', 'Seats left', 110),
        ]:
            self.show_tree.heading(key, text=title)
            self.show_tree.column(key, width=width,
                                  anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.show_tree.yview)
        self.show_tree.configure(yscrollcommand=vsb.set)
        self.show_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _build_mine_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Bookings")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="My cinema bookings",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel_booking).pack(side='right')

        cols = ('booking_id', 'title', 'date', 'time',
                'seats', 'total', 'status')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('booking_id', 'Booking', 80), ('title', 'Movie', 260),
            ('date', 'Date', 110), ('time', 'Time', 80),
            ('seats', 'Seats', 70), ('total', 'Total £', 100),
            ('status', 'Status', 110),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width,
                                  anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_showings()
        self._load_mine()

    def _load_showings(self):
        for i in self.show_tree.get_children():
            self.show_tree.delete(i)
        today = datetime.now().date().isoformat()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, showing_date, showing_time, movie_title, "
                    "       screen, price, total_seats, booked_seats "
                    "FROM cinema_showings "
                    "WHERE showing_date >= ? "
                    "  AND COALESCE(status, 'scheduled') = 'scheduled' "
                    "ORDER BY showing_date, showing_time LIMIT 500",
                    (today,)
                )
                for row in cur.fetchall():
                    sid, date, time_, title, screen, price, total, booked = row
                    avail = max((total or 0) - (booked or 0), 0)
                    price_str = f"{price:.2f}" if price is not None else ''
                    self.show_tree.insert('', 'end', iid=str(sid), values=(
                        (date or '')[:10], (time_ or '')[:5], title or '',
                        screen or '', price_str, avail
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _book(self):
        if not self.user_id:
            messagebox.showerror("Not Signed In",
                                 "Your account has no user ID.",
                                 parent=self.window)
            return
        sel = self.show_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Pick a showing to book.",
                                parent=self.window)
            return
        sid = int(sel[0])
        import tkinter.simpledialog as sd
        seats = sd.askinteger("Seats",
                              "How many seats?",
                              parent=self.window, minvalue=1, maxvalue=20,
                              initialvalue=1)
        if not seats:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT total_seats, booked_seats, price, status "
                    "FROM cinema_showings WHERE id = ?", (sid,)
                )
                row = cur.fetchone()
                if not row:
                    return
                total, booked, price, status = row
                if status != 'scheduled':
                    messagebox.showerror("Unavailable",
                                         "This showing is not bookable.",
                                         parent=self.window)
                    return
                if (booked or 0) + seats > (total or 0):
                    messagebox.showerror(
                        "Not Enough Seats",
                        f"Only {(total or 0) - (booked or 0)} seats left.",
                        parent=self.window)
                    return
                total_price = (price or 0) * seats
                cur.execute(
                    "INSERT INTO cinema_bookings "
                    "(showing_id, user_id, seats, total_price, "
                    " booking_date, status) "
                    "VALUES (?, ?, ?, ?, ?, 'booked')",
                    (sid, self.user_id, seats, total_price,
                     datetime.now().isoformat(timespec='seconds'))
                )
                cur.execute(
                    "UPDATE cinema_showings "
                    "SET booked_seats = COALESCE(booked_seats, 0) + ? "
                    "WHERE id = ?", (seats, sid)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Booking Failed", str(e),
                                 parent=self.window)
            return
        messagebox.showinfo("Booked",
                            f"{seats} seat(s) booked. Total £{total_price:.2f}.",
                            parent=self.window)
        self._refresh_all()

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        if not self.user_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT b.booking_id, s.movie_title, s.showing_date, "
                    "       s.showing_time, b.seats, b.total_price, b.status "
                    "FROM cinema_bookings b "
                    "JOIN cinema_showings s ON s.id = b.showing_id "
                    "WHERE b.user_id = ? "
                    "ORDER BY s.showing_date DESC, s.showing_time DESC",
                    (self.user_id,)
                )
                for row in cur.fetchall():
                    tp = f"{row[5]:.2f}" if row[5] is not None else ''
                    self.mine_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[0], row[1] or '', (row[2] or '')[:10],
                        (row[3] or '')[:5], row[4] or 0, tp, row[6] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _cancel_booking(self):
        sel = self.mine_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Pick a booking to cancel.",
                                parent=self.window)
            return
        bid = int(sel[0])
        if not messagebox.askyesno("Cancel Booking",
                                   "Cancel this booking?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT showing_id, seats, status FROM cinema_bookings "
                    "WHERE booking_id = ? AND user_id = ?",
                    (bid, self.user_id)
                )
                row = cur.fetchone()
                if not row or row[2] != 'booked':
                    return
                cur.execute(
                    "UPDATE cinema_bookings SET status = 'cancelled' "
                    "WHERE booking_id = ?", (bid,)
                )
                cur.execute(
                    "UPDATE cinema_showings SET booked_seats = "
                    "    CASE WHEN COALESCE(booked_seats, 0) >= ? "
                    "         THEN booked_seats - ? ELSE 0 END "
                    "WHERE id = ?", (row[1], row[1], row[0])
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Cancel Failed", str(e),
                                 parent=self.window)
            return
        self._refresh_all()


def launch_cinema_staff_portal(parent, auth):
    return CinemaStaffPortal(parent, auth)


def launch_cinema_student_portal(parent, auth):
    return CinemaStudentPortal(parent, auth)
