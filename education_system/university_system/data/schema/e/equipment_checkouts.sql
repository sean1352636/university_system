CREATE TABLE IF NOT EXISTS equipment_checkouts (
            checkout_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER,
            borrower_id TEXT,
            club_id INTEGER,
            checkout_date TEXT,
            expected_return TEXT,
            actual_return TEXT,
            condition_out TEXT,
            condition_in TEXT,
            notes TEXT,
            status TEXT DEFAULT 'checked_out',
            FOREIGN KEY (equipment_id) REFERENCES union_equipment (equipment_id),
            FOREIGN KEY (borrower_id) REFERENCES students (student_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        );
