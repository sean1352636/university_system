-- Fix user_accounts.user_id foreign keys after users table reorganization
-- This was missed in the initial reorganization and causes login role issues

BEGIN TRANSACTION;

-- Create a temporary mapping table for the ID changes
CREATE TEMPORARY TABLE id_mapping (old_id INTEGER, new_id INTEGER);

-- Insert the ID mappings (same as used in reorganize_users_v2.sql)
-- Admin: 196 -> 1
INSERT INTO id_mapping VALUES (196, 1);

-- Staff: 193 -> 2
INSERT INTO id_mapping VALUES (193, 2);

-- Default student: 1 -> 3
INSERT INTO id_mapping VALUES (1, 3);

-- All other users: shifted by +2
-- IDs 2-192 (excluding 193) become 4-194
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

-- IDs 194-195 become 196-197
INSERT INTO id_mapping VALUES (194, 196);
INSERT INTO id_mapping VALUES (195, 197);

-- Update user_accounts.user_id using the mapping
UPDATE user_accounts
SET user_id = (
    SELECT new_id
    FROM id_mapping
    WHERE old_id = user_accounts.user_id
)
WHERE user_id IN (SELECT old_id FROM id_mapping);

-- Clean up temporary table
DROP TABLE id_mapping;

COMMIT;

-- Verify the fix
SELECT 'After fix:' as status;
SELECT ua.username, ua.user_id, u.username as actual_username, u.role
FROM user_accounts ua
LEFT JOIN users u ON ua.user_id = u.id
WHERE ua.username IN ('admin', 'staff', 'student')
ORDER BY ua.username;
