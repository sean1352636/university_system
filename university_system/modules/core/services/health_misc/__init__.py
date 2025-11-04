"""Re-exported health portal helpers split from the legacy miscellaneous module."""

from __future__ import annotations

from university_system.modules.core.services.health_misc.health_context import (
    backup_before_operation,
    cipher_suite,
    get_connection,
    logging,
)
from university_system.modules.core.services.health_misc.health_db_backup import _sqlite_main_db_path, create_sqlite_backup, ensure_templates_schema
from university_system.modules.core.services.health_misc.audit import (
    analyze_data_access_patterns,
    log_audit_event,
    performance_improvement,
    view_failed_logins,
)
from university_system.modules.core.services.health_misc.security import (
    decrypt_sensitive_data,
    encrypt_sensitive_data,
    truthy,
    validate_csv_format,
)
from university_system.modules.core.services.health_misc.operations import (
    block_time_slots,
    external_system_connections,
    patient_queue,
    pending_tasks,
    quick_patient_lookup,
)
from university_system.modules.core.services.health_misc.dashboards import critical_alerts_dashboard, generate_custom_report
from university_system.modules.core.services.health_misc.reports import (
    generate_appointment_schedule_report,
    generate_health_condition_analysis,
    generate_provider_performance_report,
    generate_student_health_summary,
    generate_vaccination_status_report,
)
from university_system.modules.core.services.health_misc.templates import (
    create_new_template,
    edit_template,
    import_templates,
    import_templates_from_path,
    shared_templates,
    template_usage_statistics,
    use_existing_template,
)
from university_system.modules.core.services.health_misc.directory import emergency_information, specialist_directory
from university_system.modules.core.services.health_misc.contacts import (
    add_emergency_contact,
    delete_emergency_contact,
    get_user_student_id,
    manage_contact_hierarchy,
    manage_emergency_contacts,
    update_emergency_contact,
    view_emergency_contacts,
)
from university_system.modules.core.services.health_misc.surveillance import (
    analyze_disease_trends,
    conduct_contact_tracing,
    disease_surveillance_system,
    generate_disease_surveillance_report,
    investigate_outbreak,
    report_disease_case,
    view_disease_cases,
)
from university_system.modules.core.services.health_misc.allergies import (
    check_basic_interactions,
    check_drug_interactions,
    critical_values_alert,
    manage_allergies,
    view_allergies,
)
from university_system.modules.core.services.health_misc.medication import manage_refill_reminders, track_medication_adherence
from university_system.modules.core.services.health_misc.vitals import (
    calculate_bmi,
    check_vital_signs_alerts,
    manage_vital_signs,
    record_vital_signs,
    view_vital_signs,
    view_vital_signs_trends,
)

__all__ = [
    "_sqlite_main_db_path",
    "add_emergency_contact",
    "analyze_data_access_patterns",
    "analyze_disease_trends",
    "backup_before_operation",
    "block_time_slots",
    "calculate_bmi",
    "check_basic_interactions",
    "check_drug_interactions",
    "check_vital_signs_alerts",
    "cipher_suite",
    "conduct_contact_tracing",
    "create_new_template",
    "create_sqlite_backup",
    "critical_alerts_dashboard",
    "critical_values_alert",
    "decrypt_sensitive_data",
    "delete_emergency_contact",
    "disease_surveillance_system",
    "edit_template",
    "emergency_information",
    "encrypt_sensitive_data",
    "ensure_templates_schema",
    "external_system_connections",
    "generate_appointment_schedule_report",
    "generate_custom_report",
    "generate_disease_surveillance_report",
    "generate_health_condition_analysis",
    "generate_provider_performance_report",
    "generate_student_health_summary",
    "generate_vaccination_status_report",
    "get_connection",
    "get_user_student_id",
    "import_templates",
    "import_templates_from_path",
    "investigate_outbreak",
    "log_audit_event",
    "manage_allergies",
    "manage_contact_hierarchy",
    "manage_emergency_contacts",
    "manage_refill_reminders",
    "manage_vital_signs",
    "patient_queue",
    "pending_tasks",
    "performance_improvement",
    "quick_patient_lookup",
    "record_vital_signs",
    "report_disease_case",
    "shared_templates",
    "specialist_directory",
    "template_usage_statistics",
    "track_medication_adherence",
    "truthy",
    "update_emergency_contact",
    "use_existing_template",
    "validate_csv_format",
    "view_allergies",
    "view_disease_cases",
    "view_emergency_contacts",
    "view_failed_logins",
    "view_vital_signs",
    "view_vital_signs_trends",
]
