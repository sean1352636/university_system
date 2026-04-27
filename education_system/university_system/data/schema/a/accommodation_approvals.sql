CREATE TABLE IF NOT EXISTS accommodation_approvals (
    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    approved_by INTEGER NOT NULL,
    approved_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
);
