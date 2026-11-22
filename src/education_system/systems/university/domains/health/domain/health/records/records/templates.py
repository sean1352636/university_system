import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import (
    create_new_template, edit_template, use_existing_template,
    import_templates, template_usage_statistics, shared_templates,
)
from education_system.systems.university.domains.health.domain.health.records.backup_export import bulk_import_records


def health_record_templates(auth):
    """Health record templates for common conditions"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to use record templates.")
        return

    # One template store (services/templates): the built-in templates and
    # the saved ones, and using one creates the health record.
    use_existing_template(auth)


def template_validation(auth):
    """Basic validation for record templates (safe no-op if table missing)."""
    try:
        from education_system.systems.university.domains.health.domain.health.services import ensure_templates_schema
        ensure_templates_schema()

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name, COALESCE(category, 'Uncategorized') FROM templates LIMIT 20")
        rows = c.fetchall()
        if rows:
            print("\nTemplate Validation:")
            for name, category in rows:
                print(f"- {name} [{category}]")
        else:
            print("No templates found; nothing to validate.")
    except Exception as e:
        print(f"Template validation skipped: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)



def template_categories(auth):
    """List distinct template categories (safe if table absent)."""
    try:
        from education_system.systems.university.domains.health.domain.health.services import ensure_templates_schema
        ensure_templates_schema()

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT COALESCE(category, 'Uncategorized') FROM templates ORDER BY 1")
        cats = [row[0] for row in c.fetchall()]
        if cats:
            print("\nTemplate Categories:")
            for i, cat in enumerate(cats, 1):
                print(f"{i}. {cat}")
        else:
            print("No template categories found.")
    except Exception as e:
        print(f"Template categories unavailable: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)



def enhanced_health_record_templates(auth):
    """Enhanced health record template system"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage record templates.")
        return

    while True:
        print("\n===== Health Record Templates =====")
        print("1. Use Existing Template")
        print("2. Create New Template")
        print("3. Edit Template")
        print("4. Template Categories")
        print("5. Import Templates")
        print("6. Template Usage Statistics")
        print("7. Shared Templates")
        print("8. Template Validation")
        print("9. Return to Main Menu")

        choice = input("\nEnter your choice (1-9): ")

        if choice == '1':
            use_existing_template(auth)
        elif choice == '2':
            create_new_template(auth)
        elif choice == '3':
            edit_template(auth)
        elif choice == '4':
            template_categories(auth)
        elif choice == '5':
            import_templates(auth)
        elif choice == '6':
            template_usage_statistics(auth)
        elif choice == '7':
            from education_system.systems.university.domains.health.domain.health.records.backup_export import bulk_import_records
            bulk_import_records(auth)
        elif choice == '8':
            template_validation(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")



