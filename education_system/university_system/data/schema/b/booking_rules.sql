CREATE TABLE IF NOT EXISTS booking_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER,
                    category_id INTEGER,
                    rule_type TEXT NOT NULL,
                    rule_value TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id),
                    FOREIGN KEY (category_id) REFERENCES equipment_categories(category_id)
                );
