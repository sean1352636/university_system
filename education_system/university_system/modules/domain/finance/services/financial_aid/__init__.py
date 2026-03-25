"""
Integrated Financial Aid & Scholarship Management Module

Provides comprehensive financial aid and scholarship management including:
- Financial aid applications and FAFSA integration
- Aid package creation and management
- Scholarship opportunities and applications
- Award disbursements and tracking
- Renewal requirement management
- Compliance reporting

Managers:
    - FinancialAidManager: Manage financial aid applications and packages
    - ScholarshipManager: Manage scholarships and awards

Example Usage:
    from education_system.university_system.modules.domain.finance.services.financial_aid import (
        FinancialAidManager,
        ScholarshipManager
    )

    # Import FAFSA data
    aid_mgr = FinancialAidManager()
    aid_mgr.import_fafsa_data(
        student_id=1,
        academic_year="2024-2025",
        efc=5000,
        submission_date=datetime.now().date()
    )

    # Create scholarship
    scholarship_mgr = ScholarshipManager()
    scholarship_id = scholarship_mgr.create_scholarship(
        name="Presidential Scholarship",
        amount=10000,
        min_gpa=3.5,
        renewable=True
    )
"""

from education_system.university_system.modules.domain.finance.services.financial_aid.aid_manager import FinancialAidManager
from education_system.university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
from education_system.university_system.modules.domain.finance.services.financial_aid.schema import create_financial_aid_tables

__all__ = [
    'FinancialAidManager',
    'ScholarshipManager',
    'create_financial_aid_tables'
]
