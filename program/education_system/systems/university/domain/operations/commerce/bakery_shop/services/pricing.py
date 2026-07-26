"""PricingMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class PricingMixin:
    def compute_discounts(self, cart, *, promo_code=None,
                          loyalty_redeem_pts=0, apply_birthday=False,
                          apply_referral=True, now=None):
        """Compute the full price waterfall for a cart.

        Order: combos → happy-hour → user tier → birthday → first-purchase
        → promo → referral → loyalty redemption.  Each layer applies to
        the remainder after previous layers. Returns a dict with subtotal,
        breakdown (list of (label, amount)), total, and the loyalty
        points earned / redeemed."""
        now = now or datetime.now()
        breakdown = []
        warnings = []
        user = self.current_user

        # Raw subtotal
        full_subtotal = 0.0
        for item, qty in cart.items():
            info = self._product_info(item)
            if info:
                full_subtotal += float(info["price"]) * int(qty)

        # 1. Combos
        combos_applied, remaining_items = self._apply_combos(cart)
        combos_savings = sum(c["saving"] for c in combos_applied)
        if combos_savings > 0:
            names = ", ".join(f"{c['name']} ×{c['count']}" for c in combos_applied)
            breakdown.append((f"Combo: {names}", -combos_savings))

        # 2. Punch-card free items: if user has accumulated enough punches
        # in a category AND this cart contains an item from that category,
        # give one of those items free (cheapest one for fairness).
        punch_savings = 0.0
        punch_redeemed_category = None
        if user:
            for cat, threshold in PUNCH_CARD_CATEGORIES.items():
                current = self.get_punch_count(user, cat)
                cat_items_in_cart = [
                    (it, qty) for it, qty in cart.items()
                    if self._product_category(it) == cat
                ]
                if not cat_items_in_cart:
                    continue
                if current + sum(q for _, q in cat_items_in_cart) >= threshold:
                    # Give the cheapest unit free
                    cheapest = min(
                        (self._product_info(it)["price"] for it, _ in cat_items_in_cart),
                        default=0,
                    )
                    if cheapest > 0:
                        punch_savings = float(cheapest)
                        punch_redeemed_category = cat
                        breakdown.append(
                            (f"Punch card: free {cat} item", -punch_savings))
                        break

        running = full_subtotal - combos_savings - punch_savings

        # 3. Happy hour — on remaining (non-combo) items in eligible category
        hh_savings = 0.0
        active_hh = self._active_happy_hours(now)
        for hh in active_hh:
            for item, qty in remaining_items.items():
                info = self._product_info(item)
                if not info:
                    continue
                if hh["category"] != "all" and self._product_category(item) != hh["category"]:
                    continue
                hh_savings += info["price"] * qty * (hh["pct"] / 100.0)
        if hh_savings > 0:
            breakdown.append((f"Happy Hour ({active_hh[0]['name']})",
                              -hh_savings))
        running -= hh_savings

        # 4. User tier (Student 10% / Staff 15%)
        tier_pct = 0.10 if self.user_type == "Student" else 0.15 if self.user_type == "Staff" else 0
        tier_savings = running * tier_pct
        if tier_savings > 0:
            breakdown.append((f"{self.user_type} discount", -tier_savings))
        running -= tier_savings

        # 5. Birthday (20% — once per year)
        bday_savings = 0.0
        if apply_birthday and user and not self._birthday_already_claimed(user):
            bday_savings = running * BIRTHDAY_DISCOUNT_PCT
            if bday_savings > 0:
                breakdown.append(("🎂 Birthday treat", -bday_savings))
        running -= bday_savings

        # 6. First purchase (15%)
        first_savings = 0.0
        if user and self.is_first_purchase(user):
            first_savings = running * FIRST_PURCHASE_DISCOUNT_PCT
            if first_savings > 0:
                breakdown.append(("Welcome — first purchase", -first_savings))
        running -= first_savings

        # 7. Promo code (% or fixed)
        promo_savings = 0.0
        promo_meta = None
        if promo_code:
            promo_savings, promo_meta = self.validate_promo(promo_code, running)
            if promo_meta is None and promo_code.strip():
                warnings.append(f"Promo '{promo_code}' is invalid or expired.")
            elif promo_savings > 0:
                breakdown.append((f"Promo {promo_meta['code']}", -promo_savings))
        running -= promo_savings

        # 8. Referral bonus (apply once per pending referee, fixed £)
        referral_savings = 0.0
        referral_id = None
        if apply_referral and user:
            bonus, rid = self.get_pending_referral_bonus(user)
            if bonus and rid:
                referral_savings = min(bonus, running)
                referral_id = rid
                breakdown.append(("Referral bonus", -referral_savings))
        running -= referral_savings

        # 9. Loyalty redemption (pts → £)
        loyalty_redeemed_pts = 0
        if user and loyalty_redeem_pts > 0:
            bal, _ = self.get_loyalty_points(user)
            usable = min(loyalty_redeem_pts, bal,
                         int(running * LOYALTY_POINTS_PER_GBP_REDEEM))
            if usable > 0:
                value = usable / LOYALTY_POINTS_PER_GBP_REDEEM
                breakdown.append((f"Loyalty redemption ({usable} pts)", -value))
                loyalty_redeemed_pts = usable
                running -= value

        total = max(0.0, round(running, 2))
        total_discount = round(full_subtotal - total, 2)
        loyalty_earned = int(total * LOYALTY_POINTS_PER_POUND)

        return {
            "subtotal": round(full_subtotal, 2),
            "breakdown": [(lbl, round(amt, 2)) for lbl, amt in breakdown],
            "total_discount": total_discount,
            "total": total,
            "loyalty_earned": loyalty_earned,
            "loyalty_redeemed": loyalty_redeemed_pts,
            "promo_meta": promo_meta,
            "referral_id": referral_id,
            "punch_redeemed_category": punch_redeemed_category,
            "warnings": warnings,
            "applied_birthday": bday_savings > 0,
            "applied_first_purchase": first_savings > 0,
        }

