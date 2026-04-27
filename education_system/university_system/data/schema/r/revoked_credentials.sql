CREATE TABLE IF NOT EXISTS revoked_credentials (
    revocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    revoked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    revoked_by INTEGER,
    blockchain_revocation_hash TEXT,
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);
