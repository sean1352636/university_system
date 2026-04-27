CREATE TABLE IF NOT EXISTS workflow_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                type_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT,
                created_date TEXT,
                FOREIGN KEY (type_id) REFERENCES document_types (type_id)
            );
