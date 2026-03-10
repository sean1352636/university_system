# Education System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive, enterprise-grade education management platform spanning four distinct systems — **University**, **Sixth Form College**, **Secondary School**, and **Primary School** — designed to handle all aspects of educational administration. This modular platform integrates academic, financial, student affairs, health services, and administrative operations into a unified, scalable solution with multiple interface options (CLI, GUI, REST API), shared authentication, and a unified launcher with cross-system switching.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Systems Overview](#systems-overview)
- [What's New](#whats-new)
- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Python Packages](#python-packages)
- [Development](#development)
- [Testing](#testing)
- [Security](#security)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Module Guides](#module-guides)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/sean1352636/university_system.git
cd university_system
pip install -r requirements.txt

# Run the unified launcher (interactive system & mode selection)
python run.py

# Or specify system and mode directly
python run.py --university --gui    # University GUI
python run.py --college --gui       # Sixth Form College GUI
python run.py --school --gui        # Secondary School GUI
python run.py --primary --gui       # Primary School GUI
python run.py --university --cli    # University CLI
python run.py --college --cli       # College CLI
python run.py --school --cli        # Secondary School CLI
python run.py --primary --cli       # Primary School CLI
python run.py --college --api       # College REST API
python run.py --university --api    # University REST API
python run.py --university --test   # University tests
python run.py --college --test      # College tests

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
```

**Default Login**: `superadmin` / `SuperAdmin@123` (access to all systems — change immediately in production!)

---

## Systems Overview

The Education System is a unified platform containing four independently functional management systems, each tailored to a specific tier of education:

### 1. University Management System

A full-featured higher education platform with the most comprehensive feature set.

| Metric | Value |
|--------|-------|
| **Python Files** | 3,420+ |
| **Domain Modules** | 51 |
| **API Route Files** | 64 |
| **Test Files** | 465+ |
| **Infrastructure Subsystems** | 22 |
| **Interfaces** | CLI, GUI (tkinter), REST API (Flask), Web Portal (SPA) |
| **i18n** | 10 languages (ar, de, en, es, fr, ja, ko, pt, ru, zh) |
| **Authentication** | 7 methods (password, TOTP, email/SMS OTP, WebAuthn, biometric, SSO) |

**Domain areas:** Academics, Finance, Student Affairs, Health Services, Housing, Commerce & Dining, Campus & Facilities, Mobility & Transport, Staff HR (31 managers), Student Success (23 modules), and 15+ business service modules (barber, cinema, gym, dentist, etc.).

### 2. Sixth Form College System

A Further Education (FE) college management system for 16-19 institutions, with 110 domain modules.

| Metric | Value |
|--------|-------|
| **Python Files** | 930+ |
| **Domain Modules** | 110 |
| **API Route Files** | 59 |
| **Test Files** | 59 |
| **Service Files** | 221 |
| **GUI Files** | 225 |
| **Interfaces** | CLI, GUI (tkinter), REST API (Flask) |

**Domain areas:** Academic & Learning (29 modules — apprenticeships, T-levels, functional skills, UCAS, value-added, study programmes, ILP, skills passport, etc.), Student Support & Welfare (15 — safeguarding, SEND, Prevent duty, wellbeing, counseling, peer mentoring), Staff Management (11 — appraisals, CPD, DBS checks, recruitment, staff wellbeing), Administration & Governance (15 — GDPR, quality assurance, self-assessment, KPI dashboard, risk management, compliance), Campus & Facilities (8), Communication & Engagement (7), Finance & Funding (6 — bursary, funding, print credits), and specialist services (marketing, destinations, onboarding, alumni).

### 3. Secondary School Management System

A secondary school management system for Years 7-11 (KS3/KS4, GCSE grades 9-1).

| Metric | Value |
|--------|-------|
| **Python Files** | 290+ |
| **Domain Categories** | 7 |
| **Domain Modules** | 51 |
| **Service Files** | 101 |
| **GUI Files** | 101 |
| **Interfaces** | CLI, GUI (tkinter) |

**Domain areas:** Academics (12 — students, subjects, enrollment, grades, attendance, timetable, homework, exams, progress, interventions, reports), Pastoral Care (8 — behaviour, detentions, exclusions, rewards, safeguarding, SEND), Staff (5 — HR, CPD, cover, staff directory), Admin (9 — admissions, finance, audit log, policies, data export), Student Life (10 — clubs, meals, transport, trips, careers, library, medical, form groups, consent), Facilities (6 — room booking, assets, seating plans, visitors, incidents), and Communication (7 — email, notifications, announcements, calendar, parents' evening).

### 4. Primary School Management System

A primary school management system for Reception through Year 6 (EYFS, KS1, KS2).

| Metric | Value |
|--------|-------|
| **Python Files** | 280+ |
| **Domain Categories** | 7 |
| **Domain Modules** | 46 |
| **Service Files** | 92 |
| **GUI Files** | 92 |
| **Interfaces** | CLI, GUI (tkinter) |

**Domain areas:** Academics (11 — pupils, subjects, classes, assessment, attendance, timetable, homework, SATs, phonics, reading records, progress), Pastoral Care (5 — behaviour, rewards, safeguarding, SEND, pastoral), Staff (4 — HR, CPD, cover, staff directory), Admin (8 — users, settings, admissions, finance, data export, audit log, policies, documents), Pupil Life (8 — clubs, meals, transport, trips, library, medical, class groups, consent), Facilities (4 — room booking, assets, visitors, incidents), and Communication (6 — email, notifications, announcements, calendar, parents' evening, communication log).

### Unified Launcher

All four systems are accessed through a single entry point (`run.py`) that provides both CLI and GUI system selection, with shared authentication (`education_system/shared/auth/`) and support for system/mode switching at runtime via `education_system/switch.py`. Users with access to multiple systems (e.g. superadmin) can switch between systems without re-authenticating.

---

## What's New

### Version 7.5.0 (March 2026)

**Cross-System CLI Switching & Shared Authentication Fixes**

- **System Switching in All CLIs**: All four system CLIs (University, College, Secondary School, Primary School) now support switching to any other system at runtime without re-authenticating
- **University CLI Switch Menu**: Added Switch to College / Secondary School / Primary School options to the university CLI menu
- **CLI Logout Fix**: Logging out and re-logging in via CLI now correctly returns to the universal system selection menu (previously locked users into the current system)
- **Auth Sync Fix**: University CLI auth state now stays in sync after system switches, preventing spurious login prompts
- **Switch Module Enhancement**: `switch.py` `request_logout()` now accepts a `mode` parameter for CLI/GUI-aware logout signalling

### Version 5.47.0 (February 25, 2026)

**Full Web Portal UI for the REST API**

- **Web Portal** (v5.47.0): Complete single-page application at `/portal` with login, dashboard, full CRUD for Students/Courses/Modules/Assignments/Grades/Enrollments/Finance/Users, and auto-detected list views for all other API sections. Dark sidebar navigation, responsive layout, JWT auth with auto-refresh, search/pagination, modal forms, toast notifications. Root `/` now redirects to the portal.

**Previous: 20+ New Staff HR Modules, 5 Student Services, Academic Advising, Codebase Consolidation, Error Logging Overhaul**

Major platform expansion since v5.42.54 across 30+ releases:

- **Centralized Error Logging** (v5.46.3): Added `StreamHandler` to root logger so errors print to stderr and `logs/app.log`; lowered `ErrorLogger` console threshold from CRITICAL to ERROR; added `patch_messagebox_logging()` to auto-log ~4,350 GUI `showerror`/`showwarning` calls (with tracebacks) across ~690 files without per-file changes; fixed 4 Staff HR database schema mismatches (`ip_manager`, `equipment_manager`, `workload_manager`)
- **Staff HR Expansion** (v5.44.0-v5.46.0): 20 new Staff HR modules — Payroll Management, Faculty Schedule Builder, Curriculum Design, Travel & Conference, Sabbatical/Study Leave, Committee Management, IP Management, Lab/Equipment Booking, Substitute Cover, Workload Dashboard, Staff Directory, Mentoring Programme, Grant Budget Tracking, Peer Review, Communication Hub, Teaching Load Management, and more. 75+ new database tables with full GUI integration
- **Student Services** (v5.43.0): 5 new student-facing features — Academic Advising Portal, Digital Student ID Card, Study Room Booking, Printing Services, and Textbook & Course Materials Store
- **Codebase Consolidation** (v5.46.1-v5.46.2): Merged fragmented versioned files — 7 Staff HR schema files into one consolidated module, admin tools GUI and locale files (4 → 2), using centralised path helpers
- **Continued Refactoring** (v5.42.55-v5.42.64): Additional monolithic file decompositions maintaining backward compatibility via `__init__.py` re-exports

**Earlier Highlights (v5.39.6-v5.42.54):**
- Advanced Authentication System (v5.40.0): WebAuthn/FIDO2, SSO (SAML 2.0 & OIDC), biometric, account linking, delegated access
- Massive Code Refactoring (v5.42.x): 54 monolithic files decomposed into focused modular packages
- i18n Expansion (v5.41.x): 500+ hardcoded strings replaced with `_t()` translation calls
- 50+ critical bug fixes, security hardening (removed hardcoded credentials, `secrets`-based password generation)

**Earlier Highlights (v5.22-v5.39.5):**
- Flask REST API with JWT authentication, 57+ endpoint groups across 60 route files
- Major security audit: 25+ critical/high/medium fixes across 30+ files
- Role-based dashboards (admin, instructor, student) with live data and system health monitoring
- 13 student self-service GUIs (profile, security, grades, degree progress, GPA calculator, messaging, forums, etc.)
- Office Hours & TA Management with full CLI + GUI + REST API support
- Seed demo data script populating 30 tables with 310+ records
- Observability & monitoring, automated backups, LRU caching, Remember Me auth
- 10-language internationalization support (ar, de, en, es, fr, ja, ko, pt, ru, zh)

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## Overview

The Education System is a full-featured platform built with Python that provides:

- **Multi-System Architecture**: Four complete management systems (University, Sixth Form College, Secondary School, Primary School) under a unified launcher with shared authentication and cross-system switching
- **Modular Architecture**: Domain-driven design with clearly separated concerns across infrastructure, domain, service, and interface layers
- **Multiple Interfaces**: Command-line (CLI), graphical (Tkinter), REST API (Flask), and Web Portal (browser-based SPA) for diverse user preferences
- **Comprehensive Coverage**: Academic management, financial services, health services, housing, student affairs, and commerce domains
- **Scalable Design**: Thread-safe database connection pooling, Write-Ahead Logging (WAL), and infrastructure-agnostic architecture
- **Secure by Default**: bcrypt password hashing (with legacy PBKDF2-SHA256 transparent migration), 7 authentication methods (including WebAuthn, biometric, SSO), role-based access control, and comprehensive audit logging
- **Extensible**: Manager pattern for modular code organization, making it easy to extend and maintain

### Target Users

- **Administrators**: System configuration, user management, comprehensive reporting, and audit trail analysis
- **Faculty**: Course management, assignment creation, grading, attendance tracking, and academic analytics
- **Students**: Course enrollment, assignment submission, grade viewing, service requests, and student union participation
- **Staff**: Financial operations, health services, facility management, and student support services

### Statistics (All Systems Combined)

- **Total Python Files**: 4,920+ across all four systems
- **Total Domain Modules**: 258 (51 university + 110 college + 51 secondary + 46 primary)
- **Total API Route Files**: 123 (64 university + 59 college)
- **Total Test Files**: 525+ (465 university + 59 college + 1 secondary)
- **Python Version**: 3.11+ (tested on 3.11, 3.12)

#### University System
- **Python Files**: 3,420+
- **Domain Modules**: 51 (including 23 student success modules)
- **REST API Endpoints**: 57+ endpoint groups across 64 route files with JWT authentication
- **Database Tables**: 160+ normalized tables (including 23 Staff HR + 40 Student Success tables)
- **Permissions**: 355+ fine-grained RBAC permissions
- **Email Templates**: 358 templates in 40 categories
- **Staff HR Managers**: 31 specialized manager classes
- **Authentication Methods**: 7 (password, TOTP, email OTP, SMS OTP, WebAuthn, biometric, SSO)
- **Internationalization**: 10 supported languages (ar, de, en, es, fr, ja, ko, pt, ru, zh)
- **Extras**: 90+ games, utilities, and mini-projects included

#### College System
- **Python Files**: 930+
- **Domain Modules**: 110
- **REST API Route Files**: 59
- **Service / GUI / CLI Files**: 221 / 225 / 221

#### Secondary School System
- **Python Files**: 290+
- **Domain Modules**: 51 across 7 categories
- **Service / GUI Files**: 101 / 101

#### Primary School System
- **Python Files**: 280+
- **Domain Modules**: 46 across 7 categories
- **Service / GUI Files**: 92 / 92

---

## Key Features

> The features below primarily describe the **University System**, the most comprehensive of the four systems. The College, Secondary School, and Primary School systems share similar architectural patterns but are tailored to their respective educational contexts — see [Systems Overview](#systems-overview) for details.

### Academic Management
- **Course Management**: Course creation, curriculum planning, prerequisites, and scheduling
- **Student Enrollment**: Registration workflows, waitlists, and prerequisite validation
- **Grade Tracking**: Comprehensive grading system with weighted calculations, GPA computation, and transcript generation
- **Assignment System**: 19 specialized manager files for assignments, submissions, rubric-based grading, peer reviews, and group assignments
- **Virtual Classroom**: Online session management with recording capabilities and analytics
- **Attendance Tracking**: Automated attendance monitoring with alerts and comprehensive reports
- **Academic Analytics**: Performance tracking, predictive analytics, and batch grade prediction

### Financial Services
- **Billing & Payments**: Automated tuition billing, invoice generation, payment processing, and installment plans
- **Scholarship Management**: Application workflows, approval processes, and disbursement tracking
- **Financial Aid**: Need assessment, award management, and compliance reporting
- **Budget Management**: Department budget planning, expense tracking, and variance analysis
- **Collections**: Automated reminder system for overdue payments
- **Financial Reporting**: Revenue forecasts, financial analytics, and comprehensive reports

### Student Success & Engagement

A comprehensive suite of AI-powered and student-focused tools designed to enhance academic success, financial wellness, career readiness, and campus life:

#### 🎓 Academic & Study Tools
- **AI Study Companion** - Intelligent study assistance with:
  - Personalized study plan generator based on upcoming exams and assignment deadlines
  - Spaced repetition flashcard system integrated with course materials
  - AI-powered concept explainer that breaks down difficult topics from enrolled courses
  - Smart scheduling that adapts to your study habits and availability
  - Progress tracking and analytics for study sessions

- **Peer Study Matching** - Find perfect study partners with:
  - Intelligent matching algorithm based on study style, schedule, and course enrollment
  - Shared virtual study rooms with integrated Pomodoro timers
  - Collaborative note-taking and resource sharing
  - Anonymous Q&A board per course (Piazza-style) with voting and best answers
  - Study group management with attendance tracking

- **Academic Progress Dashboard** - Visual degree tracking with:
  - Interactive degree completion tracker ("You're 67% through your CS degree")
  - "What-if" GPA calculator to simulate future grade scenarios
  - Early warning system: "Based on your current trajectory, you may want to focus on MATH201"
  - Graduation forecast with timeline and acceleration options
  - Milestone tracking (Freshman Year Complete, Junior Standing, etc.)
  - Progress snapshots by semester with trend visualization

- **Course Planning Assistant** - Multi-semester planning with:
  - Visual prerequisite mapping and course dependency tracking
  - Conflict detection for scheduling future semesters
  - Recommendations based on peers with similar majors/interests
  - Workload balancing across semesters
  - Integration with degree requirements

#### 💰 Financial Wellness & Employment
- **Student Job Board** - On-campus employment hub with:
  - On-campus job listings (library, dining, IT helpdesk, research assistants)
  - Work-study hour tracking integrated with financial aid allocation
  - Skill-based matching algorithm for student employment
  - Application tracking and interview scheduling
  - Performance reviews and supervisor feedback
  - Automated payroll integration

- **Budget Tracker** - Personal finance management with:
  - Personal finance dashboard linked to tuition/fees
  - Meal plan usage tracker with "days remaining" projections
  - Textbook cost comparison tool across vendors (new, used, rental, digital)
  - Expense categorization and spending analytics
  - Savings goals with progress tracking
  - Income tracking (work-study, scholarships, family support)
  - Budget alerts for overspending

- **Scholarship Finder** - Maximize funding opportunities with:
  - Personalized scholarship recommendations based on student profile
  - Eligibility matching with compatibility scores
  - Application deadline reminders and calendar integration
  - Document vault for essays, transcripts, recommendation letters
  - Application progress tracking
  - Award history and renewal tracking

#### 🏠 Campus Life & Housing
- **Roommate Finder & Compatibility** - Find compatible living partners:
  - Comprehensive lifestyle questionnaire (sleep schedule, noise tolerance, cleanliness)
  - Scientific compatibility scoring algorithm
  - Anonymous messaging before confirming roommate matches
  - Housing preferences and budget matching
  - Roommate agreement templates

- **Campus Navigation & Wayfinding** - Never get lost on campus:
  - Interactive campus map with building directory
  - Indoor navigation for large buildings
  - Accessible route finder for students with mobility needs
  - "Find nearest" feature (restroom, printer, study space, coffee, vending)
  - Event location integration
  - Turn-by-turn directions

- **Lost & Found System** - Recover lost items faster:
  - Report lost items with photo upload and detailed descriptions
  - Browse found items database with advanced filtering
  - Automated notifications when matching items are found
  - Claim verification process
  - Campus-wide and building-specific searches
  - Integration with campus security

- **Student Marketplace** - Campus buying and selling:
  - Buy/sell used textbooks with course-specific listings
  - Furniture and electronics marketplace
  - Subletting listings for housing
  - Free stuff board ("curb alerts" for items being given away)
  - Seller ratings and reviews
  - Safe transaction guidelines

#### 🧠 Wellness & Mental Health
- **Mental Health & Wellness Hub** - Comprehensive student wellness:
  - Optional periodic wellness surveys with mood tracking
  - Mood pattern recognition and personalized insights
  - Discrete counseling appointment booking with immediate availability
  - Crisis resources always visible with 24/7 hotlines
  - Sleep goal setting with gentle reminders
  - Hydration and exercise tracking with gamification points
  - Meditation and mindfulness resources
  - Stress management workshops and events

- **Accessibility Services Portal** - Streamlined accommodation support:
  - Streamlined accommodation request workflow
  - Real-time status tracking for requests
  - Direct messaging with disability services staff
  - Document upload for medical documentation
  - Accommodation renewal tracking
  - Faculty notification system for approved accommodations

#### 🎉 Social & Community
- **Event Discovery Engine** - Never miss campus events:
  - Personalized event recommendations based on interests and past attendance
  - Friends' event attendance (opt-in social feature)
  - Calendar integration with one-click RSVP
  - Event reminders and location details
  - Event check-in for attendance tracking
  - Event photos and recaps

- **Interest-Based Social Matching** - Connect with like-minded students:
  - Find students with similar hobbies, music taste, or career goals
  - Study abroad buddy finder with destination matching
  - Intramural sports team formation
  - Club recommendation engine
  - Social activity suggestions based on personality type
  - Networking for major-specific communities

- **Achievement & Portfolio System** - Showcase your accomplishments:
  - Digital portfolio for projects, research, leadership roles
  - Verified badges (Dean's List, club officer, volunteer hours)
  - Shareable public profile for internship applications
  - Skills endorsement from peers and faculty
  - Resume builder with achievement integration
  - LinkedIn integration for professional networking

#### 📱 Quality of Life Tools
- **Smart Notifications Hub** - Control your information flow:
  - Unified notification center across all university systems
  - Customizable quiet hours and priority levels
  - Daily digest option instead of real-time alerts
  - Channel-specific preferences (academic, social, financial)
  - Push, email, and SMS notification options
  - Smart bundling of related notifications

- **Feedback & Suggestion Box** - Make your voice heard:
  - Anonymous feedback to departments and administration
  - Upvoting system for popular suggestions
  - Status tracking ("Under Review", "Planned", "Implemented")
  - Response from administrators
  - Public suggestion board with trending ideas
  - Impact tracking for implemented suggestions

### Student Affairs
- **Student Union**: 18 specialized files covering clubs, events, elections, facility booking, and competitions
- **Mentorship Program**: Peer mentoring with intelligent matching algorithms and session tracking
- **Equipment Checkout**: Resource lending system for cameras, laptops, and other equipment
- **Engagement System**: Gamification with points, badges, leaderboards, and rewards
- **Community Service**: Volunteer opportunity tracking and service hour management
- **Green Initiatives**: Sustainability programs and environmental impact tracking
- **Academic Support**: Study groups, tutoring services, and peer support programs

### Health Services
- **Medical Records**: HIPAA-compliant secure health information management with encryption
- **Appointment Scheduling**: Online booking system with automated email and SMS reminders
- **Health Portal**: Student-facing portal for accessing records and prescription information
- **Immunization Tracking**: Vaccination records and compliance monitoring
- **Medical Accommodations**: Integration with accessibility tools for students with special needs
- **Analytics**: Health service utilization reports and trend analysis

### Staff HR Management
A comprehensive human resources management system with 15 specialized managers + Staff CRUD:

- **Staff CRUD Management**: Complete staff account management
  - Create new staff members with secure authentication (PBKDF2, 1M iterations)
  - View all staff in searchable tree view with filtering
  - Update staff information, roles (staff/instructor/admin), and active/inactive status
  - Delete staff accounts (admin only) with confirmation and audit logging
  - Advanced search by username, email, name, or role
  - Real-time password reset capability
  - Activity logging for compliance and audit trails
  - Accessible via: Main GUI → Human Resources ▶ Staff Management
  - Role-based permissions (Staff can create/edit, Admin can delete)
  - Test script included: `python3 test_staff_crud.py`
- **Employee Management**: Staff profiles, directory, department management, and organizational structure
- **Contract Management**: Employment contracts, renewal tracking (30/60/90 day alerts), probation periods, amendments history
- **Leave Management**: Leave requests, approval workflows, balance tracking, multiple leave types, calendar integration
- **Time & Attendance**: Clock in/out, timesheet management, approval workflows, overtime tracking
- **Performance Management**: Appraisal cycles, goal setting, performance reviews, 360-degree feedback
- **Training & Development**: Training programs, certifications, mandatory training tracking, expiry alerts
- **Recruitment**: Job postings, application tracking, hiring pipeline, interview scheduling
- **Onboarding**: New hire checklists, task assignments, document collection, orientation tracking
- **Expense Claims**: Expense submission, multi-level approval, category limits, reimbursement tracking
- **Grievance Management**: Confidential grievance filing (anonymous option), investigation workflows, appeals process
- **Disciplinary Management**: Disciplinary records, action tracking, appeals, documentation
- **Exit Management**: Exit interviews, turnover analytics, knowledge transfer, retention insights
- **Asset Management**: Equipment allocation, tracking, depreciation, maintenance schedules
- **Academic Staff Tools**: Faculty management, teaching assignments, research tracking, supervision
- **Communication**: Staff announcements, broadcasts, internal messaging

**Staff HR Features:**
- 14 CLI menu modules for complete terminal-based management
- 14 GUI windows with full Tkinter interfaces
- 23 new database tables with comprehensive schema
- Role-based access (Admin, Manager, Staff views)
- Activity logging for compliance and audit trails
- **Input Validation**: CLI validators with re-prompting, GUI FormValidator class with error highlighting
- **Integration Tests**: Comprehensive test coverage for all HR managers

### Housing & Accommodation
- **Room Assignment**: Automated and manual room assignment workflows
- **Housing Applications**: Online application processing with priority ranking
- **Facility Maintenance**: Maintenance request tracking and work order management
- **Occupancy Management**: Real-time occupancy tracking and availability reporting

### Commerce & Dining
- **Restaurant Management**: Cafeteria and dining hall operations management
- **Menu Management**: Dynamic menu creation and nutritional information tracking
- **Ordering System**: Online ordering with pickup and delivery options
- **Inventory Tracking**: Real-time inventory management and reordering automation
- **Customer Feedback**: Rating and review system for continuous improvement
- **Charity Shop**: Complete stock management system with:
  - Item categorization (Clothing, Books, Electronics, Furniture, etc.)
  - Sales tracking and revenue reporting
  - Shopping basket functionality
  - Student finance account integration
  - Daily/weekly/monthly sales reports
  - Charts and analytics visualization

### Extras & Tools
- **Integrated Launcher**: Built-in launcher for 90+ additional programs accessible from the main GUI
- **Standalone Games**: Python games including Asteroids, Pong, Snake, Tetris, Flappy Bird, and more
- **Game Projects**: Larger game projects with assets (Aeroblasters, Cave Story, GhostBusters, etc.)
- **Standalone Utilities**: Calculator, countdown timer, network tools, username finder
- **Python Utility Projects**: File explorer, image viewer, note-taking apps, paint, text editor, to-do apps
- **91 Mini Projects**: Collection of Python mini-projects for learning and reference

### Mobility & Transportation
- **Taxi Booking**: Complete taxi booking system with fare estimation, driver tracking, and receipt generation
- **Train Station**: Train ticket booking with schedule viewing, seat selection, and e-tickets
- **Parking Management**: Campus parking permits, space availability, and violation tracking
- **Trip Management**: Student trip organization with registration and payment processing
- **Mobile PWA**: Progressive web app interface for mobile access

### Infrastructure
- **Internationalization (i18n)**: Multi-language support with 10 languages
  - Translation function `_t()` available across all GUI modules
  - Translations in `data/locales/` (ar, de, en, es, fr, ja, ko, pt, ru, zh)
  - GUI language selector for runtime language switching
- **Authentication**: Centralized authentication with multi-factor authentication (TOTP, Email OTP, SMS OTP, WebAuthn, Biometric, SSO)
- **Authorization**: Role-based access control (RBAC) with fine-grained permissions
- **Database**: SQLite (default) with connection pooling, WAL mode, and support for PostgreSQL/MySQL
- **Backup System**: Comprehensive backup management with 6 pre-configured templates (daily, encrypted, incremental, cloud, selective, remote)
- **Email Service**: Asynchronous email queue with SMTP integration, 358 templates in 40 categories, and automated scheduling
  - **Email Scheduler**: Background service with scheduled tasks:
    - Satisfaction surveys: Daily at 09:00
    - Book return reminders: Daily at 08:00
    - Overdue book notices: Daily at 10:00
    - SLA breach alerts: Every 30 minutes
- **Console Output**: Professional terminal formatting with ANSI colors, progress bars, tables, and interactive prompts
- **REST API**: Production-ready Flask API server with JWT authentication, 57+ endpoint groups, pagination, rate limiting, and CORS support
- **AI Integration**: Chatbot capabilities, plagiarism detection, and predictive analytics
- **Activity Logging**: Comprehensive audit trails for compliance and security monitoring
- **PDF Database Export**: Comprehensive PDF report generation with charts, tables, and visualizations for full database export
- **Role-Based Dashboards**: Admin, instructor, and student dashboards with live data, system health monitoring, login analytics, and operational metrics

---

## System Architecture

### 4-Layer Domain-Driven Design

```
┌─────────────────────────────────────────────────┐
│  Interface Layer (CLI, GUI, Web)                │
│  - User interaction and presentation            │
├─────────────────────────────────────────────────┤
│  Domain/Service Layer (Business Logic)          │
│  - Core business rules and workflows            │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer (Auth, DB, Email, AI)     │
│  - Cross-cutting technical concerns             │
├─────────────────────────────────────────────────┤
│  Data Layer (SQLite with Connection Pool)       │
│  - Data persistence and transactions            │
└─────────────────────────────────────────────────┘
```

### Design Patterns

- **Domain-Driven Design (DDD)**: Clear separation between business domains
- **Manager Pattern**: Large modules organized with specialized manager classes
- **Repository Pattern**: Data access abstraction for database independence
- **Service Layer**: Encapsulation of complex business logic
- **Factory Pattern**: Centralized object creation and initialization
- **Observer Pattern**: Event-driven notifications across modules
- **Strategy Pattern**: Pluggable algorithms (grading strategies, payment processors, etc.)

### Key Architectural Principles

1. **Single Responsibility**: Each file and class has one clear purpose (~750 lines average)
2. **Explicit Imports**: No wildcard imports for better code clarity and maintainability
3. **Context Managers**: Always used for resource management (database, files, transactions)
4. **Transaction Safety**: ACID-compliant operations with automatic rollback on failure
5. **Centralized Configuration**: Single source of truth via `paths` module
6. **Activity Logging**: All data modifications logged for compliance
7. **Permission Checks**: RBAC enforced at service layer before operations
8. **Backward Compatibility**: Legacy imports preserved via `__init__.py` re-exports

---

## Tech Stack

### Core Technologies

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.8+ (tested on 3.8-3.12) |
| **GUI Framework** | Tkinter (ttk widgets, clam theme) |
| **Web Framework** | Flask (REST API), flask-cors |
| **Database** | SQLite (default), PostgreSQL, MySQL |
| **Authentication** | PBKDF2-SHA256 (1M iterations), PyJWT, pyotp (TOTP), cryptography |

### Data & Analytics

| Category | Technologies |
|----------|-------------|
| **Data Processing** | pandas, numpy |
| **Visualization** | matplotlib, seaborn, plotly |
| **Machine Learning** | scikit-learn (optional: tensorflow, torch) |
| **Document Generation** | reportlab, openpyxl, fpdf2 |

### Development Tools

| Category | Technologies |
|----------|-------------|
| **Testing** | pytest, pytest-cov, pytest-xdist |
| **Code Quality** | Black (formatter), Ruff (linter), mypy (type checking), isort |
| **Scheduling** | schedule library |
| **Networking** | requests, urllib3, paramiko (SSH) |

### Optional Cloud Integration

| Provider | Package |
|----------|---------|
| **AWS** | boto3 |
| **Azure** | azure-storage-blob |
| **Google Cloud** | google-cloud-storage |

---

## Installation

### Prerequisites

- **Python**: 3.8 or higher (3.9+ recommended)
- **pip**: Python package manager
- **SQLite**: Included with Python (or PostgreSQL/MySQL for production)
- **Git**: For cloning the repository
- **Tkinter**: GUI framework (usually included with Python)

**System-specific requirements:**
- Ubuntu/Debian: `sudo apt-get install python3-tk python3-dev`
- CentOS/RHEL: `yum install tkinter python3-devel`
- macOS/Windows: Tkinter included with Python

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/sean1352636/university_system.git
cd university_system

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables (optional)
# Create a .env file based on the Configuration section below
# Edit .env with your configuration

# 4. Run the application
python run.py
```

### Development Setup

```bash
# Install with development dependencies
make install-dev

# Complete setup with pre-commit hooks and directories
make setup

# Verify installation
python run.py --test

# Or use Make commands
make install       # Install production dependencies
make setup         # Complete development setup
make test          # Run tests
```

### Default Login Credentials

All systems use a **unified authentication** system. Log in once and choose which system to access.

**Super Admin** (all systems):

| Username | Password | Access |
|----------|----------|--------|
| `superadmin` | `SuperAdmin@123` | All 4 systems (admin) |

**University System**:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin |
| `staff` | `staff123` | Staff |
| `S12345` | `student123` | Student |

**College System** (Sixth Form):

| Username | Password | Role |
|----------|----------|------|
| `admin1` | `admin1234` | Admin |
| `staff1` | `staff1234` | Staff |
| `student1` | `student1234` | Student |

**Secondary School System**:

| Username | Password | Role |
|----------|----------|------|
| `admin2` | `admin1234` | Admin |
| `staff2` | `staff1234` | Staff |
| `student2` | `student1234` | Student |

**Primary School System**:

| Username | Password | Role |
|----------|----------|------|
| `admin3` | `admin1234` | Admin |
| `staff3` | `staff1234` | Staff |
| `student3` | `student1234` | Student |

> Password pattern: `<Role>@<System>123`

⚠️ **Security Warning**: Change all default passwords immediately after installation, especially in production environments.

---

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Core Settings
DEFAULT_ADMIN_PASSWORD=your_secure_password
DEFAULT_STAFF_PASSWORD=your_secure_password
DEFAULT_STUDENT_PASSWORD=your_secure_password

# Database Configuration (optional - defaults to SQLite)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=university_system
DB_USER=db_user
DB_PASSWORD=secure_password

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_email_password

# Application Settings
APP_ENV=development
DEBUG=True
LOG_LEVEL=INFO
```

### Database Configuration

The system uses a **single unified database** for all operations.

**Supported Database Backends:**

- **SQLite** (default): Zero configuration required
  - Location: `data/db_files/student_records.db`
  - Ideal for development and small-to-medium deployments
  - Configured via `paths.DEFAULT_DB_PATH`

- **PostgreSQL**: Production-grade option (configure in `.env`)
  - Recommended for large-scale deployments
  - Better concurrent access handling

- **MySQL**: Alternative production option (configure in `.env`)

**Database Features:**
- **Thread-safe connection pooling**: 2-10 connections (configurable)
- **Write-Ahead Logging (WAL)**: Improved concurrency without blocking
- **ACID compliance**: Automatic rollback on errors via context managers
- **Schema migration support**: Version-controlled database changes
- **Backup & restore utilities**: Automated and manual options

---

## Usage

### Unified Launcher

```bash
# Start with interactive menu (recommended for first-time users)
python run.py
```

The launcher presents two menus:
1. **Select Mode** — CLI, GUI, API, or Test
2. **Select System** — University, Sixth Form College, Secondary School, or Primary School

For GUI mode, a graphical system selector window appears instead of a text menu.

```bash
# Direct launch examples
python run.py --university --gui    # University GUI
python run.py --college --gui       # College GUI
python run.py --school --gui        # Secondary School GUI
python run.py --primary --gui       # Primary School GUI
python run.py --university --cli    # University CLI
python run.py --college --cli       # College CLI
python run.py --school --cli        # Secondary School CLI
python run.py --primary --cli       # Primary School CLI
python run.py --college --api       # College REST API
python run.py --university --api    # University REST API
```

All four systems support both CLI and GUI modes. REST API is available for University and College systems. Within any CLI session, multi-system users can switch to another system without re-authenticating.

### REST API Server & Web Portal (University)

```bash
# Start the University API server
python run.py --university --api

# Or run directly
python -m education_system.university_system.api.api_server
```

Then open your browser:
- **Web Portal**: `http://localhost:5000/portal` (or just `http://localhost:5000/` which redirects there)
- **API Docs (Swagger UI)**: `http://localhost:5000/api/docs`
- **JSON API Index**: `http://localhost:5000/api`

**Default Login**: `superadmin` / `SuperAdmin@123`

#### Web Portal

The built-in web portal is a full single-page application served directly by the API server — no separate frontend build required. It includes:

- **Login page** with JWT authentication
- **Dashboard** with live system statistics (students, courses, enrollments, payments, and 20+ other counts)
- **Full CRUD pages** for Students, Courses, Modules, Assignments — search, pagination, add/edit/delete
- **Enrollment management** — enroll students, view active enrollments, drop with confirmation
- **Grade management** — record, edit, and delete grades with letter-grade badges
- **Finance** — view fees, record payments with method selection
- **User management** — list and manage user accounts with role badges
- **Auto-detected list views** for all other API sections (Housing, Library, Events, Dining, Facilities, Alumni, Clubs, Help Desk, etc.)
- **Responsive design** — works on desktop, tablet, and mobile

#### REST API

The JSON API provides:
- **JWT Authentication**: Login, logout, token refresh, and current-user endpoints
- **57+ Endpoint Groups**: Full CRUD for students, modules, courses, enrollments, grades, finance, attendance, assignments, timetable, housing, library, health, career, research, admissions, alumni, events, dining, HR, helpdesk, LMS, chat, and more
- **Pagination & Filtering**: Paginated responses with search, sort, and filter query parameters
- **Rate Limiting**: Per-IP sliding-window rate limiter
- **Input Validation**: Request payload validation for all mutation endpoints
- **Activity Logging**: All mutations logged for audit compliance

**API Endpoints Overview:**
```
/portal              - Web Portal (full UI)
/api/docs            - Swagger UI documentation
/api/auth/*          - Authentication (login, logout, refresh, me)
/api/students/*      - Student CRUD
/api/modules/*       - Module CRUD
/api/courses/*       - Course CRUD
/api/enrollments/*   - Enrollment management
/api/grades/*        - Grade management
/api/finance/*       - Financial services
/api/attendance/*    - Attendance tracking
/api/assignments/*   - Assignment management
/api/housing/*       - Housing management
/api/health-services/* - Health services
/api/hr/*            - Staff HR management
/api/helpdesk/*      - Support tickets
/api/lms/*           - Learning management
/api/dashboard/stats - Aggregate statistics
/api/health          - System health check
...and 40+ more endpoint groups
```

### Command-Line Interface (CLI)

```bash
# University CLI
python run.py --university --cli

# College CLI
python run.py --college --cli
```

**Main Menu Options:**
1. Authentication (Login/Logout/Registration)
2. Academic Management (Courses, Enrollment, Attendance)
3. Assignment System (Create, Submit, Grade)
4. Financial Services (Billing, Payments, Scholarships)
5. Student Union (Clubs, Events, Mentorship)
6. Health Services (Appointments, Records)
7. Administrative Functions (Reports, Backups)

### Graphical User Interface (GUI)

```bash
# Launch via unified launcher
python run.py --university --gui
python run.py --college --gui
python run.py --school --gui

# Launch specific University GUI applications directly
python -m education_system.university_system.modules.shared.gui.main.main_gui
python -m education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_gui
```

### Email Scheduler

The system includes a background email scheduler for automated notifications:

```bash
# Start email scheduler (runs in background)
python -m university_system.utils.email_scheduler_control start

# Check scheduler status
python -m university_system.utils.email_scheduler_control status

# Stop scheduler
python -m university_system.utils.email_scheduler_control stop

# Run in foreground (for testing/debugging)
python -m university_system.utils.email_scheduler_control run

# Alternative: Run directly
python -m university_system.infrastructure.email.email_scheduler
```

**Scheduled Tasks:**
- **Satisfaction surveys**: Daily at 09:00
- **Book return reminders**: Daily at 08:00
- **Overdue book notices**: Daily at 10:00
- **SLA breach alerts**: Every 30 minutes

See `university_system/docs/infrastructure/EMAIL_SCHEDULER.md` for detailed documentation.

### Extras & Tools Launcher

The system includes a comprehensive launcher for 90+ additional programs:

```bash
# Launch from main GUI
# Navigate to "AI & Advanced Tools" → "Extras & Tools"

# Launch standalone
python -m university_system.extras.launcher

# Or use the shell script
./university_system/extras/launch.sh
```

**Available Categories:**
- **Standalone Games**: Quick Python games (Asteroids, Pong, Snake, etc.)
- **Game Projects**: Larger games with assets (30+ projects)
- **Standalone Utilities**: Calculator, countdown, network tools
- **Python Utility Projects**: File explorer, image viewer, paint, text editor
- **91 Mini Projects**: Collection of Python mini-projects

**Features:**
- Integrated with main GUI (button in "AI & Advanced Tools" section)
- Category-based navigation
- Automatic entry point detection for projects
- Status display for launched programs
- Matches university system's visual style

### Console Output Utility

The system includes a professional console output utility for enhanced terminal formatting:

```bash
# Demo the console output features
python3 -m university_system.tests.test_console_output
```

**Features:**
- **Colored Messages**: Success (✓ green), Error (✗ red), Warning (⚠ yellow), Info (ℹ cyan), Debug (🔧 dim)
- **Formatted Tables**: Professional bordered tables with auto-sizing columns
- **Progress Bars**: Color-coded progress indicators (red → yellow → green)
- **Interactive Menus**: Numbered menu options with styling
- **Box Messages**: Bordered notifications for important information
- **Headers & Banners**: Decorative section dividers with multiple border styles
- **Summary Boxes**: Statistics display in formatted containers

**Usage in Code:**
```python
from education_system.university_system.modules.shared.utils.console_output import console

# Basic messages
console.success("Operation completed successfully!")
console.error("An error occurred")
console.warning("This is a warning")
console.info("Here's some information")

# Tables
headers = ["ID", "Name", "Course", "Grade"]
rows = [["001", "John Doe", "CS101", "A"]]
console.table(headers, rows, title="Student Records")

# Progress bars
for i in range(100):
    console.progress(i, 100, label="Processing")

# Interactive prompts
response = console.prompt("Enter your choice")
confirmed = console.confirm("Are you sure?")
```

**Smart Features:**
- Auto-detects terminal color support (graceful fallback to plain text)
- Zero external dependencies (pure Python with ANSI codes)
- Thread-safe output operations
- Works on Linux, macOS, Windows 10+ terminals

---

## Project Structure

```
education_system/                         # Root education platform
├── university_system/                    # University Management System (3,420+ files)
├── college_system/                       # Sixth Form College System (930+ files)
├── secondary_school/                     # Secondary School System (290+ files)
├── primary_school/                       # Primary School System (280+ files)
├── shared/                              # Shared modules across all 4 systems
│   ├── auth/                            # Unified authentication (bcrypt, MFA, sessions)
│   ├── cli/                             # Universal CLI login & system selection
│   ├── gui/                             # Universal GUI login window
│   └── data/db_files/auth.db            # Central authentication database
├── docs/                                # Centralised documentation
│   ├── university_system/               # University system docs
│   ├── college_system/                  # College system docs
│   ├── secondary_school/               # Secondary school docs
│   └── primary_school/                 # Primary school docs
├── switch.py                             # Runtime system/mode switching
└── __init__.py

run.py                                    # Unified launcher (CLI & GUI system selector)
pyproject.toml                            # Project configuration
```

### University System Structure

```
education_system/university_system/
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
│   │   ├── gui/                       # Database management GUI
│   │   ├── migrations/                # Schema version migrations
│   │   └── schemas/                   # Database schema definitions
│   ├── data_management/               # Automated backup scheduling
│   ├── email/                         # Email service integration
│   │   ├── admin/                     # Admin email tools (13 modules)
│   │   ├── email_service/             # Async queue & SMTP (7 modules + notifications/)
│   │   └── gui/                       # Email management GUI
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
│   │   │   │   ├── exam_scheduler/     # Exam scheduler (7 modules + tabs/)
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

### College System Structure

```
education_system/college_system/
│
├── api/                               # REST API Layer (Flask)
│   ├── api_server.py                  # Main API server
│   ├── auth.py                        # Authentication handlers
│   ├── config.py                      # API configuration
│   ├── errors.py                      # Error handling
│   ├── pagination.py                  # Pagination utilities
│   ├── validators.py                  # Input validators
│   └── routes/ (59 route files)       # API endpoints per domain
│
├── modules/
│   ├── domain/                        # 110 domain modules
│   │   ├── [Academic & Learning]      # 29 modules: apprenticeships, assignments,
│   │   │                              #   attendance, courses, enrollment, exams,
│   │   │                              #   functional_skills, grades, lesson_plans,
│   │   │                              #   markbook, observations, study_programmes,
│   │   │                              #   timetable, tlevel, tutorial, ucas,
│   │   │                              #   value_added, work_journal, etc.
│   │   ├── [Student Support]          # 15 modules: behaviour, counseling,
│   │   │                              #   enrichment, safeguarding, send,
│   │   │                              #   prevent_duty, peer_mentoring,
│   │   │                              #   student_wellbeing, wellness, etc.
│   │   ├── [Staff Management]         # 11 modules: appraisals, cpd, cover,
│   │   │                              #   dbs_checks, recruitment, staff_hr,
│   │   │                              #   staff_wellbeing, staff_absence, etc.
│   │   ├── [Admin & Governance]       # 15 modules: compliance, gdpr,
│   │   │                              #   quality_assurance, self_assessment,
│   │   │                              #   kpi_dashboard, risk_management, etc.
│   │   ├── [Campus & Facilities]      # 8 modules: assets, equipment, facilities,
│   │   │                              #   lettings, resource_booking, visitors, etc.
│   │   ├── [Communication]            # 7 modules: announcements, calendar,
│   │   │                              #   feedback, messaging, notifications, etc.
│   │   ├── [Finance & Funding]        # 6 modules: bursary, finance, funding,
│   │   │                              #   meal_ordering, print_credits, etc.
│   │   └── [Specialist Services]      # careers, destinations, marketing,
│   │                                  #   onboarding, alumni, departments, etc.
│   └── shared/
│       ├── cli/                       # Shared CLI components
│       └── gui/                       # Shared GUI (login, MFA, dashboard)
│
├── core/                              # Core utilities (exceptions, i18n, paths)
├── infrastructure/                    # Auth, database, security, validation
├── data/                              # Data and configuration files
├── tests/ (59 test files)             # Test suite
└── __init__.py
```

### Secondary School Structure

```
education_system/secondary_school/
│
├── modules/
│   ├── domain/                        # 7 domain categories, 51 modules
│   │   ├── academics/                 # 12 modules: students, subjects, enrollment,
│   │   │                              #   grades, attendance, timetable, homework,
│   │   │                              #   exams, progress, interventions, reports
│   │   ├── pastoral_care/             # 8 modules: behaviour, detentions,
│   │   │                              #   exclusions, rewards, pastoral,
│   │   │                              #   safeguarding, send
│   │   ├── staff/                     # 5 modules: hr, cpd, cover, staff_directory
│   │   ├── admin/                     # 9 modules: users, settings, admissions,
│   │   │                              #   finance, data_export, audit_log,
│   │   │                              #   policies, documents
│   │   ├── student_life/              # 10 modules: clubs, meals, transport, trips,
│   │   │                              #   careers, library, medical, form_groups,
│   │   │                              #   consent
│   │   ├── facilities/                # 6 modules: room_booking, assets,
│   │   │                              #   seating_plans, visitors, incidents
│   │   └── communication/             # 7 modules: email, notifications,
│   │                                  #   announcements, calendar,
│   │                                  #   communication_log, parents_evening
│   └── shared/
│       └── gui/                       # Shared GUI components
│
├── core/                              # Core utilities (defaults, exceptions, paths)
├── infrastructure/                    # Auth, database, validation
├── main_gui.py                        # Entry point with login/tabbed interface
├── seed_subjects.py                   # Subject seeding utility
├── data/                              # Data files
├── tests/                             # Test suite
└── __init__.py
```

### Primary School Structure

```
education_system/primary_school/
│
├── modules/
│   ├── domain/                        # 7 domain categories, 46 modules
│   │   ├── academics/                 # 11 modules: pupils, subjects, classes,
│   │   │                              #   assessment, attendance, timetable,
│   │   │                              #   homework, sats, phonics,
│   │   │                              #   reading_records, progress
│   │   ├── pastoral_care/             # 5 modules: behaviour, rewards,
│   │   │                              #   safeguarding, send, pastoral
│   │   ├── staff/                     # 4 modules: hr, cpd, cover,
│   │   │                              #   staff_directory
│   │   ├── admin/                     # 8 modules: users, settings, admissions,
│   │   │                              #   finance, data_export, audit_log,
│   │   │                              #   policies, documents
│   │   ├── pupil_life/                # 8 modules: clubs, meals, transport,
│   │   │                              #   trips, library, medical,
│   │   │                              #   class_groups, consent
│   │   ├── facilities/                # 4 modules: room_booking, assets,
│   │   │                              #   visitors, incidents
│   │   └── communication/             # 6 modules: email, notifications,
│   │                                  #   announcements, calendar,
│   │                                  #   parents_evening, communication_log
│   └── shared/
│       └── gui/                       # Shared GUI components
│
├── cli/                               # CLI interface
├── core/                              # Core utilities (defaults, exceptions, paths)
├── infrastructure/                    # Auth, database, validation
├── main_gui.py                        # GUI entry point with login/tabbed interface
├── data/                              # Data files
│   └── db_files/primary_school.db     # SQLite database
├── tests/                             # Test suite
└── __init__.py
```

### Documentation Structure

```
education_system/docs/
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
├── college_system/                      # College system documentation (planned)
│
└── secondary_school/                    # Secondary school documentation (planned)
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

## Python Packages

### Core Dependencies

#### Data Processing & Analytics
- **pandas** (≥1.3.0) - Data manipulation and analysis for academic records and reporting
- **numpy** (≥1.21.0) - Numerical computing for statistical calculations and grade analytics
- **matplotlib** (≥3.5.0) - Data visualization for charts and graphs in reports
- **seaborn** (≥0.11.0) - Statistical data visualization for analytics dashboards
- **plotly** (≥5.0.0) - Interactive plots and dashboards for web interface
- **scikit-learn** (≥1.0.0) - Machine learning algorithms for predictive analytics

#### Document Generation & Reports
- **reportlab** (≥3.6.0) - PDF generation for transcripts, reports, and certificates
- **openpyxl** (≥3.0.9) - Excel file handling for financial reports and data export
- **fpdf2** (≥2.5.0) - Alternative PDF generation for forms and documents

#### Web & Networking
- **requests** (≥2.27.0) - HTTP library for external service integration
- **flask** (≥2.0.0) - Web framework for REST API server (57+ endpoint groups)
- **flask-cors** (≥3.0.0) - Cross-Origin Resource Sharing for API
- **PyJWT** (≥2.0.0) - JSON Web Token authentication for API
- **urllib3** (≥1.26.0) - HTTP client library for reliable network operations

#### Security & Authentication
- **pyotp** (≥2.6.0) - Time-based one-time passwords (TOTP) for multi-factor authentication
- **qrcode** (≥7.3.0) - QR code generation for 2FA setup and student ID cards
- **cryptography** (≥3.4.8) - Cryptographic functions for data encryption and secure storage
- **bcrypt** (≥3.2.0) - Password hashing (complementary to PBKDF2 implementation)

#### Image Processing & Barcodes
- **Pillow** (≥8.3.0) - Image processing for photo uploads and document scanning
- **python-barcode** (≥0.13.0) - Barcode generation for library cards and asset tracking

#### System Utilities & Scheduling
- **schedule** (≥1.1.0) - Task scheduling for automated emails, backups, and reports
- **psutil** (≥5.8.0) - System monitoring for performance tracking and resource management
- **paramiko** (≥2.9.0) - SSH connectivity for remote operations and secure file transfer

#### Date/Time & Configuration
- **pytz** (≥2021.3) - Timezone handling for global institution support
- **PyYAML** (≥6.0) - YAML configuration file parsing
- **python-dateutil** (≥2.8.0) - Date parsing and manipulation for scheduling

### Built-in Modules (No Installation Required)

- **sqlite3** - Database interface (included with Python)
- **tkinter** - GUI framework (usually included with Python)
- **smtplib** - SMTP email sending
- **email** - Email message handling
- **configparser** - Configuration file parsing
- **json** - JSON data handling
- **csv** - CSV file operations
- **hashlib** - Secure hash algorithms (SHA-256, PBKDF2)
- **uuid** - UUID generation for unique identifiers
- **logging** - Application logging
- **threading** - Thread-based parallelism for async operations

### Optional Dependencies

#### Development Tools
```bash
pip install -e ".[dev]"
```
- **pytest** (≥7.0.0) - Testing framework
- **pytest-cov** (≥3.0.0) - Coverage reporting
- **pytest-xdist** (≥3.0.0) - Parallel test execution
- **black** (≥22.0.0) - Code formatting
- **ruff** (≥0.1.0) - Fast Python linter
- **mypy** (≥0.950) - Static type checking
- **isort** (≥5.12.0) - Import sorting
- **pre-commit** (≥3.0.0) - Git pre-commit hooks

#### AI/ML Features
```bash
pip install -e ".[ai]"
```
- **tensorflow** (≥2.7.0) - Deep learning for advanced AI features
- **transformers** (≥4.15.0) - NLP models for chatbot and text analysis
- **opencv-python** (≥4.5.0) - Computer vision capabilities
- **torch** (≥1.10.0) - PyTorch for deep learning models
- **spacy** (≥3.4.0) - Advanced natural language processing

#### Cloud Integration
```bash
pip install -e ".[cloud]"
```
- **boto3** (≥1.20.0) - AWS services integration
- **azure-storage-blob** (≥12.0.0) - Azure blob storage
- **google-cloud-storage** (≥2.0.0) - Google Cloud storage

### Installation Commands

```bash
# Core dependencies only
pip install -r requirements.txt

# Development environment
pip install -r requirements.txt
pip install -e ".[dev]"

# With AI features
pip install -r requirements.txt
pip install -e ".[ai]"

# Complete installation (all optional dependencies)
pip install -r requirements.txt
pip install -e ".[dev,ai,cloud]"

# Using pyproject.toml
pip install -e .
```

---

## Development

### Development Environment Setup

```bash
# 1. Install development dependencies
make install-dev

# 2. Set up pre-commit hooks
make setup

# 3. Configure IDE
# - Python path: Point to virtual environment
# - Formatter: Black (line length: 100)
# - Linter: Ruff
# - Type checker: mypy
```

### Code Style

The project follows:
- **PEP 8**: Python style guide
- **Black**: Code formatter (line length: 100)
- **Ruff**: Fast Python linter with comprehensive checks
- **mypy**: Static type checking
- **isort**: Import sorting and organization
- **Type hints**: For all public functions
- **Docstrings**: NumPy/Google style

```bash
# Format code
make format

# Check formatting without changes
make format-check

# Lint code
make lint

# Fix linting issues automatically
make lint-fix

# Type checking
make type-check

# Run all code quality checks
make check
```

### Common Development Tasks

```bash
# Install dependencies
make install          # Install production dependencies
make install-dev      # Install development dependencies
make setup            # Complete setup with pre-commit hooks

# Code quality
make format           # Format code with Black + isort
make format-check     # Check formatting without changes
make lint             # Run linter (Ruff)
make lint-fix         # Auto-fix linting issues
make type-check       # Run mypy type checking
make security-check   # Security vulnerability checks
make check            # Run all quality checks (format, lint, type)

# Testing
make test             # Run all tests
make test-fast        # Run tests in parallel (faster)
make test-coverage    # Run with coverage report (HTML)
make test-unit        # Run unit tests only
make test-integration # Run integration tests only
make test-security    # Run security tests

# Running the application
make run              # Interactive menu (choose CLI/GUI/Test)
make run-cli          # Launch CLI mode directly
make run-gui          # Launch GUI mode directly

# Database operations
make db-backup        # Create database backup
make db-restore BACKUP_FILE=path/to/backup.db  # Restore from backup
make db-reset         # Reset database (WARNING: deletes all data)

# Utilities
make clean            # Remove build artifacts and cache
make logs             # View application logs
make profile          # Run application profiler
make info             # Display project information
```

### Adding a New Feature

1. **Domain Layer**: Implement business logic in appropriate domain service
2. **Service Layer**: Create application service functions if needed
3. **Interface Layer**: Add UI components (CLI/GUI/Web)
4. **Database**: Add tables/migrations if database changes required
5. **Tests**: Write comprehensive unit and integration tests
6. **Activity Logging**: Add audit trail logging for data modifications
7. **Documentation**: Update relevant documentation files
8. **Code Review**: Ensure code follows style guide and passes all checks

### Code Organization Guidelines

- **Manager Pattern**: Use manager classes for complex modules (~750 lines per file)
- **Single Responsibility**: Each file has one clear purpose
- **Explicit Imports**: No wildcard imports (`from module import *`)
- **Context Managers**: Always use for resources (DB, files, transactions)
- **Activity Logging**: Log all data modifications using `log_activity()`
- **Permission Checks**: Enforce RBAC at service layer with `@require_permission`
- **Transaction Safety**: Use `transaction()` context manager for modifications
- **Centralized Paths**: Always use `paths.py` module for file paths

---

## Testing

### Running Tests

```bash
# Run all tests
make test
python -m pytest university_system/tests/ -v

# Run with coverage
make test-coverage
python -m pytest --cov=university_system --cov-report=html

# Run specific test file
python -m pytest university_system/tests/test_authentication.py -v

# Run specific test class
python -m pytest university_system/tests/test_authentication.py::TestAuthentication -v

# Run specific test method
python -m pytest university_system/tests/test_authentication.py::TestAuthentication::test_login -v

# Run tests in parallel (faster)
make test-fast
python -m pytest university_system/tests/ -n auto

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-security      # Security tests only
```

### Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_auth.py
│   ├── test_services.py
│   └── ...
├── integration/             # Integration tests for module interaction
│   ├── test_enrollment_flow.py
│   ├── test_payment_flow.py
│   └── ...
├── security/                # Security-specific tests
│   ├── test_password_hashing.py
│   ├── test_sql_injection.py
│   └── ...
├── fixtures/                # Test fixtures and sample data
├── conftest.py             # Pytest configuration
└── run_all_tests.py        # Comprehensive test runner
```

### Test Coverage Targets

- **Core functionality**: 90%+ (authentication, database, transactions)
- **Infrastructure**: 85%+ (email, logging, security)
- **Domain services**: 80%+ (business logic)
- **Interfaces**: 70%+ (CLI, GUI, Web)

### Writing Tests

```python
# Example test structure
import pytest
from education_system.university_system.infrastructure.auth.user_authentication import UserAuthentication

class TestAuthentication:
    """Test suite for authentication system."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.auth = UserAuthentication()

    def test_login_success(self):
        """Test successful user login."""
        result = self.auth.login("admin", "admin123")
        assert result is True
        assert self.auth.is_logged_in()

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        result = self.auth.login("admin", "wrongpassword")
        assert result is False
        assert not self.auth.is_logged_in()
```

---

## Security

The system implements comprehensive security measures following industry best practices:

### Password Security
- **bcrypt hashing** as the standard password hash (with transparent migration from legacy PBKDF2-SHA256)
- Legacy PBKDF2-SHA256 passwords (1,000,000 iterations) are automatically re-hashed to bcrypt on first successful login
- Never stores plaintext passwords
- Automatic salt generation and secure random number generation
- Password complexity requirements enforced at registration

### Multi-Factor Authentication
- **TOTP (Time-based One-Time Password)**: Google Authenticator compatible
- **Email OTP**: One-time codes via email (sends to user's configured email)
- **SMS OTP**: Text message verification (optional, via Twilio or free Email-to-SMS gateway)
- **PIN Verification**: 4-digit on-screen PIN for users without MFA setup
- **WebAuthn/FIDO2** (v5.40.0): Passwordless authentication with security keys and platform authenticators
- **Biometric Authentication** (v5.40.0): Face and fingerprint enrollment with 128-D encoding
- **SSO Integration** (v5.40.0): SAML 2.0 and OpenID Connect provider support
- **Account Linking** (v5.40.0): Multi-account support with role switching and audit trails
- **Delegated Access** (v5.40.0): Scoped, time-bound access delegation for parents/guardians
- QR code generation for easy 2FA setup
- Unified login dispatcher routing across all authentication methods

### Login Verification Options

The system offers flexible login security levels to balance security and convenience:

| Security Level | Setting | Verification Method |
|---------------|---------|---------------------|
| **Maximum** | MFA Email enabled | 6-digit code sent to email |
| **Moderate** | Verification ON, no MFA | 4-digit PIN displayed on screen |
| **Convenience** | Verification OFF | Password only (no additional step) |

**Toggle Login Verification:**
- Users can disable all verification via Authentication → Toggle Login Verification
- When disabled, login only requires username and password
- Setting is per-user and stored in database
- Can be re-enabled at any time

```python
# Check if verification is disabled for a user
from education_system.university_system.infrastructure.auth.mfa_service import MFAService
mfa_service = MFAService()

if mfa_service.is_verification_disabled(user_id):
    # Password-only login
    pass
else:
    # Require verification (PIN or Email OTP)
    pass

# Toggle verification on/off
mfa_service.set_verification_disabled(user_id, disabled=True)  # Disable
mfa_service.set_verification_disabled(user_id, disabled=False) # Enable
```

### SQL Injection Prevention
- **Parameterized queries** enforced throughout codebase
- No string concatenation or interpolation in SQL
- ORM-like patterns for safe query construction

```python
# ✓ CORRECT: Parameterized query
conn.execute("SELECT * FROM students WHERE id = ?", (student_id,))

# ✗ INCORRECT: SQL injection risk
conn.execute(f"SELECT * FROM students WHERE id = {student_id}")
```

### Transaction Safety
- **ACID-compliant** database operations
- Automatic rollback on exceptions via context managers
- Write-Ahead Logging (WAL) for data integrity

```python
# Transaction with automatic rollback on error
with transaction() as conn:
    conn.execute("INSERT INTO students ...")
    conn.execute("INSERT INTO enrollments ...")
    # Auto-commits if no exception, auto-rollbacks on error
```

### Access Control
- **Role-Based Access Control (RBAC)**: Admin, Instructor, Student, Staff, Parent roles
- **Fine-grained permissions**: Over 330 distinct permissions across all modules
- **Permission decorators**: `@require_permission('permission_name')`
- **Global auth context**: Shared authentication state across modules
- **UI-Level Access Control**: Dynamic interface filtering based on user roles

#### Role-Based UI Access Control

All GUI modules implement comprehensive role-based navigation and menu filtering, ensuring users only see features appropriate for their role:

**Admin Users** - Full system access:
- All GUI features unlocked across all modules
- System management and configuration tools
- Export/import data capabilities
- View all records system-wide
- Analytics, reports, and admin panels
- User management and permissions control

**Staff Users** - Operational access:
- Domain-specific management features (teaching, support, health services, etc.)
- Create and edit content within their domain
- View records relevant to their role
- Generate reports and analytics
- Limited to operational tasks (no system-wide administration)

**Student Users** - Self-service access:
- View own records and information
- Submit applications and requests
- Browse available services and opportunities
- Participate in student activities
- No access to administrative or management functions

**Parent Users** (Parent Portal):
- View children's academic records and progress
- Communication with teachers and staff
- Financial management for student accounts
- Health and safety information access
- Admin users can access additional parent management tools

**Implemented Across 15+ GUI Modules**:
- Finance GUI (14 tabs: Admin full, Staff 11, Student 4)
- Health Portal (Admin full, Staff operations, Student personal)
- Student Union/Campus Events (Admin full, Staff operations, Student participation)
- Trip Management (Admin/Staff create, Student register)
- Shop Management (Admin/Staff management, Student shopping)
- Student Support (Admin/Staff all tickets, Student own tickets)
- Parent Portal (Admin with Admin Panel, Parent full features)
- Helpdesk (Admin/Staff management, Student tickets only)
- Internship Portal (Admin/Staff create, Student apply)
- Career Services (Admin/Staff management, Student career development)
- Library Management (Admin full, Staff operations, Student borrow)
- Academic Calendar (Admin full, Staff teaching, Student view)
- Grade Tracking (Admin 16 features, Staff 11, Student 3)
- Assignment System (Admin 5 sections, Staff 4, Student 2)
- Course Management (Admin/Staff manage, Student enroll)

Each module includes standardized role detection methods:
```python
def get_user_role(self):
    """Get current user's role from auth system"""

def is_admin(self):
    """Check if current user is admin"""

def is_staff(self):
    """Check if current user is staff/instructor"""

def is_student(self):
    """Check if current user is student"""
```

### Audit Logging
- **Comprehensive activity logs** for all data modifications
- **User attribution** for accountability
- **Timestamp tracking** for compliance
- **Immutable audit trail** for forensic analysis

```python
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Log all data modifications
log_activity('create', 'student', student_id='12345', details={'name': 'John Doe'})
log_activity('update', 'grade', grade_id='456', changes={'old': 'B', 'new': 'A'})
log_activity('delete', 'course', course_id='CS101')
```

### Data Encryption
- **Fernet symmetric encryption** for sensitive data at rest
- **TLS/SSL support** for database connections
- **Encrypted session tokens**
- **Secure key management** via environment variables

### Account Lockout Protection
- **Failed login tracking**: Accounts locked after 5 failed attempts (configurable)
- **Lockout duration**: 15 minutes by default (configurable)
- **Remaining attempts display**: Users see how many attempts remain
- **Emergency unlock functions**: Administrative functions to unlock any account
  - All unlock attempts are logged for security audit
  - Default password: `UnlockMe2024!SecureAdmin`
  - Can be overridden via environment variable: `EMERGENCY_UNLOCK_PASSWORD`

**Available Functions:**
```python
# Unlock a specific account
auth.emergency_unlock(username, emergency_password)

# Unlock ALL locked accounts at once
auth.emergency_unlock_all(emergency_password)

# List all currently locked accounts
auth.list_locked_accounts()
# Returns: [{'username': 'user1', 'failed_attempts': 5, 'locked_at': '...', 'minutes_remaining': 10}, ...]
```

⚠️ **Security Warning**: Change the emergency unlock password in production by setting the `EMERGENCY_UNLOCK_PASSWORD` environment variable.

### Session Management
- **Token-based sessions** with configurable timeouts
- **Concurrent session limits** per user
- **Automatic session cleanup**
- **Session hijacking prevention**

### Error Handling
- **Structured exception hierarchy** preventing information leakage
- **Generic error messages** to users
- **Detailed logging** for administrators
- **No stack traces** in production

### Security Resources

| Document | Description |
|----------|-------------|
| [Security Best Practices](university_system/docs/security/SECURITY.md) | Comprehensive security features and implementation guidelines |
| [Security Guide](university_system/docs/security/SECURITY.md) | Security features and implementation guidelines |
| [Authentication Guide](university_system/docs/security/AUTHENTICATION.md) | Authentication system documentation |
| [MFA Documentation](university_system/docs/security/MFA_SYSTEM_DOCUMENTATION.md) | Multi-factor authentication setup and configuration |
| [MFA Quick Start](university_system/docs/security/MFA_QUICK_START.md) | Get MFA running quickly |

---

## Deployment

### Production Deployment

#### Using Docker (Recommended)

```bash
# Build image
docker build -t university-system:latest .

# Run container
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env.production \
  --name university-system \
  university-system:latest
```

#### Manual Deployment

```bash
# 1. Set production environment
export APP_ENV=production
export DEBUG=False

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Configure production database (PostgreSQL/MySQL recommended)
# Edit .env with production database credentials

# 4. Run the application
python run.py --gui  # For GUI
python run.py --cli  # For CLI
python run.py --api  # For REST API server
```

### Backup & Recovery

#### Pre-configured Backup Templates

The system includes **6 professionally configured backup templates** for different use cases:

1. **Daily Basic** - Standard daily backups with compression
2. **Secure Encrypted** - High-security backups with encryption and retention
3. **Incremental Fast** - Quick incremental backups for high-activity environments
4. **Cloud AWS** - AWS S3 cloud storage integration
5. **Selective Tables** - Backup only critical database tables
6. **Remote SFTP** - Secure off-site backups via SFTP

**Documentation**: See [university_system/templates/backup_templates/README.md](university_system/templates/backup_templates/README.md) for detailed template descriptions, configuration options, and usage examples.

**Using Templates via GUI**:
1. Open Data Backup GUI from the main interface
2. Click "Load Template" button
3. Select a template (descriptions shown)
4. Configure required settings (passwords, credentials)
5. Save and run backup

#### Automatic Backups
- **Location**: `backups/` directory (centralized via `paths.py`)
- **Schedule**: Daily at 2 AM (configurable per template)
- **Retention**: 7-30 days (configurable via retention policies)
- **Includes**: Database, configuration files, uploads
- **Features**: Compression, encryption, cloud sync, deduplication

#### Manual Backup

```bash
# Create full backup using Make
make db-backup

# Create backup programmatically
python -m university_system.infrastructure.database.database_utils --backup

# Using Data Backup GUI
python -m university_system.infrastructure.database.gui.data_backup_gui
```

#### Restore from Backup

```bash
# Restore using Make
make db-restore BACKUP_FILE=backups/backup_20250101.db

# Restore programmatically
python -m university_system.infrastructure.database.database_utils --restore backups/backup_20250101.db

# Using Data Backup GUI (recommended for selective restore)
python -m university_system.infrastructure.database.gui.data_backup_gui
```

#### Backup Features
- **Multiple backup types**: Full, incremental, differential, selective
- **Compression**: GZIP or ZIP with configurable compression levels
- **Encryption**: AES encryption with password protection
- **Cloud storage**: AWS S3, Google Cloud, Azure Blob
- **Remote storage**: SFTP, FTP support
- **Email notifications**: Success/failure alerts
- **Integrity verification**: Hash-based backup validation
- **Deduplication**: Reduce storage usage
- **Activity logging**: Complete audit trail in `logs/backup.log`

### Database Migration

```bash
# 1. Backup current database
make db-backup

# 2. Run migrations
python -m university_system.infrastructure.database.migrate

# 3. Verify migration
python -m university_system.infrastructure.database.verify
```

---

## Documentation

**[Documentation Hub](education_system/docs/README.md)** — Central index linking to all four systems' documentation (university, college, secondary school, primary school).

### Available Documentation

```
university_system/docs/
├── README.md                      # Documentation index
├── QUICK_START.md                 # Getting started guide
├── TROUBLESHOOTING.md             # Common issues and solutions
│
├── security/                      # Security & Authentication
│   ├── SECURITY.md               # Security features and best practices
│   ├── AUTHENTICATION.md         # Authentication implementation guide
│   ├── AUTH_QUICK_REFERENCE.md   # Quick authentication reference
│   ├── MFA_SYSTEM_DOCUMENTATION.md # Complete MFA guide
│   ├── MFA_QUICK_START.md        # MFA setup quick start
│   └── SECURITY_INTEGRATION_GUIDE.md # Remember Me & security integration (v5.11.0)
│
├── infrastructure/                # Infrastructure guides
│   ├── DATABASE.md               # Database architecture and usage
│   ├── TRANSACTIONS.md           # Transaction safety guide
│   ├── EMAIL_SCHEDULER.md        # Automated email system setup
│   ├── ENHANCEMENTS_GUIDE.md     # System enhancements guide (v5.12.0)
│   ├── IMPLEMENTATION_SUMMARY.md # Enhancement implementation details (v5.12.0)
│   ├── ADMIN_MONITORING_GUIDE.md # Admin monitoring CLI guide (v5.12.0)
│   └── CLI_INTEGRATION_SUMMARY.md # CLI integration technical summary (v5.12.0)
│
├── development/                   # Developer documentation
│   ├── README.md                 # Development overview
│   ├── EXCEPTION_HANDLING.md     # Error handling patterns
│   └── TESTING_GUIDE.md          # Writing and running tests
│
├── ai/                           # AI feature documentation
│   ├── AI_DEPENDENCIES.md        # AI library requirements
│   └── VOICE_FEATURES.md         # Voice feature documentation
│
├── guides/                       # Comprehensive user guides (20+)
│   ├── README.md                 # Guide index
│   ├── ASSIGNMENT_SYSTEM_GUIDE.md
│   ├── GRADE_TRACKING_GUIDE.md
│   ├── STAFF_CRUD_GUIDE.md
│   ├── FINANCIAL_AID_GUIDE.md
│   └── ...                       # 15+ more guides
│
└── modules/                       # Module documentation
    └── README.md                 # Module overview
```

#### Quick Links

- **[Quick Start](university_system/docs/QUICK_START.md)** - Get running in 5 minutes
- **[Troubleshooting](university_system/docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Security Guide](university_system/docs/security/SECURITY.md)** - Security features and best practices
- **[MFA Setup](university_system/docs/security/MFA_QUICK_START.md)** - Multi-factor authentication
- **[Security Integration](university_system/docs/security/SECURITY_INTEGRATION_GUIDE.md)** - Remember Me & security integration (v5.11.0)
- **[Database Guide](university_system/docs/infrastructure/DATABASE.md)** - Database architecture
- **[Testing Guide](university_system/docs/development/TESTING_GUIDE.md)** - Writing and running tests
- **[System Enhancements](university_system/docs/infrastructure/ENHANCEMENTS_GUIDE.md)** - Monitoring, backups, caching (v5.12.0)
- **[Admin Monitoring](university_system/docs/infrastructure/ADMIN_MONITORING_GUIDE.md)** - CLI monitoring for admins (v5.12.0)
- **[AI Features](university_system/docs/ai/AI_DEPENDENCIES.md)** - AI library requirements and setup
- **[User Guides](university_system/docs/guides/README.md)** - Comprehensive module guides (20+)
- **[Backup Templates](university_system/templates/backup_templates/README.md)** - Pre-configured backup templates

---

## Module Guides

**📚 [Complete Guide Index](university_system/docs/guides/README.md)** - Browse all 20+ comprehensive user guides (200+ pages of documentation)

### Academic Services

| Guide | Description |
|-------|-------------|
| [Assignment System](university_system/docs/guides/ASSIGNMENT_SYSTEM_GUIDE.md) | Assignment creation, submission management, grading with rubrics, group work, peer review, plagiarism detection |
| [Grade Tracking](university_system/docs/guides/GRADE_TRACKING_GUIDE.md) | Student grade management, performance analytics, grade distribution, weighted scoring |
| [Exam Scheduler](university_system/docs/guides/EXAM_SCHEDULER_GUIDE.md) | Automated exam scheduling with room management and conflict handling |
| [Virtual Classroom](university_system/docs/guides/VIRTUAL_CLASSROOM_GUIDE.md) | Real-time online collaboration, breakout rooms, live polls, chat, recording management |
| [Course Management](university_system/docs/guides/COURSE_MANAGEMENT_GUIDE.md) | Course catalog, registration, waitlists, prerequisites, recommendations, evaluations |
| [Degree Audit](university_system/docs/guides/DEGREE_AUDIT_GUIDE.md) | Track degree progress, what-if analysis, academic planning, graduation requirements |

### Student Affairs & Support

| Guide | Description |
|-------|-------------|
| [Student Union](university_system/docs/guides/STUDENT_UNION_GUIDE.md) | Event management, facility booking, elections, clubs, payments, peer support programs |
| [Helpdesk Support](university_system/docs/guides/HELPDESK_SUPPORT_GUIDE.md) | Support tickets, counseling services, crisis intervention, analytics, SLA management |
| [Alumni Management](university_system/docs/guides/ALUMNI_MANAGEMENT_GUIDE.md) | Alumni networking, events, career services, donations, mentorship, chapters |

### Financial Services

| Guide | Description |
|-------|-------------|
| [Financial Aid](university_system/docs/guides/FINANCIAL_AID_GUIDE.md) | FAFSA application, scholarships, grants, loans, work-study, emergency assistance |
| [Restaurant Management](university_system/docs/guides/RESTAURANT_MANAGEMENT_GUIDE.md) | Complete restaurant operations including inventory, payroll integration, waste tracking |
| [Restaurant Reports](university_system/docs/guides/RESTAURANT_REPORTS_GUIDE.md) | Financial reporting and sales analytics for restaurant operations |
| [Email Receipts](university_system/docs/guides/EMAIL_RECEIPTS_GUIDE.md) | Automated email receipts for restaurant orders, payments, refunds |

### Campus Services

| Guide | Description |
|-------|-------------|
| [Parking Management](university_system/docs/guides/PARKING_MANAGEMENT_GUIDE.md) | Parking permits, violations, visitor parking, EV charging, special events |
| [Facilities Management](university_system/docs/guides/FACILITIES_MANAGEMENT_GUIDE.md) | Room bookings, maintenance requests, work orders, asset management, space utilization |
| [Health Portal](university_system/docs/guides/HEALTH_PORTAL_GUIDE.md) | Appointments, medical records, prescriptions, immunizations, mental health, telehealth |

### Administration

| Guide | Description |
|-------|-------------|
| [Staff CRUD System](university_system/docs/guides/STAFF_CRUD_GUIDE.md) | Complete staff account management with CRUD operations, permissions, security features |
| [Student Marketplace](university_system/docs/guides/STUDENT_MARKETPLACE_GUIDE.md) | Peer-to-peer marketplace for textbooks, furniture, housing |
| [Dark Mode](university_system/docs/guides/DARK_MODE_GUIDE.md) | Enable and customize dark mode for the GUI interface |

### Quick Reference by User Type

| User Type | Recommended Guides |
|-----------|-------------------|
| **Students** | [Degree Audit](university_system/docs/guides/DEGREE_AUDIT_GUIDE.md) \| [Course Management](university_system/docs/guides/COURSE_MANAGEMENT_GUIDE.md) \| [Financial Aid](university_system/docs/guides/FINANCIAL_AID_GUIDE.md) \| [Health Portal](university_system/docs/guides/HEALTH_PORTAL_GUIDE.md) |
| **Faculty** | [Assignment System](university_system/docs/guides/ASSIGNMENT_SYSTEM_GUIDE.md) \| [Grade Tracking](university_system/docs/guides/GRADE_TRACKING_GUIDE.md) \| [Virtual Classroom](university_system/docs/guides/VIRTUAL_CLASSROOM_GUIDE.md) \| [Exam Scheduler](university_system/docs/guides/EXAM_SCHEDULER_GUIDE.md) |
| **Staff** | [Facilities Management](university_system/docs/guides/FACILITIES_MANAGEMENT_GUIDE.md) \| [Parking Management](university_system/docs/guides/PARKING_MANAGEMENT_GUIDE.md) \| [Helpdesk Support](university_system/docs/guides/HELPDESK_SUPPORT_GUIDE.md) |
| **Alumni** | [Alumni Management](university_system/docs/guides/ALUMNI_MANAGEMENT_GUIDE.md) |
| **Administrators** | [Staff CRUD](university_system/docs/guides/STAFF_CRUD_GUIDE.md) \| [Student Union](university_system/docs/guides/STUDENT_UNION_GUIDE.md) |

---

## Contributing

We welcome contributions! Please follow these steps:

1. **Fork the Repository**
   ```bash
   git clone https://github.com/sean1352636/university_system.git
   cd university_system
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Your Changes**
   - Write clean, documented code following the style guide
   - Follow architectural patterns and conventions
   - Add comprehensive unit tests
   - Update documentation as needed

4. **Run Quality Checks**
   ```bash
   make format      # Format code
   make lint        # Check code quality
   make type-check  # Run type checking
   make test        # Run all tests
   ```

5. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

6. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Contribution Guidelines

- Follow PEP 8 style guide and use Black formatter (line length: 100)
- Write meaningful, descriptive commit messages
- Include comprehensive tests for new features (minimum 80% coverage)
- Update documentation for user-facing changes
- Ensure all tests pass before submitting PR
- Add entry to `CHANGELOG.md` describing your changes
- Request code review from maintainers

For more information, see [Documentation Index](university_system/docs/README.md).

---

## Troubleshooting

### Common Issues

#### 1. Import Errors After Refactoring

The codebase was refactored in October 2025 and again in February 2026 (v5.42.x — 54 monolithic files split into packages). All refactored modules maintain backward compatibility via `__init__.py` re-exports. If you still see import errors:

```python
# Old import (deprecated):
from university_system.modules.interfaces.gui.grade_tracking_gui import GradeTrackingApp

# New import (current architecture):
from university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import GradeTrackingApp
```

#### 2. Database Lock Errors

If you encounter "database is locked" errors:
- Ensure only one instance of the application is running
- Verify WAL mode is enabled (default configuration)
- Always use context managers for database operations
- Check connection pool limits in configuration
- Restart the application to clear stale connections

#### 3. Email Delivery Issues

If emails aren't being sent:
- Verify SMTP settings in `.env` or `infrastructure/email/config.py`
- Check firewall settings and port accessibility (typically port 587 or 465)
- For Gmail: Enable "App Passwords" instead of using account password
- Test SMTP connection manually using a Python script
- Check email queue status in the database

#### 4. Module Import Errors

If you see `ModuleNotFoundError`:
```bash
# Ensure you're running from the project root
cd /path/to/university_system

# Use proper module syntax (not file paths)
python -m university_system.cli_main

# Verify Python path includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 5. Permission Errors

If you encounter file permission errors:
```bash
# Fix data directory permissions
chmod -R 755 data/ logs/ backups/

# Fix ownership (if running as different user)
chown -R yourusername:yourusername data/ logs/ backups/
```

#### 6. Tkinter Not Found

If GUI fails to start with "No module named tkinter":
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# CentOS/RHEL
sudo yum install tkinter

# macOS (usually included, but if needed)
brew install python-tk

# Windows (usually included with Python)
```

For more help, see:
- [Troubleshooting Guide](university_system/docs/TROUBLESHOOTING.md)
- [Documentation Index](university_system/docs/README.md)
- [Security Documentation](university_system/docs/security/SECURITY.md)

---

## Known Limitations

The following limitations should be considered when deploying this system:

| Limitation | Details |
|------------|---------|
| **Web Interface** | University has full Web Portal SPA + REST API (57+ endpoints with JWT auth); College has REST API (59 routes); Secondary School and Primary School are CLI+GUI only |
| **Multi-tenancy** | Single-tenant design; multi-institution hosting planned for future release |
| **SQLite Concurrency** | May have performance limits with high concurrent writes; use PostgreSQL for high-traffic deployments |
| **i18n Coverage** | Most GUI modules now have i18n support (500+ strings translated in v5.41.x); some modules still have incomplete coverage |
| **Production Readiness** | Not recommended for production without implementing security recommendations (see [Security Documentation](university_system/docs/security/SECURITY.md)) |
| **Mobile Support** | No native mobile app; web interface responsive but not mobile-optimized |
| **Real-time Features** | WebSocket support planned but not yet implemented |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### MIT License Summary

Permission is hereby granted, free of charge, to any person obtaining a copy of this software to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to the following conditions:

- The above copyright notice and this permission notice shall be included in all copies or substantial portions of the software.
- The software is provided "as is", without warranty of any kind.

---

## Acknowledgments

- **Python Software Foundation** - For the Python programming language
- **SQLite** - For the embedded database engine
- **Tkinter** - For the GUI framework
- **All Contributors** - For their valuable contributions and feedback
- **Educational Institutions** - For providing feedback and use cases

---

## Release History

### Major Releases

| Version | Date | Highlights |
|---------|------|------------|
| **7.5.0** | Mar 2026 | Cross-system CLI switching, shared authentication fixes, Primary School system (280+ files, 46 modules) |
| **Multi-System** | Mar 2026 | Unified Education System: added Sixth Form College (930+ files, 110 modules), Secondary School (290+ files, 51 modules), and Primary School (280+ files, 46 modules) systems with shared launcher and authentication |
| **5.47.0** | Feb 25, 2026 | Full Web Portal SPA at `/portal` with JWT auth, dashboard, CRUD for all major entities |
| **5.42.x** | Feb 22, 2026 | Massive codebase refactoring: 54 monolithic files split into modular packages, i18n expansion (500+ strings) |
| **5.40.0** | Feb 2026 | Advanced authentication: WebAuthn, SSO (SAML/OIDC), biometric, account linking, delegated access |
| **5.39.x** | Feb 11, 2026 | Student self-service GUIs (13 features), seed demo data, role-based dashboards, 50+ bug fixes |
| **5.36.0** | Feb 11, 2026 | Admin tools (alerts, departments, branding), batch user operations, compliance reporting |
| **5.35.0** | Feb 11, 2026 | Login analytics, operations dashboards, real-time system health monitoring |
| **5.34.0** | Feb 10, 2026 | Virtual classroom CLI, financial aid CLI, helpdesk ticket actions |
| **5.29.0** | Feb 10, 2026 | Office Hours & TA Management (CLI + GUI + API), role-based dashboards |
| **5.28.0** | Feb 10, 2026 | Major security audit: 25+ critical/high/medium fixes across 30+ files |
| **5.22.0** | Feb 9, 2026 | Flask REST API server (JWT auth, 57+ endpoint groups, 60 route files) |
| **5.17.0** | Feb 7, 2026 | Document Manager, AI Detector, Cinema, Plagiarism GUI modularization |
| **5.12.0** | Feb 1, 2026 | Observability, automated backups, LRU caching, Remember Me auth |
| **5.5.0** | Jan 2026 | Student Success Platform (18 modules, 40+ tables) |
| **5.4.0** | Jan 2026 | Staff HR Management (15 managers, 23 tables, CLI + GUI) |
| **5.2.0** | Dec 2025 | Extras & Tools (90+ games, utilities, mini-projects) |
| **5.0.0** | Oct 2024 | Major modularization (91% reduction in max file size) |

See [CHANGELOG.md](CHANGELOG.md) for complete version history with detailed release notes.

---

## Roadmap

### Multi-System Education Platform (March 2026) - CURRENT
- [x] **Unified Launcher** (`run.py`): Single entry point for University, College, Secondary School, and Primary School systems with CLI & GUI system selection and runtime switching
- [x] **Shared Authentication** (`education_system/shared/auth/`): Unified auth across all 4 systems with bcrypt hashing, MFA, sessions, and central auth.db
- [x] **Cross-System CLI Switching** (v7.5.0): All 4 CLI systems support switching to any other system without re-authenticating
- [x] **Sixth Form College System**: 930+ files, 110 domain modules, 59 API routes, 59 tests — apprenticeships, T-levels, UCAS, functional skills, safeguarding, Prevent duty, GDPR, quality assurance, bursary, funding, and more
- [x] **Secondary School System**: 290+ files, 51 domain modules — Years 7-11, KS3/KS4, GCSE grades 9-1, pastoral care, behaviour/detentions/exclusions, form groups, seating plans, parents' evening
- [x] **Primary School System**: 280+ files, 46 domain modules — Reception-Year 6, EYFS/KS1/KS2, phonics, reading records, SATs, safeguarding, SEND, pastoral care

### Version 5.47.0 (February 25, 2026) - COMPLETED
- [x] **Web Portal** (v5.47.0): Full SPA at `/portal` with JWT auth, dashboard, CRUD for all major entities
- [x] **Staff HR Expansion** (v5.44.0-v5.46.0): 20 new modules — payroll, faculty scheduling, curriculum design, travel, sabbatical, committees, IP, equipment, cover, workload, directory, mentoring, grants, peer review, communication hub, teaching load; 75+ new database tables
- [x] **Student Services** (v5.43.0): Academic advising, digital student ID, study room booking, printing services, textbook store
- [x] **Codebase Consolidation** (v5.46.1-v5.46.2): Merged fragmented versioned files (HR schemas 7→1, admin tools GUI+locale 4→2), centralised path helpers
- [x] **Continued Refactoring** (v5.42.55-v5.42.64): Additional monolithic file decompositions with backward compatibility

### Version 5.42.54 (February 22, 2026) - COMPLETED
- [x] **Advanced Authentication** (v5.40.0): WebAuthn/FIDO2, SSO (SAML 2.0 & OIDC), biometric, account linking, delegated access, 25 new permissions
- [x] **Codebase Refactoring** (v5.42.x): 54 monolithic files decomposed into modular packages with full backward compatibility
- [x] **i18n Expansion** (v5.41.x): 500+ hardcoded strings replaced with translation calls across 20+ GUI modules
- [x] **Bug Fixes** (v5.39.6-v5.40.x): 50+ database schema fixes, GUI layout corrections, email integration fixes
- [x] **Security Hardening** (v5.39.7): Removed hardcoded credentials, secure random password generation via `secrets` module

### Version 5.39.5 (February 11, 2026) - COMPLETED
- [x] **Flask REST API** (v5.22.0): 60 route files, JWT auth, 57+ endpoint groups, pagination, rate limiting
- [x] **Major Security Audit** (v5.28.0): 25+ critical/high/medium fixes across 30+ files
- [x] **Office Hours & TA Management** (v5.29.0): Full CRUD with CLI, GUI, and API
- [x] **Role-Based Dashboards** (v5.29.0-v5.39.0): Admin, instructor, student dashboards with live data
- [x] **Admin Tools** (v5.36.0): Alert config, department management, institution branding
- [x] **Instructor Tools** (v5.37.0): Roster viewer, bulk grade import, course messaging, semester analytics
- [x] **Student Self-Service** (v5.39.0): 13 new features (profile, security, notifications, grades, degree progress, catalog, GPA calculator, messaging, forums, finance, help center, documents)
- [x] **Seed Demo Data** (v5.38.0): 310+ records across 30 tables
- [x] 200+ bug fixes and quality improvements

### Version 5.17.0 (February 7, 2026) - COMPLETED
- [x] **Document Manager GUI**: 26-file modular package (from 18,953-line monolith)
- [x] **AI Detector**: 49-file modular package (from 10,864-line monolith)
- [x] **Cinema GUI**: 52-file modular package (from 11,086-line monolith)
- [x] **Plagiarism GUI**: 20-file modular package (from 7,132-line monolith)
- [x] **Housing & Shop GUIs**: Converted to modular packages

### Version 5.12.0 (February 2026) - COMPLETED
- [x] **Observability & Monitoring** - Metrics, health checks, alerts
- [x] **Automated Data Management** - Backup scheduler with retention
- [x] **Performance Optimization** - LRU cache with TTL
- [x] **Remember Me Authentication** - 30-day persistent tokens

### Version 5.5.0 (January 2026) - COMPLETED
- [x] **Student Success & Engagement Platform** - 18 comprehensive modules
- [x] 40+ new database tables, full CLI and GUI interfaces

### Version 5.4.0 (January 2026) - COMPLETED
- [x] **Staff HR Management System** - 15 specialized managers
- [x] 23 new database tables, 14 CLI menus + 14 GUI interfaces

### Version 6.0 (Q2-Q3 2026)
- [ ] Mobile application (React Native)
- [x] ~~Full web UI frontend for the REST API~~ — Completed in v5.47.0 (Web Portal SPA)
- [ ] REST API for Secondary School and Primary School systems
- [x] ~~CLI for Secondary School system~~ — Completed
- [x] ~~CLI for Primary School system~~ — Completed
- [ ] Integration with external LMS systems (Canvas, Blackboard, Moodle)
- [ ] Complete i18n support for all remaining GUI modules

### Version 7.0 (Q4 2026)
- [ ] Microservices architecture
- [ ] GraphQL API alongside REST
- [ ] Real-time collaboration features (live sessions, chat)
- [x] ~~Advanced security features (biometric auth)~~ — Completed in v5.40.0
- [ ] Blockchain credential verification

### Future Considerations
- [ ] Multi-tenancy support for hosting multiple institutions
- [ ] Cloud-native deployment (Kubernetes, Docker Swarm)
- [x] Internationalization (i18n) - 10 languages supported
- [ ] Localization (l10n) - Expanding translation coverage
- [ ] Blockchain for credential verification and academic records
- [ ] Advanced AI features (chatbot improvements, automated grading)
- [ ] Mobile-first responsive web design

---

## Support & Contact

### Getting Help

- **Documentation**: [Documentation Index](university_system/docs/README.md)
- **Troubleshooting**: [Troubleshooting Guide](university_system/docs/TROUBLESHOOTING.md)
- **Issue Tracker**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)
- **Quick Start**: [Getting Started](university_system/docs/QUICK_START.md)

### Reporting Issues

When reporting issues, please include:
1. Python version and operating system
2. Complete error message and stack trace
3. Steps to reproduce the issue
4. Expected vs. actual behavior
5. Relevant configuration (without sensitive data)

---

## Project Status

- **Platform**: Education System (University + College + Secondary School + Primary School)
- **Status**: Active Development & Maintenance
- **Total Python Files**: 4,920+ across all four systems
- **Total Domain Modules**: 258 (51 university + 110 college + 51 secondary + 46 primary)
- **Total API Route Files**: 123 (64 university + 59 college)
- **Total Test Files**: 525+
- **Python**: 3.11+ (tested on 3.11, 3.12)
- **Last Updated**: March 2026
- **Actively Maintained**: Yes
- **Production Ready**: Yes (with appropriate security configuration)
- **Code Quality**: Black formatted, Ruff linted, mypy type-checked

#### University System
- **Python Files**: 3,420+
- **REST API**: 57+ endpoint groups across 64 route files
- **Database Tables**: 160+ (including 23 Staff HR + 40 Student Success tables)
- **Authentication Methods**: 7 (password, TOTP, email OTP, SMS OTP, WebAuthn, biometric, SSO)
- **Internationalization**: 10 languages (ar, de, en, es, fr, ja, ko, pt, ru, zh)
- **Extras Included**: 90+ games, utilities, and mini-projects

#### College System
- **Python Files**: 930+, 110 domain modules, 59 API routes, 59 tests

#### Secondary School System
- **Python Files**: 290+, 51 domain modules, CLI + GUI interface

#### Primary School System
- **Python Files**: 280+, 46 domain modules, CLI + GUI interface

---

**Made with dedication for educational institutions worldwide — from secondary schools to universities**

For questions, suggestions, or support, please [open an issue](https://github.com/sean1352636/university_system/issues) or contact the development team.