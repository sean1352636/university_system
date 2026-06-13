"""University Bakery Shop — entry point.

Composes :class:`BakeryShop` from ~30 mixin classes (one per cohesive
feature area). Splitting was done mechanically from the original
single-file bakery_shop.py; every method keeps its original name,
signature, and body — only its file location changed. Internal
``self.X`` calls resolve via MRO across the mixins.
"""

# --- sys.path bootstrap (same as the original single-file module) -------- #
# When the main university GUI launches us as a subprocess, the child
# Python is invoked directly on this file's path with no PYTHONPATH set,
# so `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put that
# on sys.path. No-op when imported normally.
import os as _os
import sys as _sys
if 'education_system' not in _sys.modules:
    _here = _os.path.abspath(_os.path.dirname(__file__))
    while _here and not _os.path.isdir(_os.path.join(_here, 'education_system')):
        _parent = _os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in _sys.path:
        _sys.path.insert(0, _here)

from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403

from education_system.university_system.modules.domain.commerce.bakery_shop.domain.data import DataMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.catalog import CatalogMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.loyalty import LoyaltyMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.inventory_data import InventoryDataMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.shop_misc import ShopMiscMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.special_orders import SpecialOrdersMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.finance import FinanceMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.domain.analytics_data import AnalyticsDataMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.prefs import PrefsMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.receipts import ReceiptsMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.shifts import ShiftsMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.feedback_kitchen import FeedbackKitchenMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.pricing import PricingMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.ui.ui_core import UICoreMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_shop import ShopTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_cart import CartTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.checkout import CheckoutMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_orders import OrdersTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_rewards import RewardsTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_refunds import RefundsTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_inventory import InventoryTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_special import SpecialTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_analytics import AnalyticsTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_main.tab_admin import AdminTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.services.login_misc import LoginMiscMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_advanced.tab_production import ProductionTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_advanced.tab_pos import POSTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_advanced.tab_staff import StaffTabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_advanced.tab_reports_qa import ReportsQATabMixin
from education_system.university_system.modules.domain.commerce.bakery_shop.tabs_advanced.tab_integrations import IntegrationsTabMixin


class BakeryShop(
    DataMixin,
    CatalogMixin,
    LoyaltyMixin,
    InventoryDataMixin,
    ShopMiscMixin,
    SpecialOrdersMixin,
    FinanceMixin,
    AnalyticsDataMixin,
    PrefsMixin,
    ReceiptsMixin,
    ShiftsMixin,
    FeedbackKitchenMixin,
    PricingMixin,
    UICoreMixin,
    ShopTabMixin,
    CartTabMixin,
    CheckoutMixin,
    OrdersTabMixin,
    RewardsTabMixin,
    RefundsTabMixin,
    InventoryTabMixin,
    SpecialTabMixin,
    AnalyticsTabMixin,
    AdminTabMixin,
    LoginMiscMixin,
    ProductionTabMixin,
    POSTabMixin,
    StaffTabMixin,
    ReportsQATabMixin,
    IntegrationsTabMixin,
):
    def __init__(self, root):
        self.root = root
        self.root.title("University Bakery Shop")
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self.root.configure(bg="#FFF8E7")

        # Color scheme — start with the classic palette; user prefs may
        # swap it after auth is resolved.
        self.colors = dict(THEMES["classic"])
        self._theme_name = "classic"
        self._text_scale = 1.0

        # Product catalog with inventory + dietary/allergen/nutrition/
        # image/fresh-bake metadata. Allergens are normalised against
        # the ALLERGEN_VOCAB list, dietary tags against DIETARY_VOCAB.
        # Nutrition values are per single unit. `image` is a path
        # relative to this module's `images/` dir; the GUI falls back
        # to the emoji if the file is missing.
        self.products = {
            "Breads": {
                "White Bread":      _mk("price", 2.50, "stock", 50, "emoji", "🍞",
                                        "allergens", ["gluten", "wheat"],
                                        "dietary", ["vegetarian", "vegan"],
                                        "nutrition", {"cal": 180, "protein": 6, "carbs": 35, "fat": 2},
                                        "image", "white_bread.png",
                                        "fresh_bake_times", ["07:00", "13:00"]),
                "Whole Wheat":      _mk("price", 3.00, "stock", 40, "emoji", "🍞",
                                        "allergens", ["gluten", "wheat"],
                                        "dietary", ["vegetarian", "vegan", "high-fibre"],
                                        "nutrition", {"cal": 170, "protein": 7, "carbs": 33, "fat": 2},
                                        "image", "whole_wheat.png",
                                        "fresh_bake_times", ["07:00", "13:00"]),
                "Baguette":         _mk("price", 3.50, "stock", 30, "emoji", "🥖",
                                        "allergens", ["gluten", "wheat"],
                                        "dietary", ["vegetarian", "vegan"],
                                        "nutrition", {"cal": 250, "protein": 8, "carbs": 50, "fat": 1},
                                        "image", "baguette.png",
                                        "fresh_bake_times", ["07:30", "12:30", "16:30"]),
                "Croissant":        _mk("price", 2.75, "stock", 60, "emoji", "🥐",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 240, "protein": 5, "carbs": 26, "fat": 12},
                                        "image", "croissant.png",
                                        "fresh_bake_times", ["07:00", "10:00"]),
                "Bagel":            _mk("price", 2.00, "stock", 45, "emoji", "🥯",
                                        "allergens", ["gluten", "wheat"],
                                        "dietary", ["vegetarian", "vegan"],
                                        "nutrition", {"cal": 280, "protein": 11, "carbs": 55, "fat": 2},
                                        "image", "bagel.png",
                                        "fresh_bake_times", ["07:00"]),
            },
            "Pastries": {
                "Chocolate Muffin": _mk("price", 3.25, "stock", 35, "emoji", "🧁",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 420, "protein": 6, "carbs": 55, "fat": 19},
                                        "image", "choc_muffin.png",
                                        "fresh_bake_times", ["07:30", "11:30"]),
                "Blueberry Muffin": _mk("price", 3.25, "stock", 35, "emoji", "🧁",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 380, "protein": 5, "carbs": 53, "fat": 16},
                                        "image", "blueberry_muffin.png",
                                        "fresh_bake_times", ["07:30", "11:30"]),
                "Cinnamon Roll":    _mk("price", 3.75, "stock", 25, "emoji", "🥐",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 470, "protein": 6, "carbs": 60, "fat": 22},
                                        "image", "cinnamon_roll.png",
                                        "fresh_bake_times", ["08:00"]),
                "Donut":            _mk("price", 2.25, "stock", 50, "emoji", "🍩",
                                        "allergens", ["gluten", "wheat", "milk", "eggs", "soy"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 320, "protein": 4, "carbs": 38, "fat": 17},
                                        "image", "donut.png",
                                        "fresh_bake_times", ["07:00", "13:00"]),
                "Danish Pastry":    _mk("price", 4.00, "stock", 20, "emoji", "🥐",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 350, "protein": 5, "carbs": 38, "fat": 19},
                                        "image", "danish.png",
                                        "fresh_bake_times", ["07:30"]),
            },
            "Cakes": {
                "Chocolate Cake":   _mk("price", 25.00, "stock", 8,  "emoji", "🍰",
                                        "allergens", ["gluten", "wheat", "milk", "eggs", "soy"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 380, "protein": 4, "carbs": 50, "fat": 18},
                                        "image", "choc_cake.png",
                                        "fresh_bake_times", ["09:00"]),
                "Vanilla Cake":     _mk("price", 22.00, "stock", 8,  "emoji", "🎂",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 350, "protein": 4, "carbs": 48, "fat": 15},
                                        "image", "vanilla_cake.png",
                                        "fresh_bake_times", ["09:00"]),
                "Cheesecake":       _mk("price", 28.00, "stock", 6,  "emoji", "🍰",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 410, "protein": 7, "carbs": 35, "fat": 26},
                                        "image", "cheesecake.png",
                                        "fresh_bake_times", ["10:00"]),
                "Cupcake":          _mk("price", 3.50,  "stock", 40, "emoji", "🧁",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 290, "protein": 3, "carbs": 38, "fat": 14},
                                        "image", "cupcake.png",
                                        "fresh_bake_times", ["08:00", "12:00"]),
                "Tiramisu":         _mk("price", 32.00, "stock", 5,  "emoji", "🍰",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 450, "protein": 6, "carbs": 40, "fat": 28},
                                        "image", "tiramisu.png",
                                        "fresh_bake_times", ["10:00"]),
            },
            "Cookies": {
                "Chocolate Chip":   _mk("price", 1.75, "stock", 70, "emoji", "🍪",
                                        "allergens", ["gluten", "wheat", "milk", "eggs", "soy"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 220, "protein": 2, "carbs": 28, "fat": 11},
                                        "image", "choc_chip.png",
                                        "fresh_bake_times", ["07:30", "13:30"]),
                "Oatmeal Raisin":   _mk("price", 1.75, "stock", 50, "emoji", "🍪",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 200, "protein": 3, "carbs": 30, "fat": 8},
                                        "image", "oatmeal_raisin.png",
                                        "fresh_bake_times", ["07:30", "13:30"]),
                "Sugar Cookie":     _mk("price", 1.50, "stock", 60, "emoji", "🍪",
                                        "allergens", ["gluten", "wheat", "milk", "eggs"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 180, "protein": 2, "carbs": 26, "fat": 8},
                                        "image", "sugar_cookie.png",
                                        "fresh_bake_times", ["08:00", "14:00"]),
                "Macaron":          _mk("price", 3.00, "stock", 30, "emoji", "🍪",
                                        "allergens", ["milk", "eggs", "nuts", "almonds"],
                                        "dietary", ["vegetarian", "gluten-free"],
                                        "nutrition", {"cal": 90, "protein": 2, "carbs": 13, "fat": 4},
                                        "image", "macaron.png",
                                        "fresh_bake_times", ["10:00"]),
                "Brownie":          _mk("price", 2.50, "stock", 40, "emoji", "🍫",
                                        "allergens", ["gluten", "wheat", "milk", "eggs", "soy"],
                                        "dietary", ["vegetarian"],
                                        "nutrition", {"cal": 340, "protein": 4, "carbs": 42, "fat": 18},
                                        "image", "brownie.png",
                                        "fresh_bake_times", ["08:30", "13:30"]),
            },
            "Beverages": {
                "Coffee":           _mk("price", 2.50, "stock", 100, "emoji", "☕",
                                        "allergens", [],
                                        "dietary", ["vegan", "vegetarian", "halal", "gluten-free"],
                                        "nutrition", {"cal": 5, "protein": 0, "carbs": 0, "fat": 0},
                                        "image", "coffee.png",
                                        "fresh_bake_times", []),
                "Tea":              _mk("price", 2.00, "stock", 80,  "emoji", "🍵",
                                        "allergens", [],
                                        "dietary", ["vegan", "vegetarian", "halal", "gluten-free"],
                                        "nutrition", {"cal": 2, "protein": 0, "carbs": 0, "fat": 0},
                                        "image", "tea.png",
                                        "fresh_bake_times", []),
                "Hot Chocolate":    _mk("price", 3.00, "stock", 60,  "emoji", "☕",
                                        "allergens", ["milk"],
                                        "dietary", ["vegetarian", "halal"],
                                        "nutrition", {"cal": 220, "protein": 8, "carbs": 32, "fat": 7},
                                        "image", "hot_choc.png",
                                        "fresh_bake_times", []),
                "Fresh Juice":      _mk("price", 3.50, "stock", 40,  "emoji", "🧃",
                                        "allergens", [],
                                        "dietary", ["vegan", "vegetarian", "halal", "gluten-free"],
                                        "nutrition", {"cal": 110, "protein": 1, "carbs": 26, "fat": 0},
                                        "image", "juice.png",
                                        "fresh_bake_times", []),
                "Milk":             _mk("price", 1.75, "stock", 50,  "emoji", "🥛",
                                        "allergens", ["milk"],
                                        "dietary", ["vegetarian", "halal", "gluten-free"],
                                        "nutrition", {"cal": 150, "protein": 8, "carbs": 12, "fat": 8},
                                        "image", "milk.png",
                                        "fresh_bake_times", []),
            },
        }

        # Shopping cart and order history
        self.cart = {}
        self.orders = []

        # Resolve identity from EDU_AUTH_* env vars (no in-app login).
        user = _get_current_user()
        self._auth_user = user
        if user:
            self.current_user = (user.get('username') or user.get('email')
                                 or user.get('user_id') or 'Unknown')
            self.user_type = _bakery_user_type(user.get('role'))
        else:
            self.current_user = None
            self.user_type = "Guest"
        logger.info("Bakery Shop starting user=%s tier=%s",
                    self.current_user or 'guest', self.user_type)

        # Ensure DB schema then load saved data.
        self._ensure_schema()
        self._ensure_production_seed()
        self.load_data()

        # Currency state (used by fmt_money before the header is built).
        self._currency_code = "GBP"

        # Build the UI
        self.create_widgets()

        # Apply persisted user preferences (theme / scale / language).
        try:
            prefs = self.load_user_prefs()
            if prefs.get("text_scale", 1.0) != 1.0:
                self.apply_text_scale(prefs["text_scale"])
            if prefs.get("theme") and prefs["theme"] != "classic":
                self.apply_theme(prefs["theme"])
        except Exception:
            logger.debug("Pref apply on startup failed", exc_info=True)

        # Global keyboard shortcuts (45).
        try:
            self._bind_keyboard_shortcuts()
        except Exception:
            logger.debug("Keyboard binding failed", exc_info=True)

        # If the user has a saved cart from last session, offer to restore.
        try:
            if self.has_saved_cart():
                if messagebox.askyesno(
                    "Saved Cart",
                    "You have a cart saved from a previous session.\n"
                    "Restore it now?",
                ):
                    self.restore_saved_cart()
                    self.clear_saved_cart()
                    self.refresh_cart()
                    self.refresh_products()
                    self.update_cart_tab_title()
        except Exception:
            logger.debug("Saved-cart prompt failed", exc_info=True)


def main():
    _remove_legacy_files()
    root = tk.Tk()
    BakeryShop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
