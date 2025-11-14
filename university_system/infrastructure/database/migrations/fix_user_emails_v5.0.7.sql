-- Migration: Fix User Database Email Addresses
-- Version: 5.0.7
-- Date: 2025-11-14
-- Description: Correct admin and staff email addresses to use proper institutional format

-- Update admin user (Sean Catchpole) from student email to admin email and correct name
UPDATE users
SET email = 'sean.catchpole@university.edu',
    first_name = 'sean',
    last_name = 'catchpole'
WHERE username = '7591239' AND role = 'admin';

-- Update staff user (Lucas Jones) from student email to staff email
UPDATE users
SET email = 'lucas.jones@university.edu'
WHERE username = '1952392' AND role = 'staff';

-- Delete incomplete admin user with no email
DELETE FROM users
WHERE username = 'system_' AND role = 'admin';

-- Verify results
SELECT 'Admin and Staff Users After Migration:' as Status;
SELECT username, role, email, first_name, last_name
FROM users
WHERE role IN ('admin', 'staff')
ORDER BY role, username;
