CREATE TABLE IF NOT EXISTS parent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                notification_type TEXT,
                notification_content TEXT,
                created_date TEXT,
                read_status BOOLEAN DEFAULT 0, "created_at" TEXT, "is_read" INTEGER DEFAULT 0, "message" TEXT, "read_at" TEXT, "title" TEXT, "type" TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
