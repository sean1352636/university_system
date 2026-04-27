CREATE TABLE IF NOT EXISTS staff_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER,
                punctuality_score INTEGER DEFAULT 5,
                quality_score INTEGER DEFAULT 5,
                efficiency_score INTEGER DEFAULT 5,
                teamwork_score INTEGER DEFAULT 5,
                overall_score REAL DEFAULT 5.0,
                evaluation_date DATE DEFAULT CURRENT_DATE,
                notes TEXT,
                FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
            );
