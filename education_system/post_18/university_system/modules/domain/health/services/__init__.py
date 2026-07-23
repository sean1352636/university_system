"""
Health Services Module - Re-exports for backward compatibility

This module re-exports functions from the refactored health services submodules
to maintain backward compatibility with existing imports.
"""

# Operations functions
from education_system.post_18.university_system.modules.domain.health.services.operations import (
    block_time_slots,
    patient_queue,
    pending_tasks,
    quick_patient_lookup,
    external_system_connections,
)

# Dashboard functions
from education_system.post_18.university_system.modules.domain.health.services.dashboards import (
    critical_alerts_dashboard,
    generate_custom_report,
)

# Template functions
from education_system.post_18.university_system.modules.domain.health.services.templates import (
    use_existing_template,
    create_new_template,
    template_usage_statistics,
    edit_template,
    import_templates,
    import_templates_from_path,
    shared_templates,
)

# Directory functions
from education_system.post_18.university_system.modules.domain.health.services.directory import (
    specialist_directory,
    emergency_information,
)

# Contact functions
from education_system.post_18.university_system.modules.domain.health.services.contacts import (
    get_user_student_id,
    update_emergency_contact,
    delete_emergency_contact,
    manage_contact_hierarchy,
    manage_emergency_contacts,
    add_emergency_contact,
    view_emergency_contacts,
)

# Audit functions
from education_system.post_18.university_system.modules.domain.health.services.audit import (
    log_audit_event,
    performance_improvement,
    view_failed_logins,
    analyze_data_access_patterns,
)

# Surveillance functions
from education_system.post_18.university_system.modules.domain.health.services.surveillance import (
    generate_disease_surveillance_report,
    conduct_contact_tracing,
    investigate_outbreak,
    analyze_disease_trends,
    disease_surveillance_system,
    report_disease_case,
    view_disease_cases,
)

# Allergy management functions
from education_system.post_18.university_system.modules.domain.health.services.allergies import (
    critical_values_alert,
    manage_allergies,
    view_allergies,
    check_drug_interactions,
    check_basic_interactions,
)

# Medication functions
from education_system.post_18.university_system.modules.domain.health.services.medication import (
    track_medication_adherence,
    manage_refill_reminders,
)

# Vital signs functions
from education_system.post_18.university_system.modules.domain.health.services.vitals import (
    manage_vital_signs,
    record_vital_signs,
    check_vital_signs_alerts,
    view_vital_signs,
    view_vital_signs_trends,
    calculate_bmi,
)

# Database backup functions
from education_system.post_18.university_system.modules.domain.health.services.health_db_backup import (
    create_sqlite_backup,
    ensure_templates_schema,
    _sqlite_main_db_path,
)

# Security functions
from education_system.post_18.university_system.modules.domain.health.services.security import (
    validate_csv_format,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    truthy,
)

# Context (encryption)
from education_system.post_18.university_system.modules.domain.health.services.health_context import (
    cipher_suite,
)

# Report functions
from education_system.post_18.university_system.modules.domain.health.services.reports import (
    generate_student_health_summary,
    generate_vaccination_status_report,
    generate_appointment_schedule_report,
    generate_health_condition_analysis,
    generate_provider_performance_report,
)

# Backup utility
try:
    from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
except ImportError:
    import logging as _logging
    def backup_before_operation(operation_type):
        _logging.info(f"Backup requested for {operation_type} but backup module not available")

# Database connection (re-export from infrastructure)
from education_system.post_18.university_system.infrastructure.database.db import get_connection

__all__ = [
    # Operations
    'block_time_slots',
    'patient_queue',
    'pending_tasks',
    'quick_patient_lookup',
    'external_system_connections',

    # Dashboards
    'critical_alerts_dashboard',
    'generate_custom_report',

    # Templates
    'use_existing_template',
    'create_new_template',
    'template_usage_statistics',
    'edit_template',
    'import_templates',
    'import_templates_from_path',
    'shared_templates',

    # Directory
    'specialist_directory',
    'emergency_information',

    # Contacts
    'get_user_student_id',
    'update_emergency_contact',
    'delete_emergency_contact',
    'manage_contact_hierarchy',
    'manage_emergency_contacts',
    'add_emergency_contact',
    'view_emergency_contacts',

    # Audit
    'log_audit_event',
    'performance_improvement',
    'view_failed_logins',
    'analyze_data_access_patterns',

    # Surveillance
    'generate_disease_surveillance_report',
    'conduct_contact_tracing',
    'investigate_outbreak',
    'analyze_disease_trends',
    'disease_surveillance_system',
    'report_disease_case',
    'view_disease_cases',

    # Allergies
    'critical_values_alert',
    'manage_allergies',
    'view_allergies',
    'check_drug_interactions',
    'check_basic_interactions',

    # Medication
    'track_medication_adherence',
    'manage_refill_reminders',

    # Vital Signs
    'manage_vital_signs',
    'record_vital_signs',
    'check_vital_signs_alerts',
    'view_vital_signs',
    'view_vital_signs_trends',
    'calculate_bmi',

    # Database
    'create_sqlite_backup',
    'ensure_templates_schema',
    'validate_csv_format',
    'get_connection',
]
