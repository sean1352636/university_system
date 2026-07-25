import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime
from education_system.systems.university.infrastructure.sql_safety import escape_like

logger = logging.getLogger(__name__)


class TextbookStoreGUI:
    """Course materials and textbook listing, exchange, and purchasing system."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Textbook & Course Materials")
        self.window.geometry("1100x700")

        try:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        try:
            from education_system.systems.university.infrastructure.i18n import get_text as _t
            self._t = _t
        except ImportError:
            self._t = lambda key, **kw: key

        self._init_db()
        self._build_ui()
        self._load_data()

    def _init_db(self):
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS textbooks (
                    textbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    edition TEXT DEFAULT '',
                    publisher TEXT DEFAULT '',
                    year INTEGER,
                    module_code TEXT DEFAULT '',
                    required INTEGER DEFAULT 1,
                    price REAL DEFAULT 0.0,
                    description TEXT DEFAULT ''
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS textbook_listings (
                    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    textbook_id INTEGER,
                    seller_id TEXT NOT NULL,
                    condition TEXT DEFAULT 'good',
                    price REAL NOT NULL,
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'available',
                    listed_date TEXT DEFAULT (date('now')),
                    FOREIGN KEY (textbook_id) REFERENCES textbooks(textbook_id)
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS textbook_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER,
                    buyer_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    order_date TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (listing_id) REFERENCES textbook_listings(listing_id)
                )""")
                # Seed sample textbooks if empty
                count = conn.execute("SELECT COUNT(*) FROM textbooks").fetchone()[0]
                if count == 0:
                    samples = [
                        ("978-0132350884", "Clean Code", "Robert C. Martin", "1st", "Prentice Hall", 2008, "CS101", 1, 35.99, "A Handbook of Agile Software Craftsmanship"),
                        ("978-0201633610", "Design Patterns", "Gang of Four", "1st", "Addison-Wesley", 1994, "CS201", 1, 45.00, "Elements of Reusable Object-Oriented Software"),
                        ("978-0262033848", "Introduction to Algorithms", "Cormen et al.", "3rd", "MIT Press", 2009, "CS102", 1, 80.00, "Comprehensive algorithms textbook"),
                        ("978-0134685991", "Effective Java", "Joshua Bloch", "3rd", "Addison-Wesley", 2018, "CS201", 0, 40.00, "Best practices for Java"),
                        ("978-1449355739", "Learning Python", "Mark Lutz", "5th", "O'Reilly", 2013, "CS101", 0, 55.00, "Comprehensive Python guide"),
                        ("978-0321125217", "Domain-Driven Design", "Eric Evans", "1st", "Addison-Wesley", 2003, "CS301", 1, 50.00, "Tackling Complexity in the Heart of Software"),
                        ("978-0596517748", "JavaScript: The Good Parts", "Douglas Crockford", "1st", "O'Reilly", 2008, "WEB101", 0, 25.00, "Essential JavaScript concepts"),
                        ("978-1491950357", "Designing Data-Intensive Applications", "Martin Kleppmann", "1st", "O'Reilly", 2017, "DS201", 1, 45.00, "Big ideas behind reliable systems"),
                    ]
                    for s in samples:
                        conn.execute("INSERT INTO textbooks (isbn, title, author, edition, publisher, year, module_code, required, price, description) VALUES (?,?,?,?,?,?,?,?,?,?)", s)
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

        self._build_browse_tab()
        self._build_my_courses_tab()
        self._build_exchange_tab()
        self._build_sell_tab()
        self._build_orders_tab()

    def _build_browse_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Browse Textbooks")

        # Search bar
        search_frame = ttk.Frame(tab)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=2)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="Search", command=self._search_textbooks).pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="Module:").pack(side=tk.LEFT, padx=(15, 2))
        self.module_filter = ttk.Combobox(search_frame, values=["All"], state="readonly", width=10)
        self.module_filter.set("All")
        self.module_filter.pack(side=tk.LEFT, padx=2)
        self.module_filter.bind("<<ComboboxSelected>>", lambda e: self._search_textbooks())

        cols = ("id", "isbn", "title", "author", "edition", "module", "required", "price")
        self.browse_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (40, 120, 200, 150, 60, 70, 70, 70)):
            self.browse_tree.heading(c, text=c.replace("_", " ").title())
            self.browse_tree.column(c, width=w, minwidth=30)
        self.browse_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="View Details", command=self._view_textbook_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Find Used Copies", command=self._find_used_copies).pack(side=tk.LEFT, padx=5)

    def _build_my_courses_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Course Books")

        ttk.Label(tab, text="Required & recommended books for your enrolled modules",
                  font=("", 10)).pack(anchor=tk.W, padx=10, pady=5)

        cols = ("module", "isbn", "title", "author", "required", "price", "used_available")
        self.course_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (70, 120, 200, 150, 70, 70, 100)):
            self.course_tree.heading(c, text=c.replace("_", " ").title())
            self.course_tree.column(c, width=w, minwidth=30)
        self.course_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Button(tab, text="Refresh", command=self._load_my_course_books).pack(pady=5)

    def _build_exchange_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Used Book Exchange")

        ttk.Label(tab, text="Available used textbooks from other students",
                  font=("", 10)).pack(anchor=tk.W, padx=10, pady=5)

        cols = ("listing_id", "title", "condition", "price", "seller", "listed_date", "status")
        self.exchange_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (60, 250, 80, 70, 100, 100, 80)):
            self.exchange_tree.heading(c, text=c.replace("_", " ").title())
            self.exchange_tree.column(c, width=w, minwidth=30)
        self.exchange_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Buy Selected", command=self._buy_used).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_exchange).pack(side=tk.LEFT, padx=5)

    def _build_sell_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sell a Book")

        form = ttk.LabelFrame(tab, text="List a Textbook for Sale", padding=15)
        form.pack(fill=tk.X, padx=10, pady=10)

        row = 0
        ttk.Label(form, text="Select Textbook:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.sell_book_combo = ttk.Combobox(form, state="readonly", width=50)
        self.sell_book_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Or enter ISBN:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.sell_isbn = ttk.Entry(form, width=20)
        self.sell_isbn.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Condition:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.sell_condition = ttk.Combobox(form, values=["like_new", "good", "fair", "poor"], state="readonly", width=15)
        self.sell_condition.set("good")
        self.sell_condition.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Asking Price (\u00a3):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.sell_price = ttk.Entry(form, width=10)
        self.sell_price.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Notes:").grid(row=row, column=0, sticky=tk.NW, pady=3)
        self.sell_notes = tk.Text(form, width=40, height=3)
        self.sell_notes.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Button(form, text="List for Sale", command=self._list_for_sale).grid(
            row=row, column=1, sticky=tk.W, pady=10, padx=5)

    def _build_orders_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Orders")

        cols = ("order_id", "title", "price", "status", "date", "role")
        self.orders_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (60, 250, 70, 80, 130, 60)):
            self.orders_tree.heading(c, text=c.title())
            self.orders_tree.column(c, width=w, minwidth=30)
        self.orders_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Button(tab, text="Refresh", command=self._load_orders).pack(pady=5)

    def _load_data(self):
        self._search_textbooks()
        self._load_my_course_books()
        self._load_exchange()
        self._load_sell_combos()
        self._load_orders()

    def _search_textbooks(self):
        for item in self.browse_tree.get_children():
            self.browse_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                query = "SELECT * FROM textbooks WHERE 1=1"
                params = []
                search = self.search_entry.get().strip()
                if search:
                    query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
                    s = f"%{escape_like(search)}%"
                    params.extend([s, s, s])
                mod = self.module_filter.get()
                if mod and mod != "All":
                    query += " AND module_code = ?"
                    params.append(mod)
                query += " ORDER BY title"
                rows = conn.execute(query, params).fetchall()
                modules = set()
                for r in rows:
                    self.browse_tree.insert("", tk.END, values=(
                        r["textbook_id"], r["isbn"], r["title"], r["author"],
                        r["edition"], r["module_code"],
                        "Required" if r["required"] else "Optional",
                        f"\u00a3{r['price']:.2f}"
                    ))
                    if r["module_code"]:
                        modules.add(r["module_code"])
                # Update module filter
                all_mods = conn.execute("SELECT DISTINCT module_code FROM textbooks WHERE module_code != '' ORDER BY module_code").fetchall()
                self.module_filter['values'] = ["All"] + [r[0] for r in all_mods]
        except Exception as e:
            logger.debug(f"Search: {e}")

    def _load_my_course_books(self):
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            student_id = self._get_user_id()
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT t.*, (SELECT COUNT(*) FROM textbook_listings tl WHERE tl.textbook_id = t.textbook_id AND tl.status = 'available') as used_count
                    FROM textbooks t
                    WHERE t.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
                    ORDER BY t.required DESC, t.module_code, t.title
                """, (student_id,)).fetchall()
                for r in rows:
                    self.course_tree.insert("", tk.END, values=(
                        r["module_code"], r["isbn"], r["title"], r["author"],
                        "Required" if r["required"] else "Optional",
                        f"\u00a3{r['price']:.2f}",
                        f"{r['used_count']} used" if r['used_count'] > 0 else "None"
                    ))
                if not rows:
                    self.course_tree.insert("", tk.END, values=("", "", "No enrolled modules found", "", "", "", ""))
        except Exception as e:
            logger.debug(f"Course books: {e}")

    def _load_exchange(self):
        for item in self.exchange_tree.get_children():
            self.exchange_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT tl.*, t.title FROM textbook_listings tl
                    JOIN textbooks t ON tl.textbook_id = t.textbook_id
                    WHERE tl.status = 'available'
                    ORDER BY tl.listed_date DESC
                """).fetchall()
                for r in rows:
                    self.exchange_tree.insert("", tk.END, values=(
                        r["listing_id"], r["title"], r["condition"],
                        f"\u00a3{r['price']:.2f}", r["seller_id"],
                        r["listed_date"], r["status"]
                    ))
        except Exception as e:
            logger.debug(f"Exchange: {e}")

    def _load_sell_combos(self):
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute("SELECT textbook_id, title, author FROM textbooks ORDER BY title").fetchall()
                vals = [f"{r['textbook_id']} - {r['title']} ({r['author']})" for r in rows]
                self.sell_book_combo['values'] = vals
                if vals:
                    self.sell_book_combo.current(0)
        except Exception as e:
            logger.debug(f"Sell combos: {e}")

    def _load_orders(self):
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            user_id = self._get_user_id()
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT o.*, t.title FROM textbook_orders o
                    JOIN textbook_listings tl ON o.listing_id = tl.listing_id
                    JOIN textbooks t ON tl.textbook_id = t.textbook_id
                    WHERE o.buyer_id = ? OR o.seller_id = ?
                    ORDER BY o.order_date DESC
                """, (user_id, user_id)).fetchall()
                for r in rows:
                    role = "Buyer" if r["buyer_id"] == user_id else "Seller"
                    self.orders_tree.insert("", tk.END, values=(
                        r["order_id"], r["title"], f"\u00a3{r['price']:.2f}",
                        r["status"], r["order_date"], role
                    ))
        except Exception as e:
            logger.debug(f"Orders: {e}")

    def _view_textbook_details(self):
        sel = self.browse_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a textbook first.")
            return
        vals = self.browse_tree.item(sel[0])['values']
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM textbooks WHERE textbook_id = ?", (vals[0],)).fetchone()
                if row:
                    info = (
                        f"Title: {row['title']}\n"
                        f"Author: {row['author']}\n"
                        f"ISBN: {row['isbn']}\n"
                        f"Edition: {row['edition']}\n"
                        f"Publisher: {row['publisher']}\n"
                        f"Year: {row['year']}\n"
                        f"Module: {row['module_code']}\n"
                        f"Type: {'Required' if row['required'] else 'Optional'}\n"
                        f"Price: \u00a3{row['price']:.2f}\n\n"
                        f"{row['description']}"
                    )
                    messagebox.showinfo("Textbook Details", info)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _find_used_copies(self):
        sel = self.browse_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a textbook first.")
            return
        vals = self.browse_tree.item(sel[0])['values']
        textbook_id = vals[0]
        # Switch to exchange tab and filter
        self.notebook.select(2)
        # Reload with filter
        for item in self.exchange_tree.get_children():
            self.exchange_tree.delete(item)
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT tl.*, t.title FROM textbook_listings tl
                    JOIN textbooks t ON tl.textbook_id = t.textbook_id
                    WHERE tl.textbook_id = ? AND tl.status = 'available'
                    ORDER BY tl.price ASC
                """, (textbook_id,)).fetchall()
                for r in rows:
                    self.exchange_tree.insert("", tk.END, values=(
                        r["listing_id"], r["title"], r["condition"],
                        f"\u00a3{r['price']:.2f}", r["seller_id"],
                        r["listed_date"], r["status"]
                    ))
                if not rows:
                    messagebox.showinfo("Info", "No used copies available for this textbook.")
        except Exception as e:
            logger.debug(f"Find used: {e}")

    def _buy_used(self):
        sel = self.exchange_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a listing to buy.")
            return
        vals = self.exchange_tree.item(sel[0])['values']
        listing_id = vals[0]
        price = vals[3]
        if messagebox.askyesno("Confirm Purchase", f"Buy '{vals[1]}' for {price}?"):
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                user_id = self._get_user_id()
                with get_connection() as conn:
                    listing = conn.execute("SELECT * FROM textbook_listings WHERE listing_id = ?", (listing_id,)).fetchone()
                    if not listing or listing['status'] != 'available':
                        messagebox.showerror("Error", "Listing no longer available.")
                        return
                    if listing['seller_id'] == user_id:
                        messagebox.showerror("Error", "You cannot buy your own listing.")
                        return
                    conn.execute("INSERT INTO textbook_orders (listing_id, buyer_id, seller_id, price, status) VALUES (?, ?, ?, ?, 'pending')",
                        (listing_id, user_id, listing['seller_id'], listing['price']))
                    conn.execute("UPDATE textbook_listings SET status='sold' WHERE listing_id=?", (listing_id,))
                    conn.commit()
                messagebox.showinfo("Success", "Order placed! Contact the seller to arrange pickup.")
                self._load_exchange()
                self._load_orders()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")

    def _list_for_sale(self):
        book_val = self.sell_book_combo.get()
        price_str = self.sell_price.get().strip()
        if not price_str:
            messagebox.showwarning("Warning", "Enter an asking price.")
            return
        try:
            price = float(price_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid price.")
            return

        textbook_id = None
        if book_val:
            textbook_id = int(book_val.split(" - ")[0])

        # Handle ISBN entry for unlisted books
        isbn = self.sell_isbn.get().strip()
        if not textbook_id and isbn:
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    row = conn.execute("SELECT textbook_id FROM textbooks WHERE isbn = ?", (isbn,)).fetchone()
                    if row:
                        textbook_id = row['textbook_id']
                    else:
                        messagebox.showerror("Error", "ISBN not found in the textbook catalog.")
                        return
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

        if not textbook_id:
            messagebox.showwarning("Warning", "Select a textbook or enter an ISBN.")
            return

        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            user_id = self._get_user_id()
            with get_connection() as conn:
                conn.execute("""INSERT INTO textbook_listings
                    (textbook_id, seller_id, condition, price, notes, status)
                    VALUES (?, ?, ?, ?, ?, 'available')""",
                    (textbook_id, user_id, self.sell_condition.get(), price,
                     self.sell_notes.get("1.0", tk.END).strip()))
                conn.commit()
            messagebox.showinfo("Success", "Textbook listed for sale!")
            self.sell_price.delete(0, tk.END)
            self.sell_notes.delete("1.0", tk.END)
            self._load_exchange()
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")


def launch_textbook_gui(parent=None):
    return TextbookStoreGUI(parent=parent)
