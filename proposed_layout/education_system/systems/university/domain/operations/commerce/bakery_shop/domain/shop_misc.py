"""ShopMiscMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class ShopMiscMixin:
    def add_review(self, item_name, rating, comment="", verified=False):
        if not self.current_user:
            return False
        rating = int(rating)
        if rating < 1 or rating > 5:
            return False
        try:
            self._exec("""INSERT INTO bakery_reviews
                          (item_name, user, rating, comment, timestamp,
                           verified_purchase)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                       (item_name, self.current_user, rating, comment,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        1 if verified else 0))
            logger.info("Review added item=%s user=%s rating=%d",
                        item_name, self.current_user, rating)
            return True
        except Exception:
            logger.exception("Failed to add review for %s", item_name)
            return False

    def get_reviews(self, item_name, limit=50):
        return self._query("""SELECT user, rating, comment, timestamp,
                                     verified_purchase
                              FROM bakery_reviews
                              WHERE item_name=?
                              ORDER BY timestamp DESC LIMIT ?""",
                           (item_name, int(limit)))

    def average_rating(self, item_name):
        rows = self._query("""SELECT AVG(rating), COUNT(*)
                              FROM bakery_reviews WHERE item_name=?""",
                           (item_name,))
        if not rows or rows[0][1] == 0:
            return None, 0
        return float(rows[0][0]), int(rows[0][1])

    def _user_bought(self, item_name, user):
        if not user:
            return False
        for o in self.orders:
            if o.get("user") == user and item_name in (o.get("items") or {}):
                return True
        return False

    def top_sellers_today(self, n=3):
        today = datetime.now().strftime("%Y-%m-%d")
        tally = {}
        for o in self.orders:
            if not (o.get("timestamp") or "").startswith(today):
                continue
            if o.get("refunded"):
                continue
            for item, qty in (o.get("items") or {}).items():
                tally[item] = tally.get(item, 0) + int(qty)
        ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:n]

    def _current_currency(self):
        """Return (code, symbol, rate_from_gbp). Falls back to GBP."""
        code = getattr(self, "_currency_code", "GBP") or "GBP"
        rows = self._query("""SELECT currency, symbol, rate_from_gbp
                              FROM bakery_currency_rates
                              WHERE currency = ?""", (code,))
        if rows:
            return rows[0][0], rows[0][1], float(rows[0][2] or 1.0)
        return "GBP", "£", 1.0

    def fmt_money(self, gbp_amount):
        """Convert a GBP amount to the user's selected currency and
        format it with the currency's symbol."""
        try:
            _, symbol, rate = self._current_currency()
            return f"{symbol}{float(gbp_amount) * rate:.2f}"
        except Exception:
            return f"£{float(gbp_amount):.2f}"

    def list_currencies(self):
        return self._query("""SELECT currency, symbol, rate_from_gbp,
                                     updated_at
                              FROM bakery_currency_rates ORDER BY currency""")

    def set_currency(self, code):
        rows = self._query(
            "SELECT 1 FROM bakery_currency_rates WHERE currency=?",
            (code,))
        if not rows:
            return False
        self._currency_code = code
        logger.info("Bakery currency switched to %s by user=%s",
                    code, self.current_user)
        return True

    def upsert_currency(self, code, symbol, rate_from_gbp):
        try:
            self._exec("""INSERT INTO bakery_currency_rates
                          (currency, symbol, rate_from_gbp, updated_at)
                          VALUES (?, ?, ?, ?)
                          ON CONFLICT(currency) DO UPDATE SET
                            symbol = excluded.symbol,
                            rate_from_gbp = excluded.rate_from_gbp,
                            updated_at = excluded.updated_at""",
                       (code, symbol, float(rate_from_gbp),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Currency upserted code=%s rate=%s",
                        code, rate_from_gbp)
            return True
        except Exception:
            logger.exception("Failed to upsert currency %s", code)
            return False

    def list_favourites(self, user=None):
        user = user or self.current_user
        if not user:
            return []
        return [r[0] for r in self._query(
            "SELECT item_name FROM bakery_favourites WHERE user=? ORDER BY added_at DESC",
            (user,))]

    def is_favourite(self, item_name, user=None):
        user = user or self.current_user
        if not user:
            return False
        return bool(self._query(
            "SELECT 1 FROM bakery_favourites WHERE user=? AND item_name=?",
            (user, item_name)))

    def toggle_favourite(self, item_name):
        if not self.current_user:
            return None
        if self.is_favourite(item_name):
            self._exec(
                "DELETE FROM bakery_favourites WHERE user=? AND item_name=?",
                (self.current_user, item_name))
            logger.info("Favourite removed user=%s item=%s",
                        self.current_user, item_name)
            return False
        self._exec("""INSERT OR IGNORE INTO bakery_favourites
                      (user, item_name, added_at) VALUES (?, ?, ?)""",
                   (self.current_user, item_name,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        logger.info("Favourite added user=%s item=%s",
                    self.current_user, item_name)
        return True

    def save_cart_for_later(self):
        if not self.current_user:
            return False
        if not self.cart:
            return False
        try:
            self._exec("""INSERT OR REPLACE INTO bakery_saved_carts
                          (user, items_json, saved_at)
                          VALUES (?, ?, ?)""",
                       (self.current_user, json.dumps(self.cart),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Saved cart for user=%s items=%d",
                        self.current_user, sum(self.cart.values()))
            return True
        except Exception:
            logger.exception("save_cart_for_later failed")
            return False

    def restore_saved_cart(self):
        if not self.current_user:
            return False
        rows = self._query(
            "SELECT items_json FROM bakery_saved_carts WHERE user=?",
            (self.current_user,))
        if not rows:
            return False
        try:
            items = json.loads(rows[0][0])
        except Exception:
            return False
        # Merge into cart (respecting current stock).
        for name, qty in items.items():
            info = self._product_info(name)
            if not info:
                continue
            existing = self.cart.get(name, 0)
            allowed = max(0, info.get("stock", 0) - existing)
            add = min(int(qty), allowed)
            if add > 0:
                self.cart[name] = existing + add
        logger.info("Restored saved cart for user=%s", self.current_user)
        return True

    def clear_saved_cart(self):
        if self.current_user:
            self._exec("DELETE FROM bakery_saved_carts WHERE user=?",
                       (self.current_user,))

    def has_saved_cart(self):
        if not self.current_user:
            return False
        return bool(self._query(
            "SELECT 1 FROM bakery_saved_carts WHERE user=?",
            (self.current_user,)))

