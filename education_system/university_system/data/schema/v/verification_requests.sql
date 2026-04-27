CREATE TABLE IF NOT EXISTS verification_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    requester_name TEXT NOT NULL,
    requester_email TEXT,
    requester_organization TEXT,
    status TEXT DEFAULT 'pending',
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_date TIMESTAMP, "id" INTEGER, "notes" TEXT, "processed_at" TIMESTAMP, "processed_by" INTEGER, "request_type" TEXT, "requested_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "student_id" INTEGER,
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);
