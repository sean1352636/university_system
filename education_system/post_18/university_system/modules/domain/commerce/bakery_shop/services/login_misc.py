"""LoginMiscMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class LoginMiscMixin:
    PRODUCTION_SHELF_LIFE = {
        "Breads": 3, "Pastries": 2, "Cakes": 4,
        "Cookies": 7, "Beverages": 1,
    }

    PRODUCTION_BATCH_SIZES = {
        "Breads": 12, "Pastries": 12, "Cakes": 4,
        "Cookies": 24, "Beverages": 1,
    }

    def show_login(self):
        """Show the login dialog (or log out if currently logged in)."""
        if self.current_user:
            if messagebox.askyesno("Logout", f"Logout {self.current_user}?"):
                self.current_user = None
                self.user_type = "Guest"
                self.user_label.config(text="Guest User")
                self.login_btn.config(text="Login")
                self.refresh_admin()
                self.refresh_refunds()
                self.refresh_loyalty()
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
            text="Demo: Student (10% off), Staff (15% off)",
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
            self.refresh_refunds()
            self.refresh_loyalty()
            self.refresh_inventory()
            self.refresh_special()
            self.refresh_analytics()
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

    def set_status(self, message):
        """Update the bottom status bar."""
        self.status_bar.config(text=message)

    def _ensure_production_seed(self):
        """Seed default ingredients, recipes, starters, substitutions
        on first run. Idempotent — only inserts when each table is
        empty."""
        conn = self._connect()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if conn.execute("SELECT COUNT(*) FROM bakery_ingredients").fetchone()[0] == 0:
                conn.executemany(
                    "INSERT INTO bakery_ingredients "
                    "(name, unit, stock, reorder_level, unit_cost, allergens, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    [
                        ("flour",     "g",  50000, 10000, 0.0012, "gluten,wheat", now),
                        ("sugar",     "g",  20000,  5000, 0.0009, "",             now),
                        ("yeast",     "g",   2000,   500, 0.0150, "",             now),
                        ("salt",      "g",   5000,  1000, 0.0008, "",             now),
                        ("butter",    "g",  10000,  2000, 0.0090, "milk",         now),
                        ("milk",      "ml", 20000,  4000, 0.0010, "milk",         now),
                        ("eggs",      "each",  200,    50, 0.2500, "eggs",         now),
                        ("cocoa",     "g",   3000,   500, 0.0150, "",             now),
                        ("chocolate", "g",   5000,  1000, 0.0120, "milk,soy",     now),
                        ("oats",      "g",   8000,  1500, 0.0020, "gluten",       now),
                        ("almond_flour","g", 2000,   500, 0.0250, "nuts,almonds", now),
                        ("oil",       "ml",  5000,  1000, 0.0040, "",             now),
                    ],
                )
            if conn.execute("SELECT COUNT(*) FROM bakery_recipes").fetchone()[0] == 0:
                recipes = [
                    ("White Bread",       {"flour": 500, "yeast": 7, "salt": 10, "oil": 15}),
                    ("Whole Wheat",       {"flour": 500, "yeast": 7, "salt": 10, "oil": 15}),
                    ("Baguette",          {"flour": 400, "yeast": 6, "salt": 8}),
                    ("Croissant",         {"flour": 200, "butter": 100, "milk": 50, "yeast": 4, "eggs": 1}),
                    ("Bagel",             {"flour": 300, "yeast": 5, "salt": 6, "sugar": 10}),
                    ("Chocolate Muffin",  {"flour": 80, "sugar": 60, "cocoa": 20, "eggs": 1, "milk": 50, "oil": 30}),
                    ("Blueberry Muffin",  {"flour": 80, "sugar": 60, "eggs": 1, "milk": 50, "oil": 30}),
                    ("Cinnamon Roll",     {"flour": 100, "sugar": 30, "butter": 30, "yeast": 3, "milk": 40, "eggs": 1}),
                    ("Donut",             {"flour": 60, "sugar": 25, "oil": 50, "eggs": 1, "milk": 25}),
                    ("Danish Pastry",     {"flour": 90, "butter": 50, "sugar": 20, "eggs": 1, "milk": 30}),
                    ("Chocolate Cake",    {"flour": 250, "sugar": 250, "cocoa": 80, "eggs": 4, "butter": 200, "milk": 200}),
                    ("Vanilla Cake",      {"flour": 250, "sugar": 250, "eggs": 4, "butter": 200, "milk": 200}),
                    ("Cheesecake",        {"flour": 100, "sugar": 200, "eggs": 3, "butter": 80, "milk": 250}),
                    ("Cupcake",           {"flour": 50, "sugar": 40, "eggs": 1, "butter": 30, "milk": 25}),
                    ("Tiramisu",          {"flour": 80, "sugar": 120, "eggs": 4, "milk": 150, "cocoa": 20}),
                    ("Chocolate Chip",    {"flour": 30, "sugar": 20, "butter": 15, "chocolate": 15, "eggs": 1}),
                    ("Oatmeal Raisin",    {"flour": 25, "oats": 20, "sugar": 18, "butter": 15, "eggs": 1}),
                    ("Sugar Cookie",      {"flour": 30, "sugar": 20, "butter": 15, "eggs": 1}),
                    ("Macaron",           {"almond_flour": 20, "sugar": 25, "eggs": 1}),
                    ("Brownie",           {"flour": 40, "sugar": 60, "cocoa": 25, "butter": 40, "eggs": 1, "chocolate": 20}),
                ]
                rows = []
                for item, bom in recipes:
                    for ing, qty in bom.items():
                        rows.append((item, ing, qty))
                conn.executemany(
                    "INSERT OR IGNORE INTO bakery_recipes "
                    "(item_name, ingredient, quantity) VALUES (?,?,?)",
                    rows,
                )
            if conn.execute("SELECT COUNT(*) FROM bakery_substitutions").fetchone()[0] == 0:
                conn.executemany(
                    "INSERT OR IGNORE INTO bakery_substitutions "
                    "(ingredient, substitute, ratio, notes) VALUES (?,?,?,?)",
                    [
                        ("butter",    "oil",          0.75, "Use 3/4 amount; texture softer."),
                        ("milk",      "oat_milk",     1.0,  "Dairy-free swap; identical ratio."),
                        ("milk",      "almond_milk",  1.0,  "Adds slight nutty note."),
                        ("eggs",      "flax_egg",     1.0,  "1 tbsp ground flax + 3 tbsp water per egg."),
                        ("flour",     "gf_flour_blend", 1.0, "Add 1/4 tsp xanthan per cup."),
                        ("sugar",     "honey",        0.75, "Reduce other liquids slightly."),
                        ("chocolate", "carob",        1.0,  "Caffeine-free alternative."),
                        ("almond_flour", "sunflower_seed_flour", 1.0, "Nut-free swap."),
                        ("yeast",     "sourdough_starter", 5.0, "Use ~5x weight of active starter; extend proof."),
                    ],
                )
            if conn.execute("SELECT COUNT(*) FROM bakery_starters").fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO bakery_starters "
                    "(name, feed_interval_hours, last_fed, next_due, active, notes) "
                    "VALUES (?,?,?,?,?,?)",
                    ("House Sourdough", 24, None, None, 1, "Stored at room temp."),
                )
            conn.commit()
        except Exception:
            logger.debug("Production seed failed", exc_info=True)
        finally:
            conn.close()

    def _prod_category_for(self, item_name):
        for cat, items in self.products.items():
            if item_name in items:
                return cat
        return None

    def _prod_batch_size(self, item_name):
        cat = self._prod_category_for(item_name)
        return self.PRODUCTION_BATCH_SIZES.get(cat, 12)

    def _prod_shelf_life(self, item_name):
        cat = self._prod_category_for(item_name)
        return self.PRODUCTION_SHELF_LIFE.get(cat, 3)

    def _all_product_names(self):
        names = []
        for cat, items in self.products.items():
            names.extend(items.keys())
        return sorted(names)

    def _lazy_subnotebook(self, parent, panels, log_label="panel"):
        bg = self.colors["background"]
        sub = ttk.Notebook(parent)
        sub.pack(fill="both", expand=True, padx=8, pady=8)
        frames = {}
        for label, builder in panels:
            frame = tk.Frame(sub, bg=bg)
            sub.add(frame, text=label)
            frames[label] = frame

            def _build_once(_evt, _f=frame, _b=builder, _l=label):
                if getattr(_f, "_lazy_built", False):
                    return
                _f._lazy_built = True
                try:
                    _b(_f)
                except Exception:
                    logger.exception("%s build failed: %s", log_label, _l)
            frame.bind("<Map>", _build_once)
        return sub, frames

