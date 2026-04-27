CREATE TABLE IF NOT EXISTS asset_audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                action_category TEXT,
                action_by TEXT NOT NULL,
                action_by_name TEXT,
                action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                old_values TEXT,
                new_values TEXT,
                field_changed TEXT,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                notes TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            );
