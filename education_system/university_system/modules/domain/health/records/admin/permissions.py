from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.records.backup_export import bulk_import_records
from education_system.university_system.modules.domain.health.records.records.crud import add_health_record, view_health_records, update_health_record, delete_health_record
from education_system.university_system.modules.domain.health.records.clinical.conditions import manage_medical_conditions
from education_system.university_system.modules.domain.health.records.records.templates import health_record_templates


def setup_health_permissions(auth):
    """Set up health-specific permissions in the authentication system"""
    health_permissions = [
        'manage_health_records',
        'view_any_health_record',
        'view_own_health_record',
        'manage_health_appointments',
        'schedule_health_appointment',
        'view_own_appointments',
        'cancel_own_appointment',
        'manage_vaccinations',
        'view_own_vaccinations',
        'verify_vaccinations',
        'issue_health_advisories',
        'view_health_advisories',
        'view_health_resources',
        'update_insurance_info'
    ]

    # Add permissions to the authentication system
    for permission in health_permissions:
        if hasattr(auth, 'add_permission'):
            auth.add_permission(permission)



def manage_health_records_enhanced(auth):
    """Enhanced health records management with new features"""
    while True:
        print("\n===== Enhanced Health Records Management =====")
        print("1. Add Health Record")
        print("2. View Health Records")
        print("3. Update Health Record")
        print("4. Delete Health Record")
        print("5. Medical Conditions Management")
        print("6. Health Record Templates")
        print("7. Bulk Import Records")
        print("8. Return to Main Menu")

        choice = input("\nEnter your choice (1-8): ")

        if choice == '1':
            add_health_record(auth)
        elif choice == '2':
            view_health_records(auth)
        elif choice == '3':
            update_health_record(auth)
        elif choice == '4':
            delete_health_record(auth)
        elif choice == '5':
            manage_medical_conditions(auth)
        elif choice == '6':
            health_record_templates(auth)
        elif choice == '7':
            bulk_import_records(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")



