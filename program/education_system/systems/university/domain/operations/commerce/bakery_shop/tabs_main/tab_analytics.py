"""AnalyticsTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class AnalyticsTabMixin:
    def build_analytics_tab(self):
        self.analytics_content = tk.Frame(self.analytics_tab,
                                          bg=self.colors["background"])
        self.analytics_content.pack(fill="both", expand=True)
        self._analytics_period = "week"
        self.refresh_analytics()

    def refresh_analytics(self):
        if not getattr(self, "analytics_tab", None) or not getattr(self.analytics_tab, "_lazy_built", False):
            return
        if not hasattr(self, "analytics_content"):
            return
        for w in self.analytics_content.winfo_children():
            w.destroy()

        if self.user_type != "Admin":
            tk.Label(self.analytics_content,
                     text="🔒 Admin access required\n\n"
                          "Reporting & analytics are admin-only.",
                     font=("Arial", 14),
                     bg=self.colors["background"], fg=self.colors["text"],
                     justify="center").pack(expand=True, pady=50)
            return

        # ---- Header with period selector ----
        head = tk.Frame(self.analytics_content, bg=self.colors["background"])
        head.pack(fill="x", padx=12, pady=8)
        tk.Label(head, text="📊 Analytics & Reporting",
                 font=("Georgia", 18, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(side="left")
        tk.Label(head, text="  Period:",
                 bg=self.colors["background"]).pack(side="left", padx=(20, 4))
        for label, key in (("Today", "today"), ("Yesterday", "yesterday"),
                           ("Week", "week"), ("Month", "month"),
                           ("Year", "year")):
            is_active = key == getattr(self, "_analytics_period", "week")
            tk.Button(head, text=label,
                      bg=self.colors["primary"] if is_active
                         else self.colors["secondary"],
                      fg="white", relief="flat",
                      padx=8, pady=2,
                      command=lambda k=key: self._set_analytics_period(k)
                      ).pack(side="left", padx=2)

        # ---- Summary cards ----
        summary = self.sales_summary(self._analytics_period)
        cards_frame = tk.Frame(self.analytics_content,
                               bg=self.colors["background"])
        cards_frame.pack(fill="x", padx=12, pady=4)
        for label, value, color in (
            ("Orders", str(summary["orders_count"]), self.colors["primary"]),
            ("Items sold", str(summary["items_count"]), self.colors["accent"]),
            ("Revenue", self.fmt_money(summary["revenue"]),
             self.colors["success"]),
            ("Tips", self.fmt_money(summary["tips"]),
             self.colors["secondary"]),
            ("VAT", self.fmt_money(summary["vat"]), self.colors["secondary"]),
            ("Avg order", self.fmt_money(summary["avg_order"]),
             self.colors["primary"]),
            ("Refunds", str(summary["refunded_count"]),
             self.colors["danger"]),
        ):
            c = tk.Frame(cards_frame, bg=color, width=170, height=70)
            c.pack(side="left", padx=4, fill="x", expand=True)
            c.pack_propagate(False)
            tk.Label(c, text=label, font=("Arial", 10),
                     bg=color, fg="white").pack(pady=(8, 0))
            tk.Label(c, text=value, font=("Georgia", 14, "bold"),
                     bg=color,
                     fg="white" if color != self.colors["accent"]
                         else self.colors["text"]).pack()

        # ---- Sub-notebook ----
        nb = ttk.Notebook(self.analytics_content)
        nb.pack(fill="both", expand=True, padx=12, pady=10)

        for label, builder in (
            ("📈 Sales Trend", self._build_analytics_trend),
            ("🥇 Products",   self._build_analytics_products),
            ("👥 By Tier",     self._build_analytics_tier),
            ("🔥 Heatmap",     self._build_analytics_heatmap),
            ("🗑 Shrinkage",   self._build_analytics_shrinkage),
            ("📤 Exports",     self._build_analytics_exports),
        ):
            frame = tk.Frame(nb, bg=self.colors["background"])
            nb.add(frame, text=label)
            try:
                builder(frame)
            except Exception:
                logger.exception("Analytics sub-tab failed: %s", label)
                tk.Label(frame, text=f"(Could not render {label})",
                         bg=self.colors["background"],
                         fg=self.colors["danger"]).pack(pady=20)

    def _set_analytics_period(self, key):
        self._analytics_period = key
        self.refresh_analytics()

    def _build_analytics_trend(self, parent):
        data = self.revenue_series(self._analytics_period)
        if not data:
            tk.Label(parent, text="No data in this period.",
                     bg=self.colors["background"]).pack(pady=20)
            return
        # Draw a simple bar chart on a tk Canvas.
        canvas_w, canvas_h = 880, 320
        margin_l, margin_b, margin_t, margin_r = 60, 40, 20, 20
        canvas = tk.Canvas(parent, width=canvas_w, height=canvas_h,
                           bg="white", highlightthickness=0)
        canvas.pack(padx=10, pady=10)

        usable_w = canvas_w - margin_l - margin_r
        usable_h = canvas_h - margin_t - margin_b
        max_v = max((v for _, v in data), default=0.0) or 1.0
        bar_w = max(8, usable_w / max(len(data), 1) - 4)

        # Y-axis label
        canvas.create_text(margin_l - 8, margin_t, anchor="ne",
                           text=self.fmt_money(max_v))
        canvas.create_text(margin_l - 8, margin_t + usable_h, anchor="ne",
                           text=self.fmt_money(0))
        # Axis lines
        canvas.create_line(margin_l, margin_t,
                           margin_l, margin_t + usable_h, fill="#888")
        canvas.create_line(margin_l, margin_t + usable_h,
                           margin_l + usable_w, margin_t + usable_h, fill="#888")

        for i, (label, v) in enumerate(data):
            x = margin_l + i * (usable_w / max(len(data), 1)) + 2
            h = (v / max_v) * usable_h if max_v else 0
            canvas.create_rectangle(x, margin_t + usable_h - h,
                                    x + bar_w, margin_t + usable_h,
                                    fill=self.colors["primary"],
                                    outline=self.colors["primary"])
            if i % max(1, len(data) // 8) == 0:
                canvas.create_text(x + bar_w / 2,
                                   margin_t + usable_h + 6,
                                   anchor="n", angle=30,
                                   text=label[-5:], font=("Arial", 8))
        tk.Label(parent,
                 text=f"Revenue trend ({self._analytics_period}). "
                      f"Total: {self.fmt_money(sum(v for _, v in data))}.",
                 bg=self.colors["background"], font=("Arial", 10, "italic")
                 ).pack(pady=4)

    def _build_analytics_products(self, parent):
        wrap = tk.Frame(parent, bg=self.colors["background"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.LabelFrame(wrap, text="🥇 Top sellers",
                              bg=self.colors["background"],
                              font=("Arial", 11, "bold"))
        left.pack(side="left", fill="both", expand=True, padx=4)
        right = tk.LabelFrame(wrap, text="🐢 Slow movers",
                               bg=self.colors["background"],
                               font=("Arial", 11, "bold"))
        right.pack(side="right", fill="both", expand=True, padx=4)

        for r in self.top_sellers(self._analytics_period, 10):
            tk.Label(left, text=f"{r[0]:25s}  {r[1]:>4d} units   "
                                f"{self.fmt_money(r[2])}",
                     font=("Courier", 10),
                     bg=self.colors["background"]).pack(anchor="w", padx=6)

        for r in self.slow_movers(self._analytics_period, 10):
            tk.Label(right, text=f"{r[0]:25s}  {r[1]:>4d} units",
                     font=("Courier", 10),
                     fg=self.colors["danger"] if r[1] == 0
                        else self.colors["text"],
                     bg=self.colors["background"]).pack(anchor="w", padx=6)

    def _build_analytics_tier(self, parent):
        data = self.revenue_by_tier(self._analytics_period)
        if not any(data.values()):
            tk.Label(parent, text="No tier revenue in this period.",
                     bg=self.colors["background"]).pack(pady=20)
            return
        canvas_w, canvas_h = 600, 280
        canvas = tk.Canvas(parent, width=canvas_w, height=canvas_h,
                           bg="white", highlightthickness=0)
        canvas.pack(padx=10, pady=10)
        max_v = max(data.values()) or 1.0
        tier_colors = {
            "Student": self.colors["primary"], "Staff": self.colors["success"],
            "Admin":   self.colors["secondary"], "Guest": self.colors["accent"],
        }
        x = 60
        bar_w = 80
        for tier, value in data.items():
            h = (value / max_v) * 200
            canvas.create_rectangle(x, 240 - h, x + bar_w, 240,
                                    fill=tier_colors.get(tier, "#888"),
                                    outline=tier_colors.get(tier, "#888"))
            canvas.create_text(x + bar_w / 2, 250, anchor="n",
                                text=tier)
            canvas.create_text(x + bar_w / 2, 240 - h - 6, anchor="s",
                                text=self.fmt_money(value),
                                font=("Arial", 9, "bold"))
            x += bar_w + 30

    def _build_analytics_heatmap(self, parent):
        grid = self.busy_heatmap(self._analytics_period)
        max_c = max(grid.values()) if grid else 0
        if max_c == 0:
            tk.Label(parent, text="No order activity in this period.",
                     bg=self.colors["background"]).pack(pady=20)
            return

        canvas_w, canvas_h = 760, 280
        canvas = tk.Canvas(parent, width=canvas_w, height=canvas_h,
                           bg="white", highlightthickness=0)
        canvas.pack(padx=10, pady=10)
        cell_w, cell_h = 28, 28
        margin_x, margin_y = 60, 30
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for h in range(24):
            canvas.create_text(margin_x + h * cell_w + cell_w / 2,
                               margin_y - 14, anchor="s",
                               text=f"{h:02d}", font=("Arial", 8))
        for d in range(7):
            canvas.create_text(margin_x - 6, margin_y + d * cell_h + cell_h / 2,
                               anchor="e", text=days[d],
                               font=("Arial", 9, "bold"))
            for h in range(24):
                v = grid.get((d, h), 0)
                t = v / max_c
                # Interpolate background colour from cream to dark brown.
                r = int(255 - (255 - 0x8B) * t)
                g = int(248 - (248 - 0x45) * t)
                b = int(231 - (231 - 0x13) * t)
                fill = f"#{r:02x}{g:02x}{b:02x}"
                x0 = margin_x + h * cell_w
                y0 = margin_y + d * cell_h
                canvas.create_rectangle(x0, y0, x0 + cell_w, y0 + cell_h,
                                        fill=fill, outline="#eee")
                if v > 0 and v >= max_c * 0.5:
                    canvas.create_text(x0 + cell_w / 2, y0 + cell_h / 2,
                                       text=str(v), fill="white",
                                       font=("Arial", 8, "bold"))
        tk.Label(parent,
                 text=f"Busiest cell: {max_c} orders. Darker = busier.",
                 bg=self.colors["background"],
                 font=("Arial", 9, "italic")
                 ).pack(pady=4)

    def _build_analytics_shrinkage(self, parent):
        rep = self.shrinkage_report()
        tk.Label(parent,
                 text=f"Total shrinkage loss (estimated): "
                      f"{self.fmt_money(rep['total_loss'])}",
                 font=("Arial", 12, "bold"),
                 bg=self.colors["background"], fg=self.colors["danger"]
                 ).pack(pady=10)
        cols = ("item", "expired_units", "depleted_units",
                "unit_price", "shrinkage_value")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (220, 110, 110, 100, 130)):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=6)
        for item in rep["by_item"]:
            tree.insert("", "end", values=(
                item["item_name"], item["expired_units"],
                item["depleted_units"],
                self.fmt_money(item["unit_price"]),
                self.fmt_money(item["shrinkage_value"]),
            ))

    def _build_analytics_exports(self, parent):
        # One-shot exports
        oneshot = tk.LabelFrame(parent, text="One-shot exports",
                                 bg=self.colors["background"],
                                 font=("Arial", 11, "bold"))
        oneshot.pack(fill="x", padx=10, pady=8)

        def export(action):
            try:
                path = action()
                if path:
                    messagebox.showinfo("Exported", f"File saved to:\n{path}")
                else:
                    messagebox.showerror("Error",
                                          "Export failed; see log.")
            except Exception as e:
                logger.exception("Export action failed")
                messagebox.showerror("Error", str(e))

        tk.Button(oneshot, text="📑 Sales CSV (current period)",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=12, pady=6,
                  command=lambda: export(
                      lambda: self.export_sales_csv(self._analytics_period))
                  ).pack(side="left", padx=6, pady=8)
        tk.Button(oneshot, text="🧾 Sales PDF (current period)",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=6,
                  command=lambda: export(
                      lambda: self.export_sales_pdf(self._analytics_period))
                  ).pack(side="left", padx=6, pady=8)
        tk.Button(oneshot, text=f"Open exports folder: "
                              f"{os.path.basename(self._exports_dir())}",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=12, pady=6,
                  command=lambda: messagebox.showinfo(
                      "Exports folder", self._exports_dir())
                  ).pack(side="right", padx=6, pady=8)

        # Scheduled reports
        sched = tk.LabelFrame(parent, text="Scheduled reports",
                               bg=self.colors["background"],
                               font=("Arial", 11, "bold"))
        sched.pack(fill="both", expand=True, padx=10, pady=8)

        cols = ("id", "name", "kind", "frequency", "format",
                "last_run", "next_run", "active")
        tree = ttk.Treeview(sched, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (40, 160, 100, 130, 70, 130, 130, 60)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=4, pady=4)

        def reload():
            for it in tree.get_children():
                tree.delete(it)
            for r in self.list_scheduled_reports():
                tree.insert("", "end", values=(
                    r[0], r[1], r[2], r[3], r[5] or "csv",
                    r[6] or "—", r[7] or "—",
                    "✓" if r[8] else "✗",
                ))

        def add_dialog():
            d = tk.Toplevel(self.root); d.title("New scheduled report")
            d.geometry("440x340"); d.transient(self.root); d.grab_set()
            fields = {}
            for label, default in (
                ("Name", "Daily sales summary"),
                ("Kind (sales)", "sales"),
                ("Frequency (daily / weekly:Mon / monthly:1)", "daily"),
                ("Recipients (csv emails)", ""),
                ("Format (csv/pdf)", "csv"),
            ):
                tk.Label(d, text=label).pack(anchor="w", padx=12, pady=(8, 0))
                e = tk.Entry(d, width=50); e.insert(0, default); e.pack(padx=12)
                fields[label] = e

            def save():
                try:
                    ok = self.add_scheduled_report(
                        fields["Name"].get(),
                        fields["Kind (sales)"].get(),
                        fields["Frequency (daily / weekly:Mon / monthly:1)"].get(),
                        fields["Recipients (csv emails)"].get(),
                        fields["Format (csv/pdf)"].get(),
                    )
                    if ok:
                        d.destroy(); reload()
                    else:
                        messagebox.showerror("Error", "Could not save.", parent=d)
                except Exception as e:
                    logger.exception("Add scheduled report dialog failed")
                    messagebox.showerror("Error", str(e), parent=d)

            tk.Button(d, text="Save", bg=self.colors["success"],
                      fg="white", relief="flat", padx=20, pady=6,
                      command=save).pack(side="right", padx=12, pady=12)
            tk.Button(d, text="Cancel", bg=self.colors["secondary"],
                      fg="white", relief="flat", padx=20, pady=6,
                      command=d.destroy).pack(side="right", pady=12)

        def del_selected():
            sel = tree.selection()
            if not sel:
                return
            sid = tree.item(sel[0])["values"][0]
            self.delete_scheduled_report(sid)
            reload()

        def run_selected():
            sel = tree.selection()
            if not sel:
                return
            sid = tree.item(sel[0])["values"][0]
            path = self.run_scheduled_report(sid)
            if path:
                messagebox.showinfo("Report run",
                                    f"Generated: {path}")
            else:
                messagebox.showerror("Error",
                                     "Run failed; see log.")
            reload()

        ctl = tk.Frame(sched, bg=self.colors["background"])
        ctl.pack(fill="x", padx=4, pady=4)
        tk.Button(ctl, text="➕ Add", bg=self.colors["success"], fg="white",
                  relief="flat", padx=10, pady=4,
                  command=add_dialog).pack(side="left", padx=4)
        tk.Button(ctl, text="▶ Run Now",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10, pady=4,
                  command=run_selected).pack(side="left", padx=4)
        tk.Button(ctl, text="🗑 Delete",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  padx=10, pady=4,
                  command=del_selected).pack(side="left", padx=4)

        reload()

