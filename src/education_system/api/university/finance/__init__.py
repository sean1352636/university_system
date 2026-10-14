"""Finance HTTP routes: fees, budgets, scholarships, student finance.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.finance.blockchain_routes import blockchain_bp
from education_system.api.university.finance.budget_routes import budget_bp
from education_system.api.university.finance.finance_routes import finance_bp
from education_system.api.university.finance.financial_aid_routes import financial_aid_bp
from education_system.api.university.finance.scholarship_finder_routes import scholarship_finder_bp
from education_system.api.university.finance.scholarship_routes import scholarship_bp
from education_system.api.university.finance.student_finance_routes import student_finance_bp

DOMAIN_BLUEPRINTS = [
    blockchain_bp,
    budget_bp,
    finance_bp,
    financial_aid_bp,
    scholarship_finder_bp,
    scholarship_bp,
    student_finance_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "blockchain_bp", "budget_bp", "finance_bp", "financial_aid_bp", "scholarship_finder_bp", "scholarship_bp", "student_finance_bp"]
