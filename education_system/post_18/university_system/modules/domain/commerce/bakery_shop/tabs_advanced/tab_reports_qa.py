"""ReportsQATabMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class ReportsQATabMixin:
    WEATHER_MULTIPLIERS = {
        "normal": {"Beverages": 1.00, "default": 1.00},
        "rainy":  {"Beverages": 1.15, "default": 0.85},
        "sunny":  {"Beverages": 1.20, "default": 1.05},
        "snow":   {"Beverages": 1.30, "default": 0.65},
    }

    DEFAULT_CCPS = [
        ("Oven temp", "Ovens reach ≥ 200°C before bake",
         "≥ 200°C", "per-shift"),
        ("Cooling time", "Cool to < 21°C within 4 h",
         "< 21°C @ 4h", "per-bake"),
        ("Cold-hold", "Display fridge < 5°C",
         "< 5°C", "every 2h"),
        ("Hand-wash interval", "Hand-wash every task switch",
         "Per switch", "per-shift"),
    ]

    def build_reports_qa_tab(self):
        panels = [
            ("🗓 Hourly Heatmap",      self._build_heatmap_panel),
            ("📈 Product Mix / Margin", self._build_mix_panel),
            ("🗑 Waste Cost",          self._build_waste_dash_panel),
            ("🔮 Demand Forecast",    self._build_forecast_panel),
            ("🏆 Top / Bottom SKUs",  self._build_topbot_panel),
            ("💍 Catering Pipeline",  self._build_pipeline_panel),
            ("🌡 Temp Logs",          self._build_temp_panel),
            ("🛡 HACCP CCPs",         self._build_haccp_panel),
            ("🧼 Allergen Wash-down", self._build_wash_panel),
            ("📥 Supplier Invoices",  self._build_invoice_panel),
            ("🔗 Batch Traceability", self._build_trace_panel),
        ]
        sub, self._qa_panels = self._lazy_subnotebook(
            self.reports_qa_tab, panels, "Reports/QA")
        self.reports_qa_sub = sub

    def _build_heatmap_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Last N days:", bg=bg).pack(side="left")
        self._heatmap_days = tk.StringVar(value="14")
        tk.Entry(top, textvariable=self._heatmap_days, width=4).pack(side="left", padx=4)
        tk.Button(top, text="↻ Recompute", command=self._heatmap_refresh,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        self._heatmap_canvas = tk.Frame(parent, bg=bg)
        self._heatmap_canvas.pack(fill="both", expand=True, padx=10, pady=6)
        self._heatmap_refresh()

    def _heatmap_refresh(self):
        for w in self._heatmap_canvas.winfo_children():
            w.destroy()
        try:
            days = int(self._heatmap_days.get())
        except ValueError:
            days = 14
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        # grid[dow][hour] = total revenue
        grid = [[0.0 for _ in range(24)] for _ in range(7)]
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, total FROM bakery_orders "
                "WHERE timestamp >= ?", (cutoff,)).fetchall()
        finally:
            conn.close()
        for ts, total in rows:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            grid[dt.weekday()][dt.hour] += total or 0
        peak = max((max(r) for r in grid), default=0) or 1.0

        # Render
        days_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header = tk.Frame(self._heatmap_canvas, bg=self.colors["background"])
        header.pack(anchor="w")
        tk.Label(header, text=" ", width=4,
                 bg=self.colors["background"]).pack(side="left")
        for h in range(24):
            tk.Label(header, text=f"{h:02d}", width=4,
                     bg=self.colors["background"],
                     font=("Arial", 9)).pack(side="left")
        for d, dlabel in enumerate(days_labels):
            row = tk.Frame(self._heatmap_canvas, bg=self.colors["background"])
            row.pack(anchor="w")
            tk.Label(row, text=dlabel, width=4,
                     bg=self.colors["background"],
                     font=("Arial", 9, "bold")).pack(side="left")
            for h in range(24):
                v = grid[d][h]
                ratio = min(1.0, v / peak)
                # interpolate from #F8E5C5 → #B05A1E
                r = int(0xF8 + (0xB0 - 0xF8) * ratio)
                g = int(0xE5 + (0x5A - 0xE5) * ratio)
                b = int(0xC5 + (0x1E - 0xC5) * ratio)
                color = f"#{r:02x}{g:02x}{b:02x}"
                tk.Label(row, text=f"£{v:.0f}" if v else "·", width=4,
                         bg=color, font=("Arial", 8),
                         relief="flat").pack(side="left", padx=0, pady=0)
        tk.Label(self._heatmap_canvas,
                 text=f"Peak cell £{peak:.2f} · {days}-day window",
                 bg=self.colors["background"],
                 font=("Arial", 10, "italic")).pack(anchor="w", pady=4)

    def _build_mix_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Last N days:", bg=bg).pack(side="left")
        self._mix_days = tk.StringVar(value="30")
        tk.Entry(top, textvariable=self._mix_days, width=4).pack(side="left", padx=4)
        tk.Button(top, text="↻ Recompute", command=self._mix_refresh,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        cols = ("item", "units", "revenue", "mix_pct", "cost", "gross", "margin_pct")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=20)
        for c, h, w in [("item", "Item", 180), ("units", "Units", 80),
                        ("revenue", "Revenue", 100),
                        ("mix_pct", "% of mix", 90),
                        ("cost", "BOM cost", 100),
                        ("gross", "Gross £", 100),
                        ("margin_pct", "Margin %", 90)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._mix_tree = tv
        self._mix_refresh()

    def _mix_refresh(self):
        try:
            days = int(self._mix_days.get())
        except ValueError:
            days = 30
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        # Tally per item
        sold = {}; rev = {}
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT items_json FROM bakery_orders WHERE timestamp >= ? "
                "AND (refunded IS NULL OR refunded = 0)", (cutoff,)).fetchall()
            # Per-item BOM cost
            bom_cost = {}
            for it, in conn.execute(
                "SELECT DISTINCT item_name FROM bakery_recipes").fetchall():
                rcs = conn.execute(
                    "SELECT r.quantity, COALESCE(i.unit_cost,0) "
                    "FROM bakery_recipes r LEFT JOIN bakery_ingredients i "
                    "ON r.ingredient = i.name WHERE r.item_name=?",
                    (it,)).fetchall()
                bom_cost[it] = sum((q or 0) * (uc or 0) for q, uc in rcs)
        finally:
            conn.close()
        for (items,) in rows:
            try:
                d = json.loads(items)
            except Exception:
                continue
            for it, info in d.items():
                q = info.get("quantity", 0) if isinstance(info, dict) else int(info)
                p = info.get("price", 0) if isinstance(info, dict) else 0
                sold[it] = sold.get(it, 0) + q
                rev[it] = rev.get(it, 0.0) + q * p
        total_rev = sum(rev.values()) or 1.0
        tv = self._mix_tree
        tv.delete(*tv.get_children())
        for it in sorted(sold, key=lambda k: -rev.get(k, 0)):
            units = sold[it]; r = rev.get(it, 0)
            mix_pct = r / total_rev * 100
            cost = bom_cost.get(it, 0) * units
            gross = r - cost
            margin = (gross / r * 100) if r else 0
            tv.insert("", "end", values=(
                it, units, f"£{r:.2f}", f"{mix_pct:.1f}%",
                f"£{cost:.2f}", f"£{gross:.2f}", f"{margin:.1f}%"))

    def _build_waste_dash_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Last N days:", bg=bg).pack(side="left")
        self._wdash_days = tk.StringVar(value="30")
        tk.Entry(top, textvariable=self._wdash_days, width=4).pack(side="left", padx=4)
        tk.Button(top, text="↻ Recompute", command=self._wdash_refresh,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        self._wdash_summary_lbl = tk.Label(parent, text="",
                                            font=("Arial", 12, "bold"), bg=bg)
        self._wdash_summary_lbl.pack(anchor="w", padx=14, pady=6)
        cols = ("reason", "events", "qty", "cost")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c, h, w in [("reason", "Reason", 150), ("events", "Events", 80),
                        ("qty", "Qty", 90), ("cost", "Cost", 120)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=14, pady=6)
        self._wdash_reason_tree = tv

        tk.Label(parent, text="Worst items", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=14, pady=(8, 0))
        cols2 = ("item", "events", "qty", "cost")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=12)
        for c, h, w in [("item", "Item", 180), ("events", "Events", 80),
                        ("qty", "Qty", 90), ("cost", "Cost", 120)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=14, pady=6)
        self._wdash_item_tree = tv2
        self._wdash_refresh()

    def _wdash_refresh(self):
        try:
            days = int(self._wdash_days.get())
        except ValueError:
            days = 30
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            total = conn.execute(
                "SELECT COALESCE(SUM(cost), 0), COALESCE(SUM(quantity), 0) "
                "FROM bakery_waste_log WHERE timestamp >= ?",
                (cutoff,)).fetchone()
            by_reason = conn.execute(
                "SELECT reason_code, COUNT(*), SUM(quantity), SUM(cost) "
                "FROM bakery_waste_log WHERE timestamp >= ? "
                "GROUP BY reason_code ORDER BY SUM(cost) DESC", (cutoff,)
            ).fetchall()
            by_item = conn.execute(
                "SELECT item_name, COUNT(*), SUM(quantity), SUM(cost) "
                "FROM bakery_waste_log WHERE timestamp >= ? "
                "GROUP BY item_name ORDER BY SUM(cost) DESC LIMIT 20",
                (cutoff,)).fetchall()
        finally:
            conn.close()
        self._wdash_summary_lbl.config(
            text=f"{days}-day total: {total[1]:g} units · £{total[0]:.2f} cost")
        tv = self._wdash_reason_tree; tv.delete(*tv.get_children())
        for r, ev, q, c in by_reason:
            tv.insert("", "end", values=(r, ev, f"{q:g}",
                                         f"£{(c or 0):.2f}"))
        tv2 = self._wdash_item_tree; tv2.delete(*tv2.get_children())
        for it, ev, q, c in by_item:
            tv2.insert("", "end", values=(it, ev, f"{q:g}",
                                          f"£{(c or 0):.2f}"))

    def _build_forecast_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Forecast tomorrow's production from weekday history. "
                 "Apply an optional weather adjustment (rain dampens walk-ins, "
                 "sun lifts cold drinks).",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=4)
        tk.Label(top, text="Weather:", bg=bg).pack(side="left")
        self._forecast_weather = tk.StringVar(value="normal")
        ttk.Combobox(top, textvariable=self._forecast_weather,
                     values=["normal", "rainy", "sunny", "snow"],
                     state="readonly", width=10).pack(side="left", padx=4)
        tk.Button(top, text="🔮 Forecast tomorrow",
                  command=self._forecast_run,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="📋 Copy to Production Planner",
                  command=self._forecast_to_planner,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        cols = ("item", "weekday_avg", "weather_mult", "forecast")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("item", "Item", 200),
                        ("weekday_avg", "Weekday avg", 120),
                        ("weather_mult", "Weather ×", 120),
                        ("forecast", "Forecast units", 140)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._forecast_tree = tv
        self._forecast_results = {}

    def _forecast_run(self):
        tomorrow_wd = (datetime.now() + timedelta(days=1)).weekday()
        weather = self._forecast_weather.get()
        mults = self.WEATHER_MULTIPLIERS.get(weather, {})
        cutoff = (datetime.now() - timedelta(days=56)).strftime("%Y-%m-%d %H:%M:%S")
        # Average qty per matching weekday
        per_item_wd_qty = {}
        wd_count = {}
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, items_json FROM bakery_orders "
                "WHERE timestamp >= ? AND (refunded IS NULL OR refunded=0)",
                (cutoff,)).fetchall()
        finally:
            conn.close()
        seen_days = set()
        for ts, items in rows:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if dt.weekday() != tomorrow_wd:
                continue
            day_key = dt.strftime("%Y-%m-%d")
            seen_days.add(day_key)
            try:
                d = json.loads(items)
            except Exception:
                continue
            for it, info in d.items():
                q = info.get("quantity", 0) if isinstance(info, dict) else int(info)
                per_item_wd_qty[it] = per_item_wd_qty.get(it, 0) + q
        n_days = max(1, len(seen_days))
        tv = self._forecast_tree
        tv.delete(*tv.get_children())
        self._forecast_results = {}
        for cat, items in self.products.items():
            for it in items:
                avg = per_item_wd_qty.get(it, 0) / n_days
                mult = mults.get(cat, mults.get("default", 1.0))
                forecast = int(round(avg * mult))
                tv.insert("", "end", values=(it, f"{avg:.1f}",
                                              f"{mult:.2f}", forecast))
                self._forecast_results[it] = forecast
        self.set_status(
            f"Forecast: weekday={tomorrow_wd}, "
            f"{n_days} historical day(s), weather={weather}.")

    def _forecast_to_planner(self):
        if not self._forecast_results:
            messagebox.showinfo("Forecast", "Run a forecast first.",
                                parent=self.root); return
        if hasattr(self, "_planner_forecasts"):
            self._planner_forecasts.update(self._forecast_results)
            try:
                self._planner_refresh()
            except Exception:
                pass
            messagebox.showinfo("Forecast",
                                "Copied to Production Planner.",
                                parent=self.root)

    def _build_topbot_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Last N days:", bg=bg).pack(side="left")
        self._topbot_days = tk.StringVar(value="60")
        tk.Entry(top, textvariable=self._topbot_days, width=4).pack(side="left", padx=4)
        tk.Button(top, text="↻ Compute", command=self._topbot_refresh,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)

        frame = tk.Frame(parent, bg=bg); frame.pack(fill="both", expand=True,
                                                     padx=10, pady=6)
        lf1 = tk.LabelFrame(frame, text="🏆 Top 10", bg=bg,
                            font=("Arial", 11, "bold"))
        lf1.pack(side="left", fill="both", expand=True, padx=4)
        cols = ("item", "units", "revenue")
        self._top_tree = ttk.Treeview(lf1, columns=cols, show="headings",
                                       height=14)
        for c, h, w in [("item", "Item", 200), ("units", "Units", 80),
                        ("revenue", "Revenue", 110)]:
            self._top_tree.heading(c, text=h)
            self._top_tree.column(c, width=w, anchor="w")
        self._top_tree.pack(fill="both", expand=True)

        lf2 = tk.LabelFrame(frame, text="📉 Bottom 10 (consider delist)",
                            bg=bg, font=("Arial", 11, "bold"))
        lf2.pack(side="left", fill="both", expand=True, padx=4)
        self._bot_tree = ttk.Treeview(lf2, columns=cols, show="headings",
                                       height=14)
        for c, h, w in [("item", "Item", 200), ("units", "Units", 80),
                        ("revenue", "Revenue", 110)]:
            self._bot_tree.heading(c, text=h)
            self._bot_tree.column(c, width=w, anchor="w")
        self._bot_tree.pack(fill="both", expand=True)
        self._topbot_refresh()

    def _topbot_refresh(self):
        try:
            days = int(self._topbot_days.get())
        except ValueError:
            days = 60
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        sold = {}; rev = {}
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT items_json FROM bakery_orders WHERE timestamp >= ? "
                "AND (refunded IS NULL OR refunded=0)", (cutoff,)).fetchall()
        finally:
            conn.close()
        for (items,) in rows:
            try:
                d = json.loads(items)
            except Exception:
                continue
            for it, info in d.items():
                q = info.get("quantity", 0) if isinstance(info, dict) else int(info)
                p = info.get("price", 0) if isinstance(info, dict) else 0
                sold[it] = sold.get(it, 0) + q
                rev[it] = rev.get(it, 0) + q * p
        all_items = [(it, sold.get(it, 0), rev.get(it, 0))
                     for cat in self.products.values() for it in cat]
        # Top by revenue
        all_items.sort(key=lambda x: -x[2])
        self._top_tree.delete(*self._top_tree.get_children())
        for it, u, r in all_items[:10]:
            self._top_tree.insert("", "end",
                                   values=(it, u, f"£{r:.2f}"))
        all_items.sort(key=lambda x: (x[1], x[2]))
        self._bot_tree.delete(*self._bot_tree.get_children())
        for it, u, r in all_items[:10]:
            self._bot_tree.insert("", "end",
                                   values=(it, u, f"£{r:.2f}"))

    def _build_pipeline_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="↻ Refresh", command=self._pipeline_refresh,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        self._pipeline_summary = tk.Label(top, text="",
                                           bg=bg, font=("Arial", 11, "bold"))
        self._pipeline_summary.pack(side="left", padx=14)
        cols = ("status", "count", "value", "deposits_paid")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c, h, w in [("status", "Status", 150), ("count", "Count", 80),
                        ("value", "Total quoted", 140),
                        ("deposits_paid", "Deposits paid £", 140)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._pipeline_tree = tv

        tk.Label(parent, text="Upcoming events",
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w",
                                                          padx=12, pady=(8, 0))
        cols2 = ("event_date", "customer", "type", "servings", "quoted",
                 "deposit", "status")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=14)
        for c, h, w in [("event_date", "Event date", 110),
                        ("customer", "Customer", 150),
                        ("type", "Type", 100), ("servings", "Serves", 80),
                        ("quoted", "Quoted £", 100),
                        ("deposit", "Deposit", 100),
                        ("status", "Status", 100)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._pipeline_events_tree = tv2
        self._pipeline_refresh()

    def _pipeline_refresh(self):
        conn = self._connect()
        try:
            agg = conn.execute(
                "SELECT status, COUNT(*), COALESCE(SUM(quoted_price),0), "
                "COALESCE(SUM(CASE WHEN deposit_paid=1 THEN deposit_amount "
                "ELSE 0 END),0) FROM bakery_event_quotes "
                "GROUP BY status ORDER BY status").fetchall()
            events = conn.execute(
                "SELECT event_date, customer, event_type, servings, "
                "quoted_price, deposit_amount, deposit_paid, status "
                "FROM bakery_event_quotes WHERE event_date >= date('now') "
                "ORDER BY event_date ASC LIMIT 200").fetchall()
            grand = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(quoted_price), 0) "
                "FROM bakery_event_quotes "
                "WHERE status IN ('draft', 'sent', 'accepted')").fetchone()
        finally:
            conn.close()
        tv = self._pipeline_tree; tv.delete(*tv.get_children())
        for st, cnt, val, dep in agg:
            tv.insert("", "end", values=(st, cnt, f"£{val:.2f}", f"£{dep:.2f}"))
        tv2 = self._pipeline_events_tree; tv2.delete(*tv2.get_children())
        for ed, cust, et, sv, qp, da, dp, st in events:
            tv2.insert("", "end",
                       values=(ed, cust, et or "", sv or "",
                               f"£{(qp or 0):.2f}",
                               f"£{(da or 0):.2f}{' ✓' if dp else ''}",
                               st))
        self._pipeline_summary.config(
            text=f"Open pipeline: {grand[0]} quotes · £{grand[1]:.2f} value")

    def _build_temp_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Log reading", command=self._temp_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._temp_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        self._temp_summary = tk.Label(top, text="", bg=bg,
                                       font=("Arial", 10, "bold"))
        self._temp_summary.pack(side="left", padx=14)
        cols = ("ts", "unit", "temp", "expected", "ok", "by", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("ts", "When", 150), ("unit", "Unit", 110),
                        ("temp", "Temp °C", 90), ("expected", "Range", 110),
                        ("ok", "OK?", 60), ("by", "By", 110),
                        ("notes", "Notes", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._temp_tree = tv
        self._temp_refresh()

    def _temp_refresh(self):
        tv = self._temp_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, unit_name, temp_c, expected_min, "
                "expected_max, ok, logged_by, notes FROM bakery_temp_logs "
                "ORDER BY id DESC LIMIT 200").fetchall()
            bad = conn.execute(
                "SELECT COUNT(*) FROM bakery_temp_logs "
                "WHERE ok=0 AND date(timestamp) = date('now')").fetchone()[0]
        finally:
            conn.close()
        for ts, u, t, lo, hi, ok, by, nt in rows:
            rng = (f"{lo:g}-{hi:g}" if lo is not None and hi is not None else "")
            tv.insert("", "end", values=(ts, u, f"{t:g}", rng,
                                         "✓" if ok else "✗",
                                         by or "", nt or ""),
                      tags=("bad" if not ok else "",))
        tv.tag_configure("bad", background="#FFD9D9")
        self._temp_summary.config(
            text=f"Out-of-range today: {bad}" if bad else "All in range today.")

    def _temp_add(self):
        d = tk.Toplevel(self.root); d.title("Temperature reading")
        d.transient(self.root); d.grab_set()
        fields = [("Unit (eg fridge-1)", "fridge-1"),
                  ("Temp °C", "3.5"),
                  ("Expected min", "1.0"),
                  ("Expected max", "5.0"),
                  ("Notes", "")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            tk.Entry(d, textvariable=v, width=22).grid(row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                t = float(vars_[1].get())
                lo = float(vars_[2].get()); hi = float(vars_[3].get())
            except ValueError:
                messagebox.showerror("Temp", "Numeric.", parent=d); return
            ok = 1 if (lo <= t <= hi) else 0
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_temp_logs "
                    "(unit_name, temp_c, expected_min, expected_max, ok, "
                    "timestamp, logged_by, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (vars_[0].get(), t, lo, hi, ok, now,
                     self.current_user or "system", vars_[4].get()))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._temp_refresh()
            if not ok:
                messagebox.showwarning(
                    "Temp", "Out of expected range — investigate.",
                    parent=self.root)
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _build_haccp_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add CCP", command=self._haccp_add_ccp,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Log check (selected CCP)",
                  command=self._haccp_log_check,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🌱 Seed defaults",
                  command=self._haccp_seed_defaults,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._haccp_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        tk.Label(parent, text="CCPs", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols = ("id", "name", "target", "freq", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c, h, w in [("id", "ID", 50), ("name", "CCP", 200),
                        ("target", "Target", 200), ("freq", "Freq", 120),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=4)
        self._haccp_tree = tv

        tk.Label(parent, text="Check log", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("ts", "ccp", "value", "pass", "by", "action")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=12)
        for c, h, w in [("ts", "When", 150), ("ccp", "CCP", 150),
                        ("value", "Value", 110), ("pass", "Pass", 60),
                        ("by", "By", 120), ("action", "Corrective", 200)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._haccp_checks_tree = tv2
        self._haccp_refresh()

    def _haccp_seed_defaults(self):
        conn = self._connect()
        try:
            existing = {r[0] for r in conn.execute(
                "SELECT ccp_name FROM bakery_haccp_ccps").fetchall()}
            for n, desc, tgt, fq in self.DEFAULT_CCPS:
                if n in existing:
                    continue
                conn.execute(
                    "INSERT INTO bakery_haccp_ccps "
                    "(ccp_name, description, target_value, frequency, active) "
                    "VALUES (?,?,?,?,1)", (n, desc, tgt, fq))
            conn.commit()
        finally:
            conn.close()
        self._haccp_refresh()

    def _haccp_refresh(self):
        conn = self._connect()
        try:
            ccps = conn.execute(
                "SELECT id, ccp_name, target_value, frequency, active "
                "FROM bakery_haccp_ccps ORDER BY id").fetchall()
            checks = conn.execute(
                "SELECT c.timestamp, p.ccp_name, c.value, c.pass, "
                "c.checked_by, c.corrective_action FROM bakery_haccp_checks c "
                "JOIN bakery_haccp_ccps p ON c.ccp_id = p.id "
                "ORDER BY c.id DESC LIMIT 100").fetchall()
        finally:
            conn.close()
        tv = self._haccp_tree; tv.delete(*tv.get_children())
        for rid, n, tgt, fq, a in ccps:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, tgt or "", fq or "",
                              "yes" if a else "no"))
        tv2 = self._haccp_checks_tree; tv2.delete(*tv2.get_children())
        for ts, n, v, p, by, ca in checks:
            tag = "ok" if p else "bad"
            tv2.insert("", "end", values=(ts, n, v or "", "✓" if p else "✗",
                                          by or "", ca or ""), tags=(tag,))
        tv2.tag_configure("ok", background="#E6F4EA")
        tv2.tag_configure("bad", background="#FFD9D9")

    def _haccp_add_ccp(self):
        n = simpledialog.askstring("CCP", "Name:", parent=self.root)
        if not n:
            return
        tgt = simpledialog.askstring("CCP", "Target value:", parent=self.root) or ""
        fq = simpledialog.askstring("CCP", "Frequency:",
                                    initialvalue="per-shift",
                                    parent=self.root) or "per-shift"
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO bakery_haccp_ccps "
                "(ccp_name, target_value, frequency, active) "
                "VALUES (?,?,?,1)", (n, tgt, fq))
            conn.commit()
        finally:
            conn.close()
        self._haccp_refresh()

    def _haccp_log_check(self):
        sel = self._haccp_tree.focus()
        if not sel:
            return
        val = simpledialog.askstring("Check", "Measured value:",
                                     parent=self.root) or ""
        passed = messagebox.askyesno("Check", "Pass?", parent=self.root)
        action = "" if passed else (
            simpledialog.askstring("Check", "Corrective action:",
                                   parent=self.root) or "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_haccp_checks "
                "(ccp_id, value, pass, timestamp, checked_by, "
                "corrective_action) VALUES (?,?,?,?,?,?)",
                (int(sel), val, 1 if passed else 0, now,
                 self.current_user or "system", action))
            conn.commit()
        finally:
            conn.close()
        self._haccp_refresh()

    def _build_wash_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Log wash-down", command=self._wash_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Verify selected",
                  command=self._wash_verify,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._wash_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("ts", "area", "allergen", "by", "verified_by", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("ts", "When", 150), ("area", "Area", 150),
                        ("allergen", "Allergen", 120), ("by", "By", 130),
                        ("verified_by", "Verified by", 130),
                        ("notes", "Notes", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._wash_tree = tv
        self._wash_refresh()

    def _wash_refresh(self):
        tv = self._wash_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, timestamp, area, allergen, performed_by, "
                "verified_by, notes FROM bakery_wash_logs "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for rid, ts, ar, al, pb, vb, nt in rows:
            tag = "unv" if not vb else ""
            tv.insert("", "end", iid=str(rid),
                      values=(ts, ar, al or "", pb or "", vb or "",
                              nt or ""), tags=(tag,))
        tv.tag_configure("unv", background="#FFF2CC")

    def _wash_add(self):
        d = tk.Toplevel(self.root); d.title("Wash-down log")
        d.transient(self.root); d.grab_set()
        fields = [("Area (eg 'Mixer 2')", ""),
                  ("Allergen being cleaned for", "nuts"),
                  ("Notes", "")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            tk.Entry(d, textvariable=v, width=28).grid(row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_wash_logs "
                    "(area, allergen, timestamp, performed_by, notes) "
                    "VALUES (?,?,?,?,?)",
                    (vars_[0].get(), vars_[1].get(), now,
                     self.current_user or "system", vars_[2].get()))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._wash_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _wash_verify(self):
        sel = self._wash_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_wash_logs SET verified_by=? WHERE id=?",
                (self.current_user or "system", int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._wash_refresh()

    def _build_invoice_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Record invoice", command=self._invoice_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Accept", command=lambda: self._invoice_set("accepted"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Reject", command=self._invoice_reject,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._invoice_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "invoice", "supplier", "date", "amount", "received",
                "status", "reason")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("invoice", "Invoice #", 110),
                        ("supplier", "Supplier", 150),
                        ("date", "Date", 100), ("amount", "Amount", 100),
                        ("received", "Received", 150),
                        ("status", "Status", 100),
                        ("reason", "Reject reason", 200)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._invoice_tree = tv
        self._invoice_refresh()

    def _invoice_refresh(self):
        tv = self._invoice_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT i.id, i.invoice_number, s.name, i.invoice_date, "
                "i.amount, i.received_at, i.status, i.rejection_reason "
                "FROM bakery_supplier_invoices i "
                "LEFT JOIN bakery_suppliers s ON s.id = i.supplier_id "
                "ORDER BY i.id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for rid, inv, sup, dte, amt, rcv, st, rsn in rows:
            tag = {"accepted": "ok", "rejected": "bad"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(rid, inv or "", sup or "", dte or "",
                              f"£{(amt or 0):.2f}", rcv or "",
                              st, rsn or ""), tags=(tag,))
        tv.tag_configure("ok", background="#E6F4EA")
        tv.tag_configure("bad", background="#FFD9D9")

    def _invoice_add(self):
        conn = self._connect()
        try:
            sups = conn.execute(
                "SELECT id, name FROM bakery_suppliers ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        d = tk.Toplevel(self.root); d.title("Record invoice")
        d.transient(self.root); d.grab_set()
        sup_var = tk.StringVar(value="")
        inv_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        amt_var = tk.StringVar(value="0.00")
        tk.Label(d, text="Supplier:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        sup_map = {n: i for i, n in sups}
        sup_names = list(sup_map.keys()) or ["(none — add suppliers first)"]
        ttk.Combobox(d, textvariable=sup_var, values=sup_names,
                     state="readonly", width=24).grid(row=0, column=1, padx=8, pady=4)
        tk.Label(d, text="Invoice #:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=inv_var, width=22).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Invoice date:").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=date_var, width=14).grid(row=2, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Amount £:").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=amt_var, width=12).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                amt = float(amt_var.get())
            except ValueError:
                messagebox.showerror("Invoice", "Bad amount.", parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sid = sup_map.get(sup_var.get())
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_supplier_invoices "
                    "(supplier_id, invoice_number, invoice_date, amount, "
                    "received_at, received_by, status) "
                    "VALUES (?,?,?,?,?,?, 'pending')",
                    (sid, inv_var.get(), date_var.get(), amt, now,
                     self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._invoice_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=4, column=0, columnspan=2, pady=10)

    def _invoice_set(self, status):
        sel = self._invoice_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_supplier_invoices SET status=? WHERE id=?",
                (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._invoice_refresh()

    def _invoice_reject(self):
        sel = self._invoice_tree.focus()
        if not sel:
            return
        reason = simpledialog.askstring("Reject", "Reason:",
                                        parent=self.root) or ""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_supplier_invoices "
                "SET status='rejected', rejection_reason=? WHERE id=?",
                (reason, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._invoice_refresh()

    def _build_trace_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Capture ingredient lot numbers for each produced batch — "
                 "so a contamination event can be traced from lot → batch → "
                 "outgoing orders within seconds.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Record trace", command=self._trace_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🔎 Lookup by lot", command=self._trace_lookup,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._trace_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "batch", "item", "lots", "produced", "by")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("batch", "Batch", 80),
                        ("item", "Item", 160),
                        ("lots", "Ingredient lots", 360),
                        ("produced", "Produced", 150), ("by", "By", 110)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._trace_tree = tv
        self._trace_refresh()

    def _trace_refresh(self):
        tv = self._trace_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, product_batch_id, item_name, "
                "ingredient_lots_json, produced_at, produced_by "
                "FROM bakery_traceability ORDER BY id DESC LIMIT 200"
            ).fetchall()
        finally:
            conn.close()
        for rid, b, it, lots, pa, by in rows:
            try:
                d = json.loads(lots) if lots else {}
                desc = ", ".join(f"{k}={v}" for k, v in d.items())
            except Exception:
                desc = lots or ""
            tv.insert("", "end", values=(rid, b or "", it, desc, pa, by or ""))

    def _trace_add(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title("Record traceability")
        d.transient(self.root); d.grab_set()
        item_var = tk.StringVar(value=names[0] if names else "")
        batch_var = tk.StringVar()
        lots_var = tk.StringVar(value="flour=LOT123,butter=LOT456")
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=item_var, values=names,
                     state="readonly", width=24).grid(row=0, column=1, padx=8, pady=4)
        tk.Label(d, text="Product batch ID (optional):").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=batch_var, width=12).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Lots (ing=LOT,...):").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=lots_var, width=40).grid(row=2, column=1, padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lots = {}
            for chunk in lots_var.get().split(","):
                if "=" in chunk:
                    k, v = chunk.split("=", 1)
                    if k.strip() and v.strip():
                        lots[k.strip()] = v.strip()
            try:
                bid = int(batch_var.get()) if batch_var.get().strip() else None
            except ValueError:
                bid = None
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_traceability "
                    "(product_batch_id, item_name, ingredient_lots_json, "
                    "produced_at, produced_by) VALUES (?,?,?,?,?)",
                    (bid, item_var.get(), json.dumps(lots), now,
                     self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._trace_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=3, column=0, columnspan=2, pady=10)

    def _trace_lookup(self):
        lot = simpledialog.askstring("Lookup", "Lot number to search for:",
                                     parent=self.root)
        if not lot:
            return
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, item_name, ingredient_lots_json, produced_at "
                "FROM bakery_traceability "
                "WHERE ingredient_lots_json LIKE ?",
                (f"%{lot}%",)).fetchall()
        finally:
            conn.close()
        if not rows:
            messagebox.showinfo("Trace",
                                f"No batches reference lot '{lot}'.",
                                parent=self.root); return
        out = "\n".join(f"Batch {rid} · {it} · {pa}" for rid, it, _, pa in rows)
        messagebox.showinfo("Trace", out, parent=self.root)

