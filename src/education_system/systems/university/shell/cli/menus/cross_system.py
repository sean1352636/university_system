"""Component extracted from the legacy menu router."""
from __future__ import annotations

_CROSS_SYSTEM_MODULES = {
    "cross_analytics": ("education_system.platform.features.analytics.analytics_cli", "Analytics Dashboard"),
    "cross_outcomes": ("education_system.platform.outcomes.outcomes_cli", "Outcome Tracking"),
    "cross_predictive": ("education_system.platform.predictive.predictive_cli", "Predictive Alerts"),
    "cross_bulk_transfer": ("education_system.platform.bulk_transfer.bulk_transfer_cli", "Bulk Transfer"),
    "cross_transfer_docs": ("education_system.platform.transfer_docs.transfer_docs_cli", "Transfer Documents"),
    "cross_reverse_lookup": ("education_system.platform.reverse_lookup.reverse_lookup_cli", "Reverse Lookup"),
    "cross_parent_continuity": ("education_system.platform.parent_continuity.parent_cli", "Parent Continuity"),
    "cross_calendar": ("education_system.platform.features.calendar.calendar_cli", "Cross-System Calendar"),
    "cross_messaging": ("education_system.platform.features.messaging.cross_system_cli", "Inter-System Messaging"),
    "cross_admin_portal": ("education_system.platform.delivery.portals.admin.admin_cli", "Central Admin Portal"),
    "cross_gdpr": ("education_system.platform.governance.gdpr.gdpr_cli", "GDPR Compliance"),
    "cross_documents": ("education_system.platform.features.documents.document_cli", "Shared Documents"),
    "cross_student_portal": ("education_system.platform.delivery.portals.student.portal_cli", "Student Self-Service"),
    "cross_transcript": ("education_system.platform.features.transcript.transcript_cli", "Digital Transcript"),
    "cross_apprenticeship": ("education_system.platform.cross_system.apprenticeship_applications_cli", "Apprenticeship Progression"),
}

def _handle_cross_system_tool(option, auth):
    """Lazily import and run a cross-system shared CLI module."""
    if option not in _CROSS_SYSTEM_MODULES:
        print(f"\nUnknown cross-system tool: {option}")
        input("Press Enter to continue...")
        return

    module_path, label = _CROSS_SYSTEM_MODULES[option]
    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.run(db_path=None, auth=auth)
    except ImportError:
        print(f"\n  {label} module is not available.")
        input("Press Enter to continue...")
    except Exception as e:
        print(f"\n  Error running {label}: {e}")
        input("Press Enter to continue...")
