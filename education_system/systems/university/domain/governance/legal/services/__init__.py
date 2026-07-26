"""Legal Services Core Module"""

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
    CONSULTATION_STATUSES,
    PAYMENT_STATUSES,
    SERVICE_FEES
)

__all__ = [
    'CaseManager',
    'ConsultationManager',
    'DocumentManager',
    'PaymentManager',
    'init_legal_services_db',
    'calculate_service_fee',
    'generate_invoice_text',
    'CASE_TYPES',
    'CASE_STATUSES',
    'CONSULTATION_STATUSES',
    'PAYMENT_STATUSES',
    'SERVICE_FEES'
]
