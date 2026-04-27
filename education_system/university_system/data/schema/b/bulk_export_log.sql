CREATE TABLE IF NOT EXISTS bulk_export_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                export_type TEXT,
                resource_type TEXT,
                record_count INTEGER,
                status TEXT DEFAULT 'pending',
                ip_address TEXT,
                exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (approved_by) REFERENCES users(id)
            );
