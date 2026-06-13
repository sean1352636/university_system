"""AdminServices container — aggregates all nine domain services."""
from __future__ import annotations

from dataclasses import dataclass

from ..context import AdminContext
from ..ui_dialogs import ModulePicker, StudentPicker
from .attendance_data import AttendanceDataService
from .bulk_ops import BulkOperationsService
from .diagnostics import DiagnosticsService
from .integration import IntegrationService
from .notification import NotificationService
from .policy import PolicyService
from .reporting import ReportingService
from .request_workflow import RequestWorkflowService
from .security_audit import SecurityAuditService


@dataclass
class AdminServices:
    """Aggregates every service the Admin Tools tab needs."""
    data: AttendanceDataService
    requests: RequestWorkflowService
    policy: PolicyService
    reporting: ReportingService
    notifications: NotificationService
    integrations: IntegrationService
    bulk: BulkOperationsService
    security: SecurityAuditService
    diagnostics: DiagnosticsService

    @classmethod
    def for_context(cls, ctx: AdminContext) -> "AdminServices":
        student_picker = StudentPicker(ctx)
        module_picker = ModulePicker(ctx)
        return cls(
            data          = AttendanceDataService(ctx, module_picker),
            requests      = RequestWorkflowService(ctx, module_picker),
            policy        = PolicyService(ctx, module_picker),
            reporting     = ReportingService(ctx),
            notifications = NotificationService(ctx, student_picker,
                                                module_picker),
            integrations  = IntegrationService(ctx, student_picker,
                                                module_picker),
            bulk          = BulkOperationsService(ctx, student_picker,
                                                  module_picker),
            security      = SecurityAuditService(ctx, student_picker),
            diagnostics   = DiagnosticsService(ctx),
        )

