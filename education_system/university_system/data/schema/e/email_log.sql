CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT,
            subject TEXT,
            message TEXT,
            sent_date TEXT,
            status TEXT,
            related_to TEXT,
            student_id TEXT,
            sender_email TEXT,
            sender_name TEXT,
            cc_recipients TEXT,
            bcc_recipients TEXT,
            attachment_info TEXT,
            template_name TEXT,
            template_vars TEXT
        , [opened_at] TEXT, [clicked_at] TEXT, [delivery_status] TEXT, [bounce_reason] TEXT, "body" TEXT, "sent_at" TEXT, "error_message" TEXT);
