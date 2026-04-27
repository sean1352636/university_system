CREATE TABLE IF NOT EXISTS delegated_access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delegation_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (delegation_id) REFERENCES delegated_access(id) ON DELETE CASCADE,
                FOREIGN KEY (delegate_user_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            );
