"""UICoreMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class UICoreMixin:
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

        # Currency selector (GBP / EUR / USD / any admin-added code).
        tk.Label(self.user_frame, text="  💱",
                 bg=self.colors["primary"], fg="white",
                 font=("Arial", 11)).pack(side="left")
        self._currency_var = tk.StringVar(value=getattr(self, "_currency_code", "GBP"))
        try:
            currencies = [r[0] for r in self.list_currencies()] or ["GBP"]
        except Exception:
            currencies = ["GBP"]
        currency_box = ttk.Combobox(self.user_frame, width=5, state="readonly",
                                    values=currencies,
                                    textvariable=self._currency_var)
        currency_box.pack(side="left", padx=4)

        def _on_currency_change(_event=None):
            self.set_currency(self._currency_var.get())
            # Refresh anywhere prices are rendered.
            try:
                self.refresh_products()
                self.refresh_cart()
                self.update_cart_totals()
            except Exception:
                logger.debug("Refresh after currency change failed",
                             exc_info=True)
        currency_box.bind("<<ComboboxSelected>>", _on_currency_change)

        # Preferences button (theme / text scale / language).
        tk.Button(self.user_frame, text="⚙",
                  bg=self.colors["primary"], fg="white",
                  relief="flat", bd=0, font=("Arial", 13),
                  cursor="hand2",
                  command=self._open_prefs_dialog
                  ).pack(side="left", padx=4)

        # Staff shift indicator (admin/staff). Click to clock in / out.
        if self.user_type in ("Admin", "Staff"):
            active = self.list_active_shifts()
            is_on = any(s[1] == self.current_user for s in active)
            shift_lbl = "🟢 On shift" if is_on else "⏱ Clock in"
            def _toggle_shift():
                if any(s[1] == self.current_user
                       for s in self.list_active_shifts()):
                    self.clock_out()
                else:
                    self.clock_in()
                self._rebuild_ui()
            tk.Button(self.user_frame, text=shift_lbl,
                      bg=self.colors["success"] if is_on
                         else self.colors["secondary"],
                      fg="white", relief="flat", cursor="hand2",
                      command=_toggle_shift
                      ).pack(side="left", padx=4)

        # Feedback button (anyone).
        tk.Button(self.user_frame, text="💬",
                  bg=self.colors["primary"], fg="white",
                  relief="flat", bd=0, font=("Arial", 13),
                  cursor="hand2",
                  command=self._open_feedback_dialog
                  ).pack(side="left", padx=4)

        # In-app login removed — identity comes from the main university
        # system via EDU_AUTH_* env vars. Keep `self.login_btn` as a
        # disabled placeholder so any code still referencing it doesn't
        # blow up.
        self.login_btn = tk.Label(self.user_frame, text="", bg=self.colors["primary"])

        # ----- Body: sidebar + content area -----
        # Mirrors the main university GUI's navigation pattern: a
        # scrollable sidebar with a search box on the left, the active
        # panel on the right. Replaces the cramped 14-tab ttk.Notebook.
        body = tk.Frame(self.root, bg=self.colors["background"])
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Sidebar container with scrollable canvas ---
        sidebar = tk.LabelFrame(
            body, text=" Navigation ",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 10, "bold"),
            bd=1, relief="groove", padx=4, pady=4,
        )
        sidebar.pack(side="left", fill="y", padx=(0, 8))

        # Search entry at the top of the sidebar.
        self._nav_search_var = tk.StringVar()
        search_entry = tk.Entry(
            sidebar, textvariable=self._nav_search_var,
            font=("Arial", 10), width=22, relief="solid", bd=1,
        )
        search_entry.pack(fill="x", padx=2, pady=(2, 4))
        _SEARCH_PLACEHOLDER = "🔍 Search…"
        def _set_search_placeholder():
            search_entry.delete(0, tk.END)
            search_entry.insert(0, _SEARCH_PLACEHOLDER)
            search_entry.config(fg="gray")
        def _on_search_focus_in(_e):
            if self._nav_search_var.get() == _SEARCH_PLACEHOLDER:
                search_entry.delete(0, tk.END)
                search_entry.config(fg=self.colors["text"])
        def _on_search_focus_out(_e):
            if not self._nav_search_var.get().strip():
                _set_search_placeholder()
        search_entry.bind("<FocusIn>", _on_search_focus_in)
        search_entry.bind("<FocusOut>", _on_search_focus_out)
        _set_search_placeholder()

        # Scrollable canvas for the button list.
        canvas = tk.Canvas(
            sidebar, bg=self.colors["background"],
            highlightthickness=0, width=220,
        )
        vscroll = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="y", expand=False)
        vscroll.pack(side="right", fill="y")

        nav_inner = tk.Frame(canvas, bg=self.colors["background"])
        nav_window = canvas.create_window((0, 0), window=nav_inner, anchor="nw")

        def _on_inner_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        nav_inner.bind("<Configure>", _on_inner_configure)
        def _on_canvas_configure(e):
            # Keep the inner frame matching the canvas width.
            canvas.itemconfig(nav_window, width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scrolling — bound on the canvas itself + its children
        # (idempotent via marker attr) so wheeling anywhere in the sidebar
        # scrolls the list.
        def _on_wheel(e):
            try:
                delta = -1 if (getattr(e, "num", None) == 5
                               or getattr(e, "delta", 0) < 0) else 1
                canvas.yview_scroll(-delta, "units")
            except tk.TclError:
                pass
            return "break"
        def _bind_wheel_recursive(w):
            try:
                if not getattr(w, "_nav_wheel_bound", False):
                    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                        w.bind(seq, _on_wheel, add="+")
                    w._nav_wheel_bound = True
                for c in w.winfo_children():
                    _bind_wheel_recursive(c)
            except tk.TclError:
                pass
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(seq, _on_wheel, add="+")
        canvas._nav_wheel_bound = True
        nav_inner.bind(
            "<Configure>",
            lambda _e: _bind_wheel_recursive(nav_inner),
            add="+",
        )

        # --- Content area (right of sidebar) ---
        self._content_area = tk.Frame(body, bg=self.colors["background"])
        self._content_area.pack(side="left", fill="both", expand=True)

        # --- Panel frames (parented to the content area) ---
        _bg = self.colors["background"]
        self.shop_tab         = tk.Frame(self._content_area, bg=_bg)
        self.cart_tab         = tk.Frame(self._content_area, bg=_bg)
        self.orders_tab       = tk.Frame(self._content_area, bg=_bg)
        self.rewards_tab      = tk.Frame(self._content_area, bg=_bg)
        self.refunds_tab      = tk.Frame(self._content_area, bg=_bg)
        self.inventory_tab    = tk.Frame(self._content_area, bg=_bg)
        self.production_tab   = tk.Frame(self._content_area, bg=_bg)
        self.pos_tab          = tk.Frame(self._content_area, bg=_bg)
        self.staff_tab        = tk.Frame(self._content_area, bg=_bg)
        self.reports_qa_tab   = tk.Frame(self._content_area, bg=_bg)
        self.integrations_tab = tk.Frame(self._content_area, bg=_bg)
        self.special_tab      = tk.Frame(self._content_area, bg=_bg)
        self.analytics_tab    = tk.Frame(self._content_area, bg=_bg)
        self.admin_tab        = tk.Frame(self._content_area, bg=_bg)

        # (key, label, frame, builder) — order = sidebar order.
        self._panels = [
            ("shop",         "🛍️  Shop",                self.shop_tab,         self.build_shop_tab),
            ("cart",         "🛒  Cart (0)",            self.cart_tab,         self.build_cart_tab),
            ("orders",       "📋  My Orders",           self.orders_tab,       self.build_orders_tab),
            ("rewards",      "⭐  Rewards",             self.rewards_tab,      self.build_rewards_tab),
            ("refunds",      "💳  Refunds",             self.refunds_tab,      self.build_refunds_tab),
            ("inventory",    "🏭  Inventory",           self.inventory_tab,    self.build_inventory_tab),
            ("production",   "👨‍🍳  Production",  self.production_tab,   self.build_production_tab),
            ("pos",          "💳  POS & Sales",         self.pos_tab,          self.build_pos_tab),
            ("staff",        "👥  Staff & Customers",   self.staff_tab,        self.build_staff_tab),
            ("reports_qa",   "📊  Reports & QA",        self.reports_qa_tab,   self.build_reports_qa_tab),
            ("integrations", "🔌  Integrations",        self.integrations_tab, self.build_integrations_tab),
            ("special",      "📅  Special Orders",      self.special_tab,      self.build_special_tab),
            ("analytics",    "📊  Analytics",           self.analytics_tab,    self.build_analytics_tab),
            ("admin",        "⚙️  Admin",               self.admin_tab,        self.build_admin_tab),
        ]

        # Wire lazy-build (same <Map> trick as before — packing a panel
        # into the content area fires <Map> and builds it on first show).
        for _k, _lbl, _f, _b in self._panels:
            def _build_once(_evt, _frame=_f, _builder=_b):
                if getattr(_frame, "_lazy_built", False):
                    return
                _frame._lazy_built = True
                try:
                    _builder()
                except Exception:
                    logger.exception("Lazy panel build failed: %s", _builder.__name__)
            _f.bind("<Map>", _build_once)

        # --- Build sidebar buttons + show/hide logic ---
        self._panel_buttons = {}      # key -> tk.Button (for label updates + search)
        self._active_panel_key = None

        def _show_panel(key):
            target = next((f for (k, _l, f, _b) in self._panels if k == key), None)
            if target is None:
                return
            # Hide currently-shown panel.
            if self._active_panel_key:
                prev = next((f for (k, _l, f, _b) in self._panels
                             if k == self._active_panel_key), None)
                if prev is not None:
                    prev.pack_forget()
            target.pack(fill="both", expand=True)
            self._active_panel_key = key
            # Highlight the active button.
            for k, btn in self._panel_buttons.items():
                if k == key:
                    btn.configure(bg=self.colors["primary"], fg="white")
                else:
                    btn.configure(bg=self.colors["secondary"], fg="white")
        self._show_panel = _show_panel

        for key, label, _frame, _builder in self._panels:
            btn = tk.Button(
                nav_inner, text=label, anchor="w", justify="left",
                bg=self.colors["secondary"], fg="white",
                activebackground=self.colors["primary"], activeforeground="white",
                relief="flat", bd=0, padx=10, pady=8,
                font=("Arial", 11), cursor="hand2",
                command=lambda k=key: _show_panel(k),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._panel_buttons[key] = btn

        # --- Search: hide non-matching buttons ---
        def _apply_search(*_):
            q = self._nav_search_var.get().strip().lower()
            if q == _SEARCH_PLACEHOLDER.lower():
                q = ""
            for key, label, _frame, _builder in self._panels:
                btn = self._panel_buttons[key]
                if not q or q in label.lower() or q in key.lower():
                    btn.pack(fill="x", padx=2, pady=1)
                else:
                    btn.pack_forget()
        self._nav_search_var.trace_add("write", _apply_search)

        # Initial pass to bind wheel to children + show the default panel.
        _bind_wheel_recursive(nav_inner)
        _show_panel("shop")

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

