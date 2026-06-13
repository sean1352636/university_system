"""Tests for Nail Bar GUI — import verification and service integration."""

import pytest
pytestmark = pytest.mark.gui

import pytest


class TestNailBarImports:
    def test_gui_class_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.gui.nailbar_gui import NailBarGUI
        assert NailBarGUI is not None

    def test_treatment_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
        assert TreatmentManager is not None

    def test_technician_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TechnicianManager
        assert TechnicianManager is not None

    def test_appointment_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
        assert AppointmentManager is not None

    def test_transaction_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TransactionManager
        assert TransactionManager is not None

    def test_report_manager_importable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import ReportManager
        assert ReportManager is not None

    def test_init_nailbar_db_callable(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import init_nailbar_db
        assert callable(init_nailbar_db)

    def test_constants_defined(self):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import (
            TREATMENT_CATEGORIES, APPOINTMENT_STATUSES, TIME_SLOTS,
        )
        assert len(TREATMENT_CATEGORIES) > 0
        assert "booked" in APPOINTMENT_STATUSES
        assert "09:00" in TIME_SLOTS
