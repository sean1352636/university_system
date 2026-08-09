"""
Legal Services Module

Provides comprehensive legal aid center functionality for the university system,
including case management, consultations, document handling, billing,
and reporting with email and finance integration.
"""

from education_system.systems.university.domain.governance.legal.services.legal_services_core import (
    CaseManager,
    ConsultationManager,
    DocumentManager,
    PaymentManager,
    init_legal_services_db,
    calculate_service_fee,
    generate_invoice_text,
    CASE_TYPES,
    CASE_STATUSES,
    SERVICE_FEES
)

__all__ = [
    'LegalServicesGUI',
    'launch_legal_services_gui',
    'CaseManager',
    'ConsultationManager',
    'DocumentManager',
    'PaymentManager',
    'init_legal_services_db',
    'calculate_service_fee',
    'generate_invoice_text',
    'CASE_TYPES',
    'CASE_STATUSES',
    'SERVICE_FEES'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "LegalServicesGUI": "education_system.systems.university.interfaces.gui.governance.legal.legal_services_gui",
    "launch_legal_services_gui": "education_system.systems.university.interfaces.gui.governance.legal.legal_services_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
