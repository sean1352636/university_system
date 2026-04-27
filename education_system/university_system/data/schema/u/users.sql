CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, last_login TEXT, "password_hash" TEXT, "display_name" TEXT, "is_active" INTEGER DEFAULT 1, "failed_login_attempts" INTEGER DEFAULT 0, "locked_until" TEXT, "legacy_salt" TEXT, "password_changed_at" TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
