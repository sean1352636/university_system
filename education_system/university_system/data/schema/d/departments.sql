CREATE TABLE IF NOT EXISTS departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            manager_id INTEGER,
            email TEXT,
            sla_policy_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (manager_id) REFERENCES users (id),
            FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
        );
