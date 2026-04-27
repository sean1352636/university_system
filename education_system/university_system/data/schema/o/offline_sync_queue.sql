CREATE TABLE IF NOT EXISTS offline_sync_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,  -- create, update, delete
    entity_type TEXT NOT NULL,  -- assignment, grade, attendance
    data TEXT NOT NULL,  -- JSON
    sync_status TEXT DEFAULT 'pending',  -- pending, synced, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP, "user_id" INTEGER, "entity_id" INTEGER, "payload" TEXT,
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
);
