-- Fix Default Account Roles Issue
--
-- Problem: After reorganizing the users table, the user_accounts table's foreign keys
-- were not fully updated, causing all three default accounts (admin, staff, student)
-- to login with 'student' role instead of their correct roles.
--
-- Root Cause:
-- - The initial reorganization updated most foreign keys but missed user_accounts.user_id
-- - The default 'admin', 'staff', and 'student' accounts in user_accounts were all
--   pointing to old user_id 196 (which became a student account after reorganization)
--
-- Solution:
-- - Update user_accounts.user_id using the same ID mapping from the reorganization
-- - Manually fix the three default accounts to point to correct user IDs

BEGIN TRANSACTION;

-- Step 1: Apply the ID mapping to user_accounts.user_id (same as other foreign keys)
-- This uses the mapping from reorganize_users_v2.sql

-- Create temporary mapping table
CREATE TEMPORARY TABLE id_mapping (old_id INTEGER, new_id INTEGER);

-- Core mappings
INSERT INTO id_mapping VALUES (196, 1);  -- Admin: 196 -> 1
INSERT INTO id_mapping VALUES (193, 2);  -- Staff: 193 -> 2
INSERT INTO id_mapping VALUES (1, 3);    -- Default student: 1 -> 3

-- Shifted users: 2-192 (excluding 193) become 4-194
INSERT INTO id_mapping
SELECT old_id, old_id + 2 as new_id
FROM (
    WITH RECURSIVE cnt(x) AS (
        SELECT 2
        UNION ALL
        SELECT x+1 FROM cnt WHERE x < 192
    )
    SELECT x as old_id FROM cnt WHERE x != 193
);

-- Shifted users: 194-195 become 196-197
INSERT INTO id_mapping VALUES (194, 196);
INSERT INTO id_mapping VALUES (195, 197);

-- Apply the mapping to user_accounts.user_id
UPDATE user_accounts
SET user_id = (
    SELECT new_id
    FROM id_mapping
    WHERE old_id = user_accounts.user_id
)
WHERE user_id IN (SELECT old_id FROM id_mapping);

-- Step 2: Fix the three default accounts explicitly
-- (They were all pointing to old ID 196, so they all got mapped to 1)
UPDATE user_accounts SET user_id = 1 WHERE username = 'admin';    -- Points to admin user
UPDATE user_accounts SET user_id = 2 WHERE username = 'staff';    -- Points to staff user
UPDATE user_accounts SET user_id = 3 WHERE username = 'student';  -- Points to student user

-- Cleanup
DROP TABLE id_mapping;

COMMIT;

-- Verification query
SELECT
    'Verification Results:' as status,
    '' as username,
    '' as user_id,
    '' as linked_username,
    '' as role
UNION ALL
SELECT
    '',
    ua.username,
    CAST(ua.user_id AS TEXT),
    u.username,
    u.role
FROM user_accounts ua
LEFT JOIN users u ON ua.user_id = u.id
WHERE ua.username IN ('admin', 'staff', 'student')
ORDER BY ua.username;
