CREATE TABLE IF NOT EXISTS notification_bundle_items (
                    bundle_id INTEGER NOT NULL,
                    notification_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (bundle_id, notification_id),
                    FOREIGN KEY (bundle_id) REFERENCES bundled_notifications(bundle_id),
                    FOREIGN KEY (notification_id) REFERENCES "notifications_old"(notification_id)
                );
