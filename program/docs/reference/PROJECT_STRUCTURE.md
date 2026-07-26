# Project Structure

> Back to [README](../README.md)

## Project Structure

```
education_system/                         # Root education platform
├── nursery_system/                       # Nursery / Early Years System (360+ files, EYFS)
├── primarysch_system/                    # Primary School System (420+ files)
├── secondarysch_system/                  # Secondary School System (440+ files)
├── post_16/                              # Post-16 phase
│   └── sixthform_system/                 # Sixth Form College System (570+ files)
├── post_18/                              # Post-18 phase
│   └── university_system/                # University Management System (3,900+ files)
├── migrations/                          # Alembic migration scripts (versions/)
├── shared/                              # Shared modules across all 5 systems
│   ├── api/                             # Unified REST API (Flask, GraphQL, WebSocket)
│   │   ├── web/                         # Web Portal SPA + PWA support
│   │   └── graphql/                     # GraphQL API (Strawberry)
│   ├── auth/                            # Unified authentication (bcrypt, MFA, sessions)
│   │   └── password_reset.py            # Secure token-based password reset
│   ├── audit/                           # Unified audit logging (tamper detection)
│   ├── analytics/                       # Analytics & early warning predictions
│   ├── backup/                          # Encrypted backup/restore with scheduling
│   ├── cli/                             # Universal CLI login & system selection
│   ├── gdpr/                            # GDPR compliance (consent, SAR, portability)
│   │   ├── consent_service.py           # Consent tracking (15 types)
│   │   └── gdpr_service.py             # Data subject rights & retention
│   ├── gui/                             # Universal GUI login window
│   ├── integrations/                    # LMS providers (Canvas, Moodle, Teams)
│   ├── offline/                         # Offline-first sync infrastructure
│   ├── security/                        # Field-level encryption (Fernet AES-128)
│   ├── services/data_retention/         # GDPR data retention policies & automation
│   ├── validation/                      # Input validation & sanitization
│   ├── webhooks/                        # Webhook dispatch, HMAC signing, retry
│   └── data/db_files/                   # Central databases
│       ├── auth.db                      # Authentication database
│       ├── audit.db                     # Unified audit trail
│       ├── webhooks.db                  # Webhook subscriptions & deliveries
│       └── offline_sync.db             # Offline cache & mutation queue
├── docs/                                # Centralised documentation
│   ├── university_system/               # University system docs
│   ├── sixthform_system/                # Sixth-form system docs
│   ├── secondarysch_system/             # Secondary school docs
│   ├── primarysch_system/               # Primary school docs
│   └── nursery_system/                  # Nursery / Early Years docs
├── switch.py                             # Runtime system/mode switching
└── __init__.py

run.py                                    # Unified launcher (CLI & GUI system selector)
pyproject.toml                            # Project configuration
```

### University System Structure

```
education_system/post_18/university_system/
│
├── api/                               # REST API server (Flask)
│   ├── api_server.py                  # App factory & runner
│   ├── auth.py                        # JWT authentication (token_required, admin_required)
│   ├── config.py                      # API configuration loader
│   ├── errors.py                      # Exception-to-HTTP status mapping
│   ├── pagination.py                  # Pagination helpers
│   ├── validators.py                  # Input validation (35+ validators)
│   ├── static/                        # Web portal static assets
│   │   ├── index.html                 # SPA HTML shell (login, app layout, modal, toasts)
│   │   ├── css/style.css              # Full UI stylesheet (responsive, dark sidebar)
│   │   └── js/app.js                  # SPA JavaScript (routing, auth, CRUD pages)
│   └── routes/                        # 60+ route files (blueprint per domain)
│       ├── web_routes.py              # Web portal (/portal)
│       ├── auth_routes.py             # Login, logout, refresh, me
│       ├── student_routes.py          # Student CRUD
│       ├── finance_routes.py          # Financial services
│       ├── hr_routes.py               # Staff HR management
│       ├── helpdesk_routes.py         # Support tickets
│       └── ...                        # 55 more route files
│
├── infrastructure/                     # Core infrastructure layer
│   ├── ai/                            # AI/ML services (chatbot, analytics)
│   ├── analytics/                     # Analytics and reporting engine
│   ├── async_utils/                   # Asynchronous utilities
│   ├── auth/                          # Authentication & authorization
│   │   ├── cli/                       # Auth CLI components
│   │   ├── core_utils/                # Core auth utilities
│   │   ├── integrations/              # Auth integrations
│   │   ├── managers/                  # Auth manager classes
│   │   ├── sso_providers/             # SSO provider configurations
│   │   ├── biometric_service.py       # Face & fingerprint auth (v5.40.0)
│   │   ├── sso_service.py            # SAML 2.0 & OIDC integration (v5.40.0)
│   │   └── webauthn_service.py       # FIDO2/security key auth (v5.40.0)
│   ├── cache/                         # LRU cache with TTL
│   ├── communication/                 # Communication services (SMS, notifications)
│   ├── database/                      # Database connection & management
│   │   ├── db.py                      # Connection pooling, transactions
│   │   ├── data_backup/               # Backup system (13 modules + storage/)
│   │   ├── migrations/                # Schema version migrations
│   │   └── schemas/                   # Database schema definitions
│   ├── data_management/               # Automated backup scheduling
│   ├── email/                         # Email service integration
│   │   ├── admin/                     # Admin email tools (13 modules)
│   │   ├── email_service/             # Async queue & SMTP (7 modules + notifications/)
│   ├── ml/                            # Machine learning infrastructure
│   ├── monitoring/                    # Observability (metrics, health checks, alerts)
│   ├── performance/                   # Performance optimization (caching)
│   ├── realtime/                      # WebSocket & real-time services
│   ├── repositories/                  # Data access repositories
│   ├── search/                        # Search infrastructure (Elasticsearch)
│   ├── security/                      # Security features
│   │   ├── data_encryption.py         # Field-level encryption
│   │   ├── rate_limiter.py            # Request rate limiting
│   │   ├── session_management.py      # Secure session handling
│   │   ├── audit_trail.py             # Comprehensive audit logging
│   │   ├── immutable_audit_log.py     # Tamper-proof audit logs
│   │   └── remember_me.py            # Remember Me token system
│   ├── validation/                    # Input validation & sanitization
│   ├── workflows/                     # Business process automation
│   ├── exceptions.py                  # Centralized exceptions
│   └── shared_context.py             # Global application context
│
├── modules/                           # Main application modules
│   ├── core/                          # Core business entities
│   │   └── services/                  # Core services
│   │
│   ├── domain/                        # Domain layer (55+ business domains)
│   │   │
│   │   │  ── ACADEMIC DOMAINS ──
│   │   │
│   │   ├── academics/                 # Core academic module
│   │   │   ├── cli/                   # Academic CLI modules
│   │   │   │   ├── office_hours_cli.py # Office hours CLI
│   │   │   │   └── ta_management_cli.py # TA management CLI
│   │   │   ├── grading/               # Grading services
│   │   │   │   ├── grade_calculation/ # Grade calc package (16 modules)
│   │   │   │   ├── learning_outcomes/ # Learning outcomes package (5 modules)
│   │   │   ├── gui/
│   │   │   │   ├── academic_calendar/  # Calendar GUI (10+ files)
│   │   │   │   ├── ai_detector/        # AI detection GUI (16 views)
│   │   │   │   ├── assignment_system/  # Assignment GUI (19 managers)
│   │   │   │   │   ├── assignment_manager/ # Manager package (11 modules)
│   │   │   │   │   └── group_manager/     # Group mgmt package (5 modules)
│   │   │   │   ├── attendance_grade/   # Attendance-grade integration
│   │   │   │   ├── attendance_tracker/ # Attendance GUI (11 files)
│   │   │   │   ├── bulk_grade_import/  # Bulk grade import from CSV
│   │   │   │   ├── course_catalog/     # Course catalog & self-registration
│   │   │   │   ├── course_forums/      # Course discussion forums
│   │   │   │   ├── course_health/      # Course health dashboard
│   │   │   │   ├── course_management_gui/ # Course mgmt (15 submodules)
│   │   │   │   │   ├── core/             # Main GUI (11 mixin modules)
│   │   │   │   │   ├── recommendations/  # Recommendations (12 modules)
│   │   │   │   │   └── waitlists/        # Waitlist dialogs (7 modules)
│   │   │   │   ├── course_messaging/   # Course-targeted messaging
│   │   │   │   ├── degree_progress/    # Degree progress tracker
│   │   │   │   ├── gpa_calculator/     # What-if GPA calculator
│   │   │   │   ├── grade_tracking/     # Grade tracking (24 files)
│   │   │   │   │   └── analytics_manager/ # Analytics package (12 modules)
│   │   │   │   ├── grades_breakdown/   # Grades breakdown by module
│   │   │   │   ├── grade_tracking_management_gui/ # Grade mgmt (13 mixin modules)
│   │   │   │   ├── library/            # Library GUI (17 components)
│   │   │   │   │   └── fines/          # Fines package (10 modules)
│   │   │   │   ├── misconduct/         # Academic misconduct (18 modules)
│   │   │   │   ├── module_scheduling/  # Scheduling (8 tabs)
│   │   │   │   ├── office_hours/       # Office hours management
│   │   │   │   ├── parent_portal/      # Parent portal (20+ files)
│   │   │   │   ├── plagiarism_main_gui/ # Plagiarism GUI (20 files)
│   │   │   │   ├── roster_viewer/      # Class roster viewer & export
│   │   │   │   ├── semester_analytics/ # Semester comparison analytics
│   │   │   │   ├── ta_management/      # TA management & evaluation
│   │   │   │   ├── blockchain_credentials_gui.py
│   │   │   │   ├── course_evaluation_gui.py
│   │   │   │   ├── degree_audit_gui.py
│   │   │   │   ├── lms_gui.py
│   │   │   │   └── virtual_classroom_gui.py
│   │   │   └── services/
│   │   │       ├── academic_calendar/  # Calendar services (23 files)
│   │   │       ├── assignments/        # Assignment services
│   │   │       │   ├── assignment_submission.py # Core submission logic
│   │   │       │   ├── analytics/      # Assignment analytics
│   │   │       │   ├── assignments/    # CRUD & submissions
│   │   │       │   ├── core/           # Database, permissions, utils
│   │   │       │   ├── extensions/     # Extension requests
│   │   │       │   ├── grading/        # Grading operations
│   │   │       │   ├── groups/         # Group management
│   │   │       │   ├── maintenance/    # System maintenance
│   │   │       │   ├── notifications/  # Messaging
│   │   │       │   ├── peer_review/    # Peer review system
│   │   │       │   └── templates/      # Assignment templates
│   │   │       ├── attendance/         # Attendance services (14+ modules)
│   │   │       │   ├── cli/            # Attendance CLI (13 modules)
│   │   │       │   ├── qr_system.py    # QR attendance
│   │   │       │   ├── face_recognition_system.py
│   │   │       │   ├── geofencing.py   # Location-based attendance
│   │   │       │   └── gamification.py # Attendance rewards
│   │   │       ├── course_management/  # Course mgmt package (16 modules)
│   │   │       ├── degree_audit/       # Degree audit
│   │   │       ├── evaluation/         # Course evaluation
│   │   │       ├── library/            # Library services
│   │   │       ├── lms/                # Learning management
│   │   │       ├── module_scheduling/  # Module scheduling package (17 modules)
│   │   │       ├── office_hours/       # Office hours services
│   │   │       ├── parent_portal/      # Parent portal package (15 modules)
│   │   │       ├── plagiarism/         # Plagiarism detection (7 modules + cli/)
│   │   │       ├── ta_management/      # TA management services
│   │   │       ├── timetable/          # Timetable services
│   │   │       └── virtual_classroom/  # Virtual classroom
│   │   │
│   │   ├── admissions/                # Admissions processing
│   │   │   ├── gui/                   # Admissions CRM GUI
│   │   │   └── services/
│   │   │
│   │   ├── research/                  # Research & grants management
│   │   │   ├── gui/                   # Research grants GUI
│   │   │   └── services/
│   │   │
│   │   │  ── FINANCIAL DOMAINS ──
│   │   │
│   │   ├── finance/                   # Financial services
│   │   │   ├── billing/               # Fee structure, payment plans
│   │   │   ├── core/                  # Core finance (13 files)
│   │   │   ├── gui/
│   │   │   │   ├── finance/           # Finance mgmt GUI
│   │   │   │   │   ├── budget_manager/    # Budget mgmt package (13 modules)
│   │   │   │   │   ├── expense_manager/   # Expense mgmt package (6 modules)
│   │   │   │   │   ├── layout/            # Layout mixins (24 modules)
│   │   │   │   │   ├── settings/          # Settings package (9 modules)
│   │   │   │   │   └── transaction_manager/ # Transactions package (12 modules)
│   │   │   │   ├── finance_reporting/ # Reporting GUI (16 files)
│   │   │   │   │   └── archive_backup/  # Archive & backup package (6 modules)
│   │   │   │   ├── financial_aid/     # Aid portal GUI
│   │   │   │   │   ├── admin_portal/  # Admin portal package (10 modules)
│   │   │   │   │   └── student_portal/ # Student portal package (11 modules)
│   │   │   │   └── student_finance/   # Student financial dashboard
│   │   │   ├── reporting/             # Budget, revenue, reports
│   │   │   │   ├── financial_reports/ # Reports package (12 modules)
│   │   │   │   └── revenue_analytics/ # Revenue package (10 modules)
│   │   │   ├── scholarships/          # Scholarship programs
│   │   │   └── services/              # Financial aid services
│   │   │
│   │   │  ── STUDENT LIFE DOMAINS ──
│   │   │
│   │   ├── student_affairs/           # Student affairs
│   │   │   ├── gui/
│   │   │   │   ├── account_security/  # Account security dashboard
│   │   │   │   ├── alumni/            # Alumni GUI (13 components)
│   │   │   │   ├── document_center/   # Personal document center
│   │   │   │   ├── help_center/       # Integrated help center
│   │   │   │   ├── helpdesk/          # Helpdesk GUI
│   │   │   │   ├── internship_management/ # Internship GUI package (12 modules)
│   │   │   │   ├── messaging_hub/     # Student messaging hub
│   │   │   │   ├── notification_prefs/ # Notification preferences
│   │   │   │   ├── student_profile/   # Student profile center
│   │   │   │   ├── student_support/   # Support GUI (8 files)
│   │   │   │   └── student_union_gui/ # Union GUI (26 subdirectories)
│   │   │   ├── services/
│   │   │   │   ├── alumni_management/ # Alumni package (19 modules)
│   │   │   │   ├── early_warning/     # Early warning system
│   │   │   │   ├── helpdesk/          # Helpdesk package (10 modules + 3 subdirs)
│   │   │   │   ├── mental_health/     # Mental health services
│   │   │   │   └── student_support/   # Support system (20+ files)
│   │   │   └── student_union/         # Union services
│   │   │       └── clubs/
│   │   │           └── club_management/ # Club mgmt package (12 modules)
│   │   │
│   │   ├── housing/                   # Housing & accommodation
│   │   │   ├── gui/
│   │   │   │   └── housing_accommodation_gui/ # Housing GUI package
│   │   │   └── services/
│   │   │       ├── accommodation/     # Accommodation package (13 modules)
│   │   │       └── housing_accommodation/ # Housing package (12 modules)
│   │   │
│   │   │  ── STAFF & HR DOMAINS ──
│   │   │
│   │   ├── staff_hr/                  # Staff HR management
│   │   │   ├── cli/
│   │   │   │   ├── staff_hr_cli.py    # Main CLI entry
│   │   │   │   └── menus/             # 19 menu modules
│   │   │   ├── gui/                   # 29 GUI windows
│   │   │   └── services/
│   │   │       └── managers/          # 31 specialized managers
│   │   │
│   │   │  ── HEALTH DOMAINS ──
│   │   │
│   │   ├── health/                    # Health services
│   │   │   ├── appointments/          # Appointment booking
│   │   │   ├── gui/                   # Health portal & management GUIs
│   │   │   │   ├── health_portal/     # Portal package (14 modules + reports/)
│   │   │   │   │   └── reports/       # Health reports package (5 modules)
│   │   │   │   └── medical_accommodation/ # Accommodation GUI (12+ modules)
│   │   │   ├── portal/                # Health portal services
│   │   │   ├── records/               # Medical records (10 subpackages)
│   │   │   │   ├── admin/             # Admin, permissions, advisories
│   │   │   │   ├── analytics/         # Population, provider, trends
│   │   │   │   ├── clinical/          # Allergies, care plans, prescriptions
│   │   │   │   ├── db/                # Schema, audit
│   │   │   │   ├── records/           # CRUD, reports, templates
│   │   │   │   ├── screening/         # Schedules, results, reminders
│   │   │   │   ├── student/           # Dashboard, insurance, wellness
│   │   │   │   ├── vaccinations/      # Tracking, management, reports
│   │   │   │   └── wellness/          # Programs, challenges, resources
│   │   │   └── services/
│   │   │
│   │   │  ── CAMPUS & FACILITIES ──
│   │   │
│   │   ├── campus/                    # Campus services
│   │   │   ├── gui/
│   │   │   │   ├── community/         # Church management
│   │   │   │   └── security/          # Police, security desk (dialogs/ + tabs/)
│   │   │   └── services/              # Campus events
│   │   │
│   │   ├── facilities/                # Facility management
│   │   │   ├── gui/                   # Facilities GUI
│   │   │   └── services/
│   │   │
│   │   ├── career/                    # Career services
│   │   │   ├── gui/                   # Career services GUI
│   │   │   └── services/
│   │   │
│   │   │  ── COMMERCE & DINING ──
│   │   │
│   │   ├── commerce/                  # Commerce & dining services
│   │   │   ├── gui/
│   │   │   │   ├── restaurant_management_gui/ # Restaurant (35+ files)
│   │   │   │   ├── shop_management_gui/       # Shop mgmt package
│   │   │   │   ├── bar_gui.py
│   │   │   │   ├── cafe_system_gui.py         # Cafe GUI (+ 7 module files)
│   │   │   │   ├── grocery_gui.py
│   │   │   │   └── takeaway_gui.py
│   │   │   └── services/
│   │   │       ├── restaurant/        # Restaurant (25 files)
│   │   │       ├── grocery/           # Grocery services
│   │   │       ├── shop_management/   # Shop mgmt package (12 modules)
│   │   │       ├── takeaway/          # Takeaway services
│   │   │       └── restaurant_management.py
│   │   │
│   │   │  ── MOBILITY & TRANSPORT ──
│   │   │
│   │   ├── mobility/                  # Transportation services
│   │   │   ├── gui/
│   │   │   │   ├── parking_management/ # Parking GUI package (4+ modules + dialogs/ + tabs/)
│   │   │   │   ├── trip_management_gui/ # Trip GUI package (12 modules)
│   │   │   │   ├── taxi_booking_gui.py
│   │   │   │   ├── train_station_gui.py
│   │   │   │   └── mobile_app_pwa_gui.py
│   │   │   └── services/
│   │   │       ├── parking_management/ # Parking service package (12 modules)
│   │   │       └── trip_management/   # Trip service package (12 modules)
│   │   │
│   │   │  ── BUSINESS SERVICES ──
│   │   │
│   │   ├── barber/                    # Barber shop (features/ + tabs/ packages)
│   │   ├── betting/                   # Betting shop
│   │   ├── blockchain/                # Blockchain credentials
│   │   ├── butcher/                   # Butcher shop
│   │   ├── carrental/                 # Car rental
│   │   ├── cinema/                    # Cinema (59-file package)
│   │   │   └── gui/cinema_gui/        # Modular cinema GUI
│   │   │       └── reports/           # Sales reports (6 split modules)
│   │   ├── dentist/                   # Dental services
│   │   ├── equipment/                 # Equipment rental
│   │   ├── gym/                       # Gym & fitness
│   │   ├── legal/                     # Legal services (7 mixin modules)
│   │   ├── mail/                      # Mail/post services
│   │   ├── musicshop/                 # Music shop
│   │   ├── nailbar/                   # Nail bar/salon
│   │   ├── phoneshop/                 # Phone shop
│   │   │
│   │   │  ── STUDENT SUCCESS (23 modules) ──
│   │   │
│   │   ├── advising/                  # Academic Advising Portal
│   │   ├── student_id/                # Digital Student ID Card
│   │   ├── study_rooms/               # Study Room Booking
│   │   ├── printing/                  # Printing Services
│   │   ├── textbooks/                 # Textbook & Course Materials Store
│   │   ├── ai_study/                  # AI Study Companion
│   │   ├── study_matching/            # Peer Study Matching
│   │   ├── academic_progress/         # Academic Progress Dashboard
│   │   ├── course_planning/           # Course Planning Assistant
│   │   ├── student_jobs/              # Student Job Board
│   │   ├── budget/                    # Budget Tracker
│   │   ├── scholarship_finder/        # Scholarship Finder
│   │   ├── roommate_finder/           # Roommate Finder
│   │   ├── campus_navigation/         # Campus Navigation (gui/ split: 5 mixin modules + tabs/)
│   │   ├── lost_found/                # Lost & Found System
│   │   ├── marketplace/               # Student Marketplace
│   │   ├── wellness/                  # Mental Health & Wellness Hub
│   │   ├── accessibility/             # Accessibility Services Portal
│   │   ├── events/                    # Event Discovery Engine
│   │   ├── social_matching/           # Interest-Based Social Matching (services/ split: 9 mixin modules)
│   │   ├── portfolio/                 # Achievement & Portfolio System
│   │   ├── notifications/             # Smart Notifications Hub
│   │   ├── feedback/                  # Feedback & Suggestion Box
│   │   │   (each with cli/, gui/, and services/ subdirectories)
│   │   │
│   │   └── alumni/                    # Alumni services
│   │
│   ├── services/                      # Application services layer
│   │   ├── cli/                       # 28 CLI service modules
│   │   │   ├── academic_misconduct_cli.py
│   │   │   ├── barber_cli.py          # Barber shop CLI
│   │   │   ├── betting_shop_cli/      # Betting shop CLI package (9 modules)
│   │   │   ├── butcher_cli.py         # Butcher shop CLI
│   │   │   ├── cafe_system_cli.py     # Cafe system CLI
│   │   │   ├── charity_shop_cli/      # Charity shop CLI package (12 modules)
│   │   │   ├── cinema_cli/            # Cinema CLI package (11 modules + admin/)
│   │   │   ├── degree_audit_cli.py    # Degree audit CLI
│   │   │   ├── health_portal.py       # Health portal CLI
│   │   │   ├── nailbar_cli.py         # Nail bar CLI
│   │   │   └── ...                    # 18 more CLI modules
│   │   └── gui/                       # GUI service components
│   │       ├── charity_shop_gui/      # Charity shop GUI package (11 modules)
│   │       └── integration_marketplace_gui/ # Marketplace GUI (17 modules)
│   │
│   └── shared/                        # Shared utilities & components
│       ├── cli/                       # Main CLI application
│       ├── config/                    # Configuration management
│       │   └── templates/             # Config templates
│       ├── constants/                 # Centralized paths & constants
│       │   └── paths.py              # Single source of truth for ALL paths
│       ├── gui/                       # Shared GUI components
│       │   ├── main/                  # Main application GUI
│       │   │   ├── main_gui.py        # Main GUI application
│       │   │   ├── admin/             # Admin management GUIs
│       │   │   ├── core/              # Core GUI setup
│       │   │   ├── dashboard/         # Role-based dashboards
│       │   │   │   ├── admin_dashboard.py       # Admin dashboard
│       │   │   │   ├── instructor_dashboard.py  # Instructor dashboard
│       │   │   │   ├── student_dashboard.py     # Student dashboard
│       │   │   │   ├── student_widgets.py       # Student summary widgets
│       │   │   │   ├── login_analytics_dashboard.py # Login analytics
│       │   │   │   ├── operations_dashboard.py  # Operational metrics
│       │   │   │   ├── system_health_dashboard.py # System health (live)
│       │   │   │   └── dashboard_gui.py         # Dashboard framework
│       │   │   ├── email/             # Email GUI components
│       │   │   ├── features/          # Feature-specific GUIs
│       │   │   ├── imports/           # Import management
│       │   │   ├── staff/             # Staff management GUIs
│       │   │   └── students/          # Student management GUIs
│       │   ├── admin/                 # Admin configuration GUIs
│       │   │   ├── alert_config_gui.py          # Alert & notification config
│       │   │   ├── branding_config_gui.py       # Institution branding
│       │   │   └── department_management_gui.py # Department & org management
│       │   ├── auth/                  # Authentication GUIs (MFA wizard)
│       │   ├── advanced_search/       # Advanced search interface
│       │   ├── batch_operations/      # Batch operations GUI
│       │   │   └── mixins/            # Batch operation mixins (15 modules)
│       │   ├── database/              # Database management GUI
│       │   ├── document_manager_gui/  # Document management (26 files)
│       │   ├── email/                 # Email management GUI
│       │   ├── enhanced_reporting/    # Enhanced reporting (tabs, dialogs)
│       │   ├── logic/                 # GUI logic layer
│       │   ├── simple_activity_logger_gui/ # Activity logger (6 modules + tabs/)
│       │   ├── student_analytics_gui/ # Student analytics (10 modules)
│       │   └── tools/                 # Tool GUIs
│       ├── services/                  # Shared services
│       │   ├── ai_features/           # AI features (with GUI)
│       │   ├── analytics/             # Analytics & advanced search
│       │   │   ├── advanced_search/   # Search package (18 modules)
│       │   │   ├── enhanced_reporting/ # Reporting package (14 modules)
│       │   │   └── student_analytics/ # Analytics package (16 modules)
│       │   ├── business_intelligence/ # BI services
│       │   ├── communication/         # Communication services
│       │   ├── dashboard/             # Dashboard data services
│       │   ├── integrations/          # Integration services
│       │   │   └── integration_marketplace_core/ # Marketplace (18 modules)
│       │   └── pdf_export/            # PDF export (4 files)
│       └── utils/                     # Utility functions
│           ├── activity_logger.py     # Audit trail logging
│           ├── batch_operations/      # Batch ops package (14 modules)
│           ├── config.py              # Configuration management
│           ├── document_manager/      # Doc manager package (22 modules)
│           ├── simple_activity_logger/ # Logger package (9 modules + plugins/)
│           └── validation.py          # Input validation
│
├── utils/                             # Cross-cutting utilities
│   ├── ai/                            # AI & chatbot
│   │   ├── university_chatbot/        # Chatbot package (17 modules)
│   │   └── gui/                       # Chatbot GUI (11 modules + features/ + screens/)
│   └── logging/                       # Logging infrastructure
│       ├── log_management/            # Log mgmt package (9 modules + api/ + cli/)
│       └── gui/                       # Log GUI (4 modules + features/ + tabs/)
│
├── data/                              # Application data directory
│   ├── analytics/                     # Analytics outputs
│   │   └── plots/                     # Generated plots
│   ├── chatbot/                       # Chatbot data & models
│   ├── config/                        # Runtime configuration
│   ├── db_files/                      # Database files
│   │   ├── student_records.db         # Main SQLite database
│   │   └── exports/                   # Database exports
│   ├── email/                         # Email queue
│   ├── locales/                       # i18n translations (10 languages)
│   │   ├── ar/                        # Arabic
│   │   ├── de/                        # German
│   │   ├── en/                        # English (14 JSON files)
│   │   ├── es/                        # Spanish
│   │   ├── fr/                        # French
│   │   ├── ja/                        # Japanese
│   │   ├── ko/                        # Korean
│   │   ├── pt/                        # Portuguese
│   │   ├── ru/                        # Russian
│   │   └── zh/                        # Chinese
│   ├── reports/                       # Generated reports (PDF, Excel)
│   │   └── timetable_reports/
│   ├── submissions/                   # Assignment submissions
│   │   ├── submitted/                 # Student submissions
│   │   ├── graded/                    # Graded work
│   │   ├── feedback/                  # Submission feedback
│   │   └── templates/                 # Submission templates
│   └── uploads/                       # User uploads
│       ├── accommodation/
│       ├── lost_found/
│       ├── marketplace/
│       └── tickets/
│
├── tests/                             # Comprehensive test suite
│   ├── cli/                           # CLI tests
│   ├── gui/                           # GUI tests
│   ├── conftest.py                    # Pytest configuration
│   ├── run_all_tests.py               # Test runner
│   ├── test_end_to_end_journeys.py
│   ├── test_integration_workflows.py
│   ├── test_mfa_unique_contacts.py
│   ├── test_performance_benchmarks.py
│   ├── test_remember_me.py
│   └── test_staff_crud.py
│
├── templates/                         # All templates (consolidated)
│   ├── assignments/                   # Assignment templates
│   ├── backup_templates/              # 6 pre-configured backup templates
│   ├── course_evaluation/             # Evaluation templates
│   ├── email/                         # 358 email templates in 40 categories
│   │   ├── academics/
│   │   ├── authentication/
│   │   ├── finance/
│   │   ├── health/
│   │   ├── housing/
│   │   ├── security/
│   │   └── ...                        # 34 more category directories
│   ├── finance_templates/
│   ├── medical_templates/
│   ├── reports_templates/
│   ├── resources/
│   └── ticket_templates/
│
├── extras/                            # Extras & Tools module
│   ├── launcher.py                    # GUI launcher for all extras
│   ├── games/                         # Python games collection
│   │   ├── standalone-games/          # Single-file games
│   │   ├── Aeroblasters/              # 30+ game projects with assets:
│   │   ├── Bounce/                    # Bounce, Cave Story, Dino,
│   │   ├── Flappy Bird/               # Flappy Bird, GhostBusters,
│   │   ├── Snake/                     # Hangman, Jungle Dash,
│   │   ├── Tetris/                    # Pong, Snake, Tetris, etc.
│   │   └── ...
│   ├── standalone-utilities/          # Calculator, countdown, network tools
│   ├── python-utilities/              # 16 utility projects
│   │   ├── file-explorer/             # File explorer, image viewer,
│   │   ├── paint/                     # paint, text editor, note-taking,
│   │   ├── webapps/                   # Flask/FastAPI/Django webapps
│   │   └── ...
│   └── 91_Python_Mini_Projects-main/  # 91 mini projects collection
│
├── logs/                              # Application logs
├── backups/                           # Database backups
├── qr_codes/                          # Generated QR codes
├── scripts/                           # Utility scripts
├── extensions/                        # Extensions directory
│
├── CHANGELOG.md                       # Version history
├── docker-compose.yml                 # Docker Compose configuration
├── Dockerfile                         # Docker build configuration
├── LICENSE                            # MIT License
├── Makefile                           # Development commands
├── pyproject.toml                     # Project configuration
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
└── run.py                             # Main entry point (legacy)
```

### Sixth-Form System Structure

```
education_system/post_16/sixthform_system/
│
├── api/                               # REST API layer
├── core/                              # Core utilities (paths, exceptions, i18n)
├── infrastructure/                    # Auth, database, validation, email
├── data/                              # Per-system SQLite DB + templates
│   └── sixthform.db                   # Single shared DB for all domain tables
├── tests/                             # Test suite
│
├── modules/
│   ├── domain/                        # 9 thematic packages, 110 modules
│   │   ├── students/                  # 7: students, admissions, enrolments,
│   │   │                              #   onboarding, bulk_operations, alumni,
│   │   │                              #   advanced_search
│   │   ├── academics/                 # 15: academic_year, subjects, courses,
│   │   │                              #   class_groups, timetable, attendance,
│   │   │                              #   homework, assignments, lesson_plans,
│   │   │                              #   cover, cover_agency, enrichment,
│   │   │                              #   calendar, library, work_experience
│   │   ├── assessment/                # 15: assessments, gradebook, mock_exams,
│   │   │                              #   exam_entries, exam_results, predicted_grades,
│   │   │                              #   value_added, observations, progress,
│   │   │                              #   target_setting, reports, etc.
│   │   ├── progression/               # 6: ucas, apprenticeships, careers, offers,
│   │   │                              #   personal_statements, references
│   │   ├── pastoral/                  # 21: behaviour, detentions, safeguarding,
│   │   │                              #   send, attendance_concerns, absence_requests,
│   │   │                              #   first_aid, prevent_duty, peer_mentoring,
│   │   │                              #   wellbeing, etc.
│   │   ├── finance/                   # 7: fees, bursaries, expense_claims, funding,
│   │   │                              #   receipts, trips, census_ilr
│   │   ├── staff_comms/               # 20: staff, staff_hr, staff_absence,
│   │   │                              #   staff_wellbeing, recruitment, appraisals,
│   │   │                              #   cpd, dbs_checks, parent_contacts,
│   │   │                              #   parents_evenings, announcements,
│   │   │                              #   notifications, messaging, etc.
│   │   ├── governance/                # 9: compliance, gdpr, policies, audit_reports,
│   │   │                              #   risk_management, health_safety, etc.
│   │   └── reports/                   # 10: kpi_dashboard, data_dashboard,
│   │                                  #   mobile_dashboard, custom_export,
│   │                                  #   data_export, progress_report, etc.
│   └── shared/
│       ├── cli/                       # Shared CLI components (login, MFA, menu)
│       └── gui/                       # Shared GUI components
│
├── cli_main.py                        # CLI entry point (post-launcher)
├── gui_main.py                        # Tk GUI entry point (post-launcher)
├── paths.py                           # Convenience path exports
└── __init__.py
```

### Secondary School Structure

```
education_system/secondarysch_system/
│
├── core/                              # Core utilities (paths, exceptions)
├── data/                              # Per-system SQLite DB
│   └── secondary.db                   # Single shared DB for all domain tables
│
├── modules/
│   ├── domain/                        # 8 thematic packages, 102 modules
│   │   ├── pupils/                    # 6: pupils, admissions, enrolment,
│   │   │                              #   onboarding, bulk_operations, alumni
│   │   ├── academics/                 # 15: academic_year, subjects, options,
│   │   │                              #   timetable, attendance, homework,
│   │   │                              #   assignments, lesson_plans, calendar,
│   │   │                              #   cover, cover_agency, enrichment,
│   │   │                              #   library, form_groups
│   │   ├── assessment/                # 14: assessment_records, gradebook,
│   │   │                              #   mock_exams, exam_entries, exam_results,
│   │   │                              #   predicted_grades, gcse_options,
│   │   │                              #   observations, progress, target_setting,
│   │   │                              #   reports, etc.
│   │   ├── pastoral/                  # 23: behaviour, detentions, disciplinary,
│   │   │                              #   safeguarding, send, attendance_concerns,
│   │   │                              #   absence_requests, first_aid,
│   │   │                              #   prevent_duty, peer_mentoring,
│   │   │                              #   accessibility, complaints, equality_diversity,
│   │   │                              #   emergency, feedback, form_tutors, etc.
│   │   ├── finance/                   # 6: fees, expense_claims, funding,
│   │   │                              #   receipts, trips, census
│   │   ├── staff_comms/               # 20: staff, staff_hr, staff_absence,
│   │   │                              #   staff_wellbeing, recruitment, appraisals,
│   │   │                              #   cpd, dbs_checks, parent_contacts,
│   │   │                              #   parents_evenings, announcements,
│   │   │                              #   notifications, messaging, etc.
│   │   ├── governance/                # 10: compliance, gdpr, policies,
│   │   │                              #   audit_reports, risk_management,
│   │   │                              #   health_safety, etc.
│   │   └── reports/                   # 8: kpi_dashboard, data_dashboard,
│   │                                  #   mobile_dashboard, custom_export,
│   │                                  #   data_export, progress_report,
│   │                                  #   attendance_report, etc.
│   └── shared/
│       └── gui/                       # Shared GUI components
│
├── cli_main.py                        # CLI entry point
├── gui_main.py                        # Tk GUI entry point
└── __init__.py
```

### Primary School Structure

```
education_system/primarysch_system/
│
├── core/                              # Core utilities (paths, exceptions)
├── data/                              # Per-system SQLite DB
│   └── primary.db                     # Single shared DB for all domain tables
│
├── modules/
│   ├── domain/                        # 98 flat domain modules (no thematic
│   │   │                              #   grouping — each is its own package
│   │   │                              #   with <name>.py / <name>_cli.py /
│   │   │                              #   <name>_views.py)
│   │   │
│   │   ├── [Pupils & onboarding]      # pupils, pupils/onboarding,
│   │   │                              #   pupils/bulk_operations, pupils/leavers,
│   │   │                              #   admissions, enrolment, year_groups,
│   │   │                              #   classes, class_teachers
│   │   ├── [Academics]                # academic_year, calendar, subjects,
│   │   │                              #   timetable, attendance, lesson_plans,
│   │   │                              #   cover, homework, library, clubs
│   │   ├── [Assessment & progress]    # assessment, mtc, ks1_sats, ks2_sats,
│   │   │                              #   phonics, phonics_screening,
│   │   │                              #   reading_levels, eyfs_profile,
│   │   │                              #   target_setting, pupil_reports,
│   │   │                              #   intervention_tracking, early_warning,
│   │   │                              #   observations, progress
│   │   ├── [Pastoral & wellbeing]     # behaviour, safeguarding, send,
│   │   │                              #   pupil_premium, accessibility,
│   │   │                              #   wellbeing, pupil_support,
│   │   │                              #   attendance_concerns, absence_requests,
│   │   │                              #   first_aid, medical_records, emergency,
│   │   │                              #   prevent_duty, equality_diversity,
│   │   │                              #   complaints, feedback, surveys,
│   │   │                              #   school_council, transport, wraparound,
│   │   │                              #   house_points
│   │   ├── [Staff & communications]   # staff, teaching_assistants, staff_hr,
│   │   │                              #   staff_absence, staff_wellbeing,
│   │   │                              #   recruitment, appraisals, cpd,
│   │   │                              #   dbs_checks, departments, visitors,
│   │   │                              #   parent_contacts, parents_evenings,
│   │   │                              #   newsletters, announcements,
│   │   │                              #   notifications, activity_feed, messages,
│   │   │                              #   letter_templates, document_hub, attachments
│   │   ├── [Finance]                  # dinner_money, trips, receipts,
│   │   │                              #   expense_claims, funding, census
│   │   ├── [Reports & analytics]      # attendance_report, progress_report,
│   │   │                              #   kpi_dashboard, data_dashboard,
│   │   │                              #   mobile_dashboard, audit_reports,
│   │   │                              #   data_export, custom_export
│   │   └── [Governance & system]      # compliance, governance, policies, gdpr,
│   │                                  #   risk_management, health_safety, assets,
│   │                                  #   todo, mfa, user_management
│   │
│   └── shared/                        # Shared CLI/GUI helpers (login menus,
│                                      #   about page, settings, MFA, etc.)
│
├── cli_main.py                        # CLI entry point (post-launcher)
├── gui_main.py                        # Tk GUI entry point (post-launcher)
└── __init__.py
```

> **Flat vs. layered:** primary keeps a flat domain layout — every domain
> module is a sibling package directly under ``modules/domain/`` with
> the standard ``<name>.py`` / ``<name>_cli.py`` / ``<name>_views.py``
> triplet. Secondary and sixth-form group their modules into thematic
> packages (``academics/``, ``pastoral/``, ``assessment/`` …). The
> grouping comments above mirror how the CLI/GUI categorise actions —
> they are not actual subdirectories on disk for primary.

### Nursery System Structure

```
education_system/nursery_system/
│
├── core/                              # Core utilities
│   ├── database.py                    # Database access helpers
│   └── paths.py                       # Centralized paths (NURSERY_DB = data/nursery.db)
├── data/                              # Per-system SQLite DB
│   └── nursery.db                     # Single shared DB for all domain tables
│
├── modules/
│   └── domain/                        # 80 flat domain modules (each its own
│       │                              #   package; grouping below is thematic,
│       │                              #   not on-disk subdirectories)
│       │
│       ├── [Children & enrolment]     # children, admissions, enrolment, leavers,
│       │                              #   transitions, settling_in, cohort_tracking,
│       │                              #   key_persons
│       ├── [EYFS, curriculum &        # eyfs_compliance, eyfs_profile,
│       │    learning]                 #   curriculum_planning, observations,
│       │                              #   learning_journeys, development_tracking,
│       │                              #   effective_learning, next_steps, evidence,
│       │                              #   progress_check_2yr, daily_diary,
│       │                              #   daily_updates, activity_feed
│       ├── [Health & daily care]      # allergies, medication_log, first_aid,
│       │                              #   accident_log, accident_report,
│       │                              #   existing_injuries, sleep_log,
│       │                              #   toileting_log, bottle_feeds, meals,
│       │                              #   welfare, wellbeing
│       ├── [Safeguarding &            # safeguarding, dsl, concerns, prevent_duty,
│       │    compliance]               #   looked_after, ehc_plans, send, consents,
│       │                              #   risk_assessments, ofsted, policies,
│       │                              #   complaints, feedback, gdpr, audit_reports,
│       │                              #   data_export
│       ├── [Attendance, occupancy     # daily_register, sign_in_out,
│       │    & ratios]                 #   attendance_report, occupancy,
│       │                              #   occupancy_report, ratios, rooms
│       ├── [Finance]                  # invoices, payments, funded_hours,
│       │                              #   funding_claims, funding_report,
│       │                              #   childcare_vouchers, discounts,
│       │                              #   expense_claims
│       ├── [Staff & HR]               # staff, staff_absence, appraisals,
│       │                              #   qualifications, dbs_checks, recruitment, rota
│       ├── [Communication]            # messaging, email_centre, newsletters,
│       │                              #   parent_contacts, parent_meetings,
│       │                              #   emergency_contacts, visitors
│       └── [Administration]           # dashboard, user_management, mfa
│
├── cli_main.py                        # CLI entry point (post-launcher)
├── main_gui.py                        # Tk GUI entry point (post-launcher)
├── menu.py                            # Menu definitions
├── tests/                             # Test suite
└── __init__.py                        # Package init (SYSTEM_NAME = "Nursery System")
```

> **Launcher note:** Nursery launches directly via `python run.py --nursery --gui`
> (or `--cli`), or from the interactive launcher menu (`python run.py` → option 5).
> It is fully integrated into the shared launcher, authentication, and
> cross-system switching.

### Documentation Structure

```
docs/
│
├── university_system/                    # University system documentation
│   ├── README.md                        # Documentation index
│   ├── QUICK_START.md                   # Get running in 5 minutes
│   ├── TROUBLESHOOTING.md              # Common issues and solutions
│   ├── ai/                             # AI feature documentation
│   │   ├── AI_DEPENDENCIES.md
│   │   └── VOICE_FEATURES.md
│   ├── development/                     # Developer documentation
│   │   ├── README.md                   # Development overview
│   │   ├── API.md                      # REST API reference
│   │   ├── EXCEPTION_HANDLING.md       # Error handling patterns
│   │   ├── MIGRATION_GUIDE.md          # Module restructuring reference
│   │   └── TESTING_GUIDE.md            # Testing framework guide
│   ├── guides/                         # User guides (60+)
│   │   ├── README.md                   # Guides index
│   │   ├── academics/                  # Academic feature guides
│   │   ├── administration/             # Admin & system guides
│   │   ├── campus/                     # Campus service guides
│   │   ├── commerce/                   # Commerce & dining guides
│   │   ├── health/                     # Health service guides
│   │   ├── student/                    # Student life guides
│   │   └── technical/                  # Technical guides
│   ├── infrastructure/                  # Infrastructure guides
│   │   ├── DATABASE.md                 # Database schema and usage
│   │   ├── EMAIL_SCHEDULER.md          # Automated email system
│   │   ├── ENHANCEMENTS_GUIDE.md       # Enhancement documentation
│   │   └── TRANSACTIONS.md            # Transaction safety guide
│   ├── modules/                        # Module documentation
│   │   └── README.md                  # Module overview
│   └── security/                       # Security documentation
│       ├── AUTHENTICATION.md           # Authentication guide
│       ├── AUTH_QUICK_REFERENCE.md     # Quick auth reference
│       ├── MFA_QUICK_START.md          # MFA setup guide
│       ├── MFA_SYSTEM_DOCUMENTATION.md # Complete MFA guide
│       └── SECURITY.md               # Security best practices
│
├── sixthform_system/                   # Sixth-form system documentation (planned)
│
├── secondarysch_system/                # Secondary school documentation (planned)
│
└── primarysch_system/                  # Primary school documentation (planned)
```

### Shared Infrastructure Structure

```
education_system/shared/
│
├── api/                                 # Unified REST API server
│   ├── unified_server.py               # Flask app serving all systems
│   ├── auth.py                         # JWT auth (login, register, MFA, password reset)
│   ├── api_keys.py                     # API key auth (expiry, rotation)
│   ├── rate_limiter.py                 # Persistent rate limiting (SQLite-backed)
│   ├── middleware.py                   # Request logging, correlation IDs
│   ├── caching.py                      # Response caching middleware
│   ├── websocket_server.py            # Socket.IO real-time (chat, notifications, presence)
│   ├── graphql/                        # GraphQL API (Strawberry)
│   │   ├── schema.py                  # Root Query & Mutation
│   │   ├── types.py                   # Type definitions
│   │   ├── resolvers.py              # Query resolvers
│   │   ├── mutations.py              # Mutation handlers
│   │   └── middleware.py             # Auth & rate limit middleware
│   ├── web/                           # Web Portal
│   │   ├── routes.py                 # Login, dashboard, admin pages
│   │   └── pwa.py                    # PWA manifest, service worker, offline page
│   └── {system}/routes.py            # Per-system API route bundles
│
├── auth/                               # Unified authentication
│   ├── core.py                        # UserAuth facade (login, MFA check, password expiry)
│   ├── password_manager.py            # bcrypt hashing, common password rejection, timing fix
│   ├── password_reset.py             # Secure token-based password reset (30-min expiry)
│   ├── session_manager.py            # DB-backed sessions with timeout
│   ├── role_manager.py               # Role hierarchy (8 roles, per-system)
│   ├── mfa_service.py                # TOTP MFA with recovery codes
│   ├── schema.py                     # Auth DB schema (users, sessions, MFA, password history, consent, reset tokens)
│   └── db.py                         # Connection helper (WAL, retry, chmod 600)
│
├── audit/                              # Unified audit logging
│   └── audit_service.py              # Cross-system audit trail with checksum tamper detection
│
├── analytics/                          # Analytics & predictions
│   └── early_warning.py              # Student risk prediction (attendance, grades, behaviour)
│
├── backup/                             # Backup & restore
│   ├── backup_manager.py             # Backup with optional Fernet encryption
│   └── backup_scheduler.py           # Automated daily/weekly/hourly backups
│
├── gdpr/                               # GDPR compliance
│   ├── gdpr_service.py               # SAR, anonymisation, rectification, restriction, portability
│   └── consent_service.py            # 15 consent types (grant, withdraw, export)
│
├── integrations/                       # External system integrations
│   ├── lms_base.py                   # Abstract LMS provider
│   ├── lms_sync_service.py           # Sync orchestrator (Canvas, Moodle, Classroom)
│   └── lms_teams.py                  # Microsoft Teams for Education (Graph API)
│
├── offline/                            # Offline-first infrastructure
│   └── sync_service.py               # Local cache, mutation queue, sync state
│
├── security/                           # Security services
│   └── encryption.py                 # Fernet field-level encryption (warns if key missing)
│
├── services/data_retention/            # GDPR data retention
│   ├── models.py                     # Policies, jobs, DSAR tracking
│   ├── policy_engine.py              # Retention policy execution
│   ├── anonymizer.py                 # PII anonymisation
│   ├── archiver.py                   # Data archival
│   └── scheduler.py                  # Scheduled policy execution
│
├── validation/                         # Input validation
│   └── validators.py                 # Email, date, grade, time validators
│
├── webhooks/                           # Webhook system
│   └── webhook_service.py            # Subscribe, dispatch, HMAC sign, retry
│
├── database/                           # Database utilities
│   ├── paths.py                      # System DB paths (single source of truth)
│   └── sql_safety.py                 # SQL injection prevention
│
├── core/                               # Core infrastructure
│   └── structured_logging.py         # ELK-compatible JSON logging
│
├── data/                               # Shared data
│   ├── db_files/                     # Central databases (auth.db, audit.db, etc.)
│   └── locales/                      # i18n translations (10 languages)
│
└── tests/                              # Shared test suite
    └── test_accessibility.py          # WCAG 2.1 AA compliance tests
```

### Directory Consolidation Notes (January-February 2026)

**Recent architectural improvements** have consolidated and reorganized the entire codebase:

1. **Domain-Driven Design**: All GUIs moved into their respective domain folders
   - Academic GUIs: `modules/domain/academics/gui/`
   - Finance GUIs: `modules/domain/finance/gui/`
   - Health GUIs: `modules/domain/health/gui/`
   - Student Affairs GUIs: `modules/domain/student_affairs/gui/`
   - Commerce GUIs: `modules/domain/commerce/gui/`
   - Mobility GUIs: `modules/domain/mobility/gui/` (taxi, train, parking, trips)
   - Campus GUIs: `modules/domain/campus/gui/`
   - Career GUIs: `modules/domain/career/gui/`
   - Admissions GUIs: `modules/domain/admissions/gui/`
   - Facilities GUIs: `modules/domain/facilities/gui/`
   - Research GUIs: `modules/domain/research/gui/`
   - Additional Services: barber, betting, butcher, carrental, dentist, equipment, gym, legal, mail, musicshop, nailbar, phoneshop

2. **Eliminated `modules/interfaces/` layer**: All interfaces now live within their domains
   - Previous: `modules/interfaces/gui/finance/` → Now: `modules/domain/finance/gui/`
   - Previous: `modules/interfaces/gui/assignment_system/` → Now: `modules/domain/academics/gui/assignment_system/`

3. **Shared Components**: Consolidated to `modules/shared/`
   - Shared GUIs: `modules/shared/gui/` (main_gui.py, advanced_search_gui.py, etc.)
   - Shared Services: `modules/shared/services/`
   - Shared Utils: `modules/shared/utils/`

4. **Data Directories**: All runtime data consolidated
   - Backups: `backups/`
   - QR Codes: `qr_codes/`
   - Analytics: `data/analytics/`
   - Templates: `templates/`
   - Reports: `data/reports/`
   - Database: `data/db_files/student_records.db`

**Path Management**: All file paths are managed through `modules/shared/constants/paths.py` as the single source of truth. Always use these constants instead of hardcoded paths:

```python
from education_system.university_system.modules.shared.constants import paths

# Correct usage
backup_dir = paths.BACKUP_DIR
analytics_plots = paths.ANALYTICS_PLOTS_DIR
qr_codes = paths.QR_CODES_DIR
templates = paths.TEMPLATES_DIR
db_path = paths.DEFAULT_DB_PATH
```

**Internationalization (i18n)**: All user-facing strings should use the translation function for multi-language support:

```python
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Correct usage - all UI text uses translation keys
button_text = _t("common.save")           # "Save"
error_msg = _t("errors.login_required")   # "You must be logged in..."
domain_text = _t("taxi.book_ride")        # "Book a Ride"
```

This ensures consistency across all modules and prevents path-related errors.

---

