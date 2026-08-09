"""LoyaltyMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class LoyaltyMixin:
    def get_loyalty_points(self, user=None):
        user = user or self.current_user
        if not user:
            return 0, 0
        rows = self._query(
            "SELECT points, lifetime_points FROM bakery_loyalty WHERE user=?",
            (user,))
        if rows:
            return int(rows[0][0] or 0), int(rows[0][1] or 0)
        return 0, 0

    def _add_loyalty_points(self, user, points):
        if not user or points <= 0:
            return False
        try:
            conn = self._connect()
            try:
                conn.execute("""
                    INSERT INTO bakery_loyalty (user, points, lifetime_points, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user) DO UPDATE SET
                        points = points + excluded.points,
                        lifetime_points = lifetime_points + excluded.lifetime_points,
                        updated_at = excluded.updated_at
                """, (user, points, points,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            finally:
                conn.close()
            logger.info("Loyalty +%d for user=%s", points, user)
            return True
        except sqlite3.Error:
            logger.exception("Failed to add loyalty points for %s", user)
            return False

    def _redeem_loyalty_points(self, user, points):
        if not user or points <= 0:
            return False
        try:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT points FROM bakery_loyalty WHERE user=?", (user,))
                row = cur.fetchone()
                current = int((row or [0])[0])
                if current < points:
                    return False
                conn.execute("""
                    UPDATE bakery_loyalty
                    SET points = points - ?, updated_at = ?
                    WHERE user = ?
                """, (points, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user))
                conn.commit()
            finally:
                conn.close()
            logger.info("Loyalty -%d redeemed for user=%s", points, user)
            return True
        except sqlite3.Error:
            logger.exception("Failed to redeem loyalty points for %s", user)
            return False

    def get_punch_count(self, user, category):
        rows = self._query(
            "SELECT count FROM bakery_punch_cards WHERE user=? AND category=?",
            (user, category))
        return int(rows[0][0]) if rows else 0

    def _bump_punch(self, user, category, delta=1):
        if not user or not category or delta == 0:
            return
        try:
            conn = self._connect()
            try:
                conn.execute("""
                    INSERT INTO bakery_punch_cards (user, category, count, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user, category) DO UPDATE SET
                        count = count + excluded.count,
                        updated_at = excluded.updated_at
                """, (user, category, delta,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("Failed to bump punch card user=%s cat=%s", user, category)

    def _record_punch_redemption(self, user, category):
        try:
            conn = self._connect()
            try:
                conn.execute("""
                    UPDATE bakery_punch_cards
                    SET count = 0,
                        redemptions = redemptions + 1,
                        updated_at = ?
                    WHERE user = ? AND category = ?
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      user, category))
                conn.commit()
            finally:
                conn.close()
            logger.info("Punch redemption user=%s cat=%s", user, category)
        except sqlite3.Error:
            logger.exception("Failed to redeem punch user=%s cat=%s", user, category)

    def validate_promo(self, code, subtotal):
        """Return (savings, promo_row) for the given code or (0, None) on
        invalid/expired/exhausted. Does NOT consume the code."""
        if not code:
            return 0.0, None
        code = code.strip().upper()
        try:
            rows = self._query("""
                SELECT code, description, discount_type, discount_value,
                       min_subtotal, expiry_date, max_uses, current_uses, active
                FROM bakery_promo_codes WHERE upper(code)=?""", (code,))
            if not rows:
                return 0.0, None
            r = rows[0]
            if not r[8]:
                return 0.0, None
            if r[5]:
                try:
                    exp = datetime.strptime(r[5], "%Y-%m-%d")
                    if datetime.now() > exp.replace(hour=23, minute=59, second=59):
                        return 0.0, None
                except ValueError:
                    pass
            if r[6] is not None and r[7] is not None and r[7] >= r[6]:
                return 0.0, None
            if subtotal < (r[4] or 0):
                return 0.0, None
            savings = (subtotal * (r[3] / 100.0)) if r[2] == "percent" else float(r[3])
            return min(savings, subtotal), {
                "code": r[0], "description": r[1], "discount_type": r[2],
                "discount_value": r[3], "min_subtotal": r[4],
                "expiry_date": r[5], "max_uses": r[6],
                "current_uses": r[7], "active": r[8],
            }
        except Exception:
            logger.exception("validate_promo failed for %s", code)
            return 0.0, None

    def _consume_promo(self, code, user, order_id, amount_off):
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute("""
                    UPDATE bakery_promo_codes SET current_uses = current_uses + 1
                    WHERE upper(code) = upper(?)""", (code,))
                conn.execute("""
                    INSERT INTO bakery_promo_redemptions
                        (code, user, order_id, amount_off, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, user, order_id, amount_off, now))
                conn.commit()
            finally:
                conn.close()
            logger.info("Promo %s consumed by user=%s order=%s -£%.2f",
                        code, user, order_id, amount_off)
        except sqlite3.Error:
            logger.exception("Failed to consume promo %s", code)

    def _active_happy_hours(self, now=None):
        now = now or datetime.now()
        day = now.strftime("%a")  # Mon, Tue, ...
        hh_now = now.strftime("%H:%M")
        rows = self._query("""
            SELECT id, name, start_time, end_time, days_of_week,
                   category, discount_pct
            FROM bakery_happy_hours WHERE active=1
        """)
        active = []
        for r in rows:
            days = (r[4] or "all").lower()
            if days != "all" and day.lower() not in days:
                continue
            if not (r[2] <= hh_now <= r[3]):
                continue
            active.append({
                "id": r[0], "name": r[1],
                "start": r[2], "end": r[3],
                "days": r[4], "category": r[5] or "all",
                "pct": float(r[6] or 0),
            })
        return active

    def _active_combos(self):
        rows = self._query("""
            SELECT id, name, items_json, combo_price, description
            FROM bakery_combos WHERE active=1
        """)
        out = []
        for r in rows:
            try:
                items = json.loads(r[2])
            except (TypeError, ValueError):
                continue
            out.append({"id": r[0], "name": r[1], "items": items,
                        "combo_price": float(r[3] or 0),
                        "description": r[4]})
        return out

    def _apply_combos(self, cart):
        """Apply each active combo greedily — count how many times it can
        be assembled from the cart, and return savings + remaining items
        (the items NOT used inside any combo)."""
        remaining = dict(cart)
        combos_applied = []
        for combo in self._active_combos():
            needed = combo["items"]
            if not needed:
                continue
            try:
                possible = min((remaining.get(it, 0) // qty)
                               for it, qty in needed.items())
            except ValueError:
                possible = 0
            if possible <= 0:
                continue
            for it, qty in needed.items():
                remaining[it] -= qty * possible
                if remaining[it] <= 0:
                    remaining.pop(it, None)
            list_price_per_combo = sum(
                self._product_info(it)["price"] * qty
                for it, qty in needed.items()
                if self._product_info(it)
            )
            saving = (list_price_per_combo - combo["combo_price"]) * possible
            combos_applied.append({
                "name": combo["name"], "count": possible,
                "combo_price": combo["combo_price"],
                "list_price": list_price_per_combo,
                "saving": max(0.0, saving),
            })
        return combos_applied, remaining

    def get_pending_referral_bonus(self, user):
        rows = self._query("""
            SELECT id, bonus_referee FROM bakery_referrals
            WHERE referee = ? AND status = 'pending'""", (user,))
        if not rows:
            return 0.0, None
        return float(rows[0][1] or REFERRAL_BONUS_GBP), rows[0][0]

    def _redeem_referral(self, referral_id):
        if not referral_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._exec("""UPDATE bakery_referrals SET status='redeemed', redeemed_at=?
                      WHERE id=?""", (now, referral_id))
        # Also credit the referrer their bonus in loyalty points
        rows = self._query(
            "SELECT referrer, bonus_referrer FROM bakery_referrals WHERE id=?",
            (referral_id,))
        if rows:
            referrer, bonus_gbp = rows[0]
            if referrer and bonus_gbp:
                pts = int(float(bonus_gbp) * LOYALTY_POINTS_PER_GBP_REDEEM)
                self._add_loyalty_points(referrer, pts)

    def is_first_purchase(self, user):
        if not user:
            return False
        rows = self._query(
            "SELECT 1 FROM bakery_first_purchase_claims WHERE user=?",
            (user,))
        if rows:
            return False
        # Also check no prior orders attributed to this user.
        for o in self.orders:
            if o.get("user") == user:
                return False
        return True

    def _mark_first_purchase(self, user):
        if not user:
            return
        self._exec(
            "INSERT OR IGNORE INTO bakery_first_purchase_claims (user, claimed_at) VALUES (?, ?)",
            (user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def is_birthday_today(self, user):
        """Check the central students table for a DOB matching today."""
        if not user:
            return False
        try:
            from education_system.systems.university.infrastructure.utils.finance_integration import (
                get_student_info,
            )
            info = get_student_info(str(user)) or {}
            dob = info.get("date_of_birth") or info.get("dob")
            if not dob:
                return False
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    d = datetime.strptime(dob, fmt)
                    today = datetime.now()
                    return d.month == today.month and d.day == today.day
                except ValueError:
                    continue
            return False
        except Exception:
            logger.debug("Birthday lookup failed for user=%s", user, exc_info=True)
            return False

    def _birthday_already_claimed(self, user):
        rows = self._query(
            "SELECT 1 FROM bakery_birthday_claims WHERE user=? AND year=?",
            (user, datetime.now().year))
        return bool(rows)

    def _mark_birthday_claim(self, user):
        if not user:
            return
        self._exec("""INSERT OR IGNORE INTO bakery_birthday_claims
                      (user, year, claimed_at) VALUES (?, ?, ?)""",
                   (user, datetime.now().year,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

