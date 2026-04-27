CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id         TEXT    PRIMARY KEY,
            license_plate      TEXT    NOT NULL,
            make               TEXT,
            model              TEXT,
            year               INTEGER,
            color              TEXT,
            vehicle_type       TEXT,
            owner_id           INTEGER,
            registration_state TEXT, "is_active" BOOLEAN DEFAULT 1, "student_id" TEXT, "created_at" TIMESTAMP DEFAULT NULL, "registered_date" TIMESTAMP DEFAULT NULL, "updated_at" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );
