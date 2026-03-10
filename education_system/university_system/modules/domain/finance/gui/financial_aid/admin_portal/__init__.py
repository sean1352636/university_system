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

from .portal import AdminPortal

__all__ = ['AdminPortal']
