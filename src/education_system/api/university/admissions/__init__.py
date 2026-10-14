"""Admissions HTTP routes: applications, UCAS, clearing, CRM.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.admissions.admission_routes import admission_bp
from education_system.api.university.admissions.admissions_crm_routes import admissions_crm_bp
from education_system.api.university.admissions.clearing_adjustment_routes import clearing_adjustment_bp
from education_system.api.university.admissions.ucas_routes import ucas_bp

DOMAIN_BLUEPRINTS = [
    admission_bp,
    admissions_crm_bp,
    clearing_adjustment_bp,
    ucas_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "admission_bp", "admissions_crm_bp", "clearing_adjustment_bp", "ucas_bp"]
