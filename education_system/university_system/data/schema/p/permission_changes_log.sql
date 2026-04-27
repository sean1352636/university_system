CREATE TABLE IF NOT EXISTS permission_changes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_by INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                permission_name TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "change_reason" TEXT, "new_permissions" TEXT, "old_permissions" TEXT, "user_id" INTEGER,
                FOREIGN KEY (changed_by) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            );
