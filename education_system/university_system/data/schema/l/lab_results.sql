CREATE TABLE IF NOT EXISTS lab_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    test_name TEXT,
                    test_code TEXT,
                    result_value TEXT,
                    reference_range TEXT,
                    units TEXT,
                    status TEXT,
                    ordered_date TEXT,
                    collected_date TEXT,
                    resulted_date TEXT,
                    ordering_provider TEXT,
                    lab_name TEXT,
                    abnormal_flag TEXT,
                    created_at TEXT, "date_performed" TEXT, "normal_range" TEXT, "reviewed" INTEGER DEFAULT 0, "test_type" TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
