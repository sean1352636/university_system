CREATE TABLE IF NOT EXISTS aid_components (
    component_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL,
    aid_type TEXT NOT NULL,  -- grant, scholarship, loan, work_study
    source TEXT,  -- federal, state, institutional, private
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    disbursement_plan TEXT,  -- JSON: [{term: 'Fall', amount: 1000}, ...]
    terms_conditions TEXT,
    is_need_based BOOLEAN DEFAULT 0,
    is_renewable BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'offered',
    FOREIGN KEY (package_id) REFERENCES aid_packages(package_id) ON DELETE CASCADE
);
