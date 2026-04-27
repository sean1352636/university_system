CREATE TABLE IF NOT EXISTS sms_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipient_phone TEXT NOT NULL,
                        message TEXT NOT NULL,
                        provider TEXT,
                        status TEXT DEFAULT 'sent',
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        student_id TEXT,
                        related_to TEXT,
                        error_message TEXT,
                        message_sid TEXT
                    );
