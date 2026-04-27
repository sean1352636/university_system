"""Create production tables that exist in source CREATE statements but are
missing from the live university_system DB.

Driven by the schema audit report. Extracts the CREATE TABLE SQL literal
straight from each source file at the cited line and executes it against
the target DB with IF NOT EXISTS and foreign keys disabled.

Run:
    python -m education_system.university_system.scripts.create_missing_tables --dry-run
    python -m education_system.university_system.scripts.create_missing_tables --apply
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path("/home/seancatchpole989/education_system")
DEFAULT_DB = REPO_ROOT / "university_system/data/db_files/student_records.db"

# (table_name, source_file_relative_to_repo_root, line_number_of_CREATE)
# Curated from the schema audit report: only production tables that legitimately
# belong in student_records.db. Excludes: test fixtures, scratch tables, tables
# owned by other DBs (auth.db, tenants.db, webhooks.db, lms_integrations.db,
# per-domain .db files), and migration-helper temp tables (`*_new`, `*_old`,
# `__*_metadata`).
TABLE_SOURCES: list[tuple[str, str, int]] = [
    # Absence tracking enhancements
    ("absence_evidence_signatures", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 93),
    ("absence_push_queue", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 80),
    ("absence_request_categories", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 66),
    ("absence_settings", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 115),
    ("attendance_anomalies", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 99),
    ("attendance_kiosks", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 74),
    ("lms_access_grants", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 107),
    ("ukvi_engagement_events", "university_system/modules/domain/academics/services/attendance/absence_tracking/absence_enhancements.py", 87),
    ("abs_tracker_sms_queue", "university_system/modules/domain/academics/services/attendance/absence_tracking/admin_features.py", 1957),
    ("attendance_grade_penalties", "university_system/modules/domain/academics/services/attendance/absence_tracking/admin_features.py", 204),
    ("module_sessions", "university_system/modules/domain/academics/services/attendance/absence_tracking/admin_features.py", 2431),
    ("frequent_absence_alerts", "university_system/modules/domain/academics/services/attendance/absence_tracking/email_notifications.py", 305),
    ("frequent_absence_email_prefs", "university_system/modules/domain/academics/services/attendance/absence_tracking/email_notifications.py", 321),

    # AI detector (in-domain GUI tables)
    ("ai_activity_log", "university_system/modules/domain/academics/gui/ai_detector/model_security_view.py", 494),
    ("ai_alert_queue", "university_system/modules/domain/academics/gui/ai_detector/alerts_course_view.py", 243),
    ("ai_alert_settings", "university_system/modules/domain/academics/gui/ai_detector/alerts_course_view.py", 150),
    ("ai_assignment_profiles", "university_system/modules/domain/academics/gui/ai_detector/alerts_course_view.py", 523),
    ("ai_batch_jobs", "university_system/modules/domain/academics/gui/ai_detector/batch_processing_view.py", 302),
    ("ai_dean_escalations", "university_system/modules/domain/academics/gui/ai_detector/alerts_course_view.py", 341),
    ("ai_integration_config", "university_system/modules/domain/academics/gui/ai_detector/student_analytics_view.py", 139),
    ("ai_model_versions", "university_system/modules/domain/academics/gui/ai_detector/model_security_view.py", 211),
    ("ai_scheduled_jobs", "university_system/modules/domain/academics/gui/ai_detector/batch_processing_view.py", 435),
    ("ai_violation_records", "university_system/modules/domain/academics/gui/ai_detector/student_analytics_view.py", 297),
    ("ai_writing_fingerprints", "university_system/modules/domain/academics/gui/ai_detector/student_analytics_view.py", 503),

    # AI detector (infrastructure)
    ("ai_detector_academic_records", "university_system/infrastructure/ai/ai_detector/detector/integration_mixin.py", 295),
    ("ai_detector_activity_log", "university_system/infrastructure/ai/ai_detector/detector/audit_privacy_mixin.py", 36),
    ("ai_detector_alert_config", "university_system/infrastructure/ai/ai_detector/detector/alerts_mixin.py", 41),
    ("ai_detector_alerts", "university_system/infrastructure/ai/ai_detector/detector/alerts_mixin.py", 166),
    ("ai_detector_assignment_profiles", "university_system/infrastructure/ai/ai_detector/detector/course_management_mixin.py", 44),
    ("ai_detector_baselines", "university_system/infrastructure/ai/ai_detector/detector/course_management_mixin.py", 176),
    ("ai_detector_batch_jobs", "university_system/infrastructure/ai/ai_detector/detector/batch_operations_mixin.py", 308),
    ("ai_detector_email_alerts", "university_system/infrastructure/ai/ai_detector/detector/alerts_mixin.py", 114),
    ("ai_detector_escalations", "university_system/infrastructure/ai/ai_detector/detector/alerts_mixin.py", 318),
    ("ai_detector_model_rollbacks", "university_system/infrastructure/ai/ai_detector/detector/model_management_mixin.py", 418),
    ("ai_detector_model_versions", "university_system/infrastructure/ai/ai_detector/detector/model_management_mixin.py", 191),
    ("federated_learning", "university_system/infrastructure/ai/ai_detector/features/federated_learning.py", 69),
    ("style_fingerprints", "university_system/infrastructure/ai/ai_detector/detector/enhanced_detection_mixin.py", 252),
    ("student_review_flags", "university_system/infrastructure/ai/ai_detector/detector/student_management_mixin.py", 314),

    # Apprenticeships
    ("applications", "university_system/modules/domain/academics/apprenticeships/apprenticeship_system.py", 65),
    ("apprenticeships", "university_system/modules/domain/academics/apprenticeships/apprenticeship_system.py", 49),

    # Workflows / approvals
    ("approval_requests", "university_system/infrastructure/workflows/database.py", 85),
    ("workflow_audit_log", "university_system/infrastructure/workflows/database.py", 105),

    # Finance archive backup
    ("archive_metadata", "university_system/modules/domain/finance/gui/finance_reporting/archive_backup/archive_management.py", 213),
    ("archived_budget_records", "university_system/modules/domain/finance/gui/finance_reporting/archive_backup/archive_management.py", 202),
    ("archived_financial_aid", "university_system/modules/domain/finance/gui/finance_reporting/archive_backup/archive_management.py", 190),
    ("archived_payments", "university_system/modules/domain/finance/gui/finance_reporting/archive_backup/archive_management.py", 178),
    ("archived_transactions", "university_system/modules/domain/finance/gui/finance_reporting/archive_backup/archive_management.py", 165),
    ("financial_aid", "university_system/modules/domain/finance/gui/finance/db_manager.py", 404),
    ("financial_transactions", "university_system/modules/domain/finance/gui/finance/db_manager.py", 422),
    ("ml_predictions", "university_system/modules/domain/finance/reporting/financial_reports/db_setup.py", 46),
    ("system_performance", "university_system/modules/domain/finance/reporting/financial_reports/db_setup.py", 56),

    # Assignments
    ("assignment_drafts", "university_system/modules/domain/academics/services/assignments/assignments/crud.py", 468),
    ("attendance_grade_config", "university_system/modules/domain/academics/gui/attendance_grade/attendance_grade_gui.py", 37),

    # Student union — academic support
    ("academic_study_group_members", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 225),
    ("academic_study_groups", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 210),
    ("academic_workshop_registrations", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 771),
    ("academic_workshops", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 756),
    ("course_credit_registrations", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 1024),
    ("peer_tutoring_requests", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 452),
    ("peer_tutoring_sessions", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 440),
    ("shared_academic_resources", "university_system/modules/domain/student_affairs/gui/student_union_gui/academic/academic_support.py", 599),

    # Student union — green
    ("carbon_offsets", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 148),
    ("carbon_tracking", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 82),
    ("eco_suppliers", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 123),
    ("green_certifications", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 136),
    ("green_initiatives", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 68),
    ("green_transport_log", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 112),
    ("waste_reduction_log", "university_system/modules/domain/student_affairs/gui/student_union_gui/green/green_initiatives.py", 98),

    # Student union — student council
    ("sc_announcements", "university_system/modules/domain/student_affairs/student_union/student_council.py", 62),
    ("sc_candidates", "university_system/modules/domain/student_affairs/student_union/student_council.py", 70),
    ("sc_events", "university_system/modules/domain/student_affairs/student_union/student_council.py", 51),
    ("sc_members", "university_system/modules/domain/student_affairs/student_union/student_council.py", 42),
    ("sc_votes", "university_system/modules/domain/student_affairs/student_union/student_council.py", 78),

    # Student union — admin / elections
    ("club_memberships", "university_system/modules/domain/student_affairs/student_union/administration/student_union_core.py", 1352),
    ("election_nominations", "university_system/modules/domain/student_affairs/student_union/administration/student_union_core.py", 1651),
    ("elections", "university_system/modules/domain/student_affairs/student_union/administration/student_union_core.py", 1610),
    ("student_union_clubs", "university_system/modules/domain/student_affairs/student_union/administration/student_union_core.py", 1273),
    ("election_security_settings", "university_system/modules/domain/student_affairs/gui/student_union_gui/elections/election_compliance.py", 875),
    ("election_voting_config", "university_system/modules/domain/student_affairs/gui/student_union_gui/elections/election_voting_methods.py", 739),
    ("accessibility_feedback", "university_system/modules/domain/student_affairs/gui/student_union_gui/elections/election_accessibility.py", 201),
    ("union_voting_settings", "university_system/modules/domain/student_affairs/student_union/elections/election_gui.py", 139),
    ("configuration_audit", "university_system/modules/domain/student_affairs/student_union/services/voting.py", 699),

    # Student union — mentoring
    ("mentee_preferences", "university_system/modules/domain/student_affairs/student_union/services/mentoring_matching/matching_service.py", 96),
    ("mentor_match_recommendations", "university_system/modules/domain/student_affairs/student_union/services/mentoring_matching/matching_service.py", 105),
    ("mentor_profiles", "university_system/modules/domain/student_affairs/student_union/services/mentoring_matching/matching_service.py", 85),
    ("mentoring_outcomes", "university_system/modules/domain/student_affairs/student_union/services/mentoring_matching/matching_service.py", 114),

    # Student union — events / book clubs / wellness / support
    ("book_club_books", "university_system/modules/domain/student_affairs/gui/student_union_gui/book_clubs/book_clubs.py", 368),
    ("book_club_schedules", "university_system/modules/domain/student_affairs/gui/student_union_gui/book_clubs/book_clubs.py", 481),
    ("event_expenses", "university_system/modules/domain/student_affairs/gui/student_union_gui/events/event_finance.py", 865),
    ("event_income", "university_system/modules/domain/student_affairs/gui/student_union_gui/events/event_finance.py", 731),
    ("event_ticket_types", "university_system/modules/domain/student_affairs/gui/student_union_gui/events/event_ticketing.py", 272),
    ("recurring_event_series", "university_system/modules/domain/student_affairs/gui/student_union_gui/events/event_recurring.py", 355),
    ("expense_requests", "university_system/modules/domain/student_affairs/gui/student_union_gui/finance/expenses.py", 196),
    ("peer_matches", "university_system/modules/domain/student_affairs/gui/student_union_gui/support/peer_support.py", 282),
    ("peer_messages", "university_system/modules/domain/student_affairs/gui/student_union_gui/support/peer_support.py", 296),
    ("safety_plans", "university_system/modules/domain/student_affairs/gui/student_union_gui/support/wellness.py", 771),
    ("wellness_resources", "university_system/modules/domain/student_affairs/gui/student_union_gui/support/wellness.py", 122),
    ("workshop_proposals", "university_system/modules/domain/student_affairs/gui/student_union_gui/knowledge/knowledge_sharing.py", 233),
    ("student_trips", "university_system/modules/domain/student_affairs/gui/student_union_gui/core/utilities.py", 1083),

    # Student affairs — equality / safeguarding
    ("safeguarding_referrals", "university_system/modules/domain/student_affairs/equality_diversity/integrations.py", 463),
    ("submissions", "university_system/modules/domain/student_affairs/safeguarding/safeguarding_system.py", 177),

    # Wellbeing
    ("wellbeing_checkins", "university_system/modules/domain/student_affairs/student_wellbeing/services/wellbeing_service.py", 51),

    # Academic calendar
    ("calendar_audit_log", "university_system/modules/domain/academics/gui/academic_calendar/main_gui.py", 338),
    ("calendar_permissions", "university_system/modules/domain/academics/gui/academic_calendar/main_gui.py", 325),
    ("event_notifications", "university_system/modules/domain/academics/gui/academic_calendar/main_gui.py", 310),
    ("event_templates", "university_system/modules/domain/academics/services/academic_calendar/batch.py", 170),
    ("workflow_events", "university_system/modules/domain/academics/gui/academic_calendar/managers.py", 234),
    ("calendar_sync_settings", "university_system/modules/domain/academics/gui/attendance_tracker/misc_windows.py", 734),
    ("notification_settings", "university_system/modules/domain/academics/gui/attendance_tracker/notifications_windows.py", 1230),
    ("parent_notification_settings", "university_system/modules/domain/academics/gui/attendance_tracker/notifications_windows.py", 797),

    # Course evaluation
    ("eval_form_answers", "university_system/modules/domain/academics/services/evaluation/course_evaluation_core.py", 236),
    ("eval_form_questions", "university_system/modules/domain/academics/services/evaluation/course_evaluation_core.py", 226),
    ("eval_form_responses", "university_system/modules/domain/academics/services/evaluation/course_evaluation_core.py", 232),
    ("evaluation_forms", "university_system/modules/domain/academics/services/evaluation/course_evaluation_core.py", 220),
    ("evaluations", "university_system/modules/domain/academics/course_evaluation/course_evaluation_system.py", 32),
    ("lecturers", "university_system/modules/domain/academics/course_evaluation/lecturer_evaluation.py", 45),

    # Library
    ("library_analytics", "university_system/modules/domain/academics/services/library/settings.py", 547),
    ("library_cards", "university_system/modules/domain/academics/gui/library/barcode_cards.py", 533),
    ("library_events", "university_system/modules/domain/academics/gui/library/maintenance.py", 1041),
    ("library_payments", "university_system/modules/domain/academics/services/library/settings.py", 645),

    # Module scheduling
    ("system_logs", "university_system/modules/domain/academics/gui/module_scheduling/notifications.py", 377),

    # Grading interventions
    ("intervention_recommendations", "university_system/modules/domain/academics/grading/interventions.py", 200),

    # Placements
    ("hours_log", "university_system/modules/domain/academics/placements/placement_tracker.py", 50),

    # Parent portal
    ("parent_issues", "university_system/modules/domain/academics/services/parent_portal/quick_actions.py", 257),
    ("transport_issues", "university_system/modules/domain/academics/gui/parent_portal/transport.py", 496),

    # Auth integrations
    ("trip_registrations", "university_system/infrastructure/auth/integrations/module_permissions.py", 141),

    # Risk / legal
    ("risks", "university_system/modules/domain/legal/risk_management/university_risk_management.py", 123),

    # Research
    ("grant_tracker_alerts", "university_system/modules/domain/research/services/research_grants_core.py", 206),
    ("grant_tracker_apps", "university_system/modules/domain/research/services/research_grants_core.py", 189),
    ("grant_tracker_budget", "university_system/modules/domain/research/services/research_grants_core.py", 201),
    ("grant_tracker_milestones", "university_system/modules/domain/research/services/research_grants_core.py", 196),
    ("irb_applications", "university_system/modules/domain/research/gui/research_grants_gui.py", 1667),

    # Commerce — restaurant management (production paths only)
    ("backup_log", "university_system/modules/domain/commerce/gui/restaurant_management_gui/settings/backup_settings.py", 520),
    ("card_transactions", "university_system/modules/domain/commerce/gui/restaurant_management_gui/orders/payments.py", 697),
    ("cash_transactions", "university_system/modules/domain/commerce/gui/restaurant_management_gui/orders/payments.py", 600),
    ("customer_feedback", "university_system/modules/domain/commerce/gui/restaurant_management_gui/customers/feedback.py", 88),
    ("inventory_transactions", "university_system/modules/domain/commerce/gui/restaurant_management_gui/inventory/inventory_management.py", 290),
    ("loyalty_bonus_points", "university_system/modules/domain/commerce/gui/restaurant_management_gui/customers/loyalty.py", 665),
    ("loyalty_tier_promotions", "university_system/modules/domain/commerce/gui/restaurant_management_gui/customers/loyalty.py", 433),
    ("order_discounts", "university_system/modules/domain/commerce/gui/restaurant_management_gui/orders/payments.py", 497),
    ("qr_codes", "university_system/modules/domain/commerce/gui/restaurant_management_gui/tables/qr_codes.py", 144),
    ("qr_scans", "university_system/modules/domain/commerce/gui/restaurant_management_gui/tables/qr_codes.py", 363),
    ("restaurant_schedules", "university_system/modules/domain/commerce/gui/restaurant_management_gui/staff/staff_management.py", 192),
    ("restaurant_shift_swaps", "university_system/modules/domain/commerce/gui/restaurant_management_gui/staff/shifts_gui.py", 65),
    ("restaurant_shifts", "university_system/modules/domain/commerce/gui/restaurant_management_gui/staff/shifts_gui.py", 46),
    ("staff_performance", "university_system/modules/domain/commerce/gui/restaurant_management_gui/staff/performance.py", 104),
    ("student_meal_plans", "university_system/modules/domain/commerce/gui/restaurant_management_gui/orders/payments.py", 795),
    ("restaurant_budgets", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 306),
    ("restaurant_customer_segments", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 422),
    ("restaurant_food_safety_checks", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 447),
    ("restaurant_marketing_campaigns", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 403),
    ("restaurant_mobile_orders", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 532),
    ("restaurant_notifications", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 503),
    ("restaurant_offer_usage", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 356),
    ("restaurant_special_offers", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 336),
    ("restaurant_temperature_logs", "university_system/modules/domain/commerce/services/restaurant/operations/connection.py", 434),

    # Commerce — services CLI (production)
    ("butcher_inventory_adjustments", "university_system/modules/services/cli/butcher_cli.py", 40),
    ("butcher_product_expiry", "university_system/modules/services/cli/butcher_cli.py", 67),
    ("butcher_stock_alerts", "university_system/modules/services/cli/butcher_cli.py", 54),
    ("equipment_inventory", "university_system/modules/services/cli/equipment_rental_cli.py", 41),
    ("musicshop_wishlist", "university_system/modules/services/cli/music_shop_cli.py", 90),
    ("nailbar_payments", "university_system/modules/services/cli/nailbar_cli.py", 102),
    ("police_case_counter", "university_system/modules/services/cli/police_station_cli.py", 179),

    # Commerce — cinema (CLI production)
    ("cinema_exclusive_screenings", "university_system/modules/services/cli/cinema_cli/db.py", 134),
    ("cinema_memberships", "university_system/modules/services/cli/cinema_cli/db.py", 102),
    ("cinema_movies", "university_system/modules/services/cli/cinema_cli/db.py", 18),
    ("cinema_points_transactions", "university_system/modules/services/cli/cinema_cli/db.py", 120),
    ("cinema_screenings", "university_system/modules/services/cli/cinema_cli/db.py", 38),
    ("cinema_seats", "university_system/modules/services/cli/cinema_cli/db.py", 148),
    ("cinema_snacks_orders", "university_system/modules/services/cli/cinema_cli/db.py", 85),

    # Health (university health portal — uses student_records.db)
    ("failed_logins", "university_system/modules/domain/health/services/health_portal.py", 1678),
    ("templates", "university_system/modules/domain/health/services/health_db_backup.py", 76),

    # Communication / notifications (in-app + push + sms — uses central DB)
    ("notification_actions", "university_system/infrastructure/communication/in_app_notifications.py", 42),
    ("notification_type_preferences", "university_system/infrastructure/communication/in_app_notifications.py", 72),
    ("push_delivery_log", "university_system/infrastructure/communication/push_notifications.py", 65),
    ("push_subscriptions", "university_system/infrastructure/communication/push_notifications.py", 50),
    ("sms_log", "university_system/infrastructure/communication/sms_service.py", 83),
    ("sms_templates", "university_system/modules/shared/gui/email/email_gui/sms_tab.py", 600),
    ("delivery_logs", "university_system/modules/shared/services/communication/schema.py", 130),
    ("message_recipients", "university_system/modules/shared/services/communication/schema.py", 23),
    ("notification_subscriptions", "university_system/modules/shared/services/communication/schema.py", 158),

    # Search / analytics
    ("popular_searches", "university_system/infrastructure/search/autocomplete.py", 50),
    ("search_clicks", "university_system/infrastructure/search/analytics.py", 51),
    ("search_metrics", "university_system/infrastructure/search/analytics.py", 38),
    ("dashboard_permissions", "university_system/infrastructure/analytics/dashboard_service.py", 87),
    ("dashboards", "university_system/infrastructure/analytics/dashboard_service.py", 53),
    ("report_history", "university_system/infrastructure/analytics/report_generator.py", 69),
    ("duplicate_candidates", "university_system/modules/shared/services/analytics/advanced_search/db.py", 192),

    # Migrations — security/account-linking/SSO/webauthn (target university DB)
    ("account_link_requests", "university_system/infrastructure/database/migrations/add_account_linking.py", 45),
    ("active_role_switches", "university_system/infrastructure/database/migrations/add_account_linking.py", 63),
    ("linked_accounts", "university_system/infrastructure/database/migrations/add_account_linking.py", 29),
    ("api_request_log", "university_system/infrastructure/database/migrations/add_security_features.py", 185),
    ("dependency_vulnerabilities", "university_system/infrastructure/database/migrations/add_security_features.py", 317),
    ("document_access_control", "university_system/infrastructure/database/migrations/add_security_features.py", 248),
    ("delegated_access", "university_system/infrastructure/database/migrations/add_delegated_access.py", 28),
    ("delegated_access_audit", "university_system/infrastructure/database/migrations/add_delegated_access.py", 67),
    ("delegated_access_requests", "university_system/infrastructure/database/migrations/add_delegated_access.py", 47),
    ("sso_identities", "university_system/infrastructure/database/migrations/add_sso_system.py", 43),
    ("sso_providers", "university_system/infrastructure/database/migrations/add_sso_system.py", 29),
    ("sso_sessions", "university_system/infrastructure/database/migrations/add_sso_system.py", 60),
    ("webauthn_challenges", "university_system/infrastructure/database/migrations/add_webauthn.py", 47),
    ("webauthn_credentials", "university_system/infrastructure/database/migrations/add_webauthn.py", 28),
    ("remember_me_tokens", "university_system/infrastructure/security/remember_me.py", 355),

    # Schema files (admin/support, new features)
    ("certificates", "university_system/infrastructure/database/schemas/admin_support_schemas.py", 2317),
    ("transcript_requests", "university_system/infrastructure/database/schemas/admin_support_schemas.py", 2333),
    ("counselling_sessions", "university_system/infrastructure/database/schemas/new_features_schemas.py", 97),
    ("student_payments", "university_system/infrastructure/database/schemas/new_features_schemas.py", 53),
    ("submission_grades", "university_system/infrastructure/database/schemas/new_features_schemas.py", 31),

    # Document manager / batch ops
    ("workflow_template_steps", "university_system/modules/shared/utils/document_manager/workflows.py", 236),
    ("workflow_templates", "university_system/modules/shared/utils/document_manager/workflows.py", 223),
    ("external_api_config", "university_system/modules/shared/gui/batch_operations/mixins/external_integration.py", 174),
    ("external_db_config", "university_system/modules/shared/gui/batch_operations/mixins/external_integration.py", 109),
    ("file_share_config", "university_system/modules/shared/gui/batch_operations/mixins/external_integration.py", 228),
    ("scheduled_imports", "university_system/modules/shared/gui/batch_operations/mixins/scheduling.py", 71),

    # Migration helpers (live in same DB)
    ("finance_refunds", "university_system/scripts/fix_finance_refunds_table.py", 35),
    ("library_fine_payments", "university_system/scripts/init_library_fine_payments.py", 31),
]

# Tables that map to the table_sources index entry but use a different table
# name in the live DB. (table_name -> rename for the CREATE block.) None for now.
TABLE_RENAMES: dict[str, str] = {}

CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(\w+)[\"`\]]?\s*\(",
    re.IGNORECASE,
)


@dataclass
class ApplyResult:
    created: list[str] = field(default_factory=list)
    already_exists: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _extract_create_sql(file_path: Path, line_no: int, expected_table: str) -> str | None:
    """Return the CREATE TABLE ... ( ... ); block starting at or near line_no.

    The CREATE keyword may sit on `line_no` or a couple lines later (some
    sources have leading f-string prefix on the previous line). We scan from
    `line_no` forward until we find the matching closing paren of the column
    list, then extend to the trailing ');'. Triple-quoted f-string wrappers
    are tolerated because we only return the inner SQL substring.
    """
    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    # Build offset table for line -> char index.
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    if line_no < 1 or line_no > len(lines):
        return None
    # Search window: from the cited line, look up to 2 lines back (for prefix
    # lines like `cursor.execute("""`) and forward a few thousand chars.
    start_line = max(1, line_no - 2)
    start = offsets[start_line - 1]
    snippet = text[start : start + 8000]
    m = CREATE_RE.search(snippet)
    if not m:
        return None
    found_table = m.group(1)
    if found_table.lower() != expected_table.lower():
        # Not the right CREATE — skip.
        return None
    # Walk parens from the opening paren after the match.
    open_idx = snippet.index("(", m.end() - 1)
    depth = 0
    i = open_idx
    in_str: str | None = None
    while i < len(snippet):
        ch = snippet[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    return snippet[m.start() : end]
        i += 1
    return None


def _force_if_not_exists(sql: str) -> str:
    return re.sub(
        r"CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)",
        "CREATE TABLE IF NOT EXISTS ",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )


def create_missing_tables(
    db_path: Path = DEFAULT_DB,
    sources: Iterable[tuple[str, str, int]] = TABLE_SOURCES,
    dry_run: bool = True,
) -> ApplyResult:
    """Create missing tables in `db_path`.

    Strategy: open one connection with foreign_keys=OFF, iterate every
    (table, file, line). If the table already exists, skip. Otherwise
    extract its CREATE TABLE block from the source file, force IF NOT
    EXISTS, and execute. On dry_run, only report what would happen.
    """
    result = ApplyResult()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table, rel_path, line_no in sources:
            if table in existing:
                result.already_exists.append(table)
                continue
            file_path = REPO_ROOT / rel_path
            if not file_path.exists():
                result.skipped.append((table, f"source not found: {rel_path}"))
                continue
            sql = _extract_create_sql(file_path, line_no, table)
            if sql is None:
                result.skipped.append(
                    (table, f"could not extract CREATE block at {rel_path}:{line_no}")
                )
                continue
            sql = _force_if_not_exists(sql)
            if dry_run:
                result.created.append(table)
                continue
            try:
                conn.execute(sql)
                conn.commit()
                result.created.append(table)
            except sqlite3.Error as exc:
                result.failed.append((table, f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()
    return result


def _print_report(r: ApplyResult, dry_run: bool) -> None:
    verb = "would create" if dry_run else "created"
    print(f"=== {verb}: {len(r.created)} ===")
    for t in r.created:
        print(f"  + {t}")
    if r.already_exists:
        print(f"\n=== already exists: {len(r.already_exists)} ===")
        for t in r.already_exists:
            print(f"  = {t}")
    if r.skipped:
        print(f"\n=== skipped: {len(r.skipped)} ===")
        for t, reason in r.skipped:
            print(f"  ? {t}: {reason}")
    if r.failed:
        print(f"\n=== failed: {len(r.failed)} ===")
        for t, reason in r.failed:
            print(f"  ! {t}: {reason}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    args = p.parse_args()
    dry_run = not args.apply
    r = create_missing_tables(db_path=args.db, dry_run=dry_run)
    _print_report(r, dry_run=dry_run)


if __name__ == "__main__":
    main()
