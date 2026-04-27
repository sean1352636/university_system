CREATE TABLE IF NOT EXISTS active_role_switches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_role TEXT NOT NULL,
                switched_to_role TEXT NOT NULL,
                linked_account_id INTEGER NOT NULL,
                switched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reverted_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_account_id) REFERENCES linked_accounts(id) ON DELETE CASCADE
            );
