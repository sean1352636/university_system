CREATE TABLE IF NOT EXISTS ta_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ta_id INTEGER NOT NULL,
                        permission_type TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        granted_by TEXT NOT NULL,
                        granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (ta_id) REFERENCES teaching_assistants(id),
                        UNIQUE(ta_id, permission_type, module_code)
                    );
