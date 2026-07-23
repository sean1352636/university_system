"""CatalogMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class CatalogMixin:
    def _product_info(self, item_name):
        for cat in self.products.values():
            if item_name in cat:
                return cat[item_name]
        return None

    def _product_category(self, item_name):
        for cat_name, items in self.products.items():
            if item_name in items:
                return cat_name
        return None

    def _passes_dietary_filter(self, info, required_dietary, excluded_allergens):
        """Return True if a product matches every required dietary tag and
        contains none of the excluded allergens."""
        if not info:
            return False
        dietary = set(info.get("dietary", []) or [])
        allergens = set(info.get("allergens", []) or [])
        for tag in required_dietary:
            if tag not in dietary:
                return False
        for al in excluded_allergens:
            if al in allergens:
                return False
        return True

