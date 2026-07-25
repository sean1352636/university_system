"""
Information Rights Module

Manages the lifecycle of statutory information requests received by the
university:

* Subject Access Requests (SAR) under UK GDPR / Data Protection Act 2018
  - 1 calendar month statutory deadline (Art. 12(3))
  - extendable by a further 2 months for complex / numerous requests
* Freedom of Information Act 2000 requests (FOI)
  - 20 working day statutory deadline (s.10(1))
* Environmental Information Regulations 2004 requests (EIR)
  - 20 working day statutory deadline (reg. 5(2))

Covers intake, identity verification, deadline tracking, exemption logging,
redaction logging, communications, and outcome recording.
"""

from education_system.systems.university.domain.governance.legal.information_rights.services.information_rights_core import (  # noqa: E501
    InformationRightsService,
    InformationRightsError,
    REQUEST_TYPES,
    REQUEST_STATUSES,
    OUTCOMES,
    FOIA_EXEMPTIONS,
    DPA_EXEMPTIONS,
    EIR_EXCEPTIONS,
    IDENTITY_STATUSES,
)

__all__ = [
    "InformationRightsService",
    "InformationRightsError",
    "REQUEST_TYPES",
    "REQUEST_STATUSES",
    "OUTCOMES",
    "FOIA_EXEMPTIONS",
    "DPA_EXEMPTIONS",
    "EIR_EXCEPTIONS",
    "IDENTITY_STATUSES",
]
