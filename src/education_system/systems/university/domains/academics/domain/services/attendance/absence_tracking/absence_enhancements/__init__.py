"""
Absence Tracker — 17 enhancement features, organised as service classes.

Service classes (one responsibility each):

    EnhancementSettings        small KV settings store
    ThemeService               #36 dark mode, #42 high contrast
    TreeUxService              #37 shortcuts, #38 filter bar, #39 sort,
                               #40 pagination, #42 a11y labels
    GeofenceService            #3  geofenced check-in
    FaceCheckinService         #4  facial-recognition kiosk
    RequestCategoryService     #11 request categories + routing
    PushQueueService           #21 mobile push notification queue
    ComplianceService          #30 HESA export, #31 UKVI engagement
    EvidenceService            #35 SHA-256 signature on evidence
    LmsSyncService             #46 LMS access grants
    AnomalyService             #50 anomaly detection (concurrency, proxy)
    ChatbotService             #49 "how many more absences can I take?"
    EnhancementTabBuilder      role-aware GUI sections + bootstrap

Public API kept stable for external callers (chatbot, REST routes,
absence_tracker.py): ``ensure_enhanced_schema``, ``chatbot_absence_quota``,
``bootstrap``, ``add_filter_bar``, ``Paginator``, ``list_categories``,
``record_geofenced_checkin``, ``facial_checkin``, ``queue_push``,
``drain_push_queue``, ``hesa_export``, ``ukvi_at_risk``,
``ukvi_log_event``, ``sign_evidence``, ``verify_evidence``,
``lms_sync_approved_requests``, ``anomaly_scan`` — each delegates to the
matching service class.

Logging is routed through ``infrastructure.logging.log_config`` so output
joins ``university_system/logs/app.log``. Every state-changing DB
operation guards ``sqlite3.Error`` with explicit ``rollback()``.
"""

from __future__ import annotations

from .log import logger

from .schema import (
    SCHEMA_SQL,
    SEED_CATEGORIES,
    ensure_enhanced_schema,
)

from .settings import (
    EnhancementSettings,
    get_setting,
    set_setting,
)

from .theme import (
    THEMES,
    ThemeService,
    apply_theme,
    cycle_theme,
)

from .tree_ux import (
    Paginator,
    TreeUxService,
    make_sortable,
    add_filter_bar,
    bind_shortcuts,
    add_a11y_labels,
    apply_ux,
)

from .checkin import (
    GeofenceService,
    record_geofenced_checkin,
    FaceCheckinService,
    register_kiosk,
    facial_checkin,
)

from .categories import (
    RequestCategoryService,
    list_categories,
    set_request_category,
    route_for_request,
)

from .push import (
    PushQueueService,
    queue_push,
    drain_push_queue,
)

from .compliance import (
    HESA_COLS,
    ComplianceService,
    hesa_export,
    ukvi_log_event,
    ukvi_at_risk,
)

from .evidence import (
    EvidenceService,
    sign_evidence,
    verify_evidence,
)

from .lms import (
    LmsSyncService,
    lms_on_absence,
    lms_sync_approved_requests,
)

from .anomaly import (
    AnomalyService,
    anomaly_scan,
)

from .chatbot import (
    ChatbotService,
    chatbot_absence_quota,
)

from .tabs import (
    _tree,
    EnhancementTabBuilder,
    _build_settings_section,
    _build_categories_section,
    _build_compliance_section,
    _build_integrations_section,
    _build_student_enh_section,
    _dashboard_shim,
    build_enhancement_tabs,
    bootstrap,
)

__all__ = [
    "logger",
    "SCHEMA_SQL",
    "SEED_CATEGORIES",
    "ensure_enhanced_schema",
    "EnhancementSettings",
    "get_setting",
    "set_setting",
    "THEMES",
    "ThemeService",
    "apply_theme",
    "cycle_theme",
    "Paginator",
    "TreeUxService",
    "make_sortable",
    "add_filter_bar",
    "bind_shortcuts",
    "add_a11y_labels",
    "apply_ux",
    "GeofenceService",
    "record_geofenced_checkin",
    "FaceCheckinService",
    "register_kiosk",
    "facial_checkin",
    "RequestCategoryService",
    "list_categories",
    "set_request_category",
    "route_for_request",
    "PushQueueService",
    "queue_push",
    "drain_push_queue",
    "HESA_COLS",
    "ComplianceService",
    "hesa_export",
    "ukvi_log_event",
    "ukvi_at_risk",
    "EvidenceService",
    "sign_evidence",
    "verify_evidence",
    "LmsSyncService",
    "lms_on_absence",
    "lms_sync_approved_requests",
    "AnomalyService",
    "anomaly_scan",
    "ChatbotService",
    "chatbot_absence_quota",
    "_tree",
    "EnhancementTabBuilder",
    "_build_settings_section",
    "_build_categories_section",
    "_build_compliance_section",
    "_build_integrations_section",
    "_build_student_enh_section",
    "_dashboard_shim",
    "build_enhancement_tabs",
    "bootstrap",
]
