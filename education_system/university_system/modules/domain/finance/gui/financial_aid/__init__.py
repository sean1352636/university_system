"""
Financial Aid & Scholarships GUI Module

This module provides comprehensive GUI interfaces for financial aid and scholarship management,
including student portals, admin portals, and management tools.

Main Components:
- FinancialAidGUI: Main coordinator for the application
- StudentPortal: Student-facing interface for browsing and applying
- AdminPortal: Admin interface for management and processing
- ScholarshipManagerGUI: Scholarship management tools

Usage:
    from education_system.university_system.modules.domain.finance.gui.financial_aid import FinancialAidGUI

    # Create and run the GUI
    app = FinancialAidGUI(auth_instance=auth)
    app.run()

    # Or embed in another window
    app = FinancialAidGUI(auth_instance=auth, parent=parent_frame)
    app.create_embedded_interface()
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui import FinancialAidGUI
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal import StudentPortal
from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal import AdminPortal
from education_system.university_system.modules.domain.finance.gui.financial_aid.scholarship_manager import ScholarshipManagerGUI

__all__ = [
    'FinancialAidGUI',
    'StudentPortal',
    'AdminPortal',
    'ScholarshipManagerGUI',
]

__version__ = '1.0.0'
__author__ = 'University Management System'
