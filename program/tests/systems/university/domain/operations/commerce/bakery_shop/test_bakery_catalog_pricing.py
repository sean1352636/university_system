"""Catalog lookups, VAT computation, and the full discount waterfall."""

import pytest


# --------------------------------------------------------------------------- #
# CatalogMixin
# --------------------------------------------------------------------------- #
class TestCatalog:
    def test_product_info_found(self, shop):
        info = shop._product_info("Coffee")
        assert info is not None
        assert info["price"] == 2.50

    def test_product_info_missing(self, shop):
        assert shop._product_info("Pretzel") is None

    def test_product_category(self, shop):
        assert shop._product_category("Bagel") == "Breads"
        assert shop._product_category("Coffee") == "Beverages"

    def test_product_category_unknown(self, shop):
        assert shop._product_category("Pretzel") is None

    def test_dietary_filter_required_tag_present(self, shop):
        info = shop._product_info("Coffee")
        assert shop._passes_dietary_filter(info, ["vegan"], []) is True

    def test_dietary_filter_required_tag_absent(self, shop):
        info = shop._product_info("Croissant")  # vegetarian only
        assert shop._passes_dietary_filter(info, ["vegan"], []) is False

    def test_dietary_filter_excluded_allergen(self, shop):
        info = shop._product_info("Milk")  # contains milk
        assert shop._passes_dietary_filter(info, [], ["milk"]) is False

    def test_dietary_filter_allows_when_no_constraints(self, shop):
        info = shop._product_info("Coffee")
        assert shop._passes_dietary_filter(info, [], []) is True

    def test_dietary_filter_none_info(self, shop):
        assert shop._passes_dietary_filter(None, [], []) is False


# --------------------------------------------------------------------------- #
# FinanceMixin VAT
# --------------------------------------------------------------------------- #
class TestVAT:
    def test_standard_rate_is_inclusive(self, shop):
        # Coffee is a beverage @ 20% VAT, price treated as gross.
        res = shop.compute_vat({"Coffee": 1})
        assert res["gross"] == 2.50
        assert res["net"] == pytest.approx(2.08, abs=0.01)
        assert res["vat"] == pytest.approx(0.42, abs=0.01)
        assert res["breakdown"] == {"20%": pytest.approx(0.42, abs=0.01)}

    def test_zero_rated_bread(self, shop):
        res = shop.compute_vat({"Bagel": 2})
        assert res["gross"] == 4.00
        assert res["vat"] == 0.0
        assert res["net"] == 4.00
        assert res["breakdown"] == {"0%": 0.0}

    def test_per_item_vat_override(self, shop):
        shop.products["Breads"]["Bagel"]["vat_rate"] = 0.20
        assert shop._vat_rate_for_item("Bagel") == 0.20

    def test_vat_rate_falls_back_to_category(self, shop):
        assert shop._vat_rate_for_item("Coffee") == 0.20
        assert shop._vat_rate_for_item("Bagel") == 0.00

    def test_mixed_cart_breakdown(self, shop):
        res = shop.compute_vat({"Coffee": 1, "Bagel": 1})
        assert set(res["breakdown"]) == {"20%", "0%"}

    def test_unknown_item_skipped(self, shop):
        res = shop.compute_vat({"Pretzel": 5})
        assert res["gross"] == 0.0


# --------------------------------------------------------------------------- #
# PricingMixin.compute_discounts — the waterfall
# --------------------------------------------------------------------------- #
class TestPricingWaterfall:
    def test_guest_gets_no_tier_discount(self, make_shop):
        shop = make_shop(user=None, user_type="Guest")
        res = shop.compute_discounts({"Coffee": 2})
        assert res["subtotal"] == 5.00
        assert res["total"] == 5.00
        assert res["breakdown"] == []
        # 1 loyalty point per whole £ of the final total.
        assert res["loyalty_earned"] == 5

    def test_student_tier_10pct(self, shop):
        # Suppress the first-purchase bonus to isolate the tier discount.
        shop._mark_first_purchase("alice")
        res = shop.compute_discounts({"Coffee": 2})
        assert res["total"] == pytest.approx(4.50)
        assert any("Student" in lbl for lbl, _ in res["breakdown"])

    def test_staff_tier_15pct(self, make_shop):
        shop = make_shop(user="bob", user_type="Staff")
        shop._mark_first_purchase("bob")
        res = shop.compute_discounts({"Coffee": 2})
        assert res["total"] == pytest.approx(4.25)

    def test_first_purchase_bonus_for_new_user(self, shop):
        res = shop.compute_discounts({"Coffee": 2})
        assert res["applied_first_purchase"] is True
        # 5.00 → student 10% → 4.50 → first-purchase 15% → 3.825
        assert res["total"] == pytest.approx(3.83, abs=0.01)

    def test_first_purchase_skipped_when_prior_order_exists(self, shop):
        shop.orders.append({"user": "alice", "items": {"Tea": 1}})
        res = shop.compute_discounts({"Coffee": 2})
        assert res["applied_first_purchase"] is False

    def test_birthday_discount_applied(self, shop):
        shop._mark_first_purchase("alice")
        res = shop.compute_discounts({"Coffee": 2}, apply_birthday=True)
        assert res["applied_birthday"] is True
        # 5.00 → 10% → 4.50 → birthday 20% → 3.60
        assert res["total"] == pytest.approx(3.60)

    def test_birthday_not_reapplied_once_claimed(self, shop):
        shop._mark_first_purchase("alice")
        shop._mark_birthday_claim("alice")
        res = shop.compute_discounts({"Coffee": 2}, apply_birthday=True)
        assert res["applied_birthday"] is False

    def test_percent_promo_code(self, shop):
        shop._mark_first_purchase("alice")
        shop._exec(
            "INSERT INTO bakery_promo_codes (code, discount_type, discount_value, "
            "active) VALUES ('SAVE50', 'percent', 50, 1)")
        res = shop.compute_discounts({"Coffee": 2}, promo_code="SAVE50")
        assert res["promo_meta"]["code"] == "SAVE50"
        assert any("Promo" in lbl for lbl, _ in res["breakdown"])

    def test_fixed_promo_code(self, shop):
        shop._mark_first_purchase("alice")
        shop._exec(
            "INSERT INTO bakery_promo_codes (code, discount_type, discount_value, "
            "active) VALUES ('QUID', 'fixed', 1.0, 1)")
        res = shop.compute_discounts({"Coffee": 2}, promo_code="QUID")
        # 4.50 (after tier) minus £1 fixed promo = 3.50
        assert res["total"] == pytest.approx(3.50)

    def test_invalid_promo_warns(self, shop):
        res = shop.compute_discounts({"Coffee": 2}, promo_code="NOPE")
        assert res["promo_meta"] is None
        assert any("NOPE" in w for w in res["warnings"])

    def test_combo_saving(self, shop):
        shop._mark_first_purchase("alice")
        # Coffee (2.50) + Bagel (2.00) = 4.50 list, combo @ 4.00 → 0.50 saving.
        shop._exec(
            "INSERT INTO bakery_combos (name, items_json, combo_price, active) "
            "VALUES ('Breakfast', '{\"Coffee\": 1, \"Bagel\": 1}', 4.0, 1)")
        res = shop.compute_discounts({"Coffee": 1, "Bagel": 1})
        assert any("Combo" in lbl for lbl, _ in res["breakdown"])

    def test_happy_hour_saving(self, shop):
        from datetime import datetime
        shop._mark_first_purchase("alice")
        shop._exec(
            "INSERT INTO bakery_happy_hours (name, start_time, end_time, "
            "days_of_week, category, discount_pct, active) "
            "VALUES ('All Day', '00:00', '23:59', 'all', 'all', 25, 1)")
        now = datetime(2026, 5, 31, 12, 0, 0)
        res = shop.compute_discounts({"Coffee": 2}, now=now)
        assert any("Happy Hour" in lbl for lbl, _ in res["breakdown"])

    def test_punch_card_free_beverage(self, shop):
        shop._mark_first_purchase("alice")
        # 10 beverage punches already banked → one beverage in cart is free.
        shop._bump_punch("alice", "Beverages", 10)
        res = shop.compute_discounts({"Coffee": 1})
        assert res["punch_redeemed_category"] == "Beverages"
        assert any("Punch card" in lbl for lbl, _ in res["breakdown"])

    def test_loyalty_redemption(self, shop):
        shop._mark_first_purchase("alice")
        shop._add_loyalty_points("alice", 200)  # 200 pts = £2 redeemable
        res = shop.compute_discounts({"Coffee": 2}, loyalty_redeem_pts=200)
        assert res["loyalty_redeemed"] == 200
        # 4.50 (after tier) minus £2 = 2.50
        assert res["total"] == pytest.approx(2.50)

    def test_total_never_negative(self, shop):
        shop._exec(
            "INSERT INTO bakery_promo_codes (code, discount_type, discount_value, "
            "active) VALUES ('FREE', 'percent', 100, 1)")
        res = shop.compute_discounts({"Coffee": 1}, promo_code="FREE")
        assert res["total"] == 0.0
