CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            posted_by TEXT,
            company_name TEXT,
            job_title TEXT,
            job_description TEXT,
            location TEXT,
            job_type TEXT,
            salary_range TEXT,
            requirements TEXT,
            application_method TEXT,
            contact_email TEXT,
            post_date TEXT,
            expiry_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            category TEXT,
            experience_level TEXT, "application_deadline" TEXT, "applications_count" INTEGER DEFAULT 0, "description" TEXT, "employer_id" INTEGER, "posted_date" TEXT DEFAULT CURRENT_DATE, "responsibilities" TEXT, "status" TEXT DEFAULT 'active', "views_count" INTEGER DEFAULT 0,
            FOREIGN KEY (posted_by) REFERENCES alumni (alumni_id)
        );
