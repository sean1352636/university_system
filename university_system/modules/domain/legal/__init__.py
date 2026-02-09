"""
Legal Services Module

Provides comprehensive legal aid center functionality for the university system,
including case management, consultations, document handling, billing,
and reporting with email and finance integration.
"""

from university_system.modules.domain.legal.gui.legal_services_gui import (
    LegalServicesGUI,
    launch_legal_services_gui
)
from university_system.modules.domain.legal.services.legal_services_core import (
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
