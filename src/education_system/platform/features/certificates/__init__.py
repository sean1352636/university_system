"""Shared certificates and transcript generation module.

Provides TranscriptService and CertificateService for use across all
education subsystems (primary, secondary, college, university).
"""

from education_system.platform.features.certificates.transcript_service import TranscriptService
from education_system.platform.features.certificates.certificate_service import CertificateService

__all__ = ["TranscriptService", "CertificateService"]
