CREATE TABLE IF NOT EXISTS "students" (
        student_id TEXT PRIMARY KEY,
        email_address TEXT,
        title TEXT,
        first_name TEXT,
        middle_name TEXT,
        last_name TEXT,
        gender TEXT,
        dob TEXT,
        age INTEGER,
        course TEXT,
        registration_datetime TEXT,
        status TEXT DEFAULT 'Active',
        enrollment_date TEXT
    , emergency_contact TEXT DEFAULT '', pronouns TEXT DEFAULT '', previous_system TEXT, previous_system_id TEXT, "year" INTEGER, "program" TEXT, "phone" TEXT, "address" TEXT, "is_active" BOOLEAN DEFAULT 1, "grade_level" TEXT, created_date TIMESTAMP DEFAULT NULL);
