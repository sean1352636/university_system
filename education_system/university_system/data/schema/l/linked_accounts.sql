CREATE TABLE IF NOT EXISTS linked_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_user_id INTEGER NOT NULL,
                secondary_user_id INTEGER NOT NULL,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                linked_by INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (primary_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (secondary_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_by) REFERENCES users(id),
                UNIQUE(primary_user_id, secondary_user_id)
            );
