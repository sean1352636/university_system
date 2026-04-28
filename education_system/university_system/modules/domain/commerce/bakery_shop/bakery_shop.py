"""
University Bakery Shop Management System
A GUI application built with tkinter for managing a university bakery.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The role-based discount tier is derived
from EDU_AUTH_ROLE (student → 10%, staff → 15%, admin → admin
console). There is no in-app login.

Persistence: orders live in the central `student_records.db` table
`bakery_orders`. The legacy `bakery_orders.json` sidecar file is
removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import json
import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, simpledialog


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
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


def _bakery_user_type(role: str) -> str:
    """Map an EDU_AUTH role onto the bakery's discount-tier model:
    Admin / Staff / Student / Guest."""
    r = (role or '').lower()
    if r in ('admin', 'administrator', 'superadmin'):
        return 'Admin'
    if r in ('staff', 'instructor', 'lecturer', 'faculty', 'manager', 'hr'):
        return 'Staff'
    if r in ('student',):
        return 'Student'
    return 'Guest'


# Legacy sidecar files this module used to write — superseded by the
# central student_records.db.
_LEGACY_JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "bakery_orders.json")


def _remove_legacy_files():
    here = os.path.dirname(os.path.abspath(__file__))
    targets = [
        _LEGACY_JSON_FILE,
        os.path.abspath("bakery_orders.json"),
    ]
    if os.path.isdir(here):
        for fname in os.listdir(here):
            if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
                targets.append(os.path.join(here, fname))
    for path in set(targets):
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy bakery file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy file %s", path,
                               exc_info=True)


class BakeryShop:
    def __init__(self, root):
        self.root = root
        self.root.title("University Bakery Shop")
        self.root.geometry("1100x700")
        self.root.configure(bg="#FFF8E7")

        # Color scheme (warm bakery colors)
        self.colors = {
            "primary": "#8B4513",      # Saddle brown
            "secondary": "#D2691E",    # Chocolate
            "accent": "#FFD700",       # Gold
            "background": "#FFF8E7",   # Cream
            "card": "#FFFFFF",         # White
            "text": "#3E2723",         # Dark brown
            "success": "#4CAF50",      # Green
            "danger": "#D32F2F",       # Red
        }

        # Product catalog with inventory
        self.products = {
            "Breads": {
                "White Bread":      {"price": 2.50, "stock": 50, "emoji": "🍞"},
                "Whole Wheat":      {"price": 3.00, "stock": 40, "emoji": "🍞"},
                "Baguette":         {"price": 3.50, "stock": 30, "emoji": "🥖"},
                "Croissant":        {"price": 2.75, "stock": 60, "emoji": "🥐"},
                "Bagel":            {"price": 2.00, "stock": 45, "emoji": "🥯"},
            },
            "Pastries": {
                "Chocolate Muffin": {"price": 3.25, "stock": 35, "emoji": "🧁"},
                "Blueberry Muffin": {"price": 3.25, "stock": 35, "emoji": "🧁"},
                "Cinnamon Roll":    {"price": 3.75, "stock": 25, "emoji": "🥐"},
                "Donut":            {"price": 2.25, "stock": 50, "emoji": "🍩"},
                "Danish Pastry":    {"price": 4.00, "stock": 20, "emoji": "🥐"},
            },
            "Cakes": {
                "Chocolate Cake":   {"price": 25.00, "stock": 8,  "emoji": "🍰"},
                "Vanilla Cake":     {"price": 22.00, "stock": 8,  "emoji": "🎂"},
                "Cheesecake":       {"price": 28.00, "stock": 6,  "emoji": "🍰"},
                "Cupcake":          {"price": 3.50,  "stock": 40, "emoji": "🧁"},
                "Tiramisu":         {"price": 32.00, "stock": 5,  "emoji": "🍰"},
            },
            "Cookies": {
                "Chocolate Chip":   {"price": 1.75, "stock": 70, "emoji": "🍪"},
                "Oatmeal Raisin":   {"price": 1.75, "stock": 50, "emoji": "🍪"},
                "Sugar Cookie":     {"price": 1.50, "stock": 60, "emoji": "🍪"},
                "Macaron":          {"price": 3.00, "stock": 30, "emoji": "🍪"},
                "Brownie":          {"price": 2.50, "stock": 40, "emoji": "🍫"},
            },
            "Beverages": {
                "Coffee":           {"price": 2.50, "stock": 100, "emoji": "☕"},
                "Tea":              {"price": 2.00, "stock": 80,  "emoji": "🍵"},
                "Hot Chocolate":    {"price": 3.00, "stock": 60,  "emoji": "☕"},
                "Fresh Juice":      {"price": 3.50, "stock": 40,  "emoji": "🧃"},
                "Milk":             {"price": 1.75, "stock": 50,  "emoji": "🥛"},
            },
        }

        # Shopping cart and order history
        self.cart = {}
        self.orders = []

        # Resolve identity from EDU_AUTH_* env vars (no in-app login).
        user = _get_current_user()
        self._auth_user = user
        if user:
            self.current_user = (user.get('username') or user.get('email')
                                 or user.get('user_id') or 'Unknown')
            self.user_type = _bakery_user_type(user.get('role'))
        else:
            self.current_user = None
            self.user_type = "Guest"
        logger.info("Bakery Shop starting user=%s tier=%s",
                    self.current_user or 'guest', self.user_type)

        # Ensure DB schema then load saved data.
        self._ensure_schema()
        self.load_data()

        # Build the UI
        self.create_widgets()

    # ------------------------------------------------------------------ #
    # Persistence — central student_records.db, table `bakery_orders`
    # ------------------------------------------------------------------ #
    def _connect(self):
        from education_system.university_system.infrastructure.database.db import get_connection
        return get_connection()

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bakery_orders (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id     TEXT,
                    timestamp    TEXT NOT NULL,
                    username     TEXT,
                    user_type    TEXT,
                    items_json   TEXT NOT NULL,
                    subtotal     REAL,
                    discount     REAL,
                    total        REAL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def load_data(self):
        """Load orders from the central DB into self.orders, in the
        same shape the existing GUI code expects (list of dicts)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT order_id, timestamp, username, user_type, items_json, "
                "subtotal, discount, total FROM bakery_orders ORDER BY id ASC"
            ).fetchall()
        finally:
            conn.close()
        self.orders = []
        for r in rows:
            try:
                items = json.loads(r[4]) if r[4] else {}
            except (TypeError, ValueError):
                items = {}
            self.orders.append({
                "order_id": r[0],
                "timestamp": r[1],
                "user": r[2] or "Guest",
                "user_type": r[3] or "Guest",
                "items": items,
                "subtotal": r[5] or 0,
                "discount": r[6] or 0,
                "total": r[7] or 0,
            })

    def save_data(self):
        """Persist self.orders back to the central DB. DELETE-all +
        bulk INSERT inside one transaction keeps state consistent with
        the GUI's list-mutation patterns (append/clear/etc.)."""
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM bakery_orders")
            for o in self.orders:
                conn.execute(
                    "INSERT INTO bakery_orders (order_id, timestamp, username, "
                    "user_type, items_json, subtotal, discount, total) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (o.get("order_id"), o.get("timestamp"),
                     o.get("user"), o.get("user_type"),
                     json.dumps(o.get("items", {})),
                     o.get("subtotal", 0), o.get("discount", 0),
                     o.get("total", 0)),
                )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.exception("Failed to save bakery orders")
            messagebox.showerror("Save Error", f"Could not save data: {e}")
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #
    def create_widgets(self):
        """Build all the main UI components."""
        # ----- Header -----
        header = tk.Frame(self.root, bg=self.colors["primary"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🥐 University Bakery Shop 🍞",
            font=("Georgia", 24, "bold"),
            bg=self.colors["primary"],
            fg="white",
        )
        title.pack(side="left", padx=20, pady=15)

        # User info / login
        self.user_frame = tk.Frame(header, bg=self.colors["primary"])
        self.user_frame.pack(side="right", padx=20, pady=15)

        if self.current_user:
            user_text = f"👤 {self.current_user} ({self.user_type})"
        else:
            user_text = "Guest User"
        self.user_label = tk.Label(
            self.user_frame,
            text=user_text,
            font=("Arial", 11),
            bg=self.colors["primary"],
            fg="white",
        )
        self.user_label.pack(side="left", padx=10)
        # In-app login removed — identity comes from the main university
        # system via EDU_AUTH_* env vars. Keep `self.login_btn` as a
        # disabled placeholder so any code still referencing it doesn't
        # blow up.
        self.login_btn = tk.Label(self.user_frame, text="", bg=self.colors["primary"])

        # ----- Tab system -----
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook",
            background=self.colors["background"],
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=self.colors["secondary"],
            foreground="white",
            padding=[20, 10],
            font=("Arial", 11, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["primary"])],
            foreground=[("selected", "white")],
        )

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Create tabs
        self.shop_tab = tk.Frame(self.notebook, bg=self.colors["background"])
        self.cart_tab = tk.Frame(self.notebook, bg=self.colors["background"])
        self.orders_tab = tk.Frame(self.notebook, bg=self.colors["background"])
        self.admin_tab = tk.Frame(self.notebook, bg=self.colors["background"])

        self.notebook.add(self.shop_tab, text="🛍️  Shop")
        self.notebook.add(self.cart_tab, text="🛒  Cart (0)")
        self.notebook.add(self.orders_tab, text="📋  My Orders")
        self.notebook.add(self.admin_tab, text="⚙️  Admin")

        # Build each tab
        self.build_shop_tab()
        self.build_cart_tab()
        self.build_orders_tab()
        self.build_admin_tab()

        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Welcome to University Bakery Shop!",
            bg=self.colors["primary"],
            fg="white",
            font=("Arial", 10),
            anchor="w",
            padx=10,
            pady=4,
        )
        self.status_bar.pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ #
    # Shop Tab
    # ------------------------------------------------------------------ #
    def build_shop_tab(self):
        """Build the product browsing tab."""
        # Left: category list
        left_frame = tk.Frame(self.shop_tab, bg=self.colors["background"], width=200)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        left_frame.pack_propagate(False)

        cat_label = tk.Label(
            left_frame,
            text="Categories",
            font=("Georgia", 14, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        cat_label.pack(pady=10)

        self.selected_category = tk.StringVar(value="Breads")
        for category in self.products.keys():
            btn = tk.Radiobutton(
                left_frame,
                text=category,
                variable=self.selected_category,
                value=category,
                font=("Arial", 12),
                bg=self.colors["background"],
                fg=self.colors["text"],
                selectcolor=self.colors["accent"],
                activebackground=self.colors["background"],
                indicatoron=False,
                width=18,
                height=2,
                relief="flat",
                cursor="hand2",
                command=self.refresh_products,
            )
            btn.pack(pady=3)

        # Right: product grid (scrollable)
        right_frame = tk.Frame(self.shop_tab, bg=self.colors["background"])
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Search bar
        search_frame = tk.Frame(right_frame, bg=self.colors["background"])
        search_frame.pack(fill="x", pady=(0, 10))

        tk.Label(
            search_frame,
            text="🔍 Search:",
            font=("Arial", 11),
            bg=self.colors["background"],
            fg=self.colors["text"],
        ).pack(side="left", padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.refresh_products())
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Arial", 11),
            width=30,
        )
        search_entry.pack(side="left", padx=5)

        # Scrollable canvas for product cards
        canvas_frame = tk.Frame(right_frame, bg=self.colors["background"])
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg=self.colors["background"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.products_frame = tk.Frame(self.canvas, bg=self.colors["background"])

        self.products_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.products_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.refresh_products()

    def _on_mousewheel(self, event):
        """Allow scrolling the product grid with the mouse wheel."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def refresh_products(self):
        """Repopulate the product grid based on category and search filter."""
        # Clear existing widgets
        for widget in self.products_frame.winfo_children():
            widget.destroy()

        category = self.selected_category.get()
        search = self.search_var.get().lower().strip()

        items = self.products.get(category, {})
        # Apply search filter
        if search:
            items = {k: v for k, v in items.items() if search in k.lower()}

        # Category header
        header = tk.Label(
            self.products_frame,
            text=f"  {category}  ",
            font=("Georgia", 16, "bold"),
            bg=self.colors["accent"],
            fg=self.colors["text"],
        )
        header.grid(row=0, column=0, columnspan=3, pady=10, sticky="w")

        if not items:
            tk.Label(
                self.products_frame,
                text="No products found.",
                font=("Arial", 12, "italic"),
                bg=self.colors["background"],
                fg=self.colors["text"],
            ).grid(row=1, column=0, padx=20, pady=20)
            return

        # Render product cards in a 3-column grid
        row, col = 1, 0
        for name, info in items.items():
            self.create_product_card(name, info, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

    def create_product_card(self, name, info, row, col):
        """Create an individual product card."""
        card = tk.Frame(
            self.products_frame,
            bg=self.colors["card"],
            relief="raised",
            bd=2,
            width=240,
            height=200,
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        card.grid_propagate(False)

        # Emoji
        tk.Label(
            card,
            text=info["emoji"],
            font=("Arial", 40),
            bg=self.colors["card"],
        ).pack(pady=(10, 0))

        # Name
        tk.Label(
            card,
            text=name,
            font=("Georgia", 13, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
        ).pack(pady=2)

        # Price
        tk.Label(
            card,
            text=f"${info['price']:.2f}",
            font=("Arial", 12, "bold"),
            bg=self.colors["card"],
            fg=self.colors["secondary"],
        ).pack()

        # Stock indicator
        stock = info["stock"]
        stock_color = (
            self.colors["success"] if stock > 10
            else self.colors["accent"] if stock > 0
            else self.colors["danger"]
        )
        stock_text = f"In stock: {stock}" if stock > 0 else "Out of stock"
        tk.Label(
            card,
            text=stock_text,
            font=("Arial", 9),
            bg=self.colors["card"],
            fg=stock_color,
        ).pack()

        # Add-to-cart button
        btn = tk.Button(
            card,
            text="+ Add to Cart",
            font=("Arial", 10, "bold"),
            bg=self.colors["primary"] if stock > 0 else "gray",
            fg="white",
            relief="flat",
            cursor="hand2" if stock > 0 else "arrow",
            state="normal" if stock > 0 else "disabled",
            command=lambda n=name: self.add_to_cart(n),
        )
        btn.pack(pady=8, padx=20, fill="x")

    # ------------------------------------------------------------------ #
    # Cart Tab
    # ------------------------------------------------------------------ #
    def build_cart_tab(self):
        """Build the shopping cart tab."""
        # Header
        header = tk.Label(
            self.cart_tab,
            text="🛒 Your Shopping Cart",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        # Cart items area
        self.cart_items_frame = tk.Frame(
            self.cart_tab, bg=self.colors["card"], relief="sunken", bd=2
        )
        self.cart_items_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Summary panel at the bottom
        summary_frame = tk.Frame(self.cart_tab, bg=self.colors["primary"])
        summary_frame.pack(fill="x", padx=20, pady=10)

        self.subtotal_label = tk.Label(
            summary_frame,
            text="Subtotal: $0.00",
            font=("Arial", 12),
            bg=self.colors["primary"],
            fg="white",
        )
        self.subtotal_label.pack(side="left", padx=20, pady=10)

        self.discount_label = tk.Label(
            summary_frame,
            text="Discount: $0.00",
            font=("Arial", 12),
            bg=self.colors["primary"],
            fg="white",
        )
        self.discount_label.pack(side="left", padx=20, pady=10)

        self.total_label = tk.Label(
            summary_frame,
            text="Total: $0.00",
            font=("Arial", 14, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["accent"],
        )
        self.total_label.pack(side="left", padx=20, pady=10)

        checkout_btn = tk.Button(
            summary_frame,
            text="💳 Checkout",
            font=("Arial", 12, "bold"),
            bg=self.colors["success"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.checkout,
        )
        checkout_btn.pack(side="right", padx=20, pady=10)

        clear_btn = tk.Button(
            summary_frame,
            text="🗑️ Clear",
            font=("Arial", 12, "bold"),
            bg=self.colors["danger"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.clear_cart,
        )
        clear_btn.pack(side="right", padx=5, pady=10)

        self.refresh_cart()

    def refresh_cart(self):
        """Repaint the cart contents and update totals."""
        for widget in self.cart_items_frame.winfo_children():
            widget.destroy()

        if not self.cart:
            tk.Label(
                self.cart_items_frame,
                text="Your cart is empty 🛒\nGo to the Shop tab to add some delicious treats!",
                font=("Arial", 14, "italic"),
                bg=self.colors["card"],
                fg=self.colors["text"],
            ).pack(expand=True, pady=50)
            self.update_cart_totals()
            return

        # Column headers
        headers_frame = tk.Frame(self.cart_items_frame, bg=self.colors["secondary"])
        headers_frame.pack(fill="x")

        for text, width in [("Item", 30), ("Price", 12), ("Quantity", 18), ("Subtotal", 12), ("", 10)]:
            tk.Label(
                headers_frame,
                text=text,
                font=("Arial", 11, "bold"),
                bg=self.colors["secondary"],
                fg="white",
                width=width,
                anchor="w",
                padx=5,
                pady=8,
            ).pack(side="left")

        # Item rows
        for item_name, qty in list(self.cart.items()):
            self.create_cart_row(item_name, qty)

        self.update_cart_totals()

    def create_cart_row(self, item_name, qty):
        """Create one row in the cart for a given item."""
        # Look up the price from the catalog
        price = 0
        emoji = ""
        for category in self.products.values():
            if item_name in category:
                price = category[item_name]["price"]
                emoji = category[item_name]["emoji"]
                break

        row = tk.Frame(self.cart_items_frame, bg=self.colors["card"])
        row.pack(fill="x", pady=2)

        tk.Label(
            row,
            text=f"{emoji} {item_name}",
            font=("Arial", 11),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=30,
            anchor="w",
            padx=5,
            pady=8,
        ).pack(side="left")

        tk.Label(
            row,
            text=f"${price:.2f}",
            font=("Arial", 11),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=12,
            anchor="w",
        ).pack(side="left")

        # Quantity controls
        qty_frame = tk.Frame(row, bg=self.colors["card"], width=120)
        qty_frame.pack(side="left", padx=20)

        tk.Button(
            qty_frame,
            text="-",
            font=("Arial", 10, "bold"),
            bg=self.colors["secondary"],
            fg="white",
            width=2,
            relief="flat",
            cursor="hand2",
            command=lambda: self.update_cart_qty(item_name, -1),
        ).pack(side="left", padx=2)

        tk.Label(
            qty_frame,
            text=str(qty),
            font=("Arial", 11, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
            width=4,
        ).pack(side="left")

        tk.Button(
            qty_frame,
            text="+",
            font=("Arial", 10, "bold"),
            bg=self.colors["secondary"],
            fg="white",
            width=2,
            relief="flat",
            cursor="hand2",
            command=lambda: self.update_cart_qty(item_name, 1),
        ).pack(side="left", padx=2)

        tk.Label(
            row,
            text=f"${price * qty:.2f}",
            font=("Arial", 11, "bold"),
            bg=self.colors["card"],
            fg=self.colors["secondary"],
            width=12,
            anchor="w",
        ).pack(side="left", padx=10)

        tk.Button(
            row,
            text="✕",
            font=("Arial", 10, "bold"),
            bg=self.colors["danger"],
            fg="white",
            relief="flat",
            cursor="hand2",
            width=3,
            command=lambda: self.remove_from_cart(item_name),
        ).pack(side="left", padx=5)

    # ------------------------------------------------------------------ #
    # Cart logic
    # ------------------------------------------------------------------ #
    def add_to_cart(self, item_name):
        """Add one unit of an item to the cart, respecting stock."""
        # Get stock for this item
        stock = 0
        for category in self.products.values():
            if item_name in category:
                stock = category[item_name]["stock"]
                break

        current_qty = self.cart.get(item_name, 0)
        if current_qty >= stock:
            messagebox.showwarning("Stock Limit", f"Only {stock} units of {item_name} available!")
            return

        self.cart[item_name] = current_qty + 1
        self.update_cart_tab_title()
        self.set_status(f"Added {item_name} to cart!")

    def update_cart_qty(self, item_name, change):
        """Increase or decrease the quantity of an item in the cart."""
        if item_name not in self.cart:
            return

        new_qty = self.cart[item_name] + change

        if new_qty <= 0:
            del self.cart[item_name]
        else:
            # Check stock limit
            stock = 0
            for category in self.products.values():
                if item_name in category:
                    stock = category[item_name]["stock"]
                    break
            if new_qty > stock:
                messagebox.showwarning("Stock Limit", f"Only {stock} units available!")
                return
            self.cart[item_name] = new_qty

        self.refresh_cart()
        self.update_cart_tab_title()

    def remove_from_cart(self, item_name):
        """Remove an item entirely from the cart."""
        if item_name in self.cart:
            del self.cart[item_name]
            self.refresh_cart()
            self.update_cart_tab_title()
            self.set_status(f"Removed {item_name} from cart")

    def clear_cart(self):
        """Empty the cart after confirmation."""
        if not self.cart:
            return
        if messagebox.askyesno("Clear Cart", "Are you sure you want to clear the cart?"):
            self.cart.clear()
            self.refresh_cart()
            self.update_cart_tab_title()
            self.set_status("Cart cleared")

    def update_cart_tab_title(self):
        """Reflect the cart item count in the tab label."""
        count = sum(self.cart.values())
        self.notebook.tab(1, text=f"🛒  Cart ({count})")
        self.update_cart_totals()

    def update_cart_totals(self):
        """Recompute subtotal, discount, and total."""
        subtotal = 0
        for item_name, qty in self.cart.items():
            for category in self.products.values():
                if item_name in category:
                    subtotal += category[item_name]["price"] * qty
                    break

        # Discount based on user type
        discount_rate = 0
        if self.user_type == "Student":
            discount_rate = 0.10  # 10% off
        elif self.user_type == "Staff":
            discount_rate = 0.15  # 15% off

        discount = subtotal * discount_rate
        total = subtotal - discount

        self.subtotal_label.config(text=f"Subtotal: ${subtotal:.2f}")
        self.discount_label.config(
            text=f"Discount ({self.user_type}): ${discount:.2f}"
        )
        self.total_label.config(text=f"Total: ${total:.2f}")

    def checkout(self):
        """Finalize the order, decrement stock, and save."""
        if not self.cart:
            messagebox.showinfo("Empty Cart", "Your cart is empty!")
            return

        if self.user_type == "Guest":
            if not messagebox.askyesno(
                "Login Recommended",
                "You're checking out as a guest.\nLogin as Student or Staff to get a discount.\n\nContinue as guest?",
            ):
                return

        # Compute totals
        subtotal = sum(
            self.products[cat][item]["price"] * qty
            for item, qty in self.cart.items()
            for cat in self.products
            if item in self.products[cat]
        )

        discount_rate = 0.10 if self.user_type == "Student" else 0.15 if self.user_type == "Staff" else 0
        discount = subtotal * discount_rate
        total = subtotal - discount

        # Build the order record
        order = {
            "order_id": f"ORD-{len(self.orders) + 1001}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": self.current_user or "Guest",
            "user_type": self.user_type,
            "items": dict(self.cart),
            "subtotal": round(subtotal, 2),
            "discount": round(discount, 2),
            "total": round(total, 2),
        }

        # Decrement stock
        for item_name, qty in self.cart.items():
            for category in self.products.values():
                if item_name in category:
                    category[item_name]["stock"] -= qty
                    break

        self.orders.append(order)
        self.save_data()
        logger.info("Bakery order placed order_id=%s user=%s tier=%s items=%s total=%.2f",
                    order['order_id'], order['user'], order['user_type'],
                    sum(order['items'].values()), order['total'])

        # Show confirmation
        receipt = (
            f"Order Confirmed!\n\n"
            f"Order ID: {order['order_id']}\n"
            f"Time: {order['timestamp']}\n"
            f"Customer: {order['user']} ({order['user_type']})\n\n"
            f"Items:\n"
        )
        for item, qty in order["items"].items():
            receipt += f"  • {item} x {qty}\n"
        receipt += (
            f"\nSubtotal: ${order['subtotal']:.2f}\n"
            f"Discount: ${order['discount']:.2f}\n"
            f"Total: ${order['total']:.2f}\n\n"
            f"Thank you for your purchase! 🎉"
        )

        messagebox.showinfo("Order Successful", receipt)

        # Reset cart and refresh views
        self.cart.clear()
        self.refresh_cart()
        self.refresh_products()
        self.refresh_orders()
        self.update_cart_tab_title()
        self.set_status(f"Order {order['order_id']} placed successfully!")

    # ------------------------------------------------------------------ #
    # Orders Tab
    # ------------------------------------------------------------------ #
    def build_orders_tab(self):
        """Build the order history tab."""
        header = tk.Label(
            self.orders_tab,
            text="📋 Order History",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        # Treeview of orders
        tree_frame = tk.Frame(self.orders_tab, bg=self.colors["background"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = ("Order ID", "Date", "Customer", "Items", "Total")
        self.orders_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        widths = {"Order ID": 100, "Date": 150, "Customer": 150, "Items": 80, "Total": 100}
        for col in columns:
            self.orders_tree.heading(col, text=col)
            self.orders_tree.column(col, width=widths[col], anchor="w")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scroll.set)
        self.orders_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.orders_tree.bind("<Double-1>", self.show_order_details)

        info_label = tk.Label(
            self.orders_tab,
            text="💡 Double-click an order to view details",
            font=("Arial", 10, "italic"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        info_label.pack(pady=5)

        self.refresh_orders()

    def refresh_orders(self):
        """Repopulate the order history list."""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        # Filter to current user's orders if logged in (admins see everything)
        visible_orders = self.orders
        if self.current_user and self.user_type != "Admin":
            visible_orders = [o for o in self.orders if o.get("user") == self.current_user]

        for order in reversed(visible_orders):
            item_count = sum(order["items"].values())
            self.orders_tree.insert(
                "",
                "end",
                values=(
                    order["order_id"],
                    order["timestamp"],
                    f"{order['user']} ({order['user_type']})",
                    f"{item_count} items",
                    f"${order['total']:.2f}",
                ),
            )

    def show_order_details(self, event):
        """Show full details of a selected order."""
        selection = self.orders_tree.selection()
        if not selection:
            return

        order_id = self.orders_tree.item(selection[0])["values"][0]
        order = next((o for o in self.orders if o["order_id"] == order_id), None)

        if not order:
            return

        details = (
            f"Order ID: {order['order_id']}\n"
            f"Date: {order['timestamp']}\n"
            f"Customer: {order['user']} ({order['user_type']})\n\n"
            f"Items:\n"
        )
        for item, qty in order["items"].items():
            details += f"  • {item} x {qty}\n"
        details += (
            f"\nSubtotal: ${order['subtotal']:.2f}\n"
            f"Discount: ${order['discount']:.2f}\n"
            f"Total: ${order['total']:.2f}"
        )

        messagebox.showinfo(f"Order {order['order_id']}", details)

    # ------------------------------------------------------------------ #
    # Admin Tab
    # ------------------------------------------------------------------ #
    def build_admin_tab(self):
        """Build the admin dashboard."""
        header = tk.Label(
            self.admin_tab,
            text="⚙️ Admin Dashboard",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        self.admin_content = tk.Frame(self.admin_tab, bg=self.colors["background"])
        self.admin_content.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh_admin()

    def refresh_admin(self):
        """Render the admin dashboard contents."""
        for widget in self.admin_content.winfo_children():
            widget.destroy()

        if self.user_type != "Admin":
            tk.Label(
                self.admin_content,
                text="🔒 Admin access required\n\nLogin as 'admin' (password: admin123) to access this section.",
                font=("Arial", 14),
                bg=self.colors["background"],
                fg=self.colors["text"],
                justify="center",
            ).pack(expand=True, pady=50)
            return

        # Statistics row
        stats_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        stats_frame.pack(fill="x", pady=10)

        total_revenue = sum(o["total"] for o in self.orders)
        total_orders = len(self.orders)
        total_items = sum(sum(o["items"].values()) for o in self.orders)

        stats = [
            ("Total Orders", str(total_orders), self.colors["primary"]),
            ("Total Revenue", f"${total_revenue:.2f}", self.colors["success"]),
            ("Items Sold", str(total_items), self.colors["secondary"]),
        ]

        for label, value, color in stats:
            card = tk.Frame(stats_frame, bg=color, width=250, height=100)
            card.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            card.pack_propagate(False)

            tk.Label(card, text=label, font=("Arial", 11), bg=color, fg="white").pack(pady=(15, 5))
            tk.Label(card, text=value, font=("Georgia", 20, "bold"), bg=color, fg="white").pack()

        # Inventory management
        inv_label = tk.Label(
            self.admin_content,
            text="📦 Inventory Management",
            font=("Georgia", 14, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        inv_label.pack(pady=(20, 10), anchor="w")

        # Inventory table
        inv_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        inv_frame.pack(fill="both", expand=True)

        columns = ("Category", "Product", "Price", "Stock", "Status")
        inv_tree = ttk.Treeview(inv_frame, columns=columns, show="headings", height=12)

        for col in columns:
            inv_tree.heading(col, text=col)
            inv_tree.column(col, width=150, anchor="w")

        for category, items in self.products.items():
            for name, info in items.items():
                status = "✅ Good" if info["stock"] > 10 else "⚠️ Low" if info["stock"] > 0 else "❌ Out"
                inv_tree.insert(
                    "",
                    "end",
                    values=(category, name, f"${info['price']:.2f}", info["stock"], status),
                )

        scroll = ttk.Scrollbar(inv_frame, orient="vertical", command=inv_tree.yview)
        inv_tree.configure(yscrollcommand=scroll.set)
        inv_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Restock button
        btn_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(
            btn_frame,
            text="🔄 Restock All (+50 each)",
            font=("Arial", 11, "bold"),
            bg=self.colors["success"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.restock_all,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="📊 Export Sales Report",
            font=("Arial", 11, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.export_report,
        ).pack(side="left", padx=5)

    def restock_all(self):
        """Add 50 units to every product."""
        for category in self.products.values():
            for info in category.values():
                info["stock"] += 50
        messagebox.showinfo("Restocked", "All items have been restocked (+50 each)!")
        self.refresh_admin()
        self.refresh_products()

    def export_report(self):
        """Save a plain-text sales report to the working directory."""
        if not self.orders:
            messagebox.showinfo("No Data", "No orders to export!")
            return

        try:
            filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w") as f:
                f.write("=" * 60 + "\n")
                f.write("UNIVERSITY BAKERY SHOP - SALES REPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                total_revenue = sum(o["total"] for o in self.orders)
                f.write(f"Total Orders: {len(self.orders)}\n")
                f.write(f"Total Revenue: ${total_revenue:.2f}\n\n")
                f.write("-" * 60 + "\n")
                f.write("ORDER DETAILS\n")
                f.write("-" * 60 + "\n\n")

                for order in self.orders:
                    f.write(f"Order: {order['order_id']}\n")
                    f.write(f"Date: {order['timestamp']}\n")
                    f.write(f"Customer: {order['user']} ({order['user_type']})\n")
                    f.write("Items:\n")
                    for item, qty in order["items"].items():
                        f.write(f"  - {item} x {qty}\n")
                    f.write(f"Total: ${order['total']:.2f}\n")
                    f.write("-" * 40 + "\n")

            messagebox.showinfo("Export Complete", f"Sales report saved as:\n{filename}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Could not save report: {e}")

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #
    def show_login(self):
        """Show the login dialog (or log out if currently logged in)."""
        if self.current_user:
            if messagebox.askyesno("Logout", f"Logout {self.current_user}?"):
                self.current_user = None
                self.user_type = "Guest"
                self.user_label.config(text="Guest User")
                self.login_btn.config(text="Login")
                self.refresh_admin()
                self.refresh_orders()
                self.update_cart_totals()
                self.set_status("Logged out")
            return

        # Login window
        login_win = tk.Toplevel(self.root)
        login_win.title("Login")
        login_win.geometry("400x400")
        login_win.configure(bg=self.colors["background"])
        login_win.transient(self.root)
        login_win.grab_set()

        tk.Label(
            login_win,
            text="🔐 Login",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        ).pack(pady=20)

        # Username
        tk.Label(
            login_win,
            text="Username:",
            font=("Arial", 11),
            bg=self.colors["background"],
            fg=self.colors["text"],
        ).pack(pady=5)
        username_entry = tk.Entry(login_win, font=("Arial", 11), width=30)
        username_entry.pack(pady=5)

        # Password
        tk.Label(
            login_win,
            text="Password:",
            font=("Arial", 11),
            bg=self.colors["background"],
            fg=self.colors["text"],
        ).pack(pady=5)
        password_entry = tk.Entry(login_win, font=("Arial", 11), width=30, show="*")
        password_entry.pack(pady=5)

        # User type selector
        tk.Label(
            login_win,
            text="User Type:",
            font=("Arial", 11),
            bg=self.colors["background"],
            fg=self.colors["text"],
        ).pack(pady=5)
        user_type_var = tk.StringVar(value="Student")
        type_frame = tk.Frame(login_win, bg=self.colors["background"])
        type_frame.pack(pady=5)
        for ut in ["Student", "Staff"]:
            tk.Radiobutton(
                type_frame,
                text=ut,
                variable=user_type_var,
                value=ut,
                font=("Arial", 10),
                bg=self.colors["background"],
            ).pack(side="left", padx=10)

        # Demo credentials hint
        tk.Label(
            login_win,
            text="Demo: Student (10% off), Staff (15% off)\nAdmin: username='admin', password='admin123'",
            font=("Arial", 9, "italic"),
            bg=self.colors["background"],
            fg=self.colors["secondary"],
        ).pack(pady=10)

        def do_login():
            username = username_entry.get().strip()
            password = password_entry.get().strip()

            if not username:
                messagebox.showerror("Error", "Please enter a username", parent=login_win)
                return

            # Admin credentials
            if username.lower() == "admin" and password == "admin123":
                self.current_user = "Admin"
                self.user_type = "Admin"
            else:
                # Any non-empty creds accepted in demo (a real app would validate)
                self.current_user = username
                self.user_type = user_type_var.get()

            self.user_label.config(text=f"👤 {self.current_user} ({self.user_type})")
            self.login_btn.config(text="Logout")
            self.refresh_admin()
            self.refresh_orders()
            self.update_cart_totals()
            self.set_status(f"Welcome, {self.current_user}!")
            login_win.destroy()

        tk.Button(
            login_win,
            text="Login",
            font=("Arial", 11, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief="flat",
            padx=30,
            pady=8,
            cursor="hand2",
            command=do_login,
        ).pack(pady=15)

        username_entry.focus()
        # Allow pressing Enter to submit
        login_win.bind("<Return>", lambda e: do_login())

    # ------------------------------------------------------------------ #
    # Misc helpers
    # ------------------------------------------------------------------ #
    def set_status(self, message):
        """Update the bottom status bar."""
        self.status_bar.config(text=message)


def main():
    _remove_legacy_files()
    root = tk.Tk()
    BakeryShop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
