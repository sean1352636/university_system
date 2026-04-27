CREATE TABLE IF NOT EXISTS parent_conferences (
    conference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER,
    datetime TIMESTAMP NOT NULL,
    location TEXT,
    meeting_type TEXT DEFAULT 'in_person',  -- in_person, virtual, phone
    meeting_link TEXT,
    status TEXT DEFAULT 'scheduled',
    notes TEXT, "id" INTEGER, "instructor_id" INTEGER, "scheduled_date" TEXT, "duration" INTEGER DEFAULT 30, "created_at" TEXT,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);
