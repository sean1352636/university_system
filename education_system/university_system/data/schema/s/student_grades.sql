CREATE TABLE IF NOT EXISTS student_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            assessment_name TEXT,
            grade TEXT,
            grade_date TEXT, "assessment_date" TEXT, "assessment_type" TEXT, "comments" TEXT, "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "grade_id" INTEGER, "grade_value" TEXT, "instructor" TEXT, "is_final" BOOLEAN DEFAULT 0, "module_id" TEXT, "percentage" DECIMAL(5,2), "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP, "weight" DECIMAL(5,2),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
