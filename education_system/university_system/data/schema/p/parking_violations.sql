CREATE TABLE IF NOT EXISTS parking_violations (
            violation_id    TEXT    PRIMARY KEY,
            vehicle_id      TEXT,
            license_plate   TEXT,
            violation_type  TEXT,
            violation_date  TEXT,
            fine_amount     REAL,
            payment_status  TEXT,
            location        TEXT,
            officer_id      INTEGER, "issued_by" TEXT, "lot_id" INTEGER, "notes" TEXT, "paid_date" TEXT, "space_id" INTEGER, "status" TEXT DEFAULT 'pending', "created_at" TIMESTAMP DEFAULT NULL, "updated_at" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (officer_id) REFERENCES users(id)
        );
