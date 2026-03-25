"""Fixtures for admin module tests."""

import pytest

from education_system.college_system.modules.domain.user_management.services.user_management_service import UserManagementService
from education_system.college_system.modules.domain.policies.services.policies_service import PolicyService
from education_system.college_system.modules.domain.gdpr.services.gdpr_service import GDPRService
from education_system.college_system.modules.domain.audit_reports.services.audit_reports_service import AuditReportService
from education_system.college_system.modules.domain.bulk_operations.services.bulk_operations_service import BulkOperationService
from education_system.college_system.modules.domain.quality_assurance.services.quality_assurance_service import QualityAssuranceService
from education_system.college_system.modules.domain.document_hub.services.document_hub_service import DocumentHubService
from education_system.college_system.modules.domain.accessibility.services.accessibility_service import AccessibilityService
from education_system.college_system.modules.domain.attachments.services.attachments_service import AttachmentService


@pytest.fixture
def user_management_service(db_path):
    return UserManagementService(db_path)


@pytest.fixture
def policies_service(db_path):
    return PolicyService(db_path)


@pytest.fixture
def gdpr_service(db_path):
    return GDPRService(db_path)


@pytest.fixture
def audit_reports_service(db_path):
    return AuditReportService(db_path)


@pytest.fixture
def bulk_operations_service(db_path):
    return BulkOperationService(db_path)


@pytest.fixture
def quality_assurance_service(db_path):
    return QualityAssuranceService(db_path)


@pytest.fixture
def settings_service(db_path):
    from education_system.college_system.modules.domain.settings.services.settings_service import SettingsService
    return SettingsService(db_path)


@pytest.fixture
def admissions_service(db_path):
    from education_system.college_system.modules.domain.admissions.services.admissions_service import AdmissionsService
    return AdmissionsService(db_path)


@pytest.fixture
def document_hub_service(db_path):
    return DocumentHubService(db_path)


@pytest.fixture
def accessibility_service(db_path):
    return AccessibilityService(db_path)


@pytest.fixture
def attachments_service(db_path):
    return AttachmentService(db_path)
