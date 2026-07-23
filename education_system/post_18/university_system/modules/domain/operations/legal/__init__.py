"""
Legal Services Module

Provides comprehensive legal aid center functionality for the university system,
including case management, consultations, document handling, billing,
and reporting with email and finance integration.
"""

from education_system.post_18.university_system.modules.domain.operations.legal.gui.legal_services_gui import (
    LegalServicesGUI,
    launch_legal_services_gui
)
from education_system.post_18.university_system.modules.domain.operations.legal.services.legal_services_core import (
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
