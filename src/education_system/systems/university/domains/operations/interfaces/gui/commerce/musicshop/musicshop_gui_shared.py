"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox

import logging

from datetime import datetime

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.infrastructure.database.db import get_db_connection

from education_system.systems.university.domains.operations.domain.commerce.musicshop.services.musicshop_core import (
    ProductManager, OrderManager, TransactionManager, ReportManager, WishlistManager,
    init_musicshop_db, MUSIC_CATEGORIES, GENRES, ORDER_STATUSES, CONDITION_TYPES
)

from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    record_payment_to_finance,
    process_student_finance_account_payment,
    get_student_finance_account_balance
)

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
