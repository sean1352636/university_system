CREATE TABLE IF NOT EXISTS stored_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            cc_recipients TEXT,
            bcc_recipients TEXT,
            attachment_paths TEXT,
            created_date TEXT NOT NULL,
            template_name TEXT,
            template_vars TEXT,
            related_to TEXT,
            student_id TEXT
        );
