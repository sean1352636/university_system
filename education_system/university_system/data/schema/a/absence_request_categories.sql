CREATE TABLE IF NOT EXISTS absence_request_categories (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT UNIQUE NOT NULL,
         description TEXT,
         requires_evidence INTEGER DEFAULT 0,
         approval_route TEXT DEFAULT 'instructor',
         auto_approve INTEGER DEFAULT 0
       );
