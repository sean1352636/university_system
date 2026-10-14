"""Progression HTTP routes: credentials and portfolios.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.progression.credential_routes import credential_bp
from education_system.api.university.progression.portfolio_routes import portfolio_bp

DOMAIN_BLUEPRINTS = [
    credential_bp,
    portfolio_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "credential_bp", "portfolio_bp"]
