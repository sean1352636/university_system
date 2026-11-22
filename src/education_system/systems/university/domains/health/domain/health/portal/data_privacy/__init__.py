"""Health portal security, integration and risk-assessment administration.

This was a single 2,181-line ``data_privacy.py`` module. It is now a package of
focused modules; the import path is unchanged, so existing callers keep working:

* :mod:`.schema`            - idempotent DDL for the integration/security tables
* :mod:`.audit`             - the audit logger, ``log_audit_event`` and the log viewer
* :mod:`.encryption`        - encryption key generation and inventory
* :mod:`.security_admin`    - interactive security administration menus
* :mod:`.security_reports`  - security report generation
* :mod:`.integrations`      - external system integration management
* :mod:`.menu_wiring`       - menu wiring reference (pulls in the heavy portal UI)
* :mod:`.risk_assessment`   - database-backed risk assessment workflows
* :mod:`.risk_scoring`      - pure scoring helpers (no DB, no console I/O)

Names are resolved lazily, so importing one function does not drag in the whole
package. Prefer importing from the submodule directly in new code — in
particular, patching ``data_privacy.audit_logger`` here does *not* affect
:func:`.audit.log_audit_event`; patch ``data_privacy.audit.audit_logger``.
"""

import importlib
import os  # noqa: F401  (kept: callers patch ``data_privacy.os`` for key file I/O)

_EXPORTS = {
    # .schema
    "ensure_integration_schema": "schema",
    "ensure_security_schema": "schema",
    "_first_existing_column": "schema",
    # .audit
    "audit_logger": "audit",
    "log_audit_event": "audit",
    "view_audit_log": "audit",
    # .encryption
    "get_or_create_encryption_key": "encryption",
    "encryption_key_management": "encryption",
    # .security_admin
    "advanced_security_menu": "security_admin",
    "user_session_management": "security_admin",
    "access_control_lists": "security_admin",
    "security_policy_configuration": "security_admin",
    "security_incident_response": "security_admin",
    "ip_restriction_management": "security_admin",
    "two_factor_authentication_setup": "security_admin",
    "review_security_settings": "security_admin",
    "update_security_settings": "security_admin",
    "security_audit_menu": "security_admin",
    # .security_reports
    "generate_security_report": "security_reports",
    # .integrations
    "integration_logs": "integrations",
    "data_sync_status": "integrations",
    "laboratory_system_integration": "integrations",
    "insurance_system_integration": "integrations",
    "integration_management": "integrations",
    "api_key_management": "integrations",
    "integration_health_check": "integrations",
    # .menu_wiring
    "add_missing_menu_integrations": "menu_wiring",
    # .risk_assessment
    "view_risk_assessments": "risk_assessment",
    "screening_recommendations": "risk_assessment",
    "population_risk_analysis": "risk_assessment",
    "health_risk_assessment": "risk_assessment",
    "conduct_risk_assessment": "risk_assessment",
    # .risk_scoring
    "assess_contact_risk": "risk_scoring",
    "calculate_risk_score": "risk_scoring",
    "get_risk_factors": "risk_scoring",
    "generate_risk_recommendations": "risk_scoring",
}

__all__ = sorted(name for name in _EXPORTS if not name.startswith("_"))


def __getattr__(name):
    """Resolve a re-exported name by importing only the module that defines it."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{module_name}", __name__), name)
    globals()[name] = value  # cache so later lookups skip this hook
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
