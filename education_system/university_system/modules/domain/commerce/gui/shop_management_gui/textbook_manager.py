"""Textbook & Course Materials module for the University Shop GUI.

Functions follow the shop_management_gui mixin pattern: each takes ``self``
(a UniversityShopGUI instance) and renders into ``self.content_frame``.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_textbook_db(self):
    """Create textbook tables if they don't exist and seed sample data."""
    try:
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
                    conn.execute(
                        "INSERT INTO textbooks (isbn, title, author, edition, publisher, year, module_code, required, price, description) VALUES (?,?,?,?,?,?,?,?,?,?)", s)
                conn.commit()
    except Exception as e:
        logger.error(f"Textbook DB init error: {e}")


def _get_textbook_user_id(self):
    if self.current_user and isinstance(self.current_user, dict):
        return self.current_user.get('student_id') or self.current_user.get('username', 'unknown')
    return 'unknown'

# ---------------------------------------------------------------------------
# Show panels
# ---------------------------------------------------------------------------

def show_textbooks_browse(self):
    """Browse all textbooks panel."""
    self.clear_content()

    row = 0
    ttk.Label(self.content_frame, text="Browse Textbooks",
              style='Title.TLabel').grid(row=row, column=0, sticky=tk.W, pady=(0, 10))

    # Search bar
    row += 1
    search_frame = ttk.Frame(self.content_frame)
    search_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
    ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=2)
    self._tb_search_entry = ttk.Entry(search_frame, width=30)
    self._tb_search_entry.pack(side=tk.LEFT, padx=2)
    ttk.Button(search_frame, text="Search", command=self._tb_do_search).pack(side=tk.LEFT, padx=5)

    ttk.Label(search_frame, text="Module:").pack(side=tk.LEFT, padx=(15, 2))
    self._tb_module_filter = ttk.Combobox(search_frame, values=["All"], state="readonly", width=10)
    self._tb_module_filter.set("All")
    self._tb_module_filter.pack(side=tk.LEFT, padx=2)
    self._tb_module_filter.bind("<<ComboboxSelected>>", lambda e: self._tb_do_search())

    row += 1
    cols = ("id", "isbn", "title", "author", "edition", "module", "required", "price")
    self._tb_browse_tree = ttk.Treeview(self.content_frame, columns=cols, show="headings", height=18)
    for c, w in zip(cols, (40, 120, 200, 150, 60, 70, 70, 70)):
        self._tb_browse_tree.heading(c, text=c.replace("_", " ").title())
        self._tb_browse_tree.column(c, width=w, minwidth=30)
    self._tb_browse_tree.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    self.content_frame.rowconfigure(row, weight=1)

    row += 1
    btn = ttk.Frame(self.content_frame)
    btn.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5)
    ttk.Button(btn, text="View Details", command=self._tb_view_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn, text="Find Used Copies", command=self._tb_find_used).pack(side=tk.LEFT, padx=5)

    self._tb_do_search()


def show_textbooks_exchange(self):
    """Used book exchange panel."""
    self.clear_content()

    row = 0
    ttk.Label(self.content_frame, text="Used Book Exchange",
              style='Title.TLabel').grid(row=row, column=0, sticky=tk.W, pady=(0, 5))
    row += 1
    ttk.Label(self.content_frame, text="Available used textbooks from other students").grid(row=row, column=0, sticky=tk.W, pady=(0, 5))

    row += 1
    cols = ("listing_id", "title", "condition", "price", "seller", "listed_date", "status")
    self._tb_exchange_tree = ttk.Treeview(self.content_frame, columns=cols, show="headings", height=18)
    for c, w in zip(cols, (60, 250, 80, 70, 100, 100, 80)):
        self._tb_exchange_tree.heading(c, text=c.replace("_", " ").title())
        self._tb_exchange_tree.column(c, width=w, minwidth=30)
    self._tb_exchange_tree.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    self.content_frame.rowconfigure(row, weight=1)

    row += 1
    btn = ttk.Frame(self.content_frame)
    btn.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5)
    ttk.Button(btn, text="Buy Selected", command=self._tb_buy_used).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn, text="Refresh", command=self._tb_load_exchange).pack(side=tk.LEFT, padx=5)

    self._tb_load_exchange()


def show_textbooks_sell(self):
    """Sell a textbook panel."""
    self.clear_content()

    ttk.Label(self.content_frame, text="Sell a Textbook",
              style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

    form = ttk.LabelFrame(self.content_frame, text="List a Textbook for Sale", padding=15)
    form.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

    row = 0
    ttk.Label(form, text="Select Textbook:").grid(row=row, column=0, sticky=tk.W, pady=3)
    self._tb_sell_combo = ttk.Combobox(form, state="readonly", width=50)
    self._tb_sell_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

    row += 1
    ttk.Label(form, text="Or enter ISBN:").grid(row=row, column=0, sticky=tk.W, pady=3)
    self._tb_sell_isbn = ttk.Entry(form, width=20)
    self._tb_sell_isbn.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

    row += 1
    ttk.Label(form, text="Condition:").grid(row=row, column=0, sticky=tk.W, pady=3)
    self._tb_sell_condition = ttk.Combobox(form, values=["like_new", "good", "fair", "poor"], state="readonly", width=15)
    self._tb_sell_condition.set("good")
    self._tb_sell_condition.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

    row += 1
    ttk.Label(form, text="Asking Price (\u00a3):").grid(row=row, column=0, sticky=tk.W, pady=3)
    self._tb_sell_price = ttk.Entry(form, width=10)
    self._tb_sell_price.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

    row += 1
    ttk.Label(form, text="Notes:").grid(row=row, column=0, sticky=tk.NW, pady=3)
    self._tb_sell_notes = tk.Text(form, width=40, height=3)
    self._tb_sell_notes.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

    row += 1
    ttk.Button(form, text="List for Sale", command=self._tb_list_for_sale).grid(
        row=row, column=1, sticky=tk.W, pady=10, padx=5)

    # Load combos
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT textbook_id, title, author FROM textbooks ORDER BY title").fetchall()
            self._tb_sell_combo['values'] = [f"{r['textbook_id']} - {r['title']} ({r['author']})" for r in rows]
            if rows:
                self._tb_sell_combo.current(0)
    except Exception:
        pass


def show_textbooks_orders(self):
    """Textbook orders panel."""
    self.clear_content()

    ttk.Label(self.content_frame, text="My Textbook Orders",
              style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

    cols = ("order_id", "title", "price", "status", "date", "role")
    self._tb_orders_tree = ttk.Treeview(self.content_frame, columns=cols, show="headings", height=18)
    for c, w in zip(cols, (60, 250, 70, 80, 130, 60)):
        self._tb_orders_tree.heading(c, text=c.title())
        self._tb_orders_tree.column(c, width=w, minwidth=30)
    self._tb_orders_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    self.content_frame.rowconfigure(1, weight=1)
    ttk.Button(self.content_frame, text="Refresh", command=self._tb_load_orders).grid(row=2, column=0, pady=5)

    self._tb_load_orders()

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _tb_do_search(self):
    tree = self._tb_browse_tree
    for item in tree.get_children():
        tree.delete(item)
    try:
        with get_connection() as conn:
            query = "SELECT * FROM textbooks WHERE 1=1"
            params = []
            search = self._tb_search_entry.get().strip()
            if search:
                query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
                s = f"%{escape_like(search)}%"
                params.extend([s, s, s])
            mod = self._tb_module_filter.get()
            if mod and mod != "All":
                query += " AND module_code = ?"
                params.append(mod)
            query += " ORDER BY title"
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                tree.insert("", tk.END, values=(
                    r["textbook_id"], r["isbn"], r["title"], r["author"],
                    r["edition"], r["module_code"],
                    "Required" if r["required"] else "Optional",
                    f"\u00a3{r['price']:.2f}",
                ))
            all_mods = conn.execute(
                "SELECT DISTINCT module_code FROM textbooks WHERE module_code != '' ORDER BY module_code"
            ).fetchall()
            self._tb_module_filter['values'] = ["All"] + [r[0] for r in all_mods]
    except Exception as e:
        logger.debug(f"Textbook search: {e}")


def _tb_load_exchange(self):
    tree = self._tb_exchange_tree
    for item in tree.get_children():
        tree.delete(item)
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT tl.*, t.title FROM textbook_listings tl
                JOIN textbooks t ON tl.textbook_id = t.textbook_id
                WHERE tl.status = 'available'
                ORDER BY tl.listed_date DESC
            """).fetchall()
            for r in rows:
                tree.insert("", tk.END, values=(
                    r["listing_id"], r["title"], r["condition"],
                    f"\u00a3{r['price']:.2f}", r["seller_id"],
                    r["listed_date"], r["status"],
                ))
    except Exception as e:
        logger.debug(f"Exchange load: {e}")


def _tb_load_orders(self):
    tree = self._tb_orders_tree
    for item in tree.get_children():
        tree.delete(item)
    try:
        user_id = _get_textbook_user_id(self)
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
                tree.insert("", tk.END, values=(
                    r["order_id"], r["title"], f"\u00a3{r['price']:.2f}",
                    r["status"], r["order_date"], role,
                ))
    except Exception as e:
        logger.debug(f"Textbook orders: {e}")

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _tb_view_details(self):
    sel = self._tb_browse_tree.selection()
    if not sel:
        messagebox.showwarning("Warning", "Select a textbook first.")
        return
    vals = self._tb_browse_tree.item(sel[0])['values']
    try:
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


def _tb_find_used(self):
    sel = self._tb_browse_tree.selection()
    if not sel:
        messagebox.showwarning("Warning", "Select a textbook first.")
        return
    vals = self._tb_browse_tree.item(sel[0])['values']
    self.show_textbooks_exchange()
    tree = self._tb_exchange_tree
    for item in tree.get_children():
        tree.delete(item)
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT tl.*, t.title FROM textbook_listings tl
                JOIN textbooks t ON tl.textbook_id = t.textbook_id
                WHERE tl.textbook_id = ? AND tl.status = 'available'
                ORDER BY tl.price ASC
            """, (vals[0],)).fetchall()
            for r in rows:
                tree.insert("", tk.END, values=(
                    r["listing_id"], r["title"], r["condition"],
                    f"\u00a3{r['price']:.2f}", r["seller_id"],
                    r["listed_date"], r["status"],
                ))
            if not rows:
                messagebox.showinfo("Info", "No used copies available for this textbook.")
    except Exception as e:
        logger.debug(f"Find used: {e}")


def _tb_buy_used(self):
    sel = self._tb_exchange_tree.selection()
    if not sel:
        messagebox.showwarning("Warning", "Select a listing to buy.")
        return
    vals = self._tb_exchange_tree.item(sel[0])['values']
    listing_id, title, price = vals[0], vals[1], vals[3]
    if messagebox.askyesno("Confirm Purchase", f"Buy '{title}' for {price}?"):
        try:
            user_id = _get_textbook_user_id(self)
            with get_connection() as conn:
                listing = conn.execute(
                    "SELECT * FROM textbook_listings WHERE listing_id = ?", (listing_id,)
                ).fetchone()
                if not listing or listing['status'] != 'available':
                    messagebox.showerror("Error", "Listing no longer available.")
                    return
                if listing['seller_id'] == user_id:
                    messagebox.showerror("Error", "You cannot buy your own listing.")
                    return
                conn.execute(
                    "INSERT INTO textbook_orders (listing_id, buyer_id, seller_id, price, status) VALUES (?, ?, ?, ?, 'pending')",
                    (listing_id, user_id, listing['seller_id'], listing['price']),
                )
                conn.execute("UPDATE textbook_listings SET status='sold' WHERE listing_id=?", (listing_id,))
                conn.commit()
            messagebox.showinfo("Success", "Order placed! Contact the seller to arrange pickup.")
            self._tb_load_exchange()
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")


def _tb_list_for_sale(self):
    book_val = self._tb_sell_combo.get()
    price_str = self._tb_sell_price.get().strip()
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
        try:
            textbook_id = int(book_val.split(" - ")[0])
        except (ValueError, IndexError):
            pass

    isbn = self._tb_sell_isbn.get().strip()
    if not textbook_id and isbn:
        try:
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
        user_id = _get_textbook_user_id(self)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO textbook_listings (textbook_id, seller_id, condition, price, notes, status) VALUES (?, ?, ?, ?, ?, 'available')",
                (textbook_id, user_id, self._tb_sell_condition.get(), price,
                 self._tb_sell_notes.get("1.0", tk.END).strip()),
            )
            conn.commit()
        messagebox.showinfo("Success", "Textbook listed for sale!")
        self._tb_sell_price.delete(0, tk.END)
        self._tb_sell_notes.delete("1.0", tk.END)
    except Exception as e:
        messagebox.showerror("Error", f"Failed: {e}")
