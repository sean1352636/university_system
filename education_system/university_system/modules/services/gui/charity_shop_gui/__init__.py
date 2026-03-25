"""
Charity Shop Stock Management System
A GUI application for managing charity shop inventory with SQLite persistence.
Features: Stock tracking, sold status, revenue calculation, and data visualization.

Integrated with the University Management System.
"""

from education_system.university_system.modules.services.gui.charity_shop_gui.charity_shop_gui import CharityShopApp, main
from education_system.university_system.modules.services.gui.charity_shop_gui.database import Database
from education_system.university_system.modules.services.gui.charity_shop_gui.dialogs import ItemDialog, SellDialog, CheckoutDialog
from education_system.university_system.modules.services.gui.charity_shop_gui.charts import ChartsWindow
from education_system.university_system.modules.services.gui.charity_shop_gui.basket import BasketWindow
from education_system.university_system.modules.services.gui.charity_shop_gui._imports import load_email_template, render_email_template

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
