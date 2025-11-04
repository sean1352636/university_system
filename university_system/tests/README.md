# University System Test Suite

This directory contains comprehensive test scripts for the University System.

## New Test Scripts (15 scripts created)

### 1. **test_student_enrollment.py**
Tests student enrollment process, module assignments, and enrollment validation.
- Validates total student count
- Checks students have exactly 6 modules
- Verifies compulsory modules (CIS0001, CIS0002)
- Validates enrollment status

### 2. **test_authentication.py**
Tests authentication system and user accounts.
- Validates user account creation
- Tests password hashing
- Checks username uniqueness
- Tests actual login/logout functionality with UserAuth

### 3. **test_timetables.py**
Tests timetable generation and schedule distribution.
- Validates student timetables
- Checks for schedule conflicts
- Tests day/time slot distribution
- Validates room allocations

### 4. **test_instructors.py**
Tests instructor management and assignments.
- Validates instructor accounts
- Checks module assignments
- Tests instructor schedules
- Detects schedule conflicts

### 5. **test_database_integrity.py**
Tests database integrity and constraints.
- Checks foreign key constraints
- Validates orphaned records
- Tests NULL values in critical fields
- Verifies data relationships

### 6. **test_modules.py**
Tests module management and data.
- Validates all 14 modules from modules.py
- Checks module types and distribution
- Tests enrollment statistics
- Validates module credits

### 7. **test_student_data.py**
Tests student data validation and quality.
- Validates student demographics
- Checks age distribution
- Tests email addresses
- Validates name completeness

### 8. **test_performance.py**
Tests database query performance.
- Measures query execution times
- Tests complex joins
- Checks index effectiveness
- Validates database statistics

### 9. **test_data_consistency.py**
Tests data consistency across tables.
- Validates CS students don't have DS modules
- Validates DS students don't have CS modules
- Checks compulsory module compliance
- Tests timetable/enrollment matching

### 10. **test_user_roles.py**
Tests user roles and permissions.
- Validates role distribution
- Checks student/instructor account coverage
- Tests admin user counts
- Validates email consistency

### 11. **test_reports.py**
Tests report generation queries.
- Enrollment summary reports
- Module popularity rankings
- Instructor workload reports
- Daily schedule distribution
- Student demographics summary

### 12. **test_search_functionality.py**
Tests various search queries and filters.
- Search by name (partial match)
- Search by course
- Search by age range
- Search by module enrollment
- Complex multi-criteria searches

### 13. **test_backup_restore.py**
Tests backup and restore functionality.
- Creates database backups
- Verifies backup integrity
- Compares table counts
- Manages backup cleanup

### 14. **test_email_validation.py**
Tests email validation and formats.
- Validates email formats
- Checks for duplicates
- Tests domain distribution
- Validates email consistency

### 15. **test_schedule_conflicts.py**
Tests schedule conflict detection.
- Detects student schedule conflicts
- Detects instructor conflicts
- Checks room double-booking
- Validates time slot distribution

### 16. **test_course_requirements.py**
Tests course requirements compliance.
- Validates 6 modules per student
- Checks compulsory modules (2)
- Validates optional modules (2)
- Validates course-specific modules (2)
- Tests CS/DS module requirements

## Running Tests

### Run Individual Test
```bash
python3 -m university_system.tests.test_student_enrollment
```

### Run All Tests
```bash
python3 -m university_system.tests.run_all_tests
```

## Test Results Summary

All tests validate:
- ✓ 191 students in system
- ✓ 202 user accounts
- ✓ 12 active instructors
- ✓ 14 active modules
- ✓ All students have exactly 6 modules
- ✓ All students have compulsory modules
- ✓ No schedule conflicts
- ✓ Database integrity maintained

## Test Coverage

The test suite covers:
- Student enrollment and module assignments
- Authentication and user management
- Timetable generation
- Instructor assignments and schedules
- Database integrity and constraints
- Data consistency and validation
- Performance and optimization
- Reporting and analytics
- Search functionality
- Email validation
- Backup/restore operations
- Course requirements compliance
