"""SpecialOrdersMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class SpecialOrdersMixin:
    def list_preorders(self, *, user=None, include_completed=False):
        sql = """SELECT id, order_id, user, items_json, collection_time,
                        status, total, payment_method, paid, created_at
                 FROM bakery_preorders"""
        params = ()
        clauses = []
        if user:
            clauses.append("user = ?")
            params = (user,)
        if not include_completed:
            clauses.append("status IN ('pending','ready')")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY collection_time ASC"
        return self._query(sql, params)

    def create_preorder(self, items, collection_time, *, notes="",
                         payment_method="card"):
        if not self.current_user:
            return None
        if not items:
            return None
        # Compute discounts at request time so the customer knows their total.
        result = self.compute_discounts(items)
        try:
            order_id = f"PRE-{len(self.orders) + len(self.list_preorders(include_completed=True)) + 1001}"
            self._exec("""INSERT INTO bakery_preorders
                          (order_id, user, user_type, items_json,
                           collection_time, status, notes, subtotal,
                           discount, total, payment_method, paid, created_at)
                          VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, 0, ?)""",
                       (order_id, self.current_user, self.user_type,
                        json.dumps(items), collection_time, notes,
                        result["subtotal"], result["total_discount"],
                        result["total"], payment_method,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Pre-order created %s user=%s pickup=%s items=%d total=%.2f",
                        order_id, self.current_user, collection_time,
                        sum(items.values()), result["total"])
            return order_id
        except Exception:
            logger.exception("create_preorder failed")
            return None

    def update_preorder_status(self, preorder_id, status):
        if status not in ("pending", "ready", "collected", "cancelled"):
            return False
        self._exec("UPDATE bakery_preorders SET status=? WHERE id=?",
                   (status, preorder_id))
        logger.info("Pre-order id=%s -> %s", preorder_id, status)
        return True

    def create_custom_order(self, *, cake_type, size, flavours, message,
                            dietary, collection_date, contact_email,
                            contact_phone, notes=""):
        if not self.current_user:
            return None
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_custom_orders
                          (user, cake_type, size, flavours, message_on_cake,
                           dietary_requirements, collection_date,
                           contact_email, contact_phone, status,
                           admin_notes, created_at, updated_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'requested',
                                  ?, ?, ?)""",
                          (self.current_user, cake_type, size, flavours,
                           message, dietary, collection_date,
                           contact_email, contact_phone, notes, now, now))
                cid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Custom cake order created id=%s user=%s pickup=%s",
                        cid, self.current_user, collection_date)
            return cid
        except Exception:
            logger.exception("create_custom_order failed")
            return None

    def list_custom_orders(self, *, user=None):
        sql = """SELECT id, user, cake_type, size, collection_date,
                        status, quoted_price, contact_email, created_at
                 FROM bakery_custom_orders"""
        params = ()
        if user:
            sql += " WHERE user=?"
            params = (user,)
        sql += " ORDER BY collection_date ASC"
        return self._query(sql, params)

    def update_custom_order(self, cid, *, status=None, quoted_price=None,
                            admin_notes=None):
        sets, vals = [], []
        if status is not None:
            sets.append("status=?"); vals.append(status)
        if quoted_price is not None:
            sets.append("quoted_price=?"); vals.append(float(quoted_price))
        if admin_notes is not None:
            sets.append("admin_notes=?"); vals.append(admin_notes)
        if not sets:
            return False
        sets.append("updated_at=?"); vals.append(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        vals.append(cid)
        self._exec(f"UPDATE bakery_custom_orders SET {', '.join(sets)} "
                   f"WHERE id=?", tuple(vals))
        logger.info("Custom order id=%s updated %s", cid, sets)
        return True

    def create_bulk_order(self, items, *, department, billing_code,
                          event_date, event_location, attendees, notes=""):
        if not self.current_user:
            return None
        try:
            total = 0.0
            for name, qty in items.items():
                info = self._product_info(name)
                if info:
                    total += float(info["price"]) * int(qty)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_bulk_orders
                              (user, department, billing_code, items_json,
                               event_date, event_location, attendees, total,
                               status, notes, created_at, updated_at)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted',
                                      ?, ?, ?)""",
                              (self.current_user, department, billing_code,
                               json.dumps(items), event_date, event_location,
                               int(attendees or 0), total, notes, now, now))
                bid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Bulk order created id=%s user=%s event=%s total=%.2f",
                        bid, self.current_user, event_date, total)
            return bid
        except Exception:
            logger.exception("create_bulk_order failed")
            return None

    def list_bulk_orders(self, *, user=None):
        sql = """SELECT id, user, department, event_date, event_location,
                        attendees, total, status, created_at
                 FROM bakery_bulk_orders"""
        params = ()
        if user:
            sql += " WHERE user=?"
            params = (user,)
        sql += " ORDER BY event_date ASC"
        return self._query(sql, params)

    def update_bulk_order_status(self, bid, status):
        valid = ("submitted", "confirmed", "in_progress",
                 "delivered", "cancelled")
        if status not in valid:
            return False
        self._exec("""UPDATE bakery_bulk_orders SET status=?, updated_at=?
                      WHERE id=?""",
                   (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bid))
        logger.info("Bulk order id=%s -> %s", bid, status)
        return True

    @staticmethod
    def _compute_next_run(schedule, base=None):
        """Schedule formats:
           'daily'
           'weekly:Mon,Wed,Fri'  (any 3-letter weekday names)
           'monthly:15'          (day-of-month)"""
        base = base or datetime.now()
        sched = (schedule or "").strip().lower()
        if sched == "daily":
            return (base + timedelta(days=1)).strftime("%Y-%m-%d")
        if sched.startswith("weekly:"):
            days = [d.strip()[:3] for d in sched.split(":", 1)[1].split(",")]
            for ahead in range(1, 8):
                cand = base + timedelta(days=ahead)
                if cand.strftime("%a").lower() in days:
                    return cand.strftime("%Y-%m-%d")
        if sched.startswith("monthly:"):
            try:
                dom = int(sched.split(":", 1)[1])
            except ValueError:
                return None
            year, month = base.year, base.month
            try:
                cand = datetime(year, month, dom)
                if cand <= base:
                    raise ValueError
            except ValueError:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                try:
                    cand = datetime(year, month, dom)
                except ValueError:
                    return None
            return cand.strftime("%Y-%m-%d")
        return None

    def create_recurring_order(self, items, schedule, *, name=""):
        if not self.current_user or not items:
            return None
        try:
            next_run = self._compute_next_run(schedule)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_recurring_orders
                              (user, name, items_json, schedule, next_run,
                               last_run, active, created_at)
                              VALUES (?, ?, ?, ?, ?, NULL, 1, ?)""",
                              (self.current_user, name, json.dumps(items),
                               schedule, next_run, now))
                rid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Recurring order created id=%s user=%s schedule=%s "
                        "next=%s", rid, self.current_user, schedule, next_run)
            return rid
        except Exception:
            logger.exception("create_recurring_order failed")
            return None

    def list_recurring_orders(self, *, user=None):
        sql = """SELECT id, user, name, items_json, schedule, next_run,
                        last_run, active, created_at
                 FROM bakery_recurring_orders"""
        params = ()
        if user:
            sql += " WHERE user=?"
            params = (user,)
        sql += " ORDER BY active DESC, next_run ASC"
        return self._query(sql, params)

    def toggle_recurring(self, rid):
        self._exec("""UPDATE bakery_recurring_orders SET active = 1 - active
                      WHERE id=?""", (rid,))

    def delete_recurring(self, rid):
        self._exec("DELETE FROM bakery_recurring_orders WHERE id=?", (rid,))
        logger.info("Recurring order id=%s deleted", rid)

