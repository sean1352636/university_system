CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    credits INTEGER DEFAULT 3,
                    department TEXT,
                    instructor_id TEXT,
                    academic_year_id TEXT,
                    semester_id TEXT,
                    status TEXT DEFAULT 'active',
                    date_added TEXT NOT NULL, course_code TEXT, course_name TEXT, level TEXT, credit_hours INTEGER, current_enrollment INTEGER DEFAULT 0, max_enrollment INTEGER DEFAULT 30, description TEXT DEFAULT '', duration INTEGER, course_type TEXT DEFAULT 'Core', updated_at TEXT, created_at TEXT, tags TEXT, availability_periods TEXT DEFAULT 'Fall,Spring', learning_outcomes TEXT, assessment_methods TEXT, required_textbooks TEXT, course_fee REAL DEFAULT 0.0, lab_required BOOLEAN DEFAULT 0, online_available BOOLEAN DEFAULT 0, contact_hours_per_week INTEGER DEFAULT 3,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                    FOREIGN KEY (semester_id) REFERENCES semesters (id)
                );
