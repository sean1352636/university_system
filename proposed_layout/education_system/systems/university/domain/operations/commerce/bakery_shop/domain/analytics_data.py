"""AnalyticsDataMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class AnalyticsDataMixin:
    @staticmethod
    def _parse_order_dt(o):
        try:
            return datetime.strptime(o["timestamp"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _orders_in_range(self, start_dt, end_dt, *, include_refunded=False):
        for o in self.orders:
            dt = self._parse_order_dt(o)
            if not dt:
                continue
            if dt < start_dt or dt > end_dt:
                continue
            if not include_refunded and o.get("refunded"):
                continue
            yield o, dt

    def _range_for_period(self, period, *, anchor=None):
        anchor = anchor or datetime.now()
        if period == "today":
            start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, anchor
        if period == "yesterday":
            y = anchor - timedelta(days=1)
            start = y.replace(hour=0, minute=0, second=0, microsecond=0)
            end = y.replace(hour=23, minute=59, second=59, microsecond=0)
            return start, end
        if period == "week":
            start = (anchor - timedelta(days=6)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return start, anchor
        if period == "month":
            start = (anchor - timedelta(days=29)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return start, anchor
        if period == "year":
            start = (anchor - timedelta(days=364)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return start, anchor
        # default: lifetime
        return datetime(2000, 1, 1), anchor

    def sales_summary(self, period="today"):
        try:
            start, end = self._range_for_period(period)
            orders = list(self._orders_in_range(start, end))
            revenue = sum(float(o.get("total") or 0) for o, _ in orders)
            tips = sum(float(o.get("tip_amount") or 0) for o, _ in orders)
            vat = sum(float(o.get("vat_amount") or 0) for o, _ in orders)
            discount = sum(float(o.get("discount") or 0) for o, _ in orders)
            items_count = sum(sum((o.get("items") or {}).values())
                              for o, _ in orders)
            refunded = sum(1 for o in self.orders
                           if o.get("refunded") and self._parse_order_dt(o)
                           and start <= self._parse_order_dt(o) <= end)
            return {
                "period": period, "start": start, "end": end,
                "orders_count": len(orders),
                "items_count": items_count,
                "revenue": round(revenue, 2),
                "tips": round(tips, 2),
                "vat": round(vat, 2),
                "discount": round(discount, 2),
                "refunded_count": refunded,
                "avg_order": round(revenue / len(orders), 2) if orders else 0.0,
            }
        except Exception:
            logger.exception("sales_summary failed period=%s", period)
            return {"period": period, "orders_count": 0, "revenue": 0.0,
                    "items_count": 0, "tips": 0, "vat": 0, "discount": 0,
                    "refunded_count": 0, "avg_order": 0}

    def revenue_series(self, period="week"):
        """Return a list of (label, revenue) buckets for a chart. Daily
        buckets for week/month, monthly buckets for year."""
        start, end = self._range_for_period(period)
        if period == "year":
            buckets = {}
            cursor = start
            while cursor <= end:
                key = cursor.strftime("%Y-%m")
                buckets[key] = 0.0
                year, month = cursor.year, cursor.month + 1
                if month > 12:
                    month = 1; year += 1
                try:
                    cursor = datetime(year, month, 1)
                except ValueError:
                    break
            for o, dt in self._orders_in_range(start, end):
                key = dt.strftime("%Y-%m")
                if key in buckets:
                    buckets[key] += float(o.get("total") or 0)
            return [(k, round(v, 2)) for k, v in buckets.items()]
        days = (end.date() - start.date()).days + 1
        buckets = {(start.date() + timedelta(days=i)).isoformat(): 0.0
                   for i in range(max(days, 1))}
        for o, dt in self._orders_in_range(start, end):
            key = dt.date().isoformat()
            if key in buckets:
                buckets[key] += float(o.get("total") or 0)
        return [(k, round(v, 2)) for k, v in buckets.items()]

    def top_sellers(self, period="week", n=10):
        start, end = self._range_for_period(period)
        tally = {}
        revenue = {}
        for o, _ in self._orders_in_range(start, end):
            for item, qty in (o.get("items") or {}).items():
                tally[item] = tally.get(item, 0) + int(qty)
                info = self._product_info(item)
                price = float(info["price"]) if info else 0.0
                revenue[item] = revenue.get(item, 0) + price * int(qty)
        ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [(item, qty, round(revenue.get(item, 0.0), 2))
                for item, qty in ranked]

    def slow_movers(self, period="week", n=10):
        """Products with the lowest sales in the period, including
        items that didn't sell at all."""
        start, end = self._range_for_period(period)
        sold = {item: 0 for cat in self.products.values()
                for item in cat}
        for o, _ in self._orders_in_range(start, end):
            for item, qty in (o.get("items") or {}).items():
                if item in sold:
                    sold[item] += int(qty)
        ranked = sorted(sold.items(), key=lambda kv: kv[1])
        return ranked[:n]

    def revenue_by_tier(self, period="month"):
        start, end = self._range_for_period(period)
        tally = {"Student": 0.0, "Staff": 0.0, "Admin": 0.0, "Guest": 0.0}
        for o, _ in self._orders_in_range(start, end):
            tier = o.get("user_type") or "Guest"
            tally[tier] = tally.get(tier, 0.0) + float(o.get("total") or 0)
        return {k: round(v, 2) for k, v in tally.items()}

    def busy_heatmap(self, period="month"):
        """Return a {(weekday, hour): count} mapping; weekday is 0=Mon."""
        start, end = self._range_for_period(period)
        grid = {(d, h): 0 for d in range(7) for h in range(24)}
        for _, dt in self._orders_in_range(start, end):
            grid[(dt.weekday(), dt.hour)] = grid.get((dt.weekday(), dt.hour), 0) + 1
        return grid

    def shrinkage_report(self):
        """Aggregate expired and depleted batches into a shrinkage value
        using product list price as the cost-of-goods proxy."""
        rows = self._query("""SELECT item_name, quantity, initial_quantity,
                                     expiry_date, status, received_date
                              FROM bakery_batches
                              WHERE status IN ('expired', 'depleted')""")
        by_item = {}
        for r in rows:
            item, qty, initial, exp, status, received = r
            info = self._product_info(item)
            unit_price = float(info["price"]) if info else 0.0
            lost_qty = 0
            if status == "expired":
                lost_qty = int(qty or 0)
            entry = by_item.setdefault(item, {
                "item_name": item, "expired_units": 0,
                "depleted_units": 0, "shrinkage_value": 0.0,
                "unit_price": unit_price,
            })
            if status == "expired":
                entry["expired_units"] += lost_qty
                entry["shrinkage_value"] += lost_qty * unit_price
            else:
                entry["depleted_units"] += int((initial or 0) - (qty or 0))
        total = sum(v["shrinkage_value"] for v in by_item.values())
        return {"by_item": list(by_item.values()),
                "total_loss": round(total, 2)}

    def _exports_dir(self):
        try:
            from education_system.systems.university.infrastructure.paths import EXPORTS_BAKERY_DIR
            path = str(EXPORTS_BAKERY_DIR)
        except Exception:
            # Fallback: data/exports/bakery under the package root.
            here = os.path.dirname(os.path.abspath(__file__))
            root = here
            for _ in range(8):
                if os.path.basename(root) == "university_system":
                    break
                root = os.path.dirname(root)
            path = os.path.join(root, "data", "exports", "bakery")
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            logger.exception("Could not create exports dir")
        return path

    def export_sales_csv(self, period="month", *, out_path=None):
        import csv
        try:
            start, end = self._range_for_period(period)
            if not out_path:
                out_path = os.path.join(
                    self._exports_dir(),
                    f"sales_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["order_id", "timestamp", "user", "user_type",
                            "items", "subtotal", "discount", "vat", "tip",
                            "total", "payment_method", "refunded",
                            "promo_code", "billing_code", "gift_card"])
                for o, _ in self._orders_in_range(start, end,
                                                    include_refunded=True):
                    items_str = "; ".join(f"{n}x{q}"
                                          for n, q in (o.get("items") or {}).items())
                    w.writerow([
                        o.get("order_id"), o.get("timestamp"), o.get("user"),
                        o.get("user_type"), items_str,
                        o.get("subtotal"), o.get("discount"),
                        o.get("vat_amount") or 0, o.get("tip_amount") or 0,
                        o.get("total"), o.get("payment_method"),
                        1 if o.get("refunded") else 0,
                        o.get("promo_code") or "",
                        o.get("billing_code") or "",
                        o.get("gift_card_code") or "",
                    ])
            logger.info("Sales CSV exported period=%s -> %s",
                        period, out_path)
            return out_path
        except Exception:
            logger.exception("export_sales_csv failed period=%s", period)
            return None

    def export_sales_pdf(self, period="month", *, out_path=None):
        """Use reportlab if available; otherwise fall back to a .txt file
        with the same content."""
        summary = self.sales_summary(period)
        try:
            if not out_path:
                out_path = os.path.join(
                    self._exports_dir(),
                    f"sales_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                                  Spacer, Table, TableStyle)
                from reportlab.lib import colors
            except Exception:
                logger.warning("reportlab not installed; falling back to .txt")
                txt = out_path.replace(".pdf", ".txt")
                self._export_sales_text(period, summary, txt)
                return txt
            doc = SimpleDocTemplate(out_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"University Bakery — {period.title()} Sales Report",
                          styles["Title"]),
                Paragraph(f"{summary['start']} → {summary['end']}",
                          styles["Normal"]),
                Spacer(1, 12),
                Table([
                    ["Orders",        summary["orders_count"]],
                    ["Items sold",    summary["items_count"]],
                    ["Revenue (£)",   f"{summary['revenue']:.2f}"],
                    ["Tips (£)",      f"{summary['tips']:.2f}"],
                    ["VAT (£)",       f"{summary['vat']:.2f}"],
                    ["Discounts (£)", f"{summary['discount']:.2f}"],
                    ["Avg order (£)", f"{summary['avg_order']:.2f}"],
                    ["Refunds",       summary["refunded_count"]],
                ], style=TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ])),
                Spacer(1, 16),
                Paragraph("Top sellers", styles["Heading3"]),
                Table([["Item", "Units", "Revenue £"]] +
                      [[i, u, f"{r:.2f}"]
                       for i, u, r in self.top_sellers(period, 10)],
                      style=TableStyle([
                          ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                          ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                      ])),
            ]
            doc.build(story)
            logger.info("Sales PDF exported period=%s -> %s",
                        period, out_path)
            return out_path
        except Exception:
            logger.exception("export_sales_pdf failed period=%s", period)
            return None

    def _export_sales_text(self, period, summary, out_path):
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"University Bakery — {period.title()} Sales Report\n")
                f.write(f"{summary['start']} -> {summary['end']}\n\n")
                for k in ("orders_count", "items_count", "revenue", "tips",
                          "vat", "discount", "avg_order", "refunded_count"):
                    f.write(f"  {k}: {summary[k]}\n")
                f.write("\nTop sellers:\n")
                for i, u, r in self.top_sellers(period, 10):
                    f.write(f"  {i:30s}  {u:>5d} units   £{r:.2f}\n")
            logger.info("Sales TXT exported period=%s -> %s",
                        period, out_path)
        except Exception:
            logger.exception("_export_sales_text failed")

    def list_scheduled_reports(self):
        return self._query("""SELECT id, name, report_kind, frequency,
                                     recipients, format, last_run,
                                     next_run, active
                              FROM bakery_report_schedules
                              ORDER BY id DESC""")

    def add_scheduled_report(self, name, report_kind, frequency,
                             recipients, fmt="csv"):
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            next_run = self._compute_next_run(frequency)
            self._exec("""INSERT INTO bakery_report_schedules
                          (name, report_kind, frequency, recipients,
                           format, next_run, active, created_at, created_by)
                          VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                       (name, report_kind, frequency, recipients, fmt,
                        next_run, now, self.current_user or "system"))
            logger.info("Scheduled report added name=%s kind=%s freq=%s "
                        "next=%s", name, report_kind, frequency, next_run)
            return True
        except Exception:
            logger.exception("add_scheduled_report failed")
            return False

    def delete_scheduled_report(self, sid):
        self._exec("DELETE FROM bakery_report_schedules WHERE id=?", (sid,))

    def run_scheduled_report(self, sid):
        """Generate a report file for a scheduled-report config, email it
        to its recipients, and record the run."""
        rows = self._query("""SELECT id, name, report_kind, frequency,
                                     recipients, format
                              FROM bakery_report_schedules WHERE id=?""",
                           (sid,))
        if not rows:
            return None
        sid_, name, kind, freq, recipients, fmt = rows[0]
        try:
            period = "month"
            if kind == "sales":
                period = "month"
            out_path = (self.export_sales_pdf(period) if fmt == "pdf"
                         else self.export_sales_csv(period))
            delivered = []
            if out_path:
                try:
                    from education_system.systems.university.infrastructure.email.email_service import (
                        send_template_email, send_email,
                    )
                    body = (f"Scheduled bakery {kind} report ({period}) "
                             f"attached at {out_path}.")
                    subject = f"[Bakery] {name} — {period}"
                    for r in (recipients or "").split(","):
                        r = r.strip()
                        if not r:
                            continue
                        try:
                            # No real attachments in DB-only mode; we just
                            # email the path + summary.
                            send_email(r, subject, body)
                            delivered.append(r)
                        except Exception:
                            logger.exception("Scheduled report email to %s failed", r)
                except Exception:
                    logger.exception("Scheduled report send failed")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._exec("""INSERT INTO bakery_report_runs
                          (schedule_id, report_kind, range_start, range_end,
                           file_path, delivered_to, triggered_by, status,
                           timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (sid_, kind, period, period, out_path,
                        ", ".join(delivered),
                        self.current_user or "manual",
                        "ok" if out_path else "failed", now))
            self._exec("""UPDATE bakery_report_schedules SET last_run=?,
                          next_run=? WHERE id=?""",
                       (now, self._compute_next_run(freq), sid_))
            logger.info("Scheduled report run sid=%s file=%s delivered=%d",
                        sid_, out_path, len(delivered))
            return out_path
        except Exception:
            logger.exception("run_scheduled_report failed sid=%s", sid)
            return None

    def compute_partial_refund_amount(self, order, items):
        """Compute the refund value for a subset of an order's items,
        preserving the order's effective discount ratio so partial
        refunds are fair (£ refunded ≈ pro-rated share of total)."""
        try:
            order_items = order.get("items") or {}
            full_value = 0.0
            sub_value = 0.0
            for name, full_qty in order_items.items():
                info = self._product_info(name)
                price = float(info["price"]) if info else 0.0
                full_value += price * int(full_qty)
                take = int(items.get(name, 0))
                take = min(max(0, take), int(full_qty))
                sub_value += price * take
            if full_value <= 0:
                return 0.0
            ratio = sub_value / full_value
            return round(float(order.get("total") or 0) * ratio, 2)
        except Exception:
            logger.exception("compute_partial_refund_amount failed")
            return 0.0

