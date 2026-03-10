"""
Charity Shop Stock Management System
A GUI application for managing charity shop inventory with SQLite persistence.
Features: Stock tracking, sold status, revenue calculation, and data visualization.

Integrated with the University Management System.
"""

from .charity_shop_gui import CharityShopApp, main
from .database import Database
from .dialogs import ItemDialog, SellDialog, CheckoutDialog
from .charts import ChartsWindow
from .basket import BasketWindow
from ._imports import load_email_template, render_email_template

__all__ = [
    "CharityShopApp",
    "main",
    "Database",
    "ItemDialog",
    "SellDialog",
    "CheckoutDialog",
    "ChartsWindow",
    "BasketWindow",
    "load_email_template",
    "render_email_template",
]
