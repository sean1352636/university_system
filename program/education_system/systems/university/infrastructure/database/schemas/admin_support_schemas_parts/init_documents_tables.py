"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_documents_tables():
    """Initialize documents system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="documents"))

        # Create document_repository table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_repository (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL CHECK(length(title) > 0),
                            content TEXT NOT NULL CHECK(length(content) > 0),
                            content_hash TEXT NOT NULL,
                            author_id INTEGER NOT NULL,
                            module_code TEXT,
                            submission_date TEXT NOT NULL,
                            file_type TEXT,
                            word_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY (module_code) REFERENCES modules (module_code) ON DELETE SET NULL
                        )
        ''')

        # Create document_tags table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_tags (
                        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_name TEXT UNIQUE,
                        tag_color TEXT,
                        description TEXT
                    )
        ''')

        # Create document_workflow table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_workflow (
                        workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER,
                        step_name TEXT,
                        step_order INTEGER,
                        assigned_to TEXT,
                        status TEXT,
                        comments TEXT,
                        completed_date TEXT,
                        completed_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
                    )
        ''')

        # Create response_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS response_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT,
                    content TEXT NOT NULL,
                    category TEXT,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    variables TEXT  -- JSON array of variable names
                )
        ''')

        # Create schedule_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT UNIQUE,
                        description TEXT,
                        template_data TEXT,
                        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT
                    )
        ''')

        # `workflow_instances` is owned by infrastructure/workflows/
        # database.py (the generic workflow engine, with TEXT keys
        # and JSON columns). Its previous CREATE here defined a
        # different-shaped table that no code ever queried — left in
        # place it would clobber the engine's schema on a fresh DB,
        # so the dead block has been removed.

        # Create workflows table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    workflow_type TEXT NOT NULL, -- 'approval', 'notification', 'automation'
                    trigger_conditions TEXT, -- JSON
                    workflow_steps TEXT, -- JSON with step definitions
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="documents"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="documents", error=str(e)))
        if 'conn' in locals():
            conn.close()
