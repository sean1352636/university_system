CREATE TABLE IF NOT EXISTS credential_verifications (
    verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    verifier_name TEXT,
    verifier_email TEXT,
    verified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_method TEXT,  -- blockchain, api, manual
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);
