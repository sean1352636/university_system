"""Shared fixtures for the University Bakery Shop test suite.

``BakeryShop`` is a tkinter GUI app composed from ~30 mixins, but all of
its business logic (pricing, loyalty, VAT, inventory, finance, shifts,
feedback) lives in the domain/service mixins and only touches the DB
through the ``_connect`` chokepoint.  We exercise that logic without a
display by building an instance via ``__new__`` (skipping the GUI
``__init__``), pointing ``_connect`` at a throwaway SQLite file, and
running the real ``_ensure_schema`` so every ``bakery_*`` table exists.
"""

import os
import sqlite3
import tempfile

import pytest

from education_system.university_system.modules.domain.commerce.bakery_shop.app import (
    BakeryShop,
)


def _mk(**kw):
    return dict(kw)


# A compact but faithful catalog: every category the pricing/VAT/punch-card
# logic cares about (Breads, Pastries, Cakes, Cookies, Beverages), each with
# price/stock/allergens/dietary so dietary filters and combos work too.
def build_catalog():
    return {
        "Breads": {
            "Bagel": _mk(price=2.00, stock=45, allergens=["gluten", "wheat"],
                         dietary=["vegetarian", "vegan"]),
            "Baguette": _mk(price=3.50, stock=30, allergens=["gluten", "wheat"],
                            dietary=["vegetarian", "vegan"]),
        },
        "Pastries": {
            "Croissant": _mk(price=2.75, stock=60,
                             allergens=["gluten", "wheat", "milk", "eggs"],
                             dietary=["vegetarian"]),
        },
        "Cakes": {
            "Chocolate Cake": _mk(price=25.00, stock=8,
                                  allergens=["gluten", "wheat", "milk", "eggs"],
                                  dietary=["vegetarian"]),
        },
        "Cookies": {
            "Macaron": _mk(price=3.00, stock=30,
                           allergens=["milk", "eggs", "nuts", "almonds"],
                           dietary=["vegetarian", "gluten-free"]),
        },
        "Beverages": {
            "Coffee": _mk(price=2.50, stock=100, allergens=[],
                          dietary=["vegan", "vegetarian", "halal", "gluten-free"]),
            "Tea": _mk(price=2.00, stock=80, allergens=[],
                       dietary=["vegan", "vegetarian", "halal", "gluten-free"]),
            "Milk": _mk(price=1.75, stock=50, allergens=["milk"],
                        dietary=["vegetarian", "halal", "gluten-free"]),
        },
    }


def _make_shop(db_path, *, user="alice", user_type="Student"):
    shop = BakeryShop.__new__(BakeryShop)
    # Each call returns a fresh connection to the same file — the mixins
    # open/commit/close per operation, exactly as in production.
    shop._connect = lambda: sqlite3.connect(db_path)
    shop.current_user = user
    shop.user_type = user_type
    shop.orders = []
    shop.cart = {}
    shop.products = build_catalog()
    shop._currency_code = "GBP"
    shop._ensure_schema()
    return shop


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    for p in (path, path + "-wal", path + "-shm", path + "-journal"):
        if os.path.exists(p):
            os.unlink(p)


@pytest.fixture
def shop(db_path):
    """A Student-tier shop owned by 'alice' on a fresh in-file DB."""
    return _make_shop(db_path)


@pytest.fixture
def make_shop(db_path):
    """Factory for building shops with a different user/tier on the same DB."""
    def _factory(*, user="alice", user_type="Student"):
        return _make_shop(db_path, user=user, user_type=user_type)
    return _factory
