CREATE TABLE IF NOT EXISTS parking_occupancy (
    occupancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    available_spaces INTEGER NOT NULL,
    total_spaces INTEGER NOT NULL, "id" INTEGER, "occupancy_rate" REAL DEFAULT 0.0, "occupied_spaces" INTEGER DEFAULT 0,
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
);
