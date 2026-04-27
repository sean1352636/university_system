CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            assessment_id INTEGER,
            score REAL,
            letter_grade TEXT,
            submission_date TEXT,
            comments TEXT, graded_by TEXT, "id" INTEGER, "submission_id" INTEGER, "rubric_criteria_id" INTEGER, "points_earned" REAL, "max_points" REAL, "percentage" REAL, "feedback" TEXT, "graded_date" TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        );
