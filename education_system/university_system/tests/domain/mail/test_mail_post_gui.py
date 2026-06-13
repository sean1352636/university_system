"""Tests for Mail/Post GUI — import verification and service integration."""

import pytest
pytestmark = pytest.mark.gui

import pytest


class TestMailPostImports:
    def test_gui_class_importable(self):
        from education_system.university_system.modules.domain.communications.mail.gui.mail_post_gui import MailPostGUI
        assert MailPostGUI is not None

    def test_package_manager_importable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import PackageManager
        assert PackageManager is not None

    def test_po_box_manager_importable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import POBoxManager
        assert POBoxManager is not None

    def test_forwarding_manager_importable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import ForwardingManager
        assert ForwardingManager is not None

    def test_transaction_manager_importable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import TransactionManager
        assert TransactionManager is not None

    def test_report_manager_importable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import ReportManager
        assert ReportManager is not None

    def test_init_mail_db_callable(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import init_mail_db
        assert callable(init_mail_db)

    def test_generate_tracking_number(self):
        from education_system.university_system.modules.domain.communications.mail.services.mail_post_core import generate_tracking_number
        tracking = generate_tracking_number()
        assert tracking.startswith("UNI-")
        assert len(tracking) > 12
