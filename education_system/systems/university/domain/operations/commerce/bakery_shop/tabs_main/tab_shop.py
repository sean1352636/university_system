"""ShopTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class ShopTabMixin:
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
            width=24,
        )
        search_entry.pack(side="left", padx=5)

        # Dietary filter (Vegan / Vegetarian / Halal / Kosher /
        # Gluten-free / Dairy-free). Multi-select via menu.
        tk.Label(search_frame, text=" Diet:",
                 font=("Arial", 11),
                 bg=self.colors["background"],
                 fg=self.colors["text"]).pack(side="left", padx=(10, 2))
        self.dietary_vars = {tag: tk.BooleanVar(value=False)
                             for tag in DIETARY_VOCAB}
        diet_btn = tk.Menubutton(search_frame, text="Any",
                                 relief="raised", width=14,
                                 bg=self.colors["card"],
                                 fg=self.colors["text"])
        diet_btn.pack(side="left", padx=4)
        diet_menu = tk.Menu(diet_btn, tearoff=0)
        for tag in DIETARY_VOCAB:
            diet_menu.add_checkbutton(
                label=tag.title(), variable=self.dietary_vars[tag],
                command=lambda b=diet_btn: (
                    b.configure(text=self._summarise_filter(self.dietary_vars) or "Any"),
                    self.refresh_products()),
            )
        diet_btn.configure(menu=diet_menu)
        self._diet_btn = diet_btn

        # Exclude-allergens filter
        tk.Label(search_frame, text=" Exclude:",
                 font=("Arial", 11),
                 bg=self.colors["background"],
                 fg=self.colors["text"]).pack(side="left", padx=(10, 2))
        self.allergen_vars = {al: tk.BooleanVar(value=False)
                              for al in ALLERGEN_VOCAB}
        al_btn = tk.Menubutton(search_frame, text="None",
                               relief="raised", width=14,
                               bg=self.colors["card"],
                               fg=self.colors["text"])
        al_btn.pack(side="left", padx=4)
        al_menu = tk.Menu(al_btn, tearoff=0)
        for al in ALLERGEN_VOCAB:
            al_menu.add_checkbutton(
                label=al.title(), variable=self.allergen_vars[al],
                command=lambda b=al_btn: (
                    b.configure(text=self._summarise_filter(self.allergen_vars) or "None"),
                    self.refresh_products()),
            )
        al_btn.configure(menu=al_menu)
        self._al_btn = al_btn

        # Favourites-only toggle
        self._favourites_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(search_frame, text="♥ Favourites only",
                       variable=self._favourites_only_var,
                       bg=self.colors["background"],
                       fg=self.colors["danger"],
                       font=("Arial", 10, "bold"),
                       command=self.refresh_products
                       ).pack(side="left", padx=10)

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

    def _summarise_filter(self, var_dict):
        chosen = [k for k, v in var_dict.items() if v.get()]
        if not chosen:
            return ""
        if len(chosen) <= 2:
            return ", ".join(chosen)
        return f"{chosen[0]}, +{len(chosen) - 1}"

    def refresh_products(self):
        """Repopulate the product grid based on category, search, and
        dietary / allergen filters."""
        if not getattr(self, "shop_tab", None) or not getattr(self.shop_tab, "_lazy_built", False):
            return
        for widget in self.products_frame.winfo_children():
            widget.destroy()

        category = self.selected_category.get()
        search = self.search_var.get().lower().strip()
        required_diet = [t for t, v in (self.dietary_vars or {}).items()
                         if v.get()] if hasattr(self, "dietary_vars") else []
        excluded_allergens = [a for a, v in (self.allergen_vars or {}).items()
                              if v.get()] if hasattr(self, "allergen_vars") else []

        items = self.products.get(category, {})
        if search:
            items = {k: v for k, v in items.items() if search in k.lower()}
        if required_diet or excluded_allergens:
            items = {k: v for k, v in items.items()
                     if self._passes_dietary_filter(v, required_diet, excluded_allergens)}
        if getattr(self, "_favourites_only_var", None) \
                and self._favourites_only_var.get() and self.current_user:
            favs = set(self.list_favourites())
            items = {k: v for k, v in items.items() if k in favs}

        # Top sellers banner (today). Sourced from order history.
        try:
            sellers = self.top_sellers_today(3)
        except Exception:
            logger.exception("top_sellers_today failed")
            sellers = []
        if sellers:
            medals = ["🥇", "🥈", "🥉"]
            sellers_text = "  ".join(
                f"{medals[i] if i < 3 else '•'} {name} ({qty})"
                for i, (name, qty) in enumerate(sellers)
            )
            tk.Label(
                self.products_frame,
                text=f"  🔥 Today's Top Sellers:  {sellers_text}  ",
                font=("Georgia", 11, "bold"),
                bg=self.colors["primary"], fg="white",
            ).grid(row=0, column=0, columnspan=3, pady=(0, 6), sticky="ew")

        # Category header
        header = tk.Label(
            self.products_frame,
            text=f"  {category}  ",
            font=("Georgia", 16, "bold"),
            bg=self.colors["accent"],
            fg=self.colors["text"],
        )
        header.grid(row=1, column=0, columnspan=3, pady=10, sticky="w")

        if not items:
            tk.Label(
                self.products_frame,
                text="No products found.",
                font=("Arial", 12, "italic"),
                bg=self.colors["background"],
                fg=self.colors["text"],
            ).grid(row=2, column=0, padx=20, pady=20)
            return

        # Render product cards in a 3-column grid
        row, col = 2, 0
        for name, info in items.items():
            self.create_product_card(name, info, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

    def create_product_card(self, name, info, row, col):
        """Create an individual product card with image-or-emoji, dietary
        badges, allergen pictograms, and next-bake hint."""
        card = tk.Frame(
            self.products_frame,
            bg=self.colors["card"],
            relief="raised",
            bd=2,
            width=260,
            height=300,
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        card.grid_propagate(False)

        # Image (PIL) with emoji fallback if file missing.
        image_path = os.path.join(IMAGES_DIR, info.get("image", "")) \
            if info.get("image") else ""
        img_shown = False
        if image_path and os.path.isfile(image_path):
            try:
                from PIL import Image, ImageTk  # type: ignore
                img = Image.open(image_path).resize((100, 100))
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(card, image=photo, bg=self.colors["card"])
                lbl.image = photo  # keep ref
                lbl.pack(pady=(8, 0))
                img_shown = True
            except Exception:
                logger.debug("Could not load image %s", image_path,
                             exc_info=True)
        if not img_shown:
            tk.Label(card, text=info["emoji"], font=("Arial", 40),
                     bg=self.colors["card"]).pack(pady=(10, 0))

        # Name + heart favourite toggle
        name_row = tk.Frame(card, bg=self.colors["card"])
        name_row.pack(pady=2)
        tk.Label(
            name_row, text=name, font=("Georgia", 13, "bold"),
            bg=self.colors["card"], fg=self.colors["text"],
        ).pack(side="left")
        if self.current_user:
            fav = self.is_favourite(name)
            heart_btn = tk.Button(
                name_row, text=("♥" if fav else "♡"),
                font=("Arial", 14),
                bg=self.colors["card"],
                fg=self.colors["danger"] if fav else self.colors["text"],
                relief="flat", cursor="hand2", bd=0,
                command=lambda n=name: (self.toggle_favourite(n),
                                        self.refresh_products()),
            )
            heart_btn.pack(side="left", padx=4)

        # Dietary badges (vegan/vegetarian/halal/gluten-free…)
        badges = info.get("dietary") or []
        if badges:
            badge_text = "  ".join({
                "vegan": "🌱V", "vegetarian": "🥦Veg", "halal": "ⓗHalal",
                "kosher": "ⓚKosher", "gluten-free": "GF",
                "dairy-free": "DF", "nut-free": "NF",
                "low-sugar": "LS", "high-fibre": "HF",
            }.get(b, b) for b in badges)
            tk.Label(card, text=badge_text, font=("Arial", 9),
                     bg=self.colors["card"], fg=self.colors["secondary"]
                     ).pack(pady=(0, 2))

        # Allergens (warn if any)
        if info.get("allergens"):
            tk.Label(card, text="⚠ " + ", ".join(info["allergens"]),
                     font=("Arial", 8), wraplength=240,
                     bg=self.colors["card"], fg=self.colors["danger"]
                     ).pack(pady=(0, 2))

        # Next fresh-bake hint
        next_bake = self._next_bake_time(info)
        if next_bake:
            tk.Label(card, text=f"🔥 Next batch: {next_bake}",
                     font=("Arial", 9, "italic"),
                     bg=self.colors["card"], fg=self.colors["primary"]
                     ).pack()

        # Price
        tk.Label(
            card,
            text=self.fmt_money(info['price']),
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

        # Action buttons: Add-to-Cart + Info
        actions = tk.Frame(card, bg=self.colors["card"])
        actions.pack(pady=8, padx=12, fill="x")
        tk.Button(
            actions, text="+ Add",
            font=("Arial", 10, "bold"),
            bg=self.colors["primary"] if stock > 0 else "gray",
            fg="white", relief="flat",
            cursor="hand2" if stock > 0 else "arrow",
            state="normal" if stock > 0 else "disabled",
            command=lambda n=name: self.add_to_cart(n),
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(
            actions, text="ℹ Info",
            font=("Arial", 10),
            bg=self.colors["accent"], fg=self.colors["text"],
            relief="flat", cursor="hand2",
            command=lambda n=name, i=info: self._show_product_info(n, i),
        ).pack(side="right", padx=(4, 0))

    def _next_bake_time(self, info):
        """Return the next 'HH:MM' from info['fresh_bake_times'] later
        than now today, or None if there isn't one."""
        times = info.get("fresh_bake_times") or []
        if not times:
            return None
        now = datetime.now().strftime("%H:%M")
        upcoming = sorted(t for t in times if t > now)
        return upcoming[0] if upcoming else None

    def _show_product_info(self, name, info):
        """Popup with allergens, dietary tags, nutrition, and bake times."""
        w = tk.Toplevel(self.root)
        w.title(f"ℹ {name}")
        w.geometry("480x780")
        w.configure(bg=self.colors["background"])
        w.transient(self.root); w.grab_set()

        tk.Label(w, text=f"{info.get('emoji', '')}  {name}",
                 font=("Georgia", 16, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=10)
        tk.Label(w, text=f"£{info['price']:.2f}   •   "
                         f"In stock: {info.get('stock', 0)}",
                 bg=self.colors["background"], fg=self.colors["secondary"],
                 font=("Arial", 11, "bold")).pack(pady=2)

        def section(title):
            tk.Label(w, text=title, font=("Arial", 11, "bold"),
                     bg=self.colors["background"], fg=self.colors["text"]
                     ).pack(anchor="w", padx=20, pady=(10, 2))

        section("Dietary")
        tk.Label(w, text=", ".join(info.get("dietary") or ["—"]),
                 bg=self.colors["background"], fg=self.colors["text"],
                 wraplength=380, justify="left").pack(anchor="w", padx=30)

        section("Allergens")
        al = info.get("allergens") or []
        tk.Label(w, text=("⚠ " + ", ".join(al)) if al
                       else "No declared allergens.",
                 bg=self.colors["background"],
                 fg=self.colors["danger"] if al else self.colors["text"],
                 wraplength=380, justify="left").pack(anchor="w", padx=30)

        section("Nutrition (per unit)")
        nut = info.get("nutrition") or {}
        if nut:
            tk.Label(w, text=(f"  Calories: {nut.get('cal', '—')} kcal\n"
                              f"  Protein:  {nut.get('protein', '—')} g\n"
                              f"  Carbs:    {nut.get('carbs', '—')} g\n"
                              f"  Fat:      {nut.get('fat', '—')} g"),
                     bg=self.colors["background"], fg=self.colors["text"],
                     font=("Courier", 10), justify="left"
                     ).pack(anchor="w", padx=30)
        else:
            tk.Label(w, text="(no nutritional data)",
                     bg=self.colors["background"], fg=self.colors["text"],
                     font=("Arial", 10, "italic")).pack(anchor="w", padx=30)

        section("Fresh-bake schedule today")
        times = info.get("fresh_bake_times") or []
        if times:
            tk.Label(w, text="  " + "   ".join(times),
                     bg=self.colors["background"], fg=self.colors["primary"],
                     font=("Arial", 11, "bold")
                     ).pack(anchor="w", padx=30)
        else:
            tk.Label(w, text="(not baked on premises)",
                     bg=self.colors["background"],
                     font=("Arial", 10, "italic")
                     ).pack(anchor="w", padx=30)

        # --- Reviews & ratings ---
        avg, count = self.average_rating(name)
        stars = ("★" * int(round(avg)) + "☆" * (5 - int(round(avg)))) \
            if avg is not None else "(no ratings yet)"
        section("Reviews")
        tk.Label(w, text=f"  {stars}   {('%.1f' % avg) if avg else ''}"
                         f"  ({count} review{'s' if count != 1 else ''})",
                 bg=self.colors["background"], fg=self.colors["secondary"],
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=30)

        rev_frame = tk.Frame(w, bg=self.colors["background"])
        rev_frame.pack(fill="x", padx=30, pady=4)
        for u, rating, comment, ts, verified in self.get_reviews(name, 5):
            badge = "✅ " if verified else ""
            r_stars = "★" * int(rating) + "☆" * (5 - int(rating))
            tk.Label(rev_frame,
                     text=f"{badge}{u or 'anon'} — {r_stars}  {ts}",
                     bg=self.colors["background"],
                     fg=self.colors["text"],
                     font=("Arial", 9, "bold"),
                     ).pack(anchor="w")
            if comment:
                tk.Label(rev_frame, text=f"   {comment}",
                         bg=self.colors["background"],
                         fg=self.colors["text"],
                         font=("Arial", 9),
                         wraplength=360, justify="left"
                         ).pack(anchor="w", pady=(0, 4))

        # --- Leave a review form ---
        if self.current_user:
            section("Leave a Review")
            form = tk.Frame(w, bg=self.colors["background"])
            form.pack(fill="x", padx=30, pady=4)
            rating_var = tk.IntVar(value=5)
            rrow = tk.Frame(form, bg=self.colors["background"])
            rrow.pack(anchor="w")
            tk.Label(rrow, text="Rating:",
                     bg=self.colors["background"]).pack(side="left")
            for n in range(1, 6):
                tk.Radiobutton(rrow, text=str(n), variable=rating_var,
                               value=n, bg=self.colors["background"]
                               ).pack(side="left")
            tk.Label(form, text="Comment (optional):",
                     bg=self.colors["background"]).pack(anchor="w", pady=(4, 0))
            comment_e = tk.Entry(form, width=44); comment_e.pack(anchor="w")

            def submit_review():
                ok = self.add_review(
                    name, rating_var.get(), comment_e.get().strip(),
                    verified=self._user_bought(name, self.current_user),
                )
                if ok:
                    messagebox.showinfo("Thanks!",
                                        "Your review has been posted.",
                                        parent=w)
                    w.destroy()
                    # Reopen so the new review shows.
                    self._show_product_info(name, info)
                else:
                    messagebox.showerror("Error",
                                         "Could not submit review.",
                                         parent=w)

            tk.Button(form, text="Submit Review",
                      bg=self.colors["primary"], fg="white", relief="flat",
                      padx=12, pady=4, command=submit_review
                      ).pack(anchor="w", pady=4)
        else:
            tk.Label(w, text="(log in to leave a review)",
                     bg=self.colors["background"],
                     font=("Arial", 9, "italic")).pack(anchor="w", padx=30)

        tk.Button(w, text="Close",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=20, pady=6, command=w.destroy
                  ).pack(pady=15)

