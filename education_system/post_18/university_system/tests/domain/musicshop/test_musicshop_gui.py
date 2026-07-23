"""Tests for Music Shop GUI — import verification and service integration."""

import pytest
pytestmark = pytest.mark.gui

import pytest


class TestMusicShopImports:
    def test_gui_class_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.gui.musicshop_gui import MusicShopGUI
        assert MusicShopGUI is not None

    def test_product_manager_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import ProductManager
        assert ProductManager is not None

    def test_order_manager_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import OrderManager
        assert OrderManager is not None

    def test_wishlist_manager_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import WishlistManager
        assert WishlistManager is not None

    def test_transaction_manager_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import TransactionManager
        assert TransactionManager is not None

    def test_report_manager_importable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import ReportManager
        assert ReportManager is not None

    def test_init_musicshop_db_callable(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import init_musicshop_db
        assert callable(init_musicshop_db)

    def test_constants_defined(self):
        from education_system.post_18.university_system.modules.domain.commerce.musicshop.services.musicshop_core import MUSIC_CATEGORIES, GENRES
        assert len(MUSIC_CATEGORIES) > 0
        assert len(GENRES) > 0
