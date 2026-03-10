# Backward-compatible re-exports: all public names previously available from
# ``university_system.modules.domain.housing.services.accommodation`` remain
# importable from this package.

# -- shared constants & helpers used by external callers --
from education_system.university_system.modules.domain.housing.services.accommodation._common import (
    DB_PATH,
    NOTIFICATION_THRESHOLD_DAYS,
    TEMPLATES_TABLE,
    ACCOMMODATION_LOG_PATH,
    UPLOADS_DIR,
    get_current_user,
    backup_before_operation,
)

# -- auth / audit --
from education_system.university_system.modules.domain.housing.services.accommodation.audit import (
    auth,
    set_auth,
    log_action,
)

# -- database / schema --
from education_system.university_system.modules.domain.housing.services.accommodation.db import (
    init_accommodation_db,
    migrate_audit_log_schema,
    fix_accommodation_db_schema,
    verify_database_schema,
)

# -- validation helpers --
from education_system.university_system.modules.domain.housing.services.accommodation.validation import (
    validate_date,
    check_conflict,
    get_accommodation_types,
    validate_student_id,
)

# -- CRUD operations --
from education_system.university_system.modules.domain.housing.services.accommodation.crud import (
    add_accommodation,
    view_accommodation_by_id,
    update_accommodation,
    remove_accommodation,
    view_accommodations,
    view_students_by_accommodation,
)

# -- document upload --
from education_system.university_system.modules.domain.housing.services.accommodation.documents import (
    upload_accommodation_document,
)

# -- templates --
from education_system.university_system.modules.domain.housing.services.accommodation.templates import (
    save_template,
    apply_template,
)

# -- approval workflow --
from education_system.university_system.modules.domain.housing.services.accommodation.approval import (
    approve_accommodation,
)

# -- notifications --
from education_system.university_system.modules.domain.housing.services.accommodation.notifications import (
    notify_student,
    check_expiry_notifications,
)

# -- import / export --
from education_system.university_system.modules.domain.housing.services.accommodation.import_export import (
    bulk_import_from_csv,
    export_accommodations,
    export_to_csv,
    export_to_excel,
    export_to_pdf,
    export_to_json,
    import_from_json,
)

# -- dashboard & reports --
from education_system.university_system.modules.domain.housing.services.accommodation.dashboard import (
    show_dashboard_metrics,
    export_dashboard_report,
    generate_statistics_report,
    export_statistics_report,
)

# -- CLI menu --
from education_system.university_system.modules.domain.housing.services.accommodation.menu import (
    display_accommodation_menu,
)
