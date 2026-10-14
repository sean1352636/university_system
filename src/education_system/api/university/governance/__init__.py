"""Governance HTTP routes: HESA returns and legal.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.governance.hesa_export_routes import hesa_export_bp
from education_system.api.university.governance.legal_routes import legal_bp

DOMAIN_BLUEPRINTS = [
    hesa_export_bp,
    legal_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "hesa_export_bp", "legal_bp"]
