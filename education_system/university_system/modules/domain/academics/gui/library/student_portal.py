"""Library — Student portal.

A student-facing window: browse the catalogue, see own loans and
reservations, reserve an unavailable book, cancel own reservations.
Read-only for the catalogue; no checkout/return/admin powers.
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


def _reservation_expiry_days():
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT setting_value FROM library_settings "
                "WHERE setting_name = 'reservation_expiry_days'"
            )
            row = cur.fetchone()
            if row and row[0]:
                return int(row[0])
    except Exception:
        pass
    return 7


class LibraryStudentPortal:
    """Read-only + self-service library window for students."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.user_id = self._resolve_user_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Library — My Portal")
        self.window.geometry("1120x700")
        self.window.minsize(960, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _resolve_user_id(self):
        """user_id in book_loans/reservations is TEXT — use username / id."""
        user = (self.auth.current_user if self.auth else None) or {}
        return str(user.get('username') or user.get('user_id')
                   or user.get('id') or '')

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#2980b9', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)

        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"My Library — {display}",
                 font=('Arial', 14, 'bold'), bg='#2980b9', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1f6391', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self._build_browse_tab(nb)
        self._build_loans_tab(nb)
        self._build_reservations_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # -- Browse --------------------------------------------------------

    def _build_browse_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Browse")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=32)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_books())

        ttk.Label(bar, text="Category:").pack(side='left', padx=(10, 4))
        self.cat_var = tk.StringVar(value='All')
        self.cat_combo = ttk.Combobox(bar, textvariable=self.cat_var,
                                      state='readonly', width=18)
        self.cat_combo.pack(side='left')

        self.avail_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Available only",
                        variable=self.avail_only_var,
                        command=self._load_books).pack(side='left', padx=10)

        ttk.Button(bar, text="Search",
                   command=self._load_books).pack(side='left')
        ttk.Button(bar, text="Reserve",
                   command=self._reserve_book).pack(side='right')

        cols = ('book_id', 'title', 'author', 'category', 'status')
        self.books_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        headings = [
            ('book_id', 'ID', 90),
            ('title', 'Title', 340),
            ('author', 'Author', 220),
            ('category', 'Category', 140),
            ('status', 'Status', 110),
        ]
        for key, title, width in headings:
            self.books_tree.heading(key, text=title)
            self.books_tree.column(key, width=width,
                                   anchor='w' if key in ('title', 'author',
                                                         'category') else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.books_tree.yview)
        self.books_tree.configure(yscrollcommand=vsb.set)
        self.books_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.books_tree.tag_configure('available', background='#eafaf1')
        self.books_tree.tag_configure('unavailable', background='#fdebd0')

        self._load_categories()

    def _load_categories(self):
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT DISTINCT category FROM books "
                    "WHERE category IS NOT NULL AND category != '' "
                    "ORDER BY category"
                )
                cats = [r[0] for r in cur.fetchall()]
        except Exception:
            cats = []
        self.cat_combo['values'] = ['All'] + cats
        self.cat_combo.bind('<<ComboboxSelected>>',
                            lambda _e: self._load_books())

    def _load_books(self):
        for i in self.books_tree.get_children():
            self.books_tree.delete(i)
        query = self.search_var.get().strip()
        cat = self.cat_var.get()

        clauses = []
        params = []
        if query:
            clauses.append("(title LIKE ? OR author LIKE ? OR book_id LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        if cat and cat != 'All':
            clauses.append("category = ?")
            params.append(cat)
        if self.avail_only_var.get():
            clauses.append("status = 'available'")

        sql = ("SELECT book_id, title, author, category, status FROM books")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY title LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return

        for book_id, title, author, cat_val, status in rows:
            tag = 'available' if status == 'available' else 'unavailable'
            self.books_tree.insert('', 'end', iid=book_id, values=(
                book_id, title, author, cat_val or '', status or ''
            ), tags=(tag,))
        self.status_var.set(f"{len(rows)} book(s) shown.")

    def _reserve_book(self):
        if not self.user_id:
            messagebox.showerror("Not Signed In",
                                 "Your account is not linked to a user ID.",
                                 parent=self.window)
            return
        sel = self.books_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a book to reserve.",
                                parent=self.window)
            return
        book_id = sel[0]
        values = self.books_tree.item(book_id, 'values')
        title = values[1]
        status = values[4]

        if status == 'available':
            messagebox.showinfo(
                "Already Available",
                f"'{title}' is available now — no reservation needed. "
                "Visit the library to check it out.",
                parent=self.window)
            return

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT reservation_id FROM book_reservations "
                    "WHERE book_id = ? AND user_id = ? AND status = 'active'",
                    (book_id, self.user_id)
                )
                if cur.fetchone():
                    messagebox.showinfo(
                        "Already Reserved",
                        f"You already have an active reservation for '{title}'.",
                        parent=self.window)
                    return

                cur.execute(
                    "SELECT COALESCE(MAX(priority_order), 0) + 1 "
                    "FROM book_reservations "
                    "WHERE book_id = ? AND status = 'active'",
                    (book_id,)
                )
                priority = cur.fetchone()[0]

                now = datetime.now()
                expiry = now + timedelta(days=_reservation_expiry_days())
                cur.execute(
                    "INSERT INTO book_reservations "
                    "(book_id, user_id, reservation_date, expiry_date, "
                    " status, priority_order) "
                    "VALUES (?, ?, ?, ?, 'active', ?)",
                    (book_id, self.user_id,
                     now.strftime('%Y-%m-%d %H:%M:%S'),
                     expiry.strftime('%Y-%m-%d %H:%M:%S'),
                     priority)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Reserve Failed", str(e),
                                 parent=self.window)
            return

        messagebox.showinfo(
            "Reserved",
            f"'{title}' reserved. You are #{priority} in the queue.\n"
            f"Reservation expires {expiry.strftime('%Y-%m-%d')}.",
            parent=self.window)
        self._load_reservations()

    # -- My Loans ------------------------------------------------------

    def _build_loans_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Loans")

        ttk.Label(frame, text="Books I have (or had) on loan",
                  font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 6))

        cols = ('book_id', 'title', 'checkout', 'due', 'return', 'status', 'fine')
        self.loans_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        headings = [
            ('book_id', 'Book ID', 100),
            ('title', 'Title', 320),
            ('checkout', 'Checkout', 110),
            ('due', 'Due', 110),
            ('return', 'Returned', 110),
            ('status', 'Status', 90),
            ('fine', 'Fine', 70),
        ]
        for key, title, width in headings:
            self.loans_tree.heading(key, text=title)
            self.loans_tree.column(key, width=width,
                                   anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.loans_tree.yview)
        self.loans_tree.configure(yscrollcommand=vsb.set)
        self.loans_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.loans_tree.tag_configure('overdue', background='#f9d6d5')
        self.loans_tree.tag_configure('active', background='#fef9e7')

    def _load_loans(self):
        for i in self.loans_tree.get_children():
            self.loans_tree.delete(i)
        if not self.user_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT l.book_id, b.title, l.checkout_date, l.due_date, "
                    "       l.return_date, l.status, l.fine_amount "
                    "FROM book_loans l "
                    "LEFT JOIN books b ON b.book_id = l.book_id "
                    "WHERE l.user_id = ? ORDER BY l.checkout_date DESC",
                    (self.user_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        today = datetime.now()
        for book_id, title, ch, du, ret, st, fine in rows:
            tag = ()
            if st == 'active':
                tag = ('active',)
                try:
                    d = datetime.strptime(du[:19], '%Y-%m-%d %H:%M:%S')
                    if d < today:
                        tag = ('overdue',)
                except Exception:
                    pass
            self.loans_tree.insert('', 'end', values=(
                book_id, title or '?', (ch or '')[:10], (du or '')[:10],
                (ret or '')[:10], st or '',
                '' if fine in (None, 0, 0.0) else f"{fine:.2f}"
            ), tags=tag)

    # -- My Reservations -----------------------------------------------

    def _build_reservations_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Reservations")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Active and past reservations",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel_mine).pack(side='right')

        cols = ('res_id', 'book_id', 'title', 'reserved', 'expires',
                'priority', 'status')
        self.mres_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        headings = [
            ('res_id', 'Res ID', 60),
            ('book_id', 'Book', 110),
            ('title', 'Title', 320),
            ('reserved', 'Reserved', 120),
            ('expires', 'Expires', 120),
            ('priority', 'Queue', 80),
            ('status', 'Status', 100),
        ]
        for key, title, width in headings:
            self.mres_tree.heading(key, text=title)
            self.mres_tree.column(key, width=width,
                                  anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mres_tree.yview)
        self.mres_tree.configure(yscrollcommand=vsb.set)
        self.mres_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _load_reservations(self):
        for i in self.mres_tree.get_children():
            self.mres_tree.delete(i)
        if not self.user_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT r.reservation_id, r.book_id, b.title, "
                    "       r.reservation_date, r.expiry_date, "
                    "       r.priority_order, r.status "
                    "FROM book_reservations r "
                    "LEFT JOIN books b ON b.book_id = r.book_id "
                    "WHERE r.user_id = ? "
                    "ORDER BY r.reservation_date DESC",
                    (self.user_id,)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for rid, book_id, title, res_date, exp_date, priority, status in rows:
            self.mres_tree.insert('', 'end', iid=str(rid), values=(
                rid, book_id, title or '?',
                (res_date or '')[:16], (exp_date or '')[:16],
                priority, status or ''
            ))

    def _cancel_mine(self):
        sel = self.mres_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a reservation to cancel.",
                                parent=self.window)
            return
        rid = int(sel[0])
        current_status = self.mres_tree.item(sel[0], 'values')[6]
        if current_status != 'active':
            messagebox.showinfo("Nothing to Do",
                                "Only active reservations can be cancelled.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Cancel Reservation",
                                   "Cancel this reservation?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE book_reservations SET status = 'cancelled' "
                    "WHERE reservation_id = ? AND user_id = ?",
                    (rid, self.user_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Cancel Failed", str(e),
                                 parent=self.window)
            return
        self._load_reservations()

    # ------------------------------------------------------------------

    def _refresh_all(self):
        self._load_books()
        self._load_loans()
        self._load_reservations()


def launch_library_student_portal(parent, auth):
    """Module-level entry point."""
    return LibraryStudentPortal(parent, auth)
