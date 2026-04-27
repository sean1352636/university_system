CREATE TABLE IF NOT EXISTS parking_permits (
            permit_id     TEXT    PRIMARY KEY,
            user_id       INTEGER,
            full_name     TEXT,
            email         TEXT,
            zone          TEXT,
            permit_type   TEXT,
            start_date    TEXT,
            end_date      TEXT,
            active_status TEXT,
            vehicle_id    TEXT,
            issue_date    TEXT, "expiry_date" TEXT, "fee_paid" DECIMAL(10,2) DEFAULT 0.00, "lot_id" INTEGER, "status" TEXT DEFAULT 'active', "student_id" TEXT, "created_at" TIMESTAMP DEFAULT NULL, "updated_at" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (user_id)    REFERENCES users(id)
        );
