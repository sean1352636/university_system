from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_research_grants_system_db():
    """Initialize the Research & Grants Management database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Research & Grants Management"))

        # Research projects
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_title TEXT NOT NULL,
            project_description TEXT,
            principal_investigator_id TEXT NOT NULL,
            department TEXT NOT NULL,
            project_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            total_budget REAL DEFAULT 0,
            funding_source TEXT,
            ethics_approval_status TEXT DEFAULT 'pending',
            ethics_approval_date TEXT,
            publications_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Research team members
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_team_members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            staff_id TEXT NOT NULL,
            role TEXT NOT NULL,
            join_date TEXT DEFAULT CURRENT_DATE,
            leave_date TEXT,
            contribution_percentage REAL,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Grant applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_name TEXT NOT NULL,
            funding_agency TEXT NOT NULL,
            project_id INTEGER,
            principal_investigator_id TEXT NOT NULL,
            co_investigators TEXT,
            requested_amount REAL NOT NULL,
            application_deadline TEXT NOT NULL,
            submission_date TEXT,
            decision_date TEXT,
            decision_status TEXT DEFAULT 'pending',
            awarded_amount REAL,
            grant_period_start TEXT,
            grant_period_end TEXT,
            application_documents TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Grant budgets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            requested_amount REAL NOT NULL,
            approved_amount REAL,
            spent_amount REAL DEFAULT 0,
            remaining_amount REAL,
            FOREIGN KEY (application_id) REFERENCES grant_applications (application_id)
        )
        ''')

        # Research publications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_publications (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            publication_type TEXT NOT NULL,
            journal_name TEXT,
            conference_name TEXT,
            publication_date TEXT,
            doi TEXT,
            url TEXT,
            abstract TEXT,
            keywords TEXT,
            citation_count INTEGER DEFAULT 0,
            is_peer_reviewed BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Research milestones
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_milestones (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            milestone_name TEXT NOT NULL,
            milestone_description TEXT,
            target_date TEXT NOT NULL,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            deliverables TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Research equipment
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            model_number TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            purchase_cost REAL,
            current_location TEXT,
            assigned_project_id INTEGER,
            maintenance_schedule TEXT,
            last_maintenance_date TEXT,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (assigned_project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # IRB/Ethics reviews
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ethics_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            review_type TEXT NOT NULL,
            submission_date TEXT NOT NULL,
            review_date TEXT,
            decision TEXT DEFAULT 'pending',
            decision_date TEXT,
            reviewer_comments TEXT,
            conditions TEXT,
            approval_expiry_date TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Research & Grants Management"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Research & Grants", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FACILITIES & SPACE MANAGEMENT SCHEMAS
# ============================================================================


def init_integration_marketplace_system_db():
    """Initialize the Integration Marketplace database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Integration Marketplace"))

        # Available integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            version TEXT,
            logo_url TEXT,
            documentation_url TEXT,
            pricing_model TEXT,
            is_official BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            rating REAL DEFAULT 0,
            install_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Installed integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            installed_by TEXT NOT NULL,
            installation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            version_installed TEXT,
            configuration TEXT,
            status TEXT DEFAULT 'active',
            last_sync_date TEXT,
            sync_frequency TEXT,
            is_enabled BOOLEAN DEFAULT 1,
            FOREIGN KEY (integration_id) REFERENCES integration_catalog (integration_id)
        )
        ''')

        # Integration credentials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            oauth_token TEXT,
            refresh_token TEXT,
            token_expiry TEXT,
            endpoint_url TEXT,
            additional_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Integration sync logs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            sync_start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_end_time TEXT,
            sync_status TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            errors_encountered INTEGER DEFAULT 0,
            error_details TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Data mappings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            transformation_rule TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Webhook endpoints
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            event_type TEXT NOT NULL,
            secret_key TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_triggered_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Integration usage analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_usage_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Integration Marketplace"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Integration Marketplace", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PERFORMANCE INDEXES
# ============================================================================


def init_integration_tables():
    """Initialize integration system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="integration"))

        # Create api_integrations table
        cursor.execute('''
        CREATE TABLE api_integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    integration_name TEXT UNIQUE,
                    api_key TEXT,
                    endpoint_url TEXT,
                    status TEXT DEFAULT 'active',
                    last_sync TEXT,
                    sync_frequency TEXT DEFAULT 'daily',
                    config_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
        ''')

        # Create api_keys table
        cursor.execute('''
        CREATE TABLE api_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_name TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    permissions TEXT, -- JSON array
                    rate_limit INTEGER DEFAULT 1000,
                    is_active BOOLEAN DEFAULT 1,
                    expires_at TEXT,
                    last_used_at TEXT,
                    created_by TEXT,
                    created_at TEXT
                )
        ''')

        # Create api_usage_log table
        cursor.execute('''
        CREATE TABLE api_usage_log (
                    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id INTEGER,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    response_status INTEGER,
                    response_time_ms INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (api_key_id) REFERENCES api_keys (key_id)
                )
        ''')

        # Create system_integration_log table
        cursor.execute('''
        CREATE TABLE system_integration_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_system TEXT,
                        target_system TEXT,
                        operation TEXT,
                        status TEXT,
                        details TEXT,
                        timestamp TEXT
                    )
        ''')

        # Create system_integrations table
        cursor.execute('''
        CREATE TABLE system_integrations (
                    integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,  -- sso, lms, sis, calendar, etc.
                    config TEXT NOT NULL,  -- JSON configuration
                    is_active BOOLEAN DEFAULT 0,
                    last_sync_datetime TEXT,
                    sync_status TEXT DEFAULT 'never',
                    error_log TEXT
                )
        ''')

        # Create system_settings table
        cursor.execute('''
        CREATE TABLE system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="integration"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="integration", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# LIBRARY TABLES (14 tables)
# ============================================================================


