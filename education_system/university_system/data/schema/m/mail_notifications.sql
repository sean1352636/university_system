CREATE TABLE IF NOT EXISTS mail_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id INTEGER NOT NULL,
                    recipient_email TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    FOREIGN KEY (package_id) REFERENCES mail_packages(package_id)
                );
