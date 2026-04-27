CREATE TABLE IF NOT EXISTS scheduled_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT,
                    recipient_email TEXT NOT NULL,
                    template_vars TEXT,
                    scheduled_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                , "body" TEXT, "error_message" TEXT, "recipient" TEXT, "scheduled_time" TEXT, "sent_at" TEXT, "subject" TEXT);
