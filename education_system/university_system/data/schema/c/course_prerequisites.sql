CREATE TABLE IF NOT EXISTS course_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            prerequisite_course_id INTEGER NOT NULL,
            is_required BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL, minimum_grade TEXT DEFAULT 'D', can_be_concurrent BOOLEAN DEFAULT 0, prerequisite_type TEXT DEFAULT 'Required', "prerequisite_id" INTEGER, "module_code" TEXT, "prerequisite_module_code" TEXT, "min_grade" TEXT, "is_corequisite" BOOLEAN DEFAULT 0,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (prerequisite_course_id) REFERENCES courses (id),
            UNIQUE(course_id, prerequisite_course_id)
        );
