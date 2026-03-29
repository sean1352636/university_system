"""
Admin Portal for Financial Aid & Scholarships

Split into submodules for maintainability:
- portal: Core AdminPortal class, dashboard, and initialization
- applications: Aid application review
- packages: Aid package creation
- aid_types: Aid types display
- disbursements: Disbursement management
- reports: Report generation
- report_export: Report export and email
- fafsa_import: FAFSA data import
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.portal import AdminPortal
from education_system.university_system.infrastructure.database.db import get_connection

__all__ = ['AdminPortal', 'get_connection']
