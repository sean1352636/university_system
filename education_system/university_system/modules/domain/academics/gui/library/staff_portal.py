"""Library — Staff/Instructor portal.

A focused circulation + collection window for staff and instructors:
browse and add books, check books out, process returns, view active loans
and reservations. Admins retain the full LibraryGUI for settings, reports,
digital library, analytics, maintenance, etc.
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


def _loan_period_days():
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT setting_value FROM library_settings "
                "WHERE setting_name = 'loan_period_days'"
            )
            row = cur.fetchone()
            if row and row[0]:
                return int(row[0])
    except Exception:
        pass
    return 14


class LibraryStaffPortal:
    """Circulation + collection management for staff/instructors."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.staff_id = self._resolve_staff_id()

        self.window = tk.Toplevel(parent)
        self.window.title("Library — Staff Portal")
        self.window.geometry("1200x760")
        self.window.minsize(1000, 640)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.status_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _resolve_staff_id(self):
        user = (self.auth.current_user if self.auth else None) or {}
        return str(user.get('user_id') or user.get('id') or user.get('username') or '')

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#34495e', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)

        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Library Circulation — {display}",
                 font=('Arial', 14, 'bold'), bg='#34495e', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self._build_books_tab(nb)
        self._build_checkout_tab(nb)
        self._build_returns_tab(nb)
        self._build_loans_tab(nb)
        self._build_reservations_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var, anchor='w',
                  padding=(8, 2)).pack(fill='x')

    # -- Books tab -----------------------------------------------------

    def _build_books_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Books")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        self.books_search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.books_search_var, width=32)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_books())
        ttk.Button(bar, text="Search", command=self._load_books).pack(side='left')
        ttk.Button(bar, text="Clear",
                   command=lambda: (self.books_search_var.set(''),
                                    self._load_books())
                   ).pack(side='left', padx=4)
        ttk.Button(bar, text="+ Add Book",
                   command=self._add_book).pack(side='right')
        ttk.Button(bar, text="Edit",
                   command=self._edit_book).pack(side='right', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_books).pack(side='right', padx=4)

        cols = ('book_id', 'title', 'author', 'category', 'location', 'status')
        self.books_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        headings = [
            ('book_id', 'ID', 90),
            ('title', 'Title', 300),
            ('author', 'Author', 200),
            ('category', 'Category', 130),
            ('location', 'Location', 130),
            ('status', 'Status', 110),
        ]
        for key, title, width in headings:
            self.books_tree.heading(key, text=title)
            self.books_tree.column(key, width=width,
                                   anchor='w' if key in ('title', 'author',
                                                         'category', 'location')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.books_tree.yview)
        self.books_tree.configure(yscrollcommand=vsb.set)
        self.books_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _load_books(self):
        for i in self.books_tree.get_children():
            self.books_tree.delete(i)
        query = self.books_search_var.get().strip()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                if query:
                    like = f"%{query}%"
                    cur.execute(
                        "SELECT book_id, title, author, category, location, status "
                        "FROM books "
                        "WHERE title LIKE ? OR author LIKE ? OR book_id LIKE ? "
                        "   OR isbn LIKE ? "
                        "ORDER BY title LIMIT 500",
                        (like, like, like, like)
                    )
                else:
                    cur.execute(
                        "SELECT book_id, title, author, category, location, status "
                        "FROM books ORDER BY title LIMIT 500"
                    )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load books: {e}",
                                 parent=self.window)
            return
        for row in rows:
            self.books_tree.insert('', 'end', iid=row[0], values=row)
        self.status_var.set(f"Loaded {len(rows)} book(s).")

    def _add_book(self):
        BookEditorDialog(self.window, book=None, on_save=self._refresh_all)

    def _edit_book(self):
        sel = self.books_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a book to edit.",
                                parent=self.window)
            return
        book_id = sel[0]
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT book_id, title, author, isbn, category, "
                    "       location, status, description "
                    "FROM books WHERE book_id = ?",
                    (book_id,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        if row:
            BookEditorDialog(self.window, book=row, on_save=self._refresh_all)

    # -- Checkout tab --------------------------------------------------

    def _build_checkout_tab(self, nb):
        frame = ttk.Frame(nb, padding=12)
        nb.add(frame, text="Checkout")

        ttk.Label(frame, text="Check out a book",
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill='x', pady=4)

        ttk.Label(form, text="Book ID:").grid(row=0, column=0, sticky='w', pady=4)
        self.co_book_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.co_book_var, width=40).grid(
            row=0, column=1, sticky='w', pady=4)

        ttk.Label(form, text="User ID (borrower):").grid(row=1, column=0,
                                                          sticky='w', pady=4)
        self.co_user_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.co_user_var, width=40).grid(
            row=1, column=1, sticky='w', pady=4)

        default_due = (datetime.now() + timedelta(days=_loan_period_days())
                       ).strftime('%Y-%m-%d')
        ttk.Label(form, text="Due date (YYYY-MM-DD):").grid(row=2, column=0,
                                                             sticky='w', pady=4)
        self.co_due_var = tk.StringVar(value=default_due)
        ttk.Entry(form, textvariable=self.co_due_var, width=40).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Button(frame, text="Check Out",
                   command=self._do_checkout).pack(anchor='w', pady=(10, 4))

        self.co_result_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.co_result_var,
                  foreground='#27ae60', wraplength=600).pack(anchor='w')

    def _do_checkout(self):
        book_id = self.co_book_var.get().strip()
        user_id = self.co_user_var.get().strip()
        due = self.co_due_var.get().strip()

        if not (book_id and user_id and due):
            messagebox.showerror("Missing Fields",
                                 "Book ID, user ID, and due date are required.",
                                 parent=self.window)
            return
        try:
            datetime.strptime(due, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 "Due date must be YYYY-MM-DD.",
                                 parent=self.window)
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT title, status FROM books WHERE book_id = ?",
                    (book_id,)
                )
                row = cur.fetchone()
                if not row:
                    messagebox.showerror("Not Found",
                                         f"Book '{book_id}' not found.",
                                         parent=self.window)
                    return
                title, status = row
                if status == 'checked_out':
                    messagebox.showerror("Unavailable",
                                         f"'{title}' is already checked out.",
                                         parent=self.window)
                    return
                cur.execute(
                    "INSERT INTO book_loans "
                    "(book_id, user_id, checkout_date, due_date, status, "
                    " checkout_method, staff_id) "
                    "VALUES (?, ?, ?, ?, 'active', 'staff_portal', ?)",
                    (book_id, user_id, now, due + ' 23:59:59', self.staff_id)
                )
                cur.execute(
                    "UPDATE books SET status = 'checked_out' WHERE book_id = ?",
                    (book_id,)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Checkout Failed", str(e), parent=self.window)
            return

        self.co_result_var.set(
            f"Checked out '{title}' to {user_id}, due {due}.")
        self.co_book_var.set('')
        self.co_user_var.set('')
        self._refresh_all()

    # -- Returns tab ---------------------------------------------------

    def _build_returns_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Returns")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Active loans — double-click or select and "
                           "Mark Returned.", foreground='#555'
                  ).pack(side='left')
        ttk.Button(bar, text="Refresh",
                   command=self._load_returns).pack(side='right')
        ttk.Button(bar, text="Mark Returned",
                   command=self._mark_returned).pack(side='right', padx=4)

        cols = ('loan_id', 'book_id', 'title', 'user_id', 'checkout', 'due',
                'overdue')
        self.returns_tree = ttk.Treeview(frame, columns=cols,
                                         show='headings', selectmode='browse')
        headings = [
            ('loan_id', 'Loan', 60),
            ('book_id', 'Book ID', 90),
            ('title', 'Title', 280),
            ('user_id', 'User', 120),
            ('checkout', 'Checkout', 130),
            ('due', 'Due', 110),
            ('overdue', 'Overdue', 90),
        ]
        for key, title, width in headings:
            self.returns_tree.heading(key, text=title)
            self.returns_tree.column(key, width=width,
                                     anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.returns_tree.yview)
        self.returns_tree.configure(yscrollcommand=vsb.set)
        self.returns_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.returns_tree.tag_configure('overdue', background='#f9d6d5')
        self.returns_tree.bind('<Double-1>',
                               lambda _e: self._mark_returned())

    def _load_returns(self):
        for i in self.returns_tree.get_children():
            self.returns_tree.delete(i)
        today = datetime.now()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT l.loan_id, l.book_id, b.title, l.user_id, "
                    "       l.checkout_date, l.due_date "
                    "FROM book_loans l "
                    "LEFT JOIN books b ON b.book_id = l.book_id "
                    "WHERE l.status = 'active' "
                    "ORDER BY l.due_date"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for loan_id, book_id, title, user_id, checkout, due in rows:
            overdue = ''
            tag = ()
            try:
                d = datetime.strptime(due[:19], '%Y-%m-%d %H:%M:%S')
                if d < today:
                    days = (today - d).days
                    overdue = f"{days}d"
                    tag = ('overdue',)
            except Exception:
                pass
            self.returns_tree.insert('', 'end', iid=str(loan_id), values=(
                loan_id, book_id, title or '?', user_id,
                (checkout or '')[:16], (due or '')[:10], overdue
            ), tags=tag)
        self.status_var.set(f"{len(rows)} active loan(s).")

    def _mark_returned(self):
        sel = self.returns_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a loan to mark returned.",
                                parent=self.window)
            return
        loan_id = int(sel[0])

        fine_rate = 0.0
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT setting_value FROM library_settings "
                    "WHERE setting_name = 'fine_per_day'"
                )
                row = cur.fetchone()
                if row:
                    try:
                        fine_rate = float(row[0])
                    except ValueError:
                        fine_rate = 0.0

                cur.execute(
                    "SELECT book_id, due_date FROM book_loans WHERE loan_id = ?",
                    (loan_id,)
                )
                loan_row = cur.fetchone()
                if not loan_row:
                    return
                book_id, due = loan_row

                today = datetime.now()
                fine = 0.0
                try:
                    d = datetime.strptime(due[:19], '%Y-%m-%d %H:%M:%S')
                    if today > d:
                        fine = (today - d).days * fine_rate
                except Exception:
                    pass

                cur.execute(
                    "UPDATE book_loans SET return_date = ?, status = 'returned', "
                    "       fine_amount = ? WHERE loan_id = ?",
                    (today.strftime('%Y-%m-%d %H:%M:%S'), fine, loan_id)
                )
                cur.execute(
                    "UPDATE books SET status = 'available' WHERE book_id = ?",
                    (book_id,)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Return Failed", str(e), parent=self.window)
            return

        if fine > 0:
            messagebox.showinfo("Returned (Late)",
                                f"Returned. Fine applied: {fine:.2f}",
                                parent=self.window)
        else:
            messagebox.showinfo("Returned",
                                "Book returned. No fine.",
                                parent=self.window)
        self._refresh_all()

    # -- Loans tab -----------------------------------------------------

    def _build_loans_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="All Loans")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Filter:").pack(side='left', padx=(0, 4))
        self.loans_filter_var = tk.StringVar(value='active')
        ttk.Combobox(bar, textvariable=self.loans_filter_var,
                     values=['active', 'returned', 'all'],
                     state='readonly', width=14
                     ).pack(side='left')
        ttk.Button(bar, text="Apply",
                   command=self._load_loans).pack(side='left', padx=4)

        cols = ('loan_id', 'book_id', 'title', 'user_id', 'checkout', 'due',
                'return', 'status', 'fine')
        self.loans_tree = ttk.Treeview(frame, columns=cols,
                                       show='headings', selectmode='browse')
        headings = [
            ('loan_id', 'Loan', 60),
            ('book_id', 'Book', 90),
            ('title', 'Title', 240),
            ('user_id', 'User', 110),
            ('checkout', 'Checkout', 100),
            ('due', 'Due', 100),
            ('return', 'Returned', 100),
            ('status', 'Status', 80),
            ('fine', 'Fine', 60),
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

    def _load_loans(self):
        for i in self.loans_tree.get_children():
            self.loans_tree.delete(i)
        filt = self.loans_filter_var.get()
        sql = (
            "SELECT l.loan_id, l.book_id, b.title, l.user_id, "
            "       l.checkout_date, l.due_date, l.return_date, l.status, "
            "       l.fine_amount "
            "FROM book_loans l LEFT JOIN books b ON b.book_id = l.book_id "
        )
        if filt == 'active':
            sql += "WHERE l.status = 'active' "
        elif filt == 'returned':
            sql += "WHERE l.status = 'returned' "
        sql += "ORDER BY l.checkout_date DESC LIMIT 500"
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for loan_id, book_id, title, user_id, ch, du, ret, st, fine in rows:
            self.loans_tree.insert('', 'end', values=(
                loan_id, book_id, title or '?', user_id,
                (ch or '')[:10], (du or '')[:10], (ret or '')[:10],
                st or '',
                '' if fine in (None, 0, 0.0) else f"{fine:.2f}"
            ))

    # -- Reservations tab ----------------------------------------------

    def _build_reservations_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Reservations")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Active reservations",
                  foreground='#555').pack(side='left')
        ttk.Button(bar, text="Refresh",
                   command=self._load_reservations).pack(side='right')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel_reservation).pack(side='right', padx=4)

        cols = ('res_id', 'book_id', 'title', 'user_id', 'reserved', 'expires',
                'priority')
        self.res_tree = ttk.Treeview(frame, columns=cols,
                                     show='headings', selectmode='browse')
        headings = [
            ('res_id', 'Res ID', 60),
            ('book_id', 'Book', 100),
            ('title', 'Title', 280),
            ('user_id', 'User', 120),
            ('reserved', 'Reserved', 130),
            ('expires', 'Expires', 130),
            ('priority', 'Priority', 80),
        ]
        for key, title, width in headings:
            self.res_tree.heading(key, text=title)
            self.res_tree.column(key, width=width,
                                 anchor='w' if key == 'title' else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.res_tree.yview)
        self.res_tree.configure(yscrollcommand=vsb.set)
        self.res_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _load_reservations(self):
        for i in self.res_tree.get_children():
            self.res_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT r.reservation_id, r.book_id, b.title, r.user_id, "
                    "       r.reservation_date, r.expiry_date, r.priority_order "
                    "FROM book_reservations r "
                    "LEFT JOIN books b ON b.book_id = r.book_id "
                    "WHERE r.status = 'active' "
                    "ORDER BY r.reservation_date"
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return
        for row in rows:
            self.res_tree.insert('', 'end', iid=str(row[0]), values=(
                row[0], row[1], row[2] or '?', row[3],
                (row[4] or '')[:16], (row[5] or '')[:16], row[6]
            ))

    def _cancel_reservation(self):
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a reservation to cancel.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Cancel Reservation",
                                   "Mark this reservation cancelled?",
                                   parent=self.window):
            return
        rid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE book_reservations SET status = 'cancelled' "
                    "WHERE reservation_id = ?", (rid,)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Cancel Failed", str(e), parent=self.window)
            return
        self._load_reservations()

    # ------------------------------------------------------------------

    def _refresh_all(self):
        self._load_books()
        self._load_returns()
        self._load_loans()
        self._load_reservations()


class BookEditorDialog:
    """Add or edit a book."""

    def __init__(self, parent, book, on_save):
        self.book = book  # tuple or None
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Book" if book else "Add Book")
        self.dialog.geometry("460x520")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=12)
        frame.pack(fill='both', expand=True)

        fields = [
            ('Book ID', 'book_id', True),
            ('Title', 'title', False),
            ('Author', 'author', False),
            ('ISBN', 'isbn', False),
            ('Category', 'category', False),
            ('Location', 'location', False),
            ('Status', 'status', False),
        ]
        self.vars = {}
        for i, (label, key, is_id) in enumerate(fields):
            ttk.Label(frame, text=label + ':').grid(row=i, column=0,
                                                     sticky='w', pady=3)
            v = tk.StringVar()
            e = ttk.Entry(frame, textvariable=v, width=40)
            e.grid(row=i, column=1, sticky='w', pady=3)
            self.vars[key] = v
            # book tuple: book_id, title, author, isbn, category, location,
            # status, description
            if book:
                idx = ['book_id', 'title', 'author', 'isbn', 'category',
                       'location', 'status', 'description'].index(key)
                v.set(book[idx] if book[idx] is not None else '')
                if is_id:
                    e.configure(state='readonly')
        if not book:
            self.vars['status'].set('available')

        ttk.Label(frame, text="Description:").grid(
            row=len(fields), column=0, sticky='nw', pady=3)
        self.desc_text = tk.Text(frame, width=30, height=6, wrap='word')
        self.desc_text.grid(row=len(fields), column=1, sticky='w', pady=3)
        if book and book[7]:
            self.desc_text.insert('1.0', book[7])

        btns = ttk.Frame(frame)
        btns.grid(row=len(fields) + 1, column=0, columnspan=2,
                  pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save", command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        desc = self.desc_text.get('1.0', 'end').strip()
        if not data['book_id'] or not data['title'] or not data['author']:
            messagebox.showerror("Missing Fields",
                                 "Book ID, title, and author are required.",
                                 parent=self.dialog)
            return
        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                if self.book:
                    cur.execute(
                        "UPDATE books SET title=?, author=?, isbn=?, "
                        "       category=?, location=?, status=?, "
                        "       description=?, last_updated=? "
                        "WHERE book_id = ?",
                        (data['title'], data['author'], data['isbn'] or None,
                         data['category'], data['location'],
                         data['status'] or 'available', desc, now,
                         data['book_id'])
                    )
                else:
                    cur.execute(
                        "INSERT INTO books "
                        "(book_id, title, author, isbn, category, location, "
                        " status, description, added_date, last_updated) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (data['book_id'], data['title'], data['author'],
                         data['isbn'] or None, data['category'],
                         data['location'], data['status'] or 'available',
                         desc, now, now)
                    )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed",
                                 f"Could not save book: {e}",
                                 parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_library_staff_portal(parent, auth):
    """Module-level entry point."""
    return LibraryStaffPortal(parent, auth)
