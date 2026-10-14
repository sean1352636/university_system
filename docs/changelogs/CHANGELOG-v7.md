# Changelog Archive — Version 7.x

This file contains the version 7 history moved from the main
[CHANGELOG.md](../../CHANGELOG.md) to keep the current changelog focused.

For current changes and version 9, see [CHANGELOG.md](../../CHANGELOG.md).
Other historical versions are archived alongside this file.

---

## [7.32.0] — 2026-03-13

### Web Dashboard — Full Navigation for Secondary & Primary Schools

Added comprehensive sidebar navigation to the web SPA for both the secondary school and primary school systems, matching the existing university and college navigation patterns.

#### Secondary School Navigation (~50 items across 8 categories)
- **Academics** — Enrollments, Subjects, Timetable, Exams, Exam Results, Homework, Submissions, Progress Targets, Interventions
- **Pastoral Care** — Behaviour, Detentions, Exclusions, Rewards, Pastoral Notes, House Points, Safeguarding, SEND, SEND Provisions
- **Communication** — Announcements, Notifications, Email, Calendar, Communication Log, Parents Evening
- **Student Life** — Clubs, Trips, Careers, Work Experience, Library, Library Loans, Meals, Medical, First Aid, Consent, Form Groups, Transport
- **Staff & HR** — Staff Directory, Staff HR, Staff Leave, Cover, CPD
- **Facilities** — Room Bookings, Assets, Visitors, Incidents, Seating Plans
- **Finance** — Transactions, Budgets
- **Administration** — Admissions, Documents, Policies, Settings, Audit Log

#### Primary School Navigation (~40 items across 8 categories)
- **Academics** — Classes, Subjects, Timetable, Assessments, Homework, Phonics, SATs, Reading Records, Progress
- **Pastoral Care** — Behaviour, Rewards, Safeguarding, SEND, Pastoral Notes
- **Communication** — Announcements, Notifications, Email, Calendar, Communication Log, Parents Evening
- **Pupil Life** — Clubs, Trips, Library, Library Loans, Meals, Medical, Consent, Transport
- **Staff & HR** — Staff Directory, Staff HR, Staff Leave, Cover, CPD
- **Facilities** — Room Bookings, Assets, Visitors, Incidents
- **Finance** — Transactions, Budgets
- **Administration** — Admissions, Documents, Policies, Settings, Audit Log

All navigation items use the generic table viewer (`tbl:` prefix) to render data from the corresponding system database with auto-detected columns, pagination, and search.

---

## [7.31.0] — 2026-03-13

### Secondary School — Full API Route Coverage (44 new routes)

Created 44 API route files under `shared/api/secondary/routes/`, bringing secondary school coverage from 8 routes to 52 (51 blueprints + auth). Every domain service module now has a corresponding REST API.

#### New Routes by Category

- **Academics** (6) — `exams`, `homework`, `interventions`, `progress`, `reports`, `timetable`
- **Admin** (8) — `admissions`, `audit_log`, `data_export`, `documents`, `finance`, `policies`, `settings`, `users`
- **Communication** (6) — `announcements`, `calendar`, `communication_log`, `email`, `notifications`, `parents_evening`
- **Facilities** (5) — `assets`, `incidents`, `room_booking`, `seating_plans`, `visitors`
- **Pastoral Care** (6) — `detentions`, `exclusions`, `pastoral`, `rewards`, `safeguarding`, `send`
- **Staff** (4) — `cover`, `cpd`, `hr`, `staff_directory`
- **Student Life** (9) — `careers`, `clubs`, `consent`, `form_groups`, `library`, `meals`, `medical`, `transport`, `trips`

#### Technical Details
- All routes follow the established secondary pattern: imports from `shared.api.secondary.auth` and `shared.api.secondary.validators`
- Service imports use nested domain paths (e.g. `secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service`)
- Each route file includes: Blueprint, `_db_path` global, `init_*_routes()` function, CRUD endpoints with `@token_required` and `@role_required` decorators
- Updated `shared/api/secondary/routes/__init__.py` with all 51 blueprints and 51 init functions

---

## [7.30.0] — 2026-03-13

### Security, Bug Fixes, and Feature Improvements

Comprehensive audit and fix pass covering security vulnerabilities, code quality, and missing features across all 4 education systems (~200+ files modified).

#### Security Fixes

##### SQL Injection — Dynamic Column Names (CRITICAL)
- **92 service files patched** — all dynamic `SET` clause column names now validated with `validate_identifier()` before interpolation
- Affected systems: college (45 files), primary (37 files), secondary (8 files), shared (2 files)
- Created new `sql_safety.py` modules for secondary and primary schools

##### LIKE Wildcard Injection (MEDIUM)
- **45 files patched** — all `f"%{search}%"` patterns now escape `%` and `_` via `escape_like()`
- College (20 files), secondary (4 files), primary (4 files), university (17 files)

##### JWT Secret (CRITICAL)
- Default JWT secret changed from `"change-me-in-production"` to `secrets.token_urlsafe(64)` auto-generated at module load
- Env var `JWT_SECRET_KEY` still overrides when set

##### CSRF Protection (HIGH)
- JSON POST/PUT/DELETE/PATCH requests now validate `Origin`/`Referer` headers against server host
- Non-browser clients (no Origin/Referer) are allowed through
- Cross-origin browser requests are blocked with 403

##### SVG Upload Removal (HIGH)
- Removed `image/svg+xml` and `.svg` from allowed upload types to prevent XSS/XXE attacks

##### MFA Recovery Code Rate Limiting (MEDIUM)
- `verify_recovery_code()` now tracks failed attempts per user — locks out after 5 failures for 15 minutes
- Successful verification clears the counter

##### Enhanced Rate Limiting (MEDIUM)
- Added per-username rate limiting (5 attempts/60s) alongside existing per-IP tracking
- Login route checks both stores

##### Insecure Temporary Passwords (LOW)
- Replaced `random.choices` with `secrets.choice` for password generation in CLI menus and parent portal admin

##### Encryption Key Storage (MEDIUM)
- Moved default key storage from database directory to separate `.keys/` subdirectory
- Added warning log when file-based storage is used
- Backward-compatible migration from legacy path

#### Bug Fixes

##### Database Connection Leaks
- **10 connections fixed** in college and secondary `student_gui.py` — all wrapped in `try/finally`
- Verified all secondary/primary GUI files are clean (service layer pattern used consistently)

##### Silent Exception Swallowing
- **13 `except Exception: pass` replaced** with `logging.warning(..., exc_info=True)` — 8 in college student GUI, 4 in secondary student GUI, 1 in enrollment service

##### Missing DB Error Logging
- **4 exception handlers enhanced** in `college/infrastructure/database/db.py` — transaction rollback, connection pool, execute_write, and manager transaction now log errors

##### Cross-Database Logic Moved to Service Layer
- **College `student_gui.py`** — removed raw `sqlite3` access to secondary DB and auth DB; added 4 new service methods: `fetch_secondary_students`, `import_from_secondary`, `mark_secondary_as_transferred`, `notify_transfer`
- **Secondary `student_gui.py`** — same refactoring for primary school imports; 4 analogous service methods added
- Both GUIs now call service methods instead of managing cross-system DB connections directly

##### Schema Column Mismatches
- **ComplianceService** — fixed `funding_body`/`funding_type` → `learning_aim`/`funding_model`
- **AssetsService** — fixed `loaned_to`/`asset_name` → `student_id`/`description`
- **ParentsEveningService** — fixed `teacher_id`/`slot_duration_mins` → `staff_id`/`slot_duration`

#### New Features

##### Delete Operations (18 Services)
Added missing delete methods to college services: enrollment, grades, attendance, first_aid, helpdesk (cascades to responses), parent_portal, admissions, safeguarding, behaviour, pastoral, send, exams, compliance, parents_evening, careers, bursary, assets, library

##### Skeleton GUIs Implemented (6 Modules)
Populated empty `_load_*()` methods with real data loading:
- **UCAS** — applications + choices
- **Value Added** — baselines + predictions
- **ILP** — plans, targets, reviews
- **T-Levels** — routes, enrollments, placement logs
- **Apprenticeships** — standards, enrollments, OTJ logs, reviews
- **Governance** — governors, meetings, actions, strategic plans

##### Stub Functions Implemented
- **9 automation functions** in university student support: escalation processing, keyword-based sentiment analysis, category suggestion (10 categories), auto-assignment, resolution time estimation, background task scheduler, notification queue processing, metrics calculation, staff assignment loading
- **AI detector custom dataset** — loads `.json`, `.jsonl`, `.csv` with validation and trains TF-IDF + RandomForest
- **Plagiarism integration** — real API-based implementation replacing placeholder

##### Pagination (6 GUI Modules + 4 Services)
- Added paginated loading (50 records/page) with Previous/Next buttons, page indicator, and record count
- **GUIs**: students, courses, enrollment, grades, attendance, assignments
- **Services**: added `count_*()` methods and `limit`/`offset` params to students, enrollment, assignments, attendance
- Search and filter actions reset to page 0

##### CSV Export (108 GUI Modules — Full Coverage)
- Created shared helper `college_system/modules/shared/csv_export.py`
- Added "Export CSV" buttons to **all 108 college GUI modules** with Treeview data tables
- Multi-tab modules export per-tab (e.g. disciplinary exports cases/evidence/appeals separately; pastoral exports notes/wellbeing/LAC)
- Modules with multiple treeviews get per-treeview export buttons (e.g. funding: records, evidence, rules, resits)
- Initial 12 modules: students, attendance, grades, courses, enrollment, assignments, staff, finance, safeguarding, behaviour, exams, timetable
- Remaining 96 modules: all other domain modules including departments, governance, helpdesk, library, marketing, recruitment, risk management, student support, and more

##### API Input Validation (4 Systems)
Added 7 validation functions to all 4 system validator files:
- `validate_email` — regex format check
- `validate_date` — parse with format string
- `validate_date_range` — ensures start <= end
- `validate_phone` — digits/spaces/+/-/parens, 7-15 digit length
- `validate_string_length` — min/max bounds
- `validate_enum` — value in allowed set
- `validate_positive_int` — positive integer check

##### Keyboard Accessibility (6 GUI Modules)
- **Main GUI shell** — `Escape` (close/back), `Ctrl+D` (dashboard), `Ctrl+L` (logout), `Ctrl+Q` (exit), accelerator labels on menu items
- **Students** — `Return` (edit), `Delete` (delete with confirm), `Ctrl+F` (search), `Ctrl+N` (add new), `Escape` (close dialog)
- **Courses** — `Return` (edit), `Delete` (delete with confirm), `Ctrl+N` (add new), `Escape` (close dialog)
- **Attendance** — `Return` (view record), `Ctrl+N` (create session)
- **Grades** — `Return` (view details), `Escape` (close transcript)
- **Enrollment** — `Return` (view details), `Delete` (drop with confirm), `Ctrl+N` (enroll)

##### Test Coverage (8 New Test Files, 133 Tests)
- **New coverage**: compliance (16 tests), first_aid (17 tests), assets (16 tests), parents_evening (18 tests), parent_portal (15 tests)
- **Extended coverage**: assignments (17 tests), courses (18 tests), grades (16 tests)
- Tests cover CRUD operations, edge cases (not found, duplicates, invalid data), and cascading deletes

---

## [7.29.0] — 2026-03-13

### Fixed — CSP Compliance & Inline Style Cleanup

Resolved Content Security Policy violations blocking inline styles across the web dashboard.

#### CSP Policy Update
- **Added `'unsafe-inline'` to `style-src`** in unified server CSP — required for dynamic data-driven colors (system accents, chart bar widths, status dots)
- **Added `_custom_csp` guard** — `after_request` handler now skips CSP override when a route sets `response._custom_csp = True`, fixing docs route CSP

#### Inline Style Removal (~40 occurrences)
- **Replaced all `style=` attributes** with CSS utility classes (`.sa-hidden`, `.sa-text-center`, `.sa-fw-bold`, `.sa-text-success`, `.sa-text-danger`, `.sa-cursor-pointer`, `.sa-max-w-400`, etc.)
- **Replaced `.style.display` JS assignments** with `classList.toggle("sa-hidden", ...)` across user filtering, notification modal toggle, and search detail panel
- **Replaced `.style.color` JS assignments** with `classList.add/remove` for success/danger feedback in backup status and batch operation results
- **Only 9 dynamic-color inline styles remain** — system accent `background:${color}` values that depend on runtime data

#### Form Validation Fix
- **Removed `required` from notification recipient input** — was causing "invalid form control not focusable" errors when the input was hidden in broadcast mode
- **Changed modal field visibility** to use `.sa-hidden` class toggle instead of `.style.display`

#### New CSS Classes
- Utility classes: `.sa-hidden`, `.sa-text-center`, `.sa-fw-bold`, `.sa-text-success`, `.sa-text-danger`, `.sa-cursor-pointer`, `.sa-max-w-400`, `.sa-w-full`, `.sa-mt-1`, `.sa-mb-075`, `.sa-textarea`
- Component classes: `.picker-bg`, `.picker-logout`, `.picker-body`, `.picker-welcome`, `.topbar-left`, `.sa-notif-count`, `.sa-broadcast-btn`, `.sa-batch-apply-btn`, `.sa-backup-btn`, `.settings-password-hint`, `.settings-submit-btn`, `.settings-account`, `.att-bar-row`, `.att-bar-header`, `.att-bar-count`, `.badge-spaced`

#### Files Changed
- `shared/api/unified_server.py` — CSP `style-src` update + `_custom_csp` guard
- `shared/api/web/static/js/app.js` — replaced ~40 inline styles and ~10 `.style.*` JS assignments
- `shared/api/web/static/css/style.css` — added utility and component classes

---

## [7.28.0] — 2026-03-13

### Added — Superadmin Web Dashboard & Full Feature Implementation

Complete cross-system superadmin dashboard in the web frontend, matching the tkinter GUI's 13-section layout with real backend data.

#### Superadmin App Shell
- **Superadmin detection** — `isSuperadmin()` checks admin role in all 4 systems, auto-routes to `__superadmin__` mode
- **Dark sidebar** with 13 navigation items matching GUI: Dashboard, System Health, User Management, Student Analytics, Notifications, Student Search, Student Journey, Permission Matrix, Audit Log, Backup/Restore, Batch Operations, Active Sessions, Quick Launch
- **"Admin Dashboard" button** in per-system view for superadmins to return to cross-system overview
- **System color scheme** matching GUI: Primary=#e67e22, Secondary=#8e44ad, College=#27ae60, University=#2980b9

#### Dashboard Overview
- **4 color-coded system cards** with student/staff counts, DB size, and online/offline status dots
- **Summary stats row** — total students, staff, transfers, registered users
- **Recent activity feed** with timestamps

#### System Health
- **Health cards per system** with status badge, database exists/size, student/staff count, table count, last activity, DB path

#### User Management
- **Full user table** with username, display name, email, system badges, role badges, active status, last login
- **Triple filtering** — search box, system dropdown, role dropdown with live client-side filtering

#### Student Analytics (fully implemented)
- **Summary cards** — total students, active, transferred, graduated
- **Per-system breakdown** with system-colored cards showing total/active/transferred/graduated/dropped counts
- **Retention statistics table** — system, total, active, retained %, dropped out, dropout %
- **Transfer rates table** — source system, destination, count, rate %
- **Year-over-year trends table** — system, year, student count

#### Notifications (fully implemented)
- **Notification list** with ID, sender system, title, message preview, priority badge, read status, date
- **Unread count badge** with mark-all-read button
- **Send notification modal** — recipient user ID, target system, title, priority, message
- **Broadcast to role modal** — target system, target role, title, priority, message
- **Backend endpoints**: `GET/POST notifications`, `POST mark-read`, `POST send`, `POST broadcast`

#### Student Search (fully implemented)
- **Cross-system search** — searches all 4 system databases for matching students
- **Results table** with system badge, student ID, name, status, year/group
- **Click-to-expand detail panel** showing full student information

#### Student Journey (fully implemented)
- **Timeline visualization** with colored dots and connecting lines per system stage
- **Journey cards** showing system name, student info (ID, status, enrollment date, year group), and academic history
- **Search-first workflow** — finds student, then fetches cross-system journey data

#### Permission Matrix (fully implemented)
- **Matrix table** showing each user's role across all 4 systems (Primary, Secondary, College, University)
- **Role badges** per cell, em-dash for no access

#### Backup / Restore (fully implemented)
- **Backup rows per system** with colored accent stripe, DB name, size, and "Backup Now" button
- **Live status feedback** — success/error messages after backup attempt
- **Backend endpoint**: `POST /web/superadmin/backup` with system parameter

#### Batch Operations (fully implemented)
- **Bulk role change** — select system, current role, new role; applies to all matching users with confirmation dialog
- **Bulk deactivation** — select system and role; deactivates all matching users with confirmation dialog
- **Backend endpoints**: `POST batch/role-change`, `POST batch/deactivate`

#### Active Sessions
- **Session table** with username, display name, created timestamp, expires timestamp

#### Quick Launch
- **4 system launch cards** with system icon, name, description, and launch button
- Clicking enters that system's per-system dashboard as superadmin

#### Backend API Endpoints Added
- `GET /api/web/superadmin/overview` — cross-system summary stats
- `GET /api/web/superadmin/health` — per-system health data
- `GET /api/web/superadmin/sessions` — active auth sessions
- `GET /api/web/superadmin/audit` — audit log entries
- `GET /api/web/superadmin/analytics` — student analytics via AnalyticsService
- `GET /api/web/superadmin/notifications` — notifications via CrossSystemNotificationService
- `POST /api/web/superadmin/notifications/mark-read`
- `POST /api/web/superadmin/notifications/send`
- `POST /api/web/superadmin/notifications/broadcast`
- `GET /api/web/superadmin/search` — cross-system student search via JourneyService
- `GET /api/web/superadmin/journey` — student journey data via JourneyService
- `GET /api/web/superadmin/permissions` — permission matrix from auth DB
- `POST /api/web/superadmin/backup` — database backup
- `GET /api/web/superadmin/backup/info` — database info for backup page
- `POST /api/web/superadmin/batch/role-change`
- `POST /api/web/superadmin/batch/deactivate`

#### CSS Added
- Superadmin layout: `.sa-app`, `.sa-sidebar`, `.sa-header`, `.sa-brand`, `.sa-topbar`, `.sa-content`, `.sa-welcome`
- System cards: `.sa-system-cards`, `.sa-sys-card`, `.sa-sys-accent`, `.sa-sys-body`, `.sa-sys-dot`
- Summary stats: `.sa-summary-row`, `.sa-stat-card`, `.sa-stat-accent`
- Health cards: `.sa-health-grid`, `.sa-health-card`, `.sa-health-accent`
- Activity feed: `.sa-activity-list`, `.sa-activity-item`
- User management: `.sa-users-toolbar`, `.sa-filter-group`
- Analytics: `.sa-analytics-cards`, `.sa-analytics-card`
- Notifications: `.sa-notif-toolbar`, `.sa-notif-badge`
- Search: `.sa-search-bar`, `.sa-search-detail`
- Journey timeline: `.sa-journey-stage`, `.sa-journey-dot-col`, `.sa-journey-dot`, `.sa-journey-line`, `.sa-journey-card`
- Permissions: `.sa-perm-table`, `.sa-perm-check`, `.sa-perm-cross`
- Backup: `.sa-backup-row`, `.sa-backup-accent`, `.sa-backup-info`
- Batch operations: `.sa-batch-form`, `.sa-batch-result`
- Quick launch: `.sa-launch-grid`, `.sa-launch-card`
- Responsive breakpoints for all new sections at 768px and 480px

#### New SVG Icons
- `activity`, `database`, `zap`, `eye`, `layers`, `archive`, `play`

#### Files Changed
- `shared/api/web/routes.py` — 16 new superadmin API endpoints
- `shared/api/web/static/js/app.js` — superadmin app shell + 13 page implementations (~900 lines added)
- `shared/api/web/static/css/style.css` — comprehensive superadmin styles (~200 lines added)

---

## [7.27.0] — 2026-03-13

### Removed — Old Web Portal

Consolidated the standalone web portal into the unified API server's web frontend (added in 7.26.0).

- **Deleted `shared/web_portal/`** — removed `app.py`, `__init__.py`, and `__pycache__/` (old Jinja2-based portal on port 8080)
- **Removed `[5] Portal` menu option** from `run.py` interactive launcher
- **Removed `--portal` CLI flag** from `run.py` argument parser
- **Removed `run_unified_portal()` function** and all portal entries from the dispatch table
- **Updated university system routes** — root redirect and `web_portal` endpoint now point to `/web/login`
- The web dashboard is now accessible via the API server (`--api` / option 3) at `/web/login`

---

## [7.26.0] — 2026-03-13

### Added — Web Login & Dashboard Frontend

Full browser-based login screen and dashboard served from the unified API server at `/web/login`.

#### Login & Authentication
- **Login page** with username/password form, styled with gradient background and Inter font
- **MFA support** — 6-digit TOTP verification screen with back-to-login option
- **JWT token management** — access + refresh tokens stored in localStorage with automatic refresh on 401
- **Session persistence** — stays logged in across page reloads

#### System Picker (Superadmin)
- **2x2 grid layout** showing all 4 systems (University, College, Secondary, Primary) with icons, role badges, and descriptions
- **Sign Out button** positioned in top-right corner
- **Single-system users skip the picker** — users with access to only one system go straight to the dashboard

#### Dashboard
- **Stats cards** — total students/pupils, courses, attendance rate, assessments (live from system databases)
- **Attendance breakdown** — bar chart showing present/late/absent percentages
- **Quick actions** — one-click navigation to Students, Courses, Attendance, Grades, Reports
- **Recent enrollments table** with student name, course, date, and status badges

#### Data Pages
- **Students/Pupils** — full list with ID, name, email, year/group, status; client-side search filtering
- **Courses** — code, name, department, credits, status
- **Attendance** — date, student, course, status with colour-coded badges
- **Grades** — student, course, assessment type, grade, date
- **Reports** (staff/admin) — aggregate stats, grade distribution, attendance by status
- **User Management** (admin) — all auth users with system/role badges, active status, search

#### Account Settings
- **Change password** form with validation (12+ chars, uppercase, lowercase, digit, special)
- **Account info** display — username, display name, user ID, system access

#### Architecture
- **SPA** — single `index.html` with vanilla JS (`app.js`), no framework dependencies
- **Flask blueprint** (`shared/api/web/routes.py`) serves static files and data API endpoints
- **Data endpoints** query real system SQLite databases: `/api/web/dashboard/<system>`, `/api/web/students/<system>`, etc.
- **Role-based access control** — students can't access student list or reports; only admins see user management
- **Responsive sidebar** with collapsible mobile menu
- **CSP updated** to allow Google Fonts (Inter) from `fonts.googleapis.com` / `fonts.gstatic.com`

#### Files Added
- `shared/api/web/__init__.py`, `routes.py` — blueprint + 7 data endpoints
- `shared/api/web/templates/index.html` — SPA entry point
- `shared/api/web/static/css/style.css` — full responsive stylesheet
- `shared/api/web/static/js/app.js` — complete SPA (~600 lines)

---

## [7.25.0] — 2026-03-13

### Changed — Unified API & Portal Architecture

Major consolidation of API and portal infrastructure into a single shared module with unified authentication.

#### API Consolidation
- **Moved all API files** from 4 separate locations (`college_system/api/`, `secondary_school/api/`, `primary_school/api/`, `university_system/api/`) into `shared/api/{college,secondary,primary,university}/` (225 files)
- **Fixed all imports** across the codebase to reference the new `education_system.shared.api.*` paths
- **Removed old `api/` directories** from each subsystem

#### Unified API Server
- **Single API server** (`shared/api/unified_server.py`) serves all systems on one port (5000)
- System routes mounted under prefixed paths: `/api/college/*`, `/api/school/*`, `/api/primary/*`
- **Removed system selection menu** for API mode — selecting `[3] API` now launches the unified server directly
- Index route at `/` returns system endpoints and auth URL

#### Unified API Authentication
- **Single login endpoint** (`shared/api/auth.py`) at `POST /api/auth/login` for all systems
- JWT contains the user's full system access list (`systems: [{system_key, role}, ...]`)
- Access + refresh token pair issued on login with token rotation on refresh
- `POST /api/auth/mfa/verify` — MFA challenge completion
- `POST /api/auth/refresh` — token refresh with rotation
- `POST /api/auth/register` — admin-only user creation with multi-system access
- `token_required`, `role_required`, `system_required` decorators for route protection
- Per-system `auth.py` files now delegate to the shared auth module
- Old per-system auth blueprints removed from `ALL_BLUEPRINTS`

#### Unified Web Portal
- **Single portal** at port 8080 with unified login (no system dropdown)
- After login, users with multiple systems see a card-based system picker with icons
- Users with single-system access skip the picker and go straight to the dashboard
- "Switch System" nav link to change between systems without logging out
- Portal resolves each system's DB path dynamically via `_resolve_db_path()`
- Root `/` and `/portal` routes redirect to `/portal/login`
- Login validates user has access to the selected system

### Removed
- `college_system/api/` directory (moved to `shared/api/college/`)
- `secondary_school/api/` directory (moved to `shared/api/secondary/`)
- `primary_school/api/` directory (moved to `shared/api/primary/`)
- `university_system/api/` directory (moved to `shared/api/university/`)
- Per-system auth blueprints from route registrations
- System selection menu when launching API mode
- Per-system portal launchers (`run_college_portal`, `run_school_portal`, etc.) replaced by `run_unified_portal`

---

## [7.24.0] — 2026-03-13

### Added — 20 Shared Infrastructure Improvements

Major infrastructure expansion across the entire education system, adding shared modules in `education_system/shared/` that benefit all four subsystems (university, college, secondary, primary).

#### Architecture & Patterns
- **DB context manager** (`shared/auth/db.py`): `get_connection()` context manager with auto-commit/rollback and guaranteed `conn.close()`
- **Base service class** (`shared/base/service.py`): `BaseService` with generic CRUD operations (get_by_id, list_all, search, insert, update, delete), column validation, and connection management
- **Base GUI classes** (`shared/base/gui.py`): `BaseModuleGUI` with tabbed layout, search bar, status bar, and treeview helpers; `BaseCRUDDialog` with auto-generated modal forms
- **Migration framework** (`shared/migrations/runner.py`): `MigrationRunner` with versioned SQL/Python migrations, `_migrations` tracking table, and `@migration` decorator

#### API & Security
- **Rate limiting** (`shared/api/rate_limiter.py`): Per-IP token-bucket rate limiter with `X-RateLimit-*` headers, `429` responses, and Flask `init_app()` integration — enabled on college, secondary, and primary API servers
- **JWT refresh tokens** (`shared/api/jwt_utils.py`): `JWTManager` with access/refresh token pairs, token rotation on refresh, revocation, and expired token cleanup
- **Health check endpoints** (`shared/api/health.py`): `/api/health` (full), `/api/health/ready`, `/api/health/live` Flask blueprint — integrated into all 3 Flask API servers, Dockerfile, and docker-compose healthcheck
- **API middleware** (`shared/api/middleware.py`): `X-Request-ID` tracking, `X-Response-Time` header, and request logging — registered on college, secondary, and primary APIs
- **Async API adapter** (`shared/api/async_adapter.py`): `AsyncFlaskRunner` wrapping Flask WSGI in aiohttp with `run_in_executor()` and `make_async_handler()` decorator

#### Observability & Compliance
- **Centralized audit logging** (`shared/audit/logger.py`): `AuditLogger` with `AuditAction` enum (auth, data, GDPR, safeguarding events), SQLite-backed append-only `audit_log` table with indexed queries

#### Reporting & Data
- **Reporting engine** (`shared/reporting/engine.py`): `ReportEngine` generating PDF (reportlab), Excel (openpyxl), and CSV reports with consistent branding across all systems
- **Student data portability** (`shared/transfer/portability.py`): `StudentDataExporter`/`StudentDataImporter` supporting JSON, CSV, and UK Common Transfer File (CTF) v18.0 XML format
- **Dashboard analytics engine** (`shared/analytics/engine.py`): `AnalyticsEngine` with `attendance_summary()`, `grade_distribution()`, `at_risk_students()`, and `system_overview()` methods

#### Real-Time & Portal
- **Real-time notifications** (`shared/notifications/realtime.py`): `NotificationBroker` with Server-Sent Events (SSE), per-user and broadcast channels, keepalive pings
- **Self-service web portal** (`shared/web_portal/app.py`): Flask-based responsive portal with login, dashboard stats, attendance badges, and grades view — launchable via `run.py --portal`

#### Testing
- **Cross-system integration tests** (`shared/tests/test_cross_system.py`): 9 test classes covering shared auth, audit logging, migrations, portability, reporting, rate limiting, health checks, and demo seeding
- **GUI testing utilities** (`shared/testing/gui_helpers.py`): `GUITestCase` with auto Tk root, `pump_events()`, widget finders, `simulate_click()`/`simulate_type()`, and `get_treeview_data()`
- **Service test helpers** (`shared/testing/service_helpers.py`): `ServiceTestCase` with temp DB, schema init, and assertion helpers

#### DevEx & CI/CD
- **Database seeding CLI** (`shared/seeding/seeder.py`): `DemoSeeder` generating realistic UK students, courses, enrollments, attendance, and grades per system — launchable via `run.py --seed`
- **Makefile** (project root): Multi-system dev commands — `make test`, `make lint`, `make seed`, `make portal`, `make docker-up`, `make ci`, per-subsystem test targets
- **CI coverage tracking** (`.github/workflows/ci.yml`): Tests across all 5 test directories with `--cov-fail-under=30`, HTML/XML coverage artifacts, `--timeout=60`, `-m "not slow and not gui"` markers

### Changed
- Docker healthcheck updated to use `/api/health/live` endpoint
- `docker-compose.yml` app service now includes healthcheck configuration
- `run.py` extended with `--portal` and `--seed` CLI flags and portal launcher functions

---

## [7.23.0] — 2026-03-12

### Added — Super Admin Dashboard: 15 Features

Major expansion of the shared superadmin dashboard (`shared/gui/superadmin_dashboard.py`) from 8 sidebar sections to 15, with full backend support in `shared/admin_portal/admin_service.py`.

#### User Management Actions (CRUD)
- Create User dialog with username, display name, email, password, and per-system role checkboxes
- Edit User dialog to update display name, email, active status, and system/role assignments
- Reset Password button with bcrypt re-hashing and legacy salt cleanup
- Deactivate User button with confirmation prompt
- All four actions accessible from the User Management toolbar

#### Send Notifications & Broadcast
- Send Notification dialog: target a specific user by ID with title, message, priority, and system
- Broadcast to Role dialog: send an announcement to all users with a given role in a target system
- Both dialogs wired to `CrossSystemNotificationService.send()` and `send_to_role()`

#### Export Buttons
- Analytics page: "Export CSV" button calls `AnalyticsService.export_summary_csv()` with file-save dialog
- Audit Log page: "Export CSV" button exports filtered audit entries to CSV

#### Audit Log Filtering
- Type filter dropdown (All / notification / transfer)
- Date range inputs (From / To) defaulting to last 30 days
- Text search on description and details fields
- Backend `get_audit_summary()` enhanced with `type_filter`, `search_text`, `date_from`, `date_to` parameters (backward-compatible)

#### Auto-Refresh with Dialog Awareness
- Dashboard and System Health sections refresh every 60 seconds
- Refresh defers automatically when a modal dialog (Toplevel) is open to prevent UI conflicts
- Timer properly cancelled on logout and window close

#### Backup / Restore Section
- Per-system database backup buttons creating timestamped copies via `shutil.copy2`
- Shared auth database backup button
- Status labels showing backup file names on success

#### Health Alert Thresholds
- Configurable thresholds: maximum DB size (MB) and minimum active student count
- Live alert display showing warnings for systems exceeding thresholds or reporting errors
- Alerts refresh on threshold save

#### Permission Matrix View
- New sidebar section showing all users in a table with one column per system (Primary, Secondary, College, University)
- Each cell shows the user's role in that system or an em dash if not assigned
- Provides an at-a-glance view of cross-system permissions

#### Student Journey Timeline
- Search by student name or ID across all 4 systems
- Visual vertical timeline with colour-coded dot and connecting line per stage
- Each stage card shows system name, student ID, status, enrollment date, year group
- Academic history entries displayed as sub-items

#### Drill-Down Analytics
- Year-over-year trends table showing student counts by year per system
- Cross-system comparison cards combining health data (students, staff, DB size) with retention metrics (retained %, dropout %)

#### Batch Operations Section
- Bulk Role Change: select system, current role, and new role — applies to all matching users with confirmation
- Bulk Deactivation: select system and role — deactivates all active matching users with confirmation

#### Active Sessions Section
- Table of active sessions showing username, user ID, token preview, created/expires timestamps
- Force Logout button to terminate all sessions for a selected user
- Refresh button to reload session data
- Backend: `get_active_sessions()` and `force_logout_user()` methods added to AdminService

#### i18n Framework
- `_t(key, default)` translation helper function with JSON locale file support
- `load_translations(locale)` loads from `shared/data/locales/<locale>/superadmin_dashboard.json`
- All navigation labels and header title wired through `_t()` with English defaults
- Ready for locale JSON files to enable multi-language support

#### About Dialog
- "About" button in header bar
- Shows application name, version (v7.22.0), description, and tech stack

### Added — Shared Service Tests (38 tests)

New test suite at `education_system/shared/tests/` covering the three core shared services:

#### AdminService (20 tests)
- System health: returns all 4 systems, counts students and staff correctly
- User management: get summary, get all users, filter by system/role, create user, duplicate detection, update user, deactivate, reset password, update system assignments
- Backup: creates timestamped file, raises on invalid system
- Audit log: empty results, filter combinations
- Sessions: get active sessions, force logout
- System config: returns correct structure

#### AnalyticsService (10 tests)
- Summary: total students, active/graduated/transferred counts, per-system breakdown
- Retention: stats for all 4 systems with percentage calculations
- Year trends: returns data grouped by enrollment year
- Transfer rates: returns list (empty when no transfer history table)
- CSV export: produces valid CSV string with all sections

#### CrossSystemNotificationService (8 tests)
- Send: returns notification dict, respects priority parameter
- Broadcast: sends to all users with target role (verified count)
- Retrieve: empty unread, unread after send, unread count, get all with limit
- Mark read: single notification, mark all read

### Changed — Shared Module Exports
- `shared/cross_system/__init__.py` now exports `JourneyService`
- `shared/notifications/__init__.py` now exports `CrossSystemNotificationService`

### Changed — Configuration
- `pyproject.toml`: added `education_system/shared/tests` to pytest `testpaths`

### Added — AdminService Backend Methods
- `create_user(username, display_name, email, password, systems_roles)` — bcrypt-hashed, with user_systems
- `update_user(user_id, display_name, email, is_active)` — partial updates
- `deactivate_user(user_id)` — sets is_active=0
- `reset_password(user_id, new_password)` — bcrypt hash, clears legacy_salt
- `update_user_systems(user_id, systems_roles)` — replaces system/role assignments
- `backup_database(system)` — timestamped shutil.copy2 backup
- `get_active_sessions()` — lists active sessions with username join
- `force_logout_user(user_id)` — deletes all sessions for a user

---

## [7.22.0] — 2026-03-12

### Fixed — College Student Creation Bugs

#### Foreign Key Constraint Failed on Student Creation
- `student_gui.py` `_on_add()` called `auth.create_user()` which creates a user in the **shared auth DB** (`auth.db`), then set that shared auth user ID on the student record — but `students.user_id` FK references the **college local** `users` table where that ID doesn't exist
- Fix: now creates user in both shared auth DB (with `systems=[("college", "student")]`) and college local `users` table, using the local ID for the student FK

#### Unique Constraint Failed on `students.student_id`
- `_generate_student_id()` used `ORDER BY id DESC LIMIT 1` to find the last student ID — if students were deleted, the highest auto-increment `id` row might not have the highest `student_id` number, causing collisions
- Fix: now uses `MAX(CAST(REPLACE(student_id, prefix, '') AS INTEGER))` to find the actual highest student ID number

#### Password Too Short for Account Creation
- Generated password format `{FirstName}{4digits}!` (e.g. "Tom1234!") was only 9 characters, below the 12-character minimum
- Fix: password now uses `{FirstName}{LastName}{4digits}!` with a minimum length guarantee

### Fixed — Transfer Notifications Not Appearing in Email Inbox

Transfer notifications were written to `notifications` tables but admins check their **email/messages inbox** which reads from separate tables (`messages`, `emails`, `email_log`).

#### All Three Transfer Paths Updated
- **University→College**: now also inserts into college `messages` table alongside `notifications`
- **College→Secondary**: now also inserts into secondary `emails` table alongside `notifications`
- **Secondary→Primary**: now also inserts into primary `email_log` table alongside `notifications`

### Fixed — Messaging & Notifications Show Empty for Logged-In Admin (College)

#### Shared Auth vs Local User ID Mismatch in GUI Queries
- `MessageFrame._get_user_id()` and `NotificationFrame._get_user_id()` returned the **shared auth** user ID (e.g. 30 for `admin1`) but queried the college local `messages`/`notifications` tables which use **local** user IDs (e.g. 8)
- Fix: both frames now resolve the local college user ID via username lookup in the college `users` table
- Also fixed guard that skipped lookup when `db_path` is `None` (always the case when launched via `run.py` — `connect(None)` correctly falls back to the default DB path)

---

## [7.21.0] — 2026-03-12

### Changed — College System Sidebar Navigation

The college system main GUI has been redesigned with a persistent sidebar navigation panel, replacing the flat grid of buttons on the dashboard.

#### Sidebar Layout
- Two-panel layout using `tk.PanedWindow`: scrollable sidebar (left, 250px) + content area (right)
- Dark-themed sidebar (`#1a2332`) with 14 collapsible sections grouping all ~130 modules:
  - Students & Learning, Courses & Curriculum, Teaching & Quality, Pastoral & Welfare, Exams & Reports, Staff, Communication, Student Life, Parents & Community, Finance & Resources, Administration, Compliance & Safety, Accessibility, Cross-System Tools
- Section headers show item count badge and toggle with click (arrow indicator)
- Buttons highlight on hover and show active state (blue) for the current module
- Breadcrumb bar at top of content area shows current location (e.g. "Staff > Cover")
- Role-based filtering — sections with no visible items for the user's role are hidden
- Sidebar hidden on login screen, appears after authentication
- Mousewheel scrolling works anywhere over the sidebar (bound to outer frame, not just canvas)
- Scroll region updates dynamically when sections expand/collapse

#### Dashboard Simplified
- Navigation buttons removed from dashboard (now in sidebar)
- Quick Actions row added with 6 shortcut buttons (Students, Courses, Attendance, Timetable, Messages, Reports)
- Stat cards now have per-card accent colours
- "Getting Started" tip card explains sidebar navigation

### Fixed — Multiple Bug Fixes

#### Auth Object Not Propagated to Frames (College System)
- When launching college via universal login, `shared_auth` replaced `app._auth` but all frames still held references to the old, never-logged-in `UserAuth` — causing "not logged in" errors
- Fix: after setting `app._auth = shared_auth`, all frame `_auth` references are now updated

#### NoneType Subscript Errors in College GUI Frames
- `message_gui.py` — added `_get_user_id()` helper with null guard on `current_user` (4 access points)
- `notification_gui.py` — same pattern (3 access points)
- `assignment_gui.py` — inline null guards on `current_user` access (3 lines)
- `timetable_gui.py` — inline null guard (1 line)
- Root cause: `refresh()` called during frame init before login, when `current_user` is `None`

#### Student Self-Service Portal Auth Handling
- `portal_gui.py` — added `_resolve_auth()` helper to handle `auth` being either a dict or `UserAuth` object

#### Student Dialog Frame Padding Error
- `student_gui.py` — fixed `pady=(10, 0)` in `tk.Frame` constructor (tuples only valid in `pack()`/`grid()`)

### Fixed — Cross-System Transfer Notifications Not Delivered

Transfer notifications were being sent via the source system's email service to admin email addresses that don't exist in that system's user database, so no inbox messages were created.

#### University→College Transfer
- Replaced university `send_email()` call with two-step notification:
  1. Cross-system notification via `CrossSystemNotificationService.send_to_role()` (visible in Cross-System Notifications module)
  2. College-local notification inserted directly into college DB `notifications` table, using username lookup to resolve local user IDs

#### College→Secondary Transfer
- Same two-step pattern: cross-system notification + secondary-local notification
- Replaced `NotificationService(self._db_path).send()` which was sending to shared auth user IDs (wrong DB)

#### Secondary→Primary Transfer
- Same two-step pattern: cross-system notification + primary-local notification
- Replaced `EmailService.send()` which required a sender_id that wasn't always available
- Primary notifications use `notification_type='Info'` column (different schema from other systems)

---

## [7.20.0] — 2026-03-12

### Changed — Legacy Language Selectors Removed & Switch System Restricted

#### Legacy Language Selectors Removed
- Removed "Change Language" button from university system GUI header
- Removed Language menu from college system File menu
- Replaced legacy `gui_language_selector.py` and `language_selector.py` in the university system with thin shims that delegate to the shared i18n module — 70+ files that import `create_language_menu_button` or `show_gui_language_selector` continue to work without changes
- University no longer shows its own language selector on startup — uses the shared one chosen at `run.py` launch
- College i18n automatically synced with the shared language choice

#### Switch System Button — Superadmin Only
- "Switch System" button/menu item now only visible to superadmin users (admin in all 4 systems) across all 4 systems:
  - Primary: sidebar button conditionally rendered
  - Secondary: sidebar button conditionally rendered
  - College: File menu item starts disabled, enabled after login for superadmin
  - University: header button conditionally rendered
- `systems` list now passed through to user dicts in primary, secondary, and college launchers so superadmin detection works
- "Super Admin Dashboard" button added to all 4 switch system dialogs (visible only to superadmin)

### Fixed
- Language selector GUI no longer breaks subsequent tkinter windows — standalone mode now uses `tk.Tk` directly instead of a `Toplevel` on a temporary hidden root, ensuring clean Tcl interpreter state for the login window
- Fixed `__superadmin__` switch routing in `run.py` — no longer falls through to "Switching to..." print and system access check; handled immediately via `continue` back to the dashboard handler

---

## [7.19.0] — 2026-03-12

### Added — Unified i18n Support Across All Systems

Language selection is now shown at the very start of `run.py`, before the login screen, and the choice is shared across all 4 education systems.

#### 13 Supported Languages
English, Español, Français, Deutsch, 中文, العربية, Português, Русский, 日本語, 한국어, Cymraeg (Welsh), Polski, اردو (Urdu)

#### Shared i18n Module (`education_system/shared/i18n/`)
- `core.py` — unified i18n engine with dot-notation key lookup, deep merge of multiple locale directories, fallback chain (current lang → English → default → key), format string support
- `selector_gui.py` — tkinter language selector dialog (400x500, dark header, listbox with native language names)
- `selector_cli.py` — CLI language selector menu with numbered list
- Language preference persisted to `shared/data/config/language_config.json`
- `add_locale_dir()` API allows each subsystem to layer system-specific translations on top of shared ones

#### Shared Locale Files (`education_system/shared/data/locales/`)
- `{lang}/common.json` for all 13 languages
- Covers: login, MFA, system picker, common UI labels, shared module names, roles, switch system, superadmin dashboard strings

#### Integration
- `run.py` shows language selector immediately on startup (GUI dialog for GUI mode, CLI menu for CLI mode, silent load for API/test)
- University system no longer shows its own language selector — uses the shared choice
- College system i18n synced with shared choice via `_init_college_i18n()`
- Secondary and primary school systems can now access translations via `from education_system.shared.i18n import t`

#### New Files
- `education_system/shared/i18n/__init__.py`
- `education_system/shared/i18n/core.py`
- `education_system/shared/i18n/selector_gui.py`
- `education_system/shared/i18n/selector_cli.py`
- `education_system/shared/data/locales/{en,es,fr,de,zh,ar,pt,ru,ja,ko,cy,pl,ur}/common.json`

---

## [7.18.0] — 2026-03-12

### Added — Super Admin Dashboard

Superadmin users now see a full management dashboard instead of just the system selection screen.

#### Dashboard Features
- **Overview**: 4 color-coded system cards (student/staff counts, DB size, status), summary metrics, recent activity feed
- **System Health**: per-system status cards with DB info, counts, last activity, and status badges
- **User Management**: filterable Treeview of all users across systems with system/role/search filters
- **Student Analytics**: cross-system student counts, transfer rates, retention statistics
- **Cross-System Notifications**: inbox with unread count badge and mark-all-read
- **Student Search**: search across all 4 databases, view details on selection
- **Audit Log**: recent transfers and cross-system activity timeline
- **Quick Launch**: 4 large color-coded buttons to drill into individual systems; returns to dashboard when system is closed

#### Integration
- `UniversalLoginWindow` detects superadmin (admin in all 4 systems) and routes to dashboard via `system_key="__superadmin__"`
- `run.py` dispatch loop handles `__superadmin__` by launching `SuperAdminDashboard` window
- After closing a launched system, superadmin returns to the dashboard (not exit)
- Logout from dashboard returns to login screen

#### New Files
- `education_system/shared/gui/superadmin_dashboard.py` — `SuperAdminDashboard(tk.Tk)` standalone window

---

## [7.17.0] — 2026-03-12

### Added — 14 Cross-System Shared Modules (GUI + CLI)

Comprehensive suite of shared tools available across all 4 education systems, each with both a tkinter GUI sidebar module and a CLI text-menu interface.

#### Data & Reporting
- **Cross-System Analytics Dashboard** (`shared/analytics/`) — aggregate metrics across all systems: total students, transfer rates, retention stats, year-over-year trends, CSV export
- **Student Outcome Tracking** (`shared/outcomes/`) — track what happens to students after they transfer: destination performance, grade averages, progression statistics
- **Predictive Alerts** (`shared/predictive/`) — flags at-risk students based on attendance (<80%), low grades, and transfer instability from previous systems; risk scored as High/Medium/Low

#### Transfer Improvements
- **Bulk Transfer** (`shared/bulk_transfer/`) — transfer multiple students at once (e.g., entire Year 6 class to secondary); auto-detects eligible students by year group, extracts academic history in batch
- **Transfer Documents** (`shared/transfer_docs/`) — generates formatted transition reports with student info, academic summary, attendance, SEN status, and transfer details; save to file
- **Reverse Lookup** (`shared/reverse_lookup/`) — from a source system, find where transferred students ended up; shows destination system, current status, grade summary, and aggregate destination statistics

#### Communication
- **Parent Account Continuity** (`shared/parent_continuity/`) — when a student transfers, detect unlinked parent accounts and link them to the destination system in the shared auth DB
- **Cross-System Calendar** (`shared/calendar/`) — shared events calendar stored in auth DB; supports event types (open day, transition, training, holiday, meeting), per-system targeting, month view, and upcoming events
- **Inter-System Messaging** (`shared/messaging/`) — teacher-to-teacher messaging about specific students across systems; inbox/sent/compose with staff directory lookup per system

#### Admin & Compliance
- **Central Admin Portal** (`shared/admin_portal/`) — superadmin dashboard showing system health (DB sizes, student/staff counts), cross-system user management, audit log of transfers and notifications
- **GDPR Compliance** (`shared/gdpr/`) — cross-system student data search, Subject Access Request report generation, student data anonymisation (with typed-name confirmation), data retention reports
- **Shared Document Storage** (`shared/documents/`) — documents (EHCPs, medical, safeguarding, transcripts) that follow students across systems; file upload/download with metadata stored in auth DB

#### Student-Facing
- **Student Self-Service Portal** (`shared/student_portal/`) — students view their own journey, records (grades/attendance per system), and submit record requests (transcript, data export, correction); admin can view and resolve pending requests
- **Digital Transcript** (`shared/transcript/`) — auto-generates a comprehensive transcript pulling data from all systems attended; includes personal info, educational history per system, grades, attendance percentages, qualifications; save to file or copy to clipboard

#### Module Registration
- All 14 modules registered in GUI sidebars of all 4 systems (primary, secondary, college, university)
- All 14 modules registered in CLI menus of all 4 systems under "Cross-System Tools"
- Role access: admin gets all modules; staff/teachers get all except Central Admin Portal and GDPR Compliance; students get Self-Service, Transcript, and Calendar; parents get Calendar and Transcript

#### New Files (42 files across 14 packages)
Each package in `education_system/shared/` contains: `__init__.py`, `*_service.py`, `*_gui.py`, `*_cli.py`
- `shared/analytics/` (analytics_service, analytics_gui, analytics_cli)
- `shared/outcomes/` (outcomes_service, outcomes_gui, outcomes_cli)
- `shared/predictive/` (predictive_service, predictive_gui, predictive_cli)
- `shared/bulk_transfer/` (bulk_transfer_service, bulk_transfer_gui, bulk_transfer_cli)
- `shared/transfer_docs/` (transfer_docs_service, transfer_docs_gui, transfer_docs_cli)
- `shared/reverse_lookup/` (reverse_lookup_service, reverse_lookup_gui, reverse_lookup_cli)
- `shared/parent_continuity/` (parent_service, parent_gui, parent_cli)
- `shared/calendar/` (calendar_service, calendar_gui, calendar_cli)
- `shared/messaging/` (messaging_service, messaging_gui, messaging_cli)
- `shared/admin_portal/` (admin_service, admin_gui, admin_cli)
- `shared/gdpr/` (gdpr_service, gdpr_gui, gdpr_cli)
- `shared/documents/` (document_service, document_gui, document_cli)
- `shared/student_portal/` (portal_service, portal_gui, portal_cli)
- `shared/transcript/` (transcript_service, transcript_gui, transcript_cli)

#### Schema Changes
- `cross_system_events` table added to shared auth DB (calendar)
- `cross_system_messages` table added to shared auth DB (messaging)
- `cross_system_documents` table added to shared auth DB (documents)
- `student_record_requests` table added to shared auth DB (student portal)

---

## [7.16.0] — 2026-03-12

### Added — Deep Cross-System Integration

Four major features that fully link all four education systems (Primary → Secondary → College → University) into a unified platform.

#### 1. Academic History Transfer
- When importing a student from a previous system, their academic history (grades, attendance, exam results) is now automatically extracted and stored
- **Secondary ← Primary**: Extracts assessments, SATs results, phonics results, and attendance records
- **College ← Secondary**: Extracts grades, exam results, and attendance records
- **University ← College**: Extracts grades and attendance session/record data
- History stored as JSON in new `academic_transfer_history` table in each destination database
- Extraction failures are handled gracefully and never block the transfer process

#### 2. Previous System ID Tracking
- New `previous_system` and `previous_system_id` columns added to the `students` table in secondary, college, and university databases
- When a student is imported, these fields are populated to maintain a link back to their record in the source system
- Enables tracing a student's full path across systems (e.g., `previous_system='primary'`, `previous_system_id='PRI0001'`)
- Schema migration runs automatically on startup — existing records are unaffected

#### 3. Cross-System Student Journey Dashboard
- New shared module (`education_system/shared/cross_system/`) available in all 4 systems' sidebars
- **Search**: Find a student across all 4 databases by name
- **Journey Timeline**: Visual timeline showing each stage of a student's educational journey
- Each stage displays: system name, student ID, year group, status, and key dates
- Academic transfer history shown inline when available
- Follows `previous_system_id` links to reconstruct the full path automatically
- Handles missing databases gracefully (e.g., if only college and university are deployed)

#### 4. Shared Cross-System Notifications
- New shared module (`education_system/shared/notifications/`) for admin-to-admin messaging across systems
- `CrossSystemNotificationService`: send notifications to specific users or broadcast to a role in any system
- `CrossSystemNotificationsFrame`: sidebar GUI with inbox, detail view, and compose dialog
- Notification data stored in shared auth database (`cross_system_notifications` table)
- Admin and staff users can send messages; all users can view their notifications
- Unread count badge, mark-as-read, mark-all-read functionality

#### Module Registration
- "Student Journey" and "Cross-System Notifications" added to admin/staff sidebar in all 4 systems
- Both modules follow the standard frame pattern (`parent, db_path=None, auth=None`)

#### New Files
- `education_system/shared/transfer/academic_history.py` — history extraction functions for all 3 source systems
- `education_system/shared/cross_system/__init__.py`
- `education_system/shared/cross_system/journey_service.py` — multi-DB query service
- `education_system/shared/cross_system/journey_dashboard.py` — tkinter journey dashboard GUI
- `education_system/shared/notifications/__init__.py`
- `education_system/shared/notifications/service.py` — cross-system notification service
- `education_system/shared/notifications/gui.py` — notification inbox GUI

#### Schema Changes
- `academic_transfer_history` table added to secondary, college, and university databases
- `previous_system TEXT` and `previous_system_id TEXT` columns added to `students` table in secondary, college, and university
- `cross_system_notifications` table added to shared auth database

---

## [7.15.0] — 2026-03-12

### Added — Admin Notification on Student Transfer

When a student is transferred between systems, the admin user(s) of the source system are now automatically notified.

#### University System (student imported from College)
- After marking a college student as transferred, emails all active college admin users via the university email service (`send_email`)
- Email includes: student name, old college student ID, new university student ID, and transfer confirmation

#### College System (student imported from Secondary School)
- After marking a secondary student as transferred, sends an in-app notification to all active secondary school admin users via `NotificationService.send()`
- Notification includes: student name, old secondary ID, new college student ID

#### Secondary School System (student imported from Primary School)
- After marking a primary pupil as transferred, sends an internal email to all active primary school admin users via `EmailService.send()`
- Email includes: pupil name, old primary pupil ID, new secondary student ID

#### Implementation Details
- Admin users are looked up from the shared auth database (`user_systems` table) by `system_key` and `role = 'admin'`
- All notification sending is wrapped in try/except so failures never block the transfer process
- Each system uses its native messaging mechanism (university: SMTP/DB email, college: notifications, secondary: internal email)

---

## [7.14.0] — 2026-03-12

### Added — MFA Setup for College, Secondary and Primary Systems

#### Secondary School System
- **MFA Verify Dialog** — new `MFAVerifyDialog` shown during login when a user has MFA enabled; accepts 6-digit TOTP codes or recovery codes
- **MFA Settings module** — new sidebar module accessible to all roles (admin, teacher, student) for setting up, disabling, and managing TOTP-based MFA
- **Login integration** — `LoginWindow._on_login()` now checks for `mfa_required` in the auth response and presents the verify dialog before completing login

#### Primary School System
- **MFA Verify Dialog** — same TOTP verification dialog integrated into the primary school login flow
- **MFA Settings module** — new sidebar module accessible to all roles (admin, staff, parent) for managing MFA
- **Login integration** — `LoginWindow._login()` now handles the MFA challenge flow

#### College System (already had MFA)
- College system already had full MFA support (`MFAVerifyDialog`, `MFASettingsFrame`, login integration) — no changes needed

#### Shared Components Used
- Both new MFA GUIs delegate to the existing shared `MFAService` (`education_system/shared/auth/mfa_service.py`) for TOTP setup, verification, and recovery code management
- Each system's `infrastructure/auth/mfa_service.py` re-exports the shared service
- MFA data stored in the central shared auth database (`shared/data/db_files/auth.db`)

#### MFA Settings Features (both systems)
- Current MFA status display (enabled/disabled)
- Recovery code count
- Setup button — generates TOTP secret, provisioning URI, and 10 recovery codes
- Disable button — removes all MFA data with confirmation prompt
- Refresh button to update status

---

## [7.13.0] — 2026-03-12

### Added — Cross-System Student Import on Create

Students can now be imported from the previous education stage when creating a new student record, enabling a seamless progression pipeline across all four systems.

#### University System
- **"Import from College System"** button added to the Create Student dialog (personal info section)
- Opens a searchable selection dialog listing all active students from the college database (`sixthform.db`)
- Autofills first name, last name, and date of birth; user completes remaining fields (title, middle name, gender)
- On successful creation, the student record is automatically removed from the college system

#### College System
- **"Import from Secondary School"** button added to the Add Student dialog (shown in add mode only)
- Opens a searchable selection dialog listing all active students from the secondary school database
- Autofills first name, last name, and date of birth
- On successful creation, the student record is automatically removed from the secondary school system

#### Secondary School System
- **"Import from Primary School"** button added to the Add Student dialog (shown in add mode only)
- Opens a searchable selection dialog listing all active pupils from the primary school database
- Autofills first name, last name, and date of birth
- On successful creation, the pupil record is automatically removed from the primary school system

#### Import Dialog Features (all three systems)
- Real-time search filtering by student name or ID
- Scrollable listbox showing student/pupil ID, name, and date of birth
- Source record only deleted after the new record is successfully created (safe rollback)

---

## [7.12.0] — 2026-03-12

### Added — Full i18n (Internationalization) for College System

#### Language Support
- **10 languages supported**: English, Welsh (Cymraeg), Spanish (Español), French (Français), German (Deutsch), Polish (Polski), Urdu (اردو), Arabic (العربية), Chinese (中文), Portuguese (Português)
- **40 locale files** created — each language has 4 JSON translation files: `gui.json`, `system.json`, `modules.json`, `api.json`
- **In-app language switching** — new "Language / Iaith" menu in the menu bar after login; selecting a language instantly rebuilds the entire UI in the chosen language without losing the logged-in session

#### GUI Integration (110 files)
- All 110 domain GUI module files updated to use `t()` translation calls for every user-facing string: headers, buttons, labels, treeview headings, messagebox titles/messages, status bars, dialog fields, and form validation messages
- Dashboard fully translated — welcome banner, quick statistics labels, navigation button labels all resolve via i18n keys at render time
- Main window translated — window title, menu bar items, top bar, switch system dialog, logout/exit confirmation dialogs
- Variable naming conflicts resolved throughout (e.g. loop variable `t` renamed to `tutor`, `tmpl`, `dtype`, `tgt` etc. to avoid shadowing the `t()` function)

#### API Integration (58 files)
- All 58 API route files updated to use `t()` for response messages (error messages, success messages, validation messages)

#### i18n Module Improvements
- Fixed `load_locale = set_language` alias placement (was before `set_language` definition, causing `NameError`)
- Fixed `cli_main.py` import to use `set_language` directly
- Added `_rebuild_ui()` method to `CollegeApp` for instant in-place language switching — destroys and recreates all widgets, menu bar, topbar, and 110+ module frames with the new language

#### Translation Coverage
- `gui.json` — 200+ keys covering login, main window, dashboard, MFA, and common UI elements (buttons, labels, statuses, field names)
- `modules.json` — 1400+ keys covering all 110+ modules with per-module management headers, CRUD messages, form labels, column headings, and navigation labels
- `api.json` — 340+ keys covering all API response messages across 40+ endpoint categories
- `system.json` — 50 keys covering app info, auth messages, menu items, and error messages

---

### [7.11.0] — 2026-03-11

#### Fixed — Document Manager GUI File Dialogs (Linux)
- **File browser shows 0 compatible documents** — All file dialog `filetypes` filters used semicolons (`*.pdf;*.jpg;*.jpeg`) to separate extensions, which only works on Windows. On Linux/Tk, semicolons are treated as literal characters in the pattern, matching nothing. Replaced with space-separated patterns (`*.pdf *.jpg *.jpeg`) across 6 files: `documents.py`, `helpers.py`, `student_portal.py`, `ocr.py` (2 dialogs), and `printing_gui.py`.

---

## [7.10.0] — 2026-03-11

#### Fixed — University Student Export
- **Excel export crash (`Invalid extension for engine: 'excel'`)** — File save dialog used `.excel` as extension (from `"Excel".lower()`). Added explicit extension mapping so Excel exports correctly use `.xlsx`.
- **PDF export text cutoff** — Replaced hard character truncation with reportlab `Paragraph` objects for proper text wrapping within table cells. Module column widths are now calculated dynamically to share remaining page width evenly.

#### Fixed — University Batch Operations GUI
- **`'EnhancedBatchOperationManager' object has no attribute 'db_manager'`** — Added `_DbManagerAdapter` that provides the `get_connection()`/`close()`/`db_path` interface expected by all batch operation mixins, backed by `DatabaseManager`. Fixes CSV import, Excel import, backup creation, and all other batch database operations.
- **`no such column: compulsory_module_1`** — `update_student_modules()` tried to write module data into non-existent columns on the `students` table. Rewrote to use the `student_modules` table (DELETE + INSERT) matching the actual schema.
- **`'BatchOperationsGUI' object has no attribute 'show_import_results'`** — Added delegation method on `BatchOperationsGUI` that forwards to `ImportManager.show_import_results()`. Fixes batch update, grade import, and module enrollment import result dialogs.
- **`KeyError: 'student_id'` in validation results** — `show_validation_results()` expected `name` and `issues` keys but validation returns `type`, `description`, `severity`. Fixed to use `.get()` with fallbacks for all key variations.
- **`'EnhancedBatchOperationManager' object has no attribute 'root'`** — `_show_validation_results_dialog()` in `validation.py` referenced `self.root` on the backend object. Changed to `tk.Toplevel()` without a parent reference.
- **`FOREIGN KEY constraint failed` when merging duplicate students** — `merge_students()` now updates/deletes related records in `student_modules`, `grades`, `attendance`, and `enrollments` before deleting the duplicate student record.
- **Missing methods: `test_rest_api_connection`, `save_rest_api_config`, `save_external_db_config`** — Added all three to `ExternalIntegrationMixin`. Config methods save to the existing `EXTERNAL_DB_CONFIG_PATH` and `EXTERNAL_API_CONFIG_PATH` files.

---

### [7.9.0] — 2026-03-11

#### Fixed — University Email System
- **Empty inbox** — Changed `JOIN users` to `LEFT JOIN users` in all mailbox queries (`get_inbox`, `get_sent_messages`, `get_archived_messages`) so messages are returned even when sender/recipient only exists in shared auth DB, not the legacy `users` table. Also fixed `chat.py` and `maintenance.py` with same pattern.

#### Fixed — Course Management GUI
- **`ScrolledText` not defined** — Added missing `from tkinter.scrolledtext import ScrolledText` import in `ui_setup.py`.
- **`ACADEMIC_SYSTEMS_AVAILABLE` not defined** — Added missing import from `_imports.py` in `ui_setup.py`.
- **`ModuleNotFoundError` on return to main menu** — Removed broken `subprocess.Popen` calls that tried to run GUI files as standalone scripts. "Return to Main Menu" now simply closes the child window.
- **Course catalog crash (`no such column: m.capacity`)** — Removed references to non-existent `capacity` and `instructor` columns from the course catalog search query.
- **Course details dropdown empty** — Changed query to use `COALESCE(course_code, code)` / `COALESCE(course_name, name)` so courses with NULL `course_code` but valid `code` column appear in the dropdown.
- **Search dialog closes immediately** — Added `self.dialog.wait_window()` to `AdvancedSearchDialog` so it blocks until the user submits or cancels.
- **15 phantom courses with None code/name in Manage Course Status** — Added `WHERE COALESCE(course_code, code) IS NOT NULL AND COALESCE(course_name, name) IS NOT NULL` filter to `ManageCourseStatusDialog.load_courses()`.
- **Enrollment counts showing 0 everywhere** — Rewrote all analytics queries (in both `core/analytics.py` and `analytics/analytics.py`) to `LEFT JOIN student_modules` and `COUNT(DISTINCT sm.student_id)` instead of reading the stale `current_enrollment` column. Affects: overall statistics, department breakdown, most popular courses, low enrollment, trends, capacity reports, and chart visualizations.
- **`EnrollmentReportDialog` not defined** — Added missing import from `analytics/analytics.py`.
- **Waitlist duplicate crash** — Added pre-check before INSERT to warn user if student is already on waitlist instead of crashing on UNIQUE constraint.

---

### [7.8.0] — 2026-03-11

#### Security — High Severity Fixes (H1–H10)
- **[H1] Replaced hardcoded weak default passwords** — All three school systems (college, secondary, primary) now read default credentials from environment variables and fall back to cryptographically random passwords via `generate_secure_password()`. Removed hardcoded `admin1234`, `staff1234`, `student1234`.
- **[H2] CORS restricted to explicit origins** — College, secondary, and primary API servers no longer allow all origins. Configurable via `COLLEGE_CORS_ORIGINS`, `SCHOOL_CORS_ORIGINS`, `PRIMARY_CORS_ORIGINS` env vars; defaults to localhost.
- **[H3] Security headers added to all API servers** — Added `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `Referrer-Policy`, and `X-XSS-Protection` headers via `_init_security()` in college, secondary, and primary API servers.
- **[H4] Cookie security flags configured** — `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE=Lax`, and `SESSION_COOKIE_SECURE` (production) now set in all three API servers.
- **[H5] CSRF protection on college API** — State-changing requests (POST/PUT/DELETE/PATCH) require JSON content-type or `X-Requested-With` header to prevent cross-site request forgery.
- **[H6] Rate limiting on college login/registration** — In-memory per-IP rate limiter: 10 login attempts/minute, 5 registration attempts/hour. Returns HTTP 429 when exceeded.
- **[H7] Encryption key file permissions hardened** — All health encryption key creation code (`data_privacy.py`, `health_portal_core.py`, `auth_encryption.py`) now sets `chmod 600` on newly created key files.
- **[H8] HTTPS/TLS via nginx reverse proxy** — Added nginx service to `docker-compose.yml` with TLS termination, HTTP→HTTPS redirect, and TLS 1.2+ configuration. App container no longer exposes ports directly.
- **[H9] Internal API bound to localhost** — Batch operations API now binds to `127.0.0.1` instead of `0.0.0.0`.
- **[H10] JWT secret persisted across restarts** — College and primary school JWT secrets now persist to `.jwt_secret` file (chmod 600) on first startup. Environment variable takes precedence. Tokens survive application restarts.

#### Security — Medium Severity Fixes (M1–M10)
- **[M1] Generic login error messages** — Deactivated account error changed to "Invalid username or password" to prevent user enumeration.
- **[M2] Object-level authorization** — Added `_check_student_access()` to college grade routes; students can only view their own records.
- **[M3] Email header injection prevention** — CRLF validation on all email header fields (To, Subject, CC, BCC) in university SMTP client.
- **[M4] Secure random for ID generation** — Replaced `random.randint()` with `secrets.randbelow()` for student ID generation in API routes, CLI, and GUI.
- **[M5] Database file permissions** — Auth database files auto-set to `chmod 600` on connection via `_secure_db_permissions()`.
- **[M6] Automatic session cleanup** — Expired sessions pruned probabilistically (1-in-20) during `validate_session()` calls.
- **[M7] Minimum password length increased** — From 8 to 12 characters (`MIN_PASSWORD_LENGTH` in shared auth defaults).
- **[M8] Docker security hardening** — Non-root user (`appuser`), `HEALTHCHECK` instruction, memory (512M) and CPU (1.0) resource limits.
- **[M9] Webhook HMAC-SHA256 verification** — Webhook endpoint supports `X-Webhook-Signature` header with mandatory timestamp validation. Legacy key auth retained as fallback.
- **[M10] SQL column name validation** — Explicit allowlist validation on dynamic SQL columns in shared auth and primary school pupil service.

#### Changed
- **Dockerfile** — Runs as non-root `appuser`, includes `HEALTHCHECK` instruction.
- **docker-compose.yml** — Added nginx reverse proxy, resource limits, internal-only app port.
- **`.gitignore`** — Added `**/.jwt_secret` and `nginx/certs/` patterns.
- **`SECURITY_AUDIT.txt`** — Updated with all fixed items (C1–C4, H1–H10, M1–M10, L1–L3).

---

### [7.7.0] — 2026-03-11

#### Added
- **MFA settings menu for secondary school and primary school CLI** — Both systems now have a `[M] MFA Settings` option in every role-based menu (admin, teacher, student for secondary; admin, teacher, parent, student for primary). Users can set up TOTP-based MFA, disable MFA, and view remaining recovery codes. New files: `secondary_school/cli/mfa_cli.py`, `primary_school/cli/mfa_cli.py`, and corresponding `infrastructure/auth/mfa_service.py` re-exports from the shared auth module.
- **University CLI "Authentication" menu option** — Added an "Authentication" entry under the Technology & Analytics section of the university main CLI menu, providing access to user management, role management, MFA settings, and account security from the main menu.

#### Fixed
- **University authentication menu crashed when accessed from main menu** — `display_auth_menu()` created a new `UserAuth()` instance instead of reusing the already-authenticated session, showing a "Not logged in" login screen. Now accepts an optional `existing_auth` parameter to reuse the current session.
- **KeyError: 'permissions' crash in university auth CLI menus** — Multiple places in `cli_menus.py` accessed `user['permissions']` directly on user dicts that don't always contain a `permissions` key (fetched user records from `get_user()`, and `current_user` from shared auth). Changed all references to use `.get('permissions', [])` with fallback to `auth.get_user_permissions()` where needed. Also fixed unsafe access to `user['password_reset_required']`.

---

### [7.6.0] — 2026-03-10

#### Fixed
- **University admin (and all roles) had no permissions in GUI/CLI** — When logging in via the universal shared auth, the `session_user` dict was built with `"permissions": []` in `run.py`, so admin users could not access any permission-gated features. Permissions are now loaded from the university auth constants (`PERMISSIONS` dict) based on the user's role, giving admin 277 permissions, staff 150, student 117, instructor 93, and parent 44. The same fix was applied to both CLI paths in `cli_main.py` as a fallback when the database permission lookup returns empty.

#### Changed
- **Eliminated all wildcard imports** — Replaced 7 `from .common_imports import *` statements with explicit, named imports across the university student dashboard, grades, and registration GUI modules.
- **Converted all relative imports to absolute imports** — 897 files converted from relative (`from .foo import bar`) to fully qualified absolute imports (`from education_system.<path>.foo import bar`) across the entire codebase. Three Django todoapp files retained relative imports due to a hyphenated directory name (`python-utilities`).

#### Fixed
- **Corrected 24 broken import paths** — Fixed imports pointing to wrong module locations, including:
  - `infrastructure.logging.log_config` → `utils.logging.log_config` (13 files)
  - `modules.finance.core.financial_core` → `modules.domain.finance.core.financial_core` (6 files)
  - `infrastructure.security.immutable_audit` → `infrastructure.security.immutable_audit_log` (3 files)
  - `infrastructure.realtime` → `infrastructure.communication.realtime_notifications`
  - `modules.shared.services.enhanced_reporting` → `modules.shared.services.analytics.enhanced_reporting`
  - `services.cli` / `services.gui` → `modules.services.cli` / `modules.services.gui`
  - 6 additional path corrections for auth, data management, assignments, grading, parking, and academic calendar modules.
- **Created 4 missing `__init__.py` files** — Added package init files for `commerce/gui`, `housing/gui`, `shared/gui` (university level), and `database/migrations` to make them importable as packages.
- **Fixed test imports** — Updated test files for academic calendar, commerce restaurant, housing accommodation, and main GUI to reference correct module paths.

#### Notes
- 13 imports reference planned-but-unimplemented modules (e.g. `budget_gui`, `scholarship_gui`, `gui_context`). All are safely wrapped in `try/except` with graceful fallbacks.
- Full audit: 18,646 import statements checked, 0 syntax errors.

---

### [7.5.0] — 2026-03-10

#### Added
- **University CLI switch system options** — Added "Switch to College", "Switch to Secondary School", and "Switch to Primary School" buttons to the university CLI menu, matching the other three systems.
- **"Switch to Primary School" option** in the secondary school CLI switch system sub-menu (was missing, only had College and University).
- **"Switch to Primary School" option** (`[R]`) in all college CLI role menus (admin, instructor, student, parent), alongside existing University and Secondary School switches.

#### Fixed
- **CLI logout now returns to universal login with system selection** — Previously, logging out from any CLI system re-prompted with a basic login that locked the user back into the same system. Multi-system users like superadmin could not switch systems after re-login. All four systems now signal back to `run.py`'s dispatch loop via `request_logout(mode="cli")`, which shows the full universal login with system picker.
- **University CLI auth sync after system switch** — Fixed stale auth state in `menu_router.py` that caused a spurious login prompt when switching to the university system from another system. The menu router now always syncs with the shared auth context instead of caching a potentially stale instance.
- **`switch.py: request_logout()`** — Now accepts a `mode` parameter (default `"gui"`) so CLI logout can correctly signal `("__login__", "cli")`.

---

### [7.4.0] — 2026-03-09

#### Added
- **Unified CLI login** (`shared/cli/login_cli.py`) — Single "Education System - Login" entry point used by all four systems (university, college, secondary, primary). Authenticates against the shared auth database with 3-attempt login and email MFA support.
  - `cli_login_prompt(auth)` — Reusable login function showing the unified header, handling MFA via `cli_mfa_verify()`.
  - `universal_cli_login()` — Login + system picker for the `run.py` CLI dispatch loop.
- **CLI MFA support** (`shared/cli/mfa_cli.py`) — Email OTP + TOTP/recovery code verification for CLI login, matching the GUI's MFA flow. Sends email OTP with on-screen fallback if SMTP delivery fails.
- **CLI logout and re-login** — All four systems now have a `[L] Logout` option in every role menu (admin, teacher/instructor, student, parent). Selecting logout clears the session and returns to the unified login prompt within the same session, without exiting the application.
- **CLI dispatch loop in `run.py`** — Added `cli_universal_login()` and a CLI dispatch loop that mirrors the GUI dispatch loop: pre-authenticates via the shared login, launches the chosen system's CLI with credentials, and handles system switching and re-login.
- **"Switch to CLI" button** in the primary school GUI sidebar, matching the other three systems.

#### Changed
- **University CLI login** (`university_system/modules/shared/cli/cli_main.py`) — Replaced the complex `display_auth_menu()` with `login_prompt()` that delegates to the shared `cli_login_prompt()`. Builds university-format `current_user` with permissions, `student_id`, and backward-compatible `id`/`user_id` keys.
- **University CLI menu router** (`menu_router.py`) — Logout now calls `login_prompt(auth)` instead of `display_auth_menu()`, showing the unified header on re-login.
- **College CLI** (`college_system/modules/shared/cli/cli_main.py`) — `login_prompt()` delegates to shared `cli_login_prompt()`. `main()` wrapped in re-login loop. All four role menus (admin, instructor, student, parent) have logout option.
- **Secondary school CLI** (`secondary_school/cli/cli_main.py`) — Same pattern: shared login, re-login loop, logout in all three role menus (admin, teacher, student).
- **Primary school CLI** (`primary_school/cli/cli_main.py`) — Same pattern: shared login, re-login loop, logout in all four role menus (admin, teacher, parent, student).
- All four system CLI launchers in `run.py` now accept `user_info=, role=, shared_auth=` parameters to skip local login when pre-authenticated.
- All standalone CLI logins use `UserAuth()` with no args (shared auth DB) instead of system-specific DB paths.

---

### [7.3.0] — 2026-03-09

#### Removed
- **University internal login screen** — The university system no longer has its own login UI. All GUI authentication is handled exclusively by the universal login (`shared/gui/login_gui.py`). Removed ~1,000 lines of dead code from `auth_gui.py` including: `show_login_screen`, `perform_login`, `_perform_login_thread`, all PIN/TOTP/email-OTP verification for login, remember-me token management, and related imports/class assignments in `main_gui.py`.
- **`run_gui_interface()`** — Removed from `misc.py` and the package `__init__.py`. The university GUI is now always launched pre-authenticated via `run.py`.

#### Changed
- `run.py: run_university_gui()` — If no pre-authenticated user is provided, shows the universal login first instead of falling back to the internal login.
- `main_gui.py: init_gui()` — Always goes directly to the main interface (no login screen fallback). `session_user` is expected from the universal login.
- `auth_gui.py` — Rewritten to contain only post-login functions: logout, session timer, password change, MFA settings, system switching, language selector.
- `gui_setup.py` — Header and nav login buttons now say "Logout" and call `logout_user()` directly.
- `toggle_login_logout()` — Simplified to always log out (user is always authenticated).
- Session expiry and logout both return to the universal login via `request_logout()` + `root.destroy()`.

---

### [7.2.2] — 2026-03-09

#### Fixed
- **MFA email OTP not sending via universal login** — The `_show_mfa` method in `login_gui.py` used `connect()` from the shared auth DB module but it was never imported, causing a `NameError` that was silently caught. Added the missing `from education_system.shared.auth.db import connect` import.
- **MFA email sent to wrong address** — The email OTP was sent to the default `admin@university.edu` from the shared auth DB instead of the user's real email (`seancatchpole989@gmail.com`) stored in the university `mfa_methods` table. Both the universal login and university internal login now check `mfa_methods` for the MFA-registered email before falling back to the shared auth DB email.
- **Shared email config not loading SMTP password** — The shared `email_config.json` was created without the SMTP password (stripped for security), but the config loader didn't fall back to the legacy university config file to retrieve it. Added a fallback chain so the password is sourced from: config file → env var / keyring → legacy config file.

#### Added
- **Shared email configuration** (`education_system/shared/email/`) — Moved `email_config.json` from `university_system/data/config/` to `shared/data/config/` so all four subsystems use a single SMTP configuration.
  - `shared/email/config.py` — Config loader with fallback chain (shared → legacy university → defaults), secure password retrieval from env vars / keyring / legacy file.
  - `shared/email/otp_sender.py` — Email OTP sender using the shared config. Removes the universal login's dependency on the university MFA service.
- **`shared/auth/core.py: complete_mfa_login()`** — Creates a session after MFA is verified externally (e.g. email OTP verified in-memory), without re-checking the TOTP code.

#### Changed
- `university_system/core/paths.py` — `EMAIL_CONFIG_FILE` and `EMAIL_CONFIG_PATH` now resolve to `shared/data/config/email_config.json` with fallback to legacy location.
- `university_system/infrastructure/email/config.py` — `load_config()` / `save_config()` delegate to shared email config loader.
- `university_system/infrastructure/auth/email_otp_service.py` — Config loading uses `shared.email.config` with legacy fallback.
- `university_system/infrastructure/auth/sms_provider.py` — SMTP config loading uses `shared.email.config` with legacy fallback.
- `university_system/modules/shared/gui/main/admin/admin_tools_gui.py` — Config editor uses `EMAIL_CONFIG_FILE` from paths (resolves to shared location).
- `shared/gui/login_gui.py` — Email OTP now generated in-memory and sent via `shared.email.otp_sender` instead of importing from university system. Verification uses in-memory hash comparison.

---

### [7.2.1] — 2026-03-09

#### Fixed
- **University MFA not prompting during universal login** — MFA set up through the university GUI wrote TOTP secrets only to the university database, but the universal login (`run.py`) checked the shared auth database (`auth.db`) where no MFA record existed. Users with MFA enabled were never prompted for a TOTP code when logging in via the universal login screen.
- **University internal login using random PIN instead of real TOTP** — The `requires_2fa` handler and all three fallback paths in `_perform_login_thread` now check for TOTP configuration and show a real authenticator code dialog instead of a random 4-digit PIN.
- **Email OTP not sent during universal or university login** — MFA verification dialogs only accepted TOTP codes from authenticator apps. Users who set up email-based MFA were shown a code prompt but never received a code. Both the universal login (`login_gui.py`) and university internal login (`auth_gui.py`) now send an email OTP before showing the verification dialog, with a fallback to display the code on screen if email delivery fails.

#### Added
- **Universal MFA across all login paths** — MFA verification now works consistently whether logging in via the universal login (`run.py`), the university internal login, or pre-authenticated sessions. Both email OTP and TOTP (authenticator app) codes are accepted at all login points.
- **Shared email configuration** (`education_system/shared/email/`) — Moved `email_config.json` from `university_system/data/config/` to `shared/data/config/` so all four subsystems share a single SMTP configuration. New modules:
  - `shared/email/config.py` — Shared config loader with fallback chain (shared → legacy university path → defaults). Handles secure password retrieval from env vars / keyring.
  - `shared/email/otp_sender.py` — Shared OTP email sender using the shared config. Removes the universal login's dependency on the university MFA service for sending emails.
- **MFA sync between university and shared auth databases** — The university `MFAService` now mirrors TOTP secrets and MFA enabled/disabled state to the shared auth `mfa_secrets` table whenever MFA is set up, enabled, disabled, or re-enabled. Sync operations are non-fatal so university MFA continues to work even if the shared auth sync fails.
- **Startup TOTP migration** — `run.py` now copies existing university TOTP secrets to the shared auth database on startup, ensuring MFA works for users who set it up before the shared-auth sync was added.
- **Cross-database user ID resolution** — Added `_resolve_shared_user_id()` helper that maps university-local user IDs to shared auth user IDs via username lookup, since the two databases use independent ID sequences.
- **TOTP detection helpers** — Added `_has_totp_configured()` and `_resolve_shared_uid()` helpers in `auth_gui.py` to check for TOTP configuration across both databases and route to the correct verification flow.
- **Missing i18n translations for academic launchers** — Added `academic_launchers.json` locale file with English translations for all ~50 keys used in `academic_launchers_gui.py`. Error dialogs were previously showing raw translation keys (e.g. `academic_launchers.errors.title`).

#### Changed
- `university_system/core/paths.py` — `EMAIL_CONFIG_FILE` and `EMAIL_CONFIG_PATH` now resolve to `shared/data/config/email_config.json` with fallback to the legacy university location.
- `university_system/infrastructure/email/config.py` — `load_config()` and `save_config()` delegate to the shared email config loader.
- `university_system/infrastructure/auth/email_otp_service.py` — Config loading uses `shared.email.config` with legacy fallback.
- `university_system/infrastructure/auth/sms_provider.py` — Both SMTP config loading points use `shared.email.config` with legacy fallback.
- `university_system/modules/shared/gui/main/admin/admin_tools_gui.py` — Config editor reads/writes via the shared `EMAIL_CONFIG_FILE` path.
- `university_system/infrastructure/auth/mfa_service.py` — `setup_totp()`, `enable_mfa()`, `disable_mfa()`, `reenable_mfa()`, and `set_verification_disabled()` now sync state to the shared auth database.
- `university_system/modules/shared/gui/main/auth_gui.py` — All three `_do_pin_verification` fallbacks in the `result is True` login path now check for TOTP first and use `_do_totp_verification` when configured.
- `shared/gui/login_gui.py` — Email OTP generation/verification now uses in-memory code storage and `shared.email.otp_sender` instead of importing from university system.

---

## [7.2.0] — 2026-03-09

### Changed
- **Logout returns to universal login** — logging out of any system (university, college, secondary school, primary school) now returns to the shared login screen instead of each system's own login page
- University default student credentials updated to match legacy university login (`S12345` / `student123` instead of `university.student` / `Student@University123`)

### Fixed
- **FOREIGN KEY constraint failed on email send** — university email service was using shared auth user IDs as foreign keys into the university `users` table; now resolves sender by username and auto-creates local profiles for shared-auth-only users
- **"table students has 15 columns but 13 values were supplied"** — student creation INSERT now explicitly lists column names instead of relying on column order (table had 2 extra columns added via ALTER TABLE: `emergency_contact`, `pronouns`)
- **"too many values to unpack (expected 13)"** — student records list and search views used `SELECT *` with 13-variable tuple unpacking but the table now has 15 columns; switched to index-based access
- **"invalid command name check_session_timer"** on logout — session timer was not cancelled before destroying the window; now calls `_cancel_timers()` before `root.destroy()`

---

## [7.1.0] — 2026-03-09

### Added
- **Unified Authentication across all 4 systems** — university, college, secondary school, and primary school now share a single auth database (`auth.db`) with one set of credentials
- University system integrated into shared auth module via adapter pattern — tries shared auth first, falls back to legacy `user_accounts` table
- 5 new university default accounts: `university.admin`, `university.staff`, `university.instructor`, `university.student`, `university.parent` (password pattern: `<Role>@University123`)
- `superadmin` account now has access to all 4 systems (previously only 3)
- Legacy PBKDF2-SHA256 password support with transparent re-hashing to bcrypt on first login (`legacy_salt` column in shared `users` table)
- Migration script (`migration_to_shared.py`) to copy existing university `user_accounts` into shared auth DB
- University system appears in the universal login system picker (blue button)
- `_ensure_default_accounts()` function to handle database upgrades — adds missing accounts and system access to existing databases

### Changed
- Total default accounts increased from 13 to 18 (5 university accounts added)
- `run.py`: university system now uses universal login flow — `run_university_gui()` accepts `user_info=, role=, shared_auth=` for pre-authenticated launch
- `run.py`: superadmin (and any multi-system user) stays logged in when switching systems — no re-authentication required if the user already has access to the target system
- **Switch System dialogs** — all 4 systems now show buttons for the other 3 systems:
  - College: added Primary School button (was missing)
  - Secondary School: added Primary School button (was missing)
  - Primary School: removed self from list, added styled buttons matching other systems
  - University: added Primary School button (was missing)
- `_init_university()` now calls `_init_shared_auth()` and runs migration automatically

### Fixed
- Switch System from superadmin account forced unnecessary re-login — now reuses existing session when user has access to the target system

---

## [7.0.0] — 2026-03-09

### Added
- **Primary School Management System** — complete new system for Reception–Year 6, placed in `education_system/primary_school/`, following the same architecture as the secondary school system
- 46 domain modules across 7 categories:
  - **Academics (11):** pupils, subjects, classes, assessment, attendance, timetable, homework, SATs, phonics, reading records, progress
  - **Pastoral Care (5):** behaviour, rewards, safeguarding, SEND, pastoral
  - **Staff (4):** HR, CPD, cover, staff directory
  - **Admin (8):** users, settings, admissions, finance, data export, audit log, policies, documents
  - **Pupil Life (8):** clubs, meals, transport, trips, library, medical, class groups, consent
  - **Communication (6):** email, notifications, announcements, calendar, parents' evening, communication log
  - **Facilities (4):** room booking, assets, visitors, incidents
- SQLite database with 52 tables, WAL mode, foreign keys, parameterised queries
- Key stage support: EYFS (Reception), KS1 (Years 1–2), KS2 (Years 3–6)
- Assessment levels: Emerging, Developing, Expected, Greater Depth
- UK primary-specific modules: SATs (KS1/KS2), phonics screening, reading records
- Role-based access control (admin, teacher, teaching_assistant, parent) with login/session management
- Tkinter GUI with scrollable sidebar navigation, ttk.Treeview lists, modal dialogs
- Dashboard with role-aware module listing
- Sidebar buttons: Logout, Shutdown, Switch System
- Switch System integration with `education_system.switch` module for seamless system transitions
- `email_log` table added to schema for placeholder email logging service
- Default user accounts seeded on first run (admin, teacher, parent)
- Primary school added to `run.py` launcher: `--primary` CLI flag, interactive menu option [4], orange GUI button

### Fixed
- **University System:** `ValueError: too many values to unpack` in student records GUI — fixed by selecting only needed columns instead of `SELECT *`
- **Primary School:** login window not appearing — `transient(parent)` inherited withdrawn state, fixed with `self.deiconify()`
- **Primary School:** sidebar buttons not visible — bottom bar packed after canvas, fixed by packing bottom bar first
- **Primary School:** errors not printing to terminal — overrode `report_callback_exception` on root and app, added `traceback.print_exc()` to all 339 except blocks across 92 module files
- **Primary School:** `SyntaxError` in `sats_gui.py` — automated import inserted inside multi-line `from ... import` block
- **Primary School:** `TclError: can't invoke destroy` — duplicate `root.destroy()` in `else` clause removed
- **Primary School:** 31 method name mismatches between GUI and service files (e.g. `list_all` vs `list_staff`, `get_records` vs `get_attendance`)
- **Primary School:** `cover_service.py` referenced `cover_arrangements` table instead of `cover_lessons` (4 occurrences)
- **Primary School:** `finance_service.py` referenced `budgets` table instead of `finance_budgets` (INSERT, SELECT, UPDATE)
- **Primary School:** `notification_gui.py` used `self._auth.get("user_id")` on `UserAuth` object — fixed to `self._auth.current_user.get("id")`
- **Primary School:** Switch System button was a placeholder — now shows system picker dialog and integrates with shared switch module

### Changed
- `run.py` updated with primary school launcher functions and dispatch table entries
- Changelog title updated to cover full Education System (not just University)
