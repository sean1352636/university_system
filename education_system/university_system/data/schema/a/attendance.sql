CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            reason TEXT, "arrival_time" TEXT, "attendance_id" INTEGER, "class_date" TEXT, "departure_time" TEXT, "module_id" TEXT, "notes" TEXT, "recorded_by" TEXT, "created_at" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
