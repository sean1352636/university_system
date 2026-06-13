"""FinanceMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class FinanceMixin:
    def _vat_rate_for_item(self, item_name):
        info = self._product_info(item_name)
        if info and "vat_rate" in info:
            return float(info["vat_rate"])
        cat = self._product_category(item_name)
        return float(VAT_RATES.get(cat, 0.0))

    def compute_vat(self, items):
        """Given a {name: qty} cart and using *list* prices, return a dict
        with net, vat, gross, and per-rate breakdown. We treat the
        product price as VAT-inclusive (typical retail display)."""
        breakdown = {}
        net = 0.0
        vat = 0.0
        for name, qty in items.items():
            info = self._product_info(name)
            if not info:
                continue
            gross_line = float(info["price"]) * int(qty)
            rate = self._vat_rate_for_item(name)
            line_net = gross_line / (1.0 + rate) if rate else gross_line
            line_vat = gross_line - line_net
            net += line_net
            vat += line_vat
            key = f"{int(rate * 100)}%"
            breakdown[key] = breakdown.get(key, 0.0) + line_vat
        return {"net": round(net, 2),
                "vat": round(vat, 2),
                "gross": round(net + vat, 2),
                "breakdown": {k: round(v, 2) for k, v in breakdown.items()}}

    @staticmethod
    def _new_gift_card_code():
        import secrets
        return "GC-" + secrets.token_hex(4).upper()

    def issue_gift_card(self, initial_balance, *, issued_to=None,
                        expiry=None, notes=""):
        try:
            initial_balance = float(initial_balance)
            if initial_balance <= 0:
                return None
            code = self._new_gift_card_code()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._exec("""INSERT INTO bakery_gift_cards
                          (code, initial_balance, balance, issued_to, expiry,
                           active, notes, created_at, created_by)
                          VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                       (code, initial_balance, initial_balance,
                        issued_to, expiry, notes, now,
                        self.current_user or "system"))
            self._exec("""INSERT INTO bakery_gift_card_txns
                          (code, txn_type, amount, user, timestamp, notes)
                          VALUES (?, 'issue', ?, ?, ?, ?)""",
                       (code, initial_balance,
                        self.current_user or "system", now,
                        f"Issued by {self.current_user or 'system'}"))
            logger.info("Gift card issued code=%s balance=%.2f to=%s",
                        code, initial_balance, issued_to or "—")
            return code
        except Exception:
            logger.exception("issue_gift_card failed")
            return None

    def validate_gift_card(self, code):
        """Return ({code, balance, expiry, active}, None) or
        (None, reason_str)."""
        if not code:
            return None, "No code provided"
        code = code.strip().upper()
        rows = self._query("""SELECT code, balance, expiry, active
                              FROM bakery_gift_cards WHERE upper(code)=?""",
                           (code,))
        if not rows:
            return None, "Card not found"
        r = rows[0]
        if not r[3]:
            return None, "Card inactive"
        if r[2]:
            try:
                if datetime.now() > datetime.strptime(r[2], "%Y-%m-%d") \
                                          .replace(hour=23, minute=59):
                    return None, "Card expired"
            except ValueError:
                pass
        if float(r[1] or 0) <= 0:
            return None, "Card exhausted"
        return {"code": r[0], "balance": float(r[1]),
                "expiry": r[2], "active": bool(r[3])}, None

    def _redeem_gift_card(self, code, amount, *, order_id=None,
                          txn_type="redeem"):
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute("BEGIN")
                cur = conn.execute(
                    "SELECT balance FROM bakery_gift_cards WHERE code=?",
                    (code,))
                row = cur.fetchone()
                if not row:
                    conn.rollback(); return False
                current = float(row[0] or 0)
                if txn_type == "redeem" and current < amount:
                    conn.rollback(); return False
                new_balance = (current - amount) if txn_type == "redeem" \
                              else (current + amount)
                conn.execute("UPDATE bakery_gift_cards SET balance=? WHERE code=?",
                             (new_balance, code))
                conn.execute("""INSERT INTO bakery_gift_card_txns
                                (code, txn_type, amount, order_id, user,
                                 timestamp)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                             (code, txn_type, amount, order_id,
                              self.current_user or "system", now))
                conn.commit()
            finally:
                conn.close()
            logger.info("Gift card %s %s amount=%.2f order=%s",
                        code, txn_type, amount, order_id or "—")
            return True
        except Exception:
            logger.exception("Gift card %s for code=%s failed", txn_type, code)
            return False

    def list_gift_cards(self, *, only_active=False):
        sql = """SELECT code, initial_balance, balance, issued_to,
                        expiry, active, created_at FROM bakery_gift_cards"""
        if only_active:
            sql += " WHERE active=1"
        sql += " ORDER BY created_at DESC"
        return self._query(sql)

    def _record_tip(self, order_id, amount):
        if amount <= 0:
            return
        try:
            self._exec("""INSERT INTO bakery_tips
                          (order_id, amount, user, timestamp)
                          VALUES (?, ?, ?, ?)""",
                       (order_id, float(amount),
                        self.current_user or "Guest",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Tip recorded order=%s amount=%.2f",
                        order_id, amount)
        except Exception:
            logger.exception("_record_tip failed for order=%s", order_id)

    def list_tips(self, since=None):
        sql = "SELECT id, order_id, amount, user, timestamp FROM bakery_tips"
        params = ()
        if since:
            sql += " WHERE timestamp >= ?"
            params = (since,)
        sql += " ORDER BY timestamp DESC"
        return self._query(sql, params)

    def list_billing_codes(self, *, only_active=True):
        sql = """SELECT code, department, contact, contact_email, active
                 FROM bakery_billing_codes"""
        if only_active:
            sql += " WHERE active=1"
        sql += " ORDER BY code"
        return self._query(sql)

    def validate_billing_code(self, code):
        if not code:
            return None
        rows = self._query("""SELECT code, department, contact_email, active
                              FROM bakery_billing_codes WHERE upper(code)=?""",
                           (code.strip().upper(),))
        if not rows or not rows[0][3]:
            return None
        return {"code": rows[0][0], "department": rows[0][1],
                "contact_email": rows[0][2]}

    def upsert_billing_code(self, code, *, department, contact="",
                            contact_email="", active=True):
        try:
            self._exec("""INSERT INTO bakery_billing_codes
                          (code, department, contact, contact_email,
                           active, created_at)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(code) DO UPDATE SET
                              department = excluded.department,
                              contact = excluded.contact,
                              contact_email = excluded.contact_email,
                              active = excluded.active""",
                       (code.strip().upper(), department, contact,
                        contact_email, 1 if active else 0,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Billing code upserted code=%s dept=%s",
                        code, department)
            return True
        except Exception:
            logger.exception("upsert_billing_code failed")
            return False

    def open_cash_drawer(self, opening_float):
        try:
            rows = self._query(
                "SELECT id FROM bakery_cash_drawer WHERE status='open' LIMIT 1")
            if rows:
                return None
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_cash_drawer
                              (opened_at, opening_float, operator, status)
                              VALUES (?, ?, ?, 'open')""",
                              (now, float(opening_float),
                               self.current_user or "system"))
                did = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Cash drawer opened id=%s float=%.2f operator=%s",
                        did, opening_float, self.current_user)
            return did
        except Exception:
            logger.exception("open_cash_drawer failed")
            return None

    def _cash_sales_since(self, opened_at):
        """Sum of *cash* payments since `opened_at`. Reads orders that
        either had payment_method=cash or carry a 'cash' entry in
        split_payments_json."""
        total = 0.0
        for o in self.orders:
            if not o.get("timestamp"):
                continue
            if o["timestamp"] < opened_at:
                continue
            if o.get("refunded"):
                continue
            splits = o.get("split_payments") or []
            if splits:
                for s in splits:
                    if s.get("method") == "cash":
                        total += float(s.get("amount") or 0)
            elif o.get("payment_method") == "cash":
                total += float(o.get("total") or 0)
        return round(total, 2)

    def close_cash_drawer(self, drawer_id, counted_amount, *, notes=""):
        try:
            rows = self._query(
                "SELECT opened_at, opening_float FROM bakery_cash_drawer "
                "WHERE id=? AND status='open'", (drawer_id,))
            if not rows:
                return None
            opened_at, opening_float = rows[0]
            cash_sales = self._cash_sales_since(opened_at)
            expected = round(float(opening_float) + cash_sales, 2)
            variance = round(float(counted_amount) - expected, 2)
            self._exec("""UPDATE bakery_cash_drawer
                          SET closed_at=?, closing_amount=?,
                              expected_amount=?, variance=?,
                              status='closed', notes=?
                          WHERE id=?""",
                       (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        float(counted_amount), expected, variance, notes,
                        drawer_id))
            logger.info("Cash drawer closed id=%s counted=%.2f "
                        "expected=%.2f variance=%.2f",
                        drawer_id, counted_amount, expected, variance)
            return {"expected": expected, "counted": float(counted_amount),
                    "variance": variance, "cash_sales": cash_sales,
                    "opening_float": float(opening_float)}
        except Exception:
            logger.exception("close_cash_drawer failed id=%s", drawer_id)
            return None

    def list_drawer_sessions(self, limit=30):
        return self._query("""SELECT id, opened_at, opening_float, closed_at,
                                     closing_amount, expected_amount,
                                     variance, operator, status, notes
                              FROM bakery_cash_drawer
                              ORDER BY id DESC LIMIT ?""", (limit,))

    def current_open_drawer(self):
        rows = self._query("""SELECT id, opened_at, opening_float, operator
                              FROM bakery_cash_drawer
                              WHERE status='open' LIMIT 1""")
        if not rows:
            return None
        r = rows[0]
        return {"id": r[0], "opened_at": r[1],
                "opening_float": float(r[2] or 0), "operator": r[3]}

    def create_refund_request(self, order_id, *, reason, reason_category,
                              items=None, requested_amount=None):
        """Customer-initiated refund request. `items` is {name: qty} for
        partial refunds, or None for whole-order."""
        if not order_id or not reason:
            return None
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                cur = conn.execute("""INSERT INTO bakery_refund_requests
                                  (order_id, user, reason, reason_category,
                                   items_json, requested_amount, status,
                                   created_at, updated_at)
                                  VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                                  (order_id, self.current_user, reason,
                                   reason_category,
                                   json.dumps(items) if items else None,
                                   requested_amount, now, now))
                rid = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
            logger.info("Refund request created id=%s order=%s user=%s "
                        "category=%s", rid, order_id,
                        self.current_user, reason_category)
            return rid
        except Exception:
            logger.exception("create_refund_request failed order=%s", order_id)
            return None

    def list_refund_requests(self, *, status=None, user=None):
        sql = """SELECT id, order_id, user, reason, reason_category,
                        items_json, requested_amount, status, admin_notes,
                        handled_by, created_at, updated_at
                 FROM bakery_refund_requests"""
        clauses, params = [], []
        if status:
            clauses.append("status = ?"); params.append(status)
        if user:
            clauses.append("user = ?"); params.append(user)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC"
        return self._query(sql, tuple(params))

    def update_refund_request(self, rid, *, status, admin_notes=None):
        try:
            self._exec("""UPDATE bakery_refund_requests
                          SET status=?, admin_notes=COALESCE(?, admin_notes),
                              handled_by=?, updated_at=?
                          WHERE id=?""",
                       (status, admin_notes,
                        self.current_user or "system",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rid))
            logger.info("Refund request id=%s -> %s by %s",
                        rid, status, self.current_user)
            return True
        except Exception:
            logger.exception("update_refund_request id=%s failed", rid)
            return False

    def _record_refund_audit(self, *, order_id, refund_ref, amount, items,
                             reason, reason_category, method,
                             notes="", refund_request_id=None):
        try:
            self._exec("""INSERT INTO bakery_refund_audit
                          (order_id, refund_ref, refund_request_id, amount,
                           items_json, reason, reason_category, method,
                           issued_by, notes, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (order_id, refund_ref, refund_request_id,
                        float(amount or 0),
                        json.dumps(items) if items else None,
                        reason, reason_category, method,
                        self.current_user or "system", notes,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Refund audit recorded order=%s ref=%s amount=%.2f "
                        "by=%s", order_id, refund_ref, float(amount or 0),
                        self.current_user)
        except Exception:
            logger.exception("Refund audit insert failed order=%s", order_id)

    def list_refund_audit(self, order_id=None):
        sql = """SELECT id, order_id, refund_ref, amount, items_json, reason,
                        reason_category, method, issued_by, notes, timestamp
                 FROM bakery_refund_audit"""
        params = ()
        if order_id:
            sql += " WHERE order_id=?"; params = (order_id,)
        sql += " ORDER BY timestamp DESC"
        return self._query(sql, params)

