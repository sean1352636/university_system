CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id         TEXT    PRIMARY KEY,
            lot_id           TEXT,
            space_number     TEXT,
            space_type       TEXT,
            occupancy_status TEXT,
            reserved_for     TEXT, "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "is_accessible" BOOLEAN DEFAULT 0, "is_available" BOOLEAN DEFAULT 1, "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
        );
