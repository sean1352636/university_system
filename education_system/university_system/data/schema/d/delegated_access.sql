CREATE TABLE IF NOT EXISTS delegated_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grantor_user_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                revoked_at TIMESTAMP,
                revoked_by INTEGER,
                FOREIGN KEY (grantor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (delegate_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (revoked_by) REFERENCES users(id)
            );
