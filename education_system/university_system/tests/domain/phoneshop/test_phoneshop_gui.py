"""Tests for Phone Shop GUI — import verification and service integration."""

import pytest
pytestmark = pytest.mark.gui

import pytest


class TestPhoneShopImports:
    def test_gui_class_importable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.gui.phoneshop_gui import PhoneShopGUI
        assert PhoneShopGUI is not None

    def test_product_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
        assert ProductManager is not None

    def test_order_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
        assert OrderManager is not None

    def test_transaction_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import TransactionManager
        assert TransactionManager is not None

    def test_report_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ReportManager
        assert ReportManager is not None

    def test_init_phoneshop_db_callable(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import init_phoneshop_db
        assert callable(init_phoneshop_db)

    def test_constants_defined(self):
        from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import (
            PHONE_CATEGORIES, ORDER_STATUSES, PAYMENT_STATUSES,
        )
        assert "Smartphone" in PHONE_CATEGORIES
        assert "pending" in ORDER_STATUSES
        assert "completed" in PAYMENT_STATUSES
