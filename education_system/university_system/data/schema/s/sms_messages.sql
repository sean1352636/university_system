CREATE TABLE IF NOT EXISTS sms_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_username TEXT,
                            recipient_name TEXT,
                            phone_number TEXT,
                            message TEXT,
                            status TEXT,
                            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        , "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "delivered_at" TEXT, "error_message" TEXT, "recipient_phone" TEXT);
