CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            enrollment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Enrolled', module_type TEXT DEFAULT 'Standard', module_name TEXT, grade TEXT, completion_date TEXT, "credits_earned" INTEGER DEFAULT 0, "enrollment_id" INTEGER, "module_id" TEXT, "semester" TEXT, "year" TEXT, "created_at" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            UNIQUE(student_id, module_code)
        );
