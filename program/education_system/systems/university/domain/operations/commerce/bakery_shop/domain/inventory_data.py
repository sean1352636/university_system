"""InventoryDataMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class InventoryDataMixin:
    def _generate_po_number(self):
        return f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def list_suppliers(self):
        return self._query("""SELECT id, name, contact, email, phone,
                                     lead_time_days, active
                              FROM bakery_suppliers ORDER BY name""")

    def add_supplier(self, name, *, contact=None, email=None, phone=None,
                     lead_time_days=3):
        try:
            self._exec("""INSERT INTO bakery_suppliers
                          (name, contact, email, phone, lead_time_days,
                           active, created_at)
                          VALUES (?, ?, ?, ?, ?, 1, ?)""",
                       (name, contact, email, phone, int(lead_time_days),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Supplier added: %s", name)
            return True
        except Exception:
            logger.exception("Failed to add supplier %s", name)
            return False

    def get_reorder_rule(self, item_name):
        rows = self._query("""SELECT item_name, min_stock, reorder_qty,
                                     supplier_id, unit_cost, auto
                              FROM bakery_reorder_rules WHERE item_name=?""",
                           (item_name,))
        if not rows:
            return None
        r = rows[0]
        return {"item_name": r[0], "min_stock": int(r[1] or 0),
                "reorder_qty": int(r[2] or 0), "supplier_id": r[3],
                "unit_cost": float(r[4] or 0), "auto": bool(r[5])}

    def set_reorder_rule(self, item_name, *, min_stock, reorder_qty,
                         supplier_id=None, unit_cost=0.0, auto=False):
        try:
            self._exec("""INSERT OR REPLACE INTO bakery_reorder_rules
                          (item_name, min_stock, reorder_qty, supplier_id,
                           unit_cost, auto, updated_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (item_name, int(min_stock), int(reorder_qty),
                        supplier_id, float(unit_cost), 1 if auto else 0,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Reorder rule set: %s min=%d qty=%d auto=%s",
                        item_name, min_stock, reorder_qty, bool(auto))
            return True
        except Exception:
            logger.exception("Failed to set reorder rule for %s", item_name)
            return False

    def create_purchase_order(self, items, supplier_id=None, *,
                              status="draft", notes="", created_by=None):
        """Create a PO. `items` is {item_name: qty} or list of dicts
        with {item, qty, unit_cost}. Stock isn't bumped until received."""
        try:
            if isinstance(items, dict):
                items = [{"item": k, "qty": int(v), "unit_cost": 0.0}
                         for k, v in items.items()]
            total = sum(float(x.get("unit_cost", 0)) * int(x["qty"]) for x in items)
            po_number = self._generate_po_number()
            lead = 3
            if supplier_id:
                rows = self._query(
                    "SELECT lead_time_days FROM bakery_suppliers WHERE id=?",
                    (supplier_id,))
                if rows:
                    lead = int(rows[0][0] or 3)
            expected = (datetime.now() + timedelta(days=lead)
                        ).strftime("%Y-%m-%d")
            self._exec("""INSERT INTO bakery_purchase_orders
                          (po_number, supplier_id, status, items_json,
                           created_at, expected_delivery, total_cost,
                           created_by, notes)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (po_number, supplier_id, status, json.dumps(items),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        expected, total, created_by or self.current_user,
                        notes))
            logger.info("PO created %s supplier=%s items=%d total=%.2f",
                        po_number, supplier_id, len(items), total)
            return po_number
        except Exception:
            logger.exception("Failed to create PO")
            return None

    def receive_purchase_order(self, po_id, *, default_shelf_days=7):
        """Mark a PO received: bump catalogue stock, create a batch per
        line. Best-effort — failures are logged and surfaced to the
        caller as False."""
        try:
            rows = self._query("""SELECT id, po_number, supplier_id, status,
                                          items_json FROM bakery_purchase_orders
                                  WHERE id=?""", (po_id,))
            if not rows:
                return False
            po = rows[0]
            if po[3] == "received":
                return False
            items = json.loads(po[4] or "[]")
            received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            expiry = (datetime.now()
                      + timedelta(days=default_shelf_days)
                      ).strftime("%Y-%m-%d")
            for line in items:
                item = line.get("item")
                qty = int(line.get("qty", 0))
                info = self._product_info(item)
                if not info:
                    logger.warning("PO %s receives unknown product %s",
                                   po[1], item)
                    continue
                info["stock"] = int(info.get("stock", 0)) + qty
                self._exec("""INSERT INTO bakery_batches
                              (item_name, quantity, initial_quantity,
                               expiry_date, received_date, lot_number,
                               supplier_id, po_id, status)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                           (item, qty, qty, expiry, received_at,
                            f"{po[1]}-{item[:3].upper()}",
                            po[2], po[0]))
            self._exec("""UPDATE bakery_purchase_orders
                          SET status='received', received_at=? WHERE id=?""",
                       (received_at, po_id))
            logger.info("PO received %s items=%d", po[1], len(items))
            return True
        except Exception:
            logger.exception("Failed to receive PO id=%s", po_id)
            return False

    def list_batches(self, *, include_depleted=False):
        sql = """SELECT id, item_name, quantity, initial_quantity,
                        expiry_date, received_date, lot_number, status
                 FROM bakery_batches"""
        if not include_depleted:
            sql += " WHERE status='active'"
        sql += " ORDER BY expiry_date ASC, id ASC"
        return self._query(sql)

    def _expire_batches(self):
        """Mark batches with expiry_date < today as 'expired'."""
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self._query("""SELECT id, item_name, quantity, expiry_date
                              FROM bakery_batches
                              WHERE status='active' AND expiry_date < ?""",
                           (today,))
        for r in rows:
            self._exec("UPDATE bakery_batches SET status='expired' WHERE id=?",
                       (r[0],))
            logger.warning("Batch %s expired item=%s qty=%d expiry=%s",
                           r[0], r[1], r[2], r[3])
        return len(rows)

    def _consume_batches_fifo(self, item_name, qty):
        """Reduce active batches for an item in expiry order. Decrements
        in-place; marks batch depleted at qty==0."""
        if qty <= 0:
            return
        try:
            conn = self._connect()
            try:
                cur = conn.execute("""SELECT id, quantity FROM bakery_batches
                                      WHERE item_name=? AND status='active'
                                      ORDER BY expiry_date ASC, id ASC""",
                                   (item_name,))
                remaining = qty
                for bid, bqty in cur.fetchall():
                    if remaining <= 0:
                        break
                    take = min(int(bqty), remaining)
                    new_qty = int(bqty) - take
                    remaining -= take
                    if new_qty <= 0:
                        conn.execute("""UPDATE bakery_batches
                                        SET quantity=0, status='depleted'
                                        WHERE id=?""", (bid,))
                    else:
                        conn.execute("UPDATE bakery_batches SET quantity=? WHERE id=?",
                                     (new_qty, bid))
                conn.commit()
                if remaining > 0:
                    logger.debug("FIFO undercount for %s: %d units unbatch-tracked",
                                 item_name, remaining)
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("FIFO batch consume failed for %s", item_name)

    def _open_alert_for(self, item_name):
        rows = self._query("""SELECT id FROM bakery_stock_alerts
                              WHERE item_name=? AND acknowledged=0""",
                           (item_name,))
        return rows[0][0] if rows else None

    def check_low_stock(self):
        """Walk all products; for any whose stock is at or below the
        configured min_stock and which has no open alert, create an
        alert, notify admin inboxes, and (if rule is auto) draft a PO.
        Returns the list of items newly alerted."""
        newly_alerted = []
        for cat_name, items in self.products.items():
            for name, info in items.items():
                rule = self.get_reorder_rule(name)
                if not rule:
                    continue
                if info.get("stock", 0) > rule["min_stock"]:
                    continue
                if self._open_alert_for(name):
                    continue
                triggered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._exec("""INSERT INTO bakery_stock_alerts
                              (item_name, threshold, current_stock,
                               triggered_at, acknowledged)
                              VALUES (?, ?, ?, ?, 0)""",
                           (name, rule["min_stock"], info.get("stock", 0),
                            triggered_at))
                logger.warning("Low stock alert: %s stock=%d threshold=%d",
                               name, info.get("stock", 0), rule["min_stock"])
                auto_po_note = ""
                po_number = None
                if rule.get("auto"):
                    po_number = self.create_purchase_order(
                        {name: rule["reorder_qty"]},
                        supplier_id=rule.get("supplier_id"),
                        status="sent",
                        created_by="auto-reorder",
                        notes=f"Auto-generated from low-stock alert for {name}",
                    )
                    if po_number:
                        auto_po_note = (f"An automatic purchase order "
                                        f"({po_number}) was generated.")
                self._notify_admins_low_stock(name, cat_name, info,
                                              rule, triggered_at,
                                              auto_po_note)
                newly_alerted.append(name)
        return newly_alerted

    def _list_admin_emails(self):
        """Return (username, email) for admin-role users in the users table."""
        try:
            conn = self._connect()
            try:
                rows = conn.execute("""SELECT username, email FROM users
                                        WHERE lower(role) IN ('admin','administrator',
                                                              'superadmin','staff')
                                          AND email IS NOT NULL AND email != ''""").fetchall()
            finally:
                conn.close()
            return [(r[0], r[1]) for r in rows]
        except sqlite3.Error:
            logger.debug("admin email lookup failed", exc_info=True)
            return []

    def _notify_admins_sold_out(self, item_name, category):
        """Send a sold-out email to every admin recipient. Fires whenever
        a transaction takes an item's stock from >0 to 0. Independent of
        the reorder-rule system: items with no rule still trigger this.
        Uses the bakery_sold_out_alert.json template."""
        try:
            from education_system.systems.university.infrastructure.email.email_service import (
                send_template_email,
            )
            triggered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            recipients = self._list_admin_emails() or [("admin", "admin@university.edu")]
            for username, email in recipients:
                try:
                    send_template_email(
                        "commerce/bakery_sold_out_alert", email,
                        {
                            "admin_name":   username or "Admin",
                            "item_name":    item_name,
                            "category":     category,
                            "triggered_at": triggered_at,
                        },
                    )
                except Exception:
                    logger.debug("sold-out email to %s failed", email, exc_info=True)
            logger.info("Sold-out notifications sent for %s to %d admin(s)",
                        item_name, len(recipients))
        except Exception:
            logger.exception("Failed to send sold-out alerts for %s", item_name)

    def _notify_admins_low_stock(self, item_name, category, info, rule,
                                 triggered_at, auto_po_note):
        try:
            from education_system.systems.university.infrastructure.email.email_service import (
                send_template_email,
            )
            supplier_name = "—"
            if rule.get("supplier_id"):
                s = self._query("SELECT name FROM bakery_suppliers WHERE id=?",
                                (rule["supplier_id"],))
                if s:
                    supplier_name = s[0][0]
            recipients = self._list_admin_emails() or [("admin", "admin@university.edu")]
            for username, email in recipients:
                try:
                    send_template_email(
                        "commerce/bakery_low_stock_alert", email,
                        {
                            "admin_name": username or "Admin",
                            "item_name": item_name,
                            "category": category,
                            "current_stock": str(info.get("stock", 0)),
                            "threshold": str(rule["min_stock"]),
                            "reorder_qty": str(rule.get("reorder_qty", 0)),
                            "supplier_name": supplier_name,
                            "triggered_at": triggered_at,
                            "auto_po_note": auto_po_note or "",
                        },
                    )
                except Exception:
                    logger.debug("low-stock email to %s failed", email, exc_info=True)
            logger.info("Low-stock notifications sent for %s to %d admin(s)",
                        item_name, len(recipients))
        except Exception:
            logger.exception("Failed to send low-stock alerts")

