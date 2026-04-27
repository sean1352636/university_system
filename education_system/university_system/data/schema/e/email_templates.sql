CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT,
            template_content TEXT,
            template_type TEXT,
            created_date TEXT,
            created_by TEXT
        , category TEXT, "id" INTEGER, "name" TEXT, "subject" TEXT, "body" TEXT, "is_shared" INTEGER DEFAULT 0, "version" INTEGER DEFAULT 1, "updated_at" TEXT, created_at TIMESTAMP DEFAULT NULL);
