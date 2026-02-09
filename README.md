# University Management System

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.17.0-brightgreen)](https://github.com/sean1352636/university_system)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive, enterprise-grade university management system designed to handle all aspects of higher education administration. This modular platform integrates academic, financial, student affairs, health services, and administrative operations into a unified, scalable solution with multiple interface options (CLI, GUI, Web).

---

## Table of Contents

- [Quick Start](#quick-start)
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

# Run the application
python run.py              # Interactive menu (recommended)
python run.py --cli        # Command-line interface
python run.py --gui        # Graphical interface
python run.py --test       # Run tests

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
make db-backup             # Backup database
```

**Default Login**: `admin` / `admin123` (change immediately in production!)

---

## What's New

### Version 5.17.0 (February 7, 2026)

**Major Refactoring - Document Manager, AI Detector, Cinema, Plagiarism GUIs**

Continued large-scale modularization of monolithic files into well-organized packages:

- **Document Manager GUI**: Split 18,953-line monolith into 26-file package using `__getattr__` delegation pattern (92% reduction)
- **AI Detector**: Split 10,864-line monolith into 49-file package with mixin-based architecture (88% reduction)
- **Cinema GUI**: Split 11,086-line monolith into 52-file package across 8 subdirectories (91% reduction)
- **Plagiarism GUI**: Split 7,132-line monolith into 20-file package (73% reduction)
- **Housing Accommodation GUI** and **Shop Management GUI**: Converted to modular packages
- All refactorings maintain 100% backward compatibility via `__init__.py` re-exports

**Recent Highlights (v5.12-v5.17):**
- Observability & monitoring infrastructure (metrics, health checks, alerts)
- Automated backup scheduling with retention policies
- LRU cache with TTL for performance optimization
- Remember Me authentication with 30-day persistent tokens
- Quiet startup mode (verbose output moved to logs)
- Improved student record update UX with multi-field sessions
- 10-language internationalization support (ar, de, en, es, fr, ja, ko, pt, ru, zh)

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## Overview

The University Management System is a full-featured platform built with Python that provides:

- **Modular Architecture**: Domain-driven design with clearly separated concerns across infrastructure, domain, service, and interface layers
- **Multiple Interfaces**: Command-line (CLI) and graphical (Tkinter) interfaces for diverse user preferences
- **Comprehensive Coverage**: Academic management, financial services, health services, housing, student affairs, and commerce domains
- **Scalable Design**: Thread-safe database connection pooling, Write-Ahead Logging (WAL), and infrastructure-agnostic architecture
- **Secure by Default**: PBKDF2-SHA256 password hashing (1M iterations), multi-factor authentication, role-based access control, and comprehensive audit logging
- **Extensible**: Manager pattern for modular code organization, making it easy to extend and maintain

### Target Users

- **Administrators**: System configuration, user management, comprehensive reporting, and audit trail analysis
- **Faculty**: Course management, assignment creation, grading, attendance tracking, and academic analytics
- **Students**: Course enrollment, assignment submission, grade viewing, service requests, and student union participation
- **Staff**: Financial operations, health services, facility management, and student support services

### Statistics

- **Version**: 5.17.0 (February 7, 2026)
- **Lines of Code**: 1,180,000+ across all modules
- **Python Files**: 2,130+ files
- **Core System**: 1,160,000+ lines across ~2,010 files
- **Extras Module**: 19,678 lines across ~120 files
- **Python Version**: 3.8+ (tested on 3.8-3.12)
- **Modules**: 53+ major functional domains (18 student success modules)
- **Test Coverage**: 85%+ for core functionality
- **Database Tables**: 120+ normalized tables (including 23 Staff HR + 40 Student Success tables)
- **Permissions**: 320+ fine-grained RBAC permissions
- **Staff HR Managers**: 15 specialized manager classes (7,199 lines)
- **Student Success Modules**: 18 comprehensive student-focused services
- **Internationalization**: 10 supported languages (ar, de, en, es, fr, ja, ko, pt, ru, zh)
- **Extras**: 90+ games, utilities, and mini-projects included

---

## Key Features

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

### Student Success & Engagement (NEW in v5.5.0)

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

### Staff HR Management (Enhanced in v5.0.79)
A comprehensive human resources management system with 15 specialized managers + Staff CRUD:

- **Staff CRUD Management** ⭐ **NEW in v5.0.79**: Complete staff account management
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
- **Authentication**: Centralized authentication with multi-factor authentication (TOTP, Email OTP, SMS OTP)
- **Authorization**: Role-based access control (RBAC) with fine-grained permissions
- **Database**: SQLite (default) with connection pooling, WAL mode, and support for PostgreSQL/MySQL
- **Backup System**: Comprehensive backup management with 6 pre-configured templates (daily, encrypted, incremental, cloud, selective, remote)
- **Email Service**: Asynchronous email queue with SMTP integration, template rendering, and automated scheduling
  - **Email Scheduler**: Background service with scheduled tasks:
    - Satisfaction surveys: Daily at 09:00
    - Book return reminders: Daily at 08:00
    - Overdue book notices: Daily at 10:00
    - SLA breach alerts: Every 30 minutes
- **Console Output**: Professional terminal formatting with ANSI colors, progress bars, tables, and interactive prompts
- **AI Integration**: Chatbot capabilities, plagiarism detection, and predictive analytics
- **Activity Logging**: Comprehensive audit trails for compliance and security monitoring
- **PDF Database Export**: Comprehensive PDF report generation with charts, tables, and visualizations for full database export

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
| **Database** | SQLite (default), PostgreSQL, MySQL |
| **Authentication** | PBKDF2-SHA256 (1M iterations), pyotp (TOTP), cryptography |

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

**Admin Account:**
- Username: `admin`
- Password: `admin123`

**Test Student:**
- Username: `student`
- Password: `student123`

**Test Staff:**
- Username: `staff`
- Password: `staff123`

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

### Interactive Menu

```bash
# Start with interactive menu (recommended for first-time users)
python run.py
```

Choose from:
1. **CLI Interface** - Full-featured command-line interface
2. **GUI Interface** - Tkinter-based graphical interface
3. **Run Tests** - Execute test suite

### Command-Line Interface (CLI)

```bash
# Direct CLI mode
python run.py --cli

# Alternative
python -m university_system.cli_main
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
# Direct GUI mode
python run.py --gui

# Launch specific GUI applications
python -m university_system.modules.shared.gui.main_gui
python -m university_system.modules.domain.academics.gui.assignment_system.assignment_gui
python -m university_system.modules.domain.finance.gui.finance_management_gui
```

- Custom exception handling

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
from university_system.modules.shared.utils.console_output import console

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
university_system/
│
├── infrastructure/                     # Core infrastructure layer
│   ├── ai/                            # AI/ML services (chatbot, analytics)
│   ├── analytics/                     # Analytics and reporting engine
│   ├── async_utils/                   # Asynchronous utilities
│   ├── auth/                          # Authentication & authorization
│   │   ├── cli/                       # Auth CLI components
│   │   ├── core_utils/                # Core auth utilities
│   │   ├── integrations/              # Auth integrations
│   │   └── managers/                  # Auth manager classes
│   ├── cache/                         # LRU cache with TTL
│   ├── communication/                 # Communication services (SMS, notifications)
│   ├── database/                      # Database connection & management
│   │   ├── db.py                      # Connection pooling, transactions
│   │   ├── gui/                       # Database management GUI
│   │   ├── migrations/                # Schema version migrations
│   │   └── schemas/                   # Database schema definitions
│   ├── data_management/               # Automated backup scheduling
│   ├── email/                         # Email service integration
│   │   ├── email_service.py           # Async queue, SMTP integration
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
│   ├── domain/                        # Domain layer (50+ business domains)
│   │   │
│   │   │  ── ACADEMIC DOMAINS ──
│   │   │
│   │   ├── academics/                 # Core academic module
│   │   │   ├── grading/               # Grading services (20 files)
│   │   │   ├── gui/
│   │   │   │   ├── academic_calendar/  # Calendar GUI (10+ files)
│   │   │   │   ├── ai_detector/        # AI detection GUI (16 views)
│   │   │   │   ├── assignment_system/  # Assignment GUI (19 managers)
│   │   │   │   ├── attendance_tracker/ # Attendance GUI (11 files)
│   │   │   │   ├── course_management_gui/ # Course mgmt (14 submodules)
│   │   │   │   ├── grade_tracking/     # Grade tracking (24 files)
│   │   │   │   ├── library/            # Library GUI (17 components)
│   │   │   │   ├── misconduct/         # Academic misconduct
│   │   │   │   ├── module_scheduling/  # Scheduling (8 tabs)
│   │   │   │   ├── parent_portal/      # Parent portal (20+ files)
│   │   │   │   ├── plagiarism_main_gui/ # Plagiarism GUI (20 files)
│   │   │   │   ├── blockchain_credentials_gui.py
│   │   │   │   ├── course_evaluation_gui.py
│   │   │   │   ├── degree_audit_gui.py
│   │   │   │   ├── exam_scheduler.py
│   │   │   │   ├── grade_tracking_management_gui.py
│   │   │   │   ├── lms_gui.py
│   │   │   │   └── virtual_classroom_gui.py
│   │   │   └── services/
│   │   │       ├── assignments/        # Assignment services
│   │   │       ├── attendance/         # Attendance services
│   │   │       ├── degree_audit/       # Degree audit
│   │   │       ├── evaluation/         # Course evaluation
│   │   │       ├── library/            # Library services
│   │   │       ├── lms/                # Learning management
│   │   │       ├── plagiarism/         # Plagiarism detection
│   │   │       ├── timetable/          # Timetable services
│   │   │       ├── virtual_classroom/  # Virtual classroom
│   │   │       ├── academic_calendar.py
│   │   │       ├── course_management.py
│   │   │       └── module_scheduling.py
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
│   │   │   │   ├── finance/           # Finance mgmt GUI (13 managers)
│   │   │   │   ├── finance_reporting/ # Reporting GUI (16 files)
│   │   │   │   └── financial_aid/     # Aid portal GUI
│   │   │   ├── reporting/             # Budget, revenue, reports
│   │   │   ├── scholarships/          # Scholarship programs
│   │   │   └── services/              # Financial aid services
│   │   │
│   │   │  ── STUDENT LIFE DOMAINS ──
│   │   │
│   │   ├── student_affairs/           # Student affairs
│   │   │   ├── gui/
│   │   │   │   ├── alumni/            # Alumni GUI (13 components)
│   │   │   │   ├── helpdesk/          # Helpdesk GUI
│   │   │   │   ├── student_support/   # Support GUI (8 files)
│   │   │   │   └── student_union_gui/ # Union GUI (26 subdirectories)
│   │   │   ├── services/
│   │   │   │   ├── early_warning/     # Early warning system
│   │   │   │   ├── mental_health/     # Mental health services
│   │   │   │   └── student_support/   # Support system (20+ files)
│   │   │   └── student_union/         # Union services (12 files)
│   │   │
│   │   ├── housing/                   # Housing & accommodation
│   │   │   ├── gui/
│   │   │   │   └── housing_accommodation_gui/ # Housing GUI package
│   │   │   └── services/
│   │   │
│   │   │  ── STAFF & HR DOMAINS ──
│   │   │
│   │   ├── staff_hr/                  # Staff HR management
│   │   │   ├── cli/
│   │   │   │   ├── staff_hr_cli.py    # Main CLI entry
│   │   │   │   └── menus/             # 18 menu modules
│   │   │   ├── gui/                   # 14 GUI windows
│   │   │   └── services/
│   │   │       └── managers/          # 15 specialized managers
│   │   │
│   │   │  ── HEALTH DOMAINS ──
│   │   │
│   │   ├── health/                    # Health services
│   │   │   ├── appointments/          # Appointment booking
│   │   │   ├── gui/                   # Health portal & management GUIs
│   │   │   ├── portal/                # Health portal services
│   │   │   ├── records/               # Medical records management
│   │   │   └── services/
│   │   │
│   │   │  ── CAMPUS & FACILITIES ──
│   │   │
│   │   ├── campus/                    # Campus services
│   │   │   ├── gui/
│   │   │   │   ├── community/         # Church management
│   │   │   │   └── security/          # Police, security desk
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
│   │   │   │   ├── cafe_system_gui.py
│   │   │   │   ├── grocery_gui.py
│   │   │   │   └── takeaway_gui.py
│   │   │   └── services/
│   │   │       ├── restaurant/        # Restaurant (25 files)
│   │   │       ├── grocery/           # Grocery services
│   │   │       ├── takeaway/          # Takeaway services
│   │   │       ├── restaurant_management.py
│   │   │       └── shop_management.py
│   │   │
│   │   │  ── MOBILITY & TRANSPORT ──
│   │   │
│   │   ├── mobility/                  # Transportation services
│   │   │   ├── gui/
│   │   │   │   ├── parking_management_gui.py
│   │   │   │   ├── taxi_booking_gui.py
│   │   │   │   ├── train_station_gui.py
│   │   │   │   ├── trip_management_gui.py
│   │   │   │   └── mobile_app_pwa_gui.py
│   │   │   └── services/
│   │   │
│   │   │  ── BUSINESS SERVICES ──
│   │   │
│   │   ├── barber/                    # Barber shop
│   │   ├── betting/                   # Betting shop
│   │   ├── blockchain/                # Blockchain credentials
│   │   ├── butcher/                   # Butcher shop
│   │   ├── carrental/                 # Car rental
│   │   ├── cinema/                    # Cinema (52-file package)
│   │   │   └── gui/cinema_gui/        # Modular cinema GUI
│   │   ├── dentist/                   # Dental services
│   │   ├── equipment/                 # Equipment rental
│   │   ├── gym/                       # Gym & fitness
│   │   ├── legal/                     # Legal services
│   │   ├── mail/                      # Mail/post services
│   │   ├── musicshop/                 # Music shop
│   │   ├── nailbar/                   # Nail bar/salon
│   │   ├── phoneshop/                 # Phone shop
│   │   │
│   │   │  ── STUDENT SUCCESS (18 modules) ──
│   │   │
│   │   ├── ai_study/                  # AI Study Companion
│   │   ├── study_matching/            # Peer Study Matching
│   │   ├── academic_progress/         # Academic Progress Dashboard
│   │   ├── course_planning/           # Course Planning Assistant
│   │   ├── student_jobs/              # Student Job Board
│   │   ├── budget/                    # Budget Tracker
│   │   ├── scholarship_finder/        # Scholarship Finder
│   │   ├── roommate_finder/           # Roommate Finder
│   │   ├── campus_navigation/         # Campus Navigation
│   │   ├── lost_found/                # Lost & Found System
│   │   ├── marketplace/               # Student Marketplace
│   │   ├── wellness/                  # Mental Health & Wellness Hub
│   │   ├── accessibility/             # Accessibility Services Portal
│   │   ├── events/                    # Event Discovery Engine
│   │   ├── social_matching/           # Interest-Based Social Matching
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
│   │   │   ├── betting_shop_cli.py    # Betting shop CLI
│   │   │   ├── butcher_cli.py         # Butcher shop CLI
│   │   │   ├── cafe_system_cli.py     # Cafe system CLI
│   │   │   ├── charity_shop_cli.py    # Charity shop CLI
│   │   │   ├── cinema_cli.py          # Cinema CLI
│   │   │   ├── degree_audit_cli.py    # Degree audit CLI
│   │   │   ├── health_portal.py       # Health portal CLI
│   │   │   ├── nailbar_cli.py         # Nail bar CLI
│   │   │   └── ...                    # 18 more CLI modules
│   │   └── gui/                       # GUI service components
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
│       │   │   ├── dashboard/         # Dashboard components
│       │   │   ├── email/             # Email GUI components
│       │   │   ├── features/          # Feature-specific GUIs
│       │   │   ├── imports/           # Import management
│       │   │   ├── staff/             # Staff management GUIs
│       │   │   └── students/          # Student management GUIs
│       │   ├── auth/                  # Authentication GUIs (MFA wizard)
│       │   ├── advanced_search/       # Advanced search interface
│       │   ├── batch_operations/      # Batch operations GUI
│       │   ├── database/              # Database management GUI
│       │   ├── document_manager_gui/  # Document management (26 files)
│       │   ├── email/                 # Email management GUI
│       │   ├── enhanced_reporting/    # Enhanced reporting (tabs, dialogs)
│       │   ├── logic/                 # GUI logic layer
│       │   └── tools/                 # Tool GUIs
│       ├── services/                  # Shared services
│       │   ├── ai_features/           # AI features (with GUI)
│       │   ├── analytics/             # Analytics & advanced search
│       │   ├── business_intelligence/ # BI services
│       │   ├── communication/         # Communication services
│       │   ├── integrations/          # Integration services
│       │   └── pdf_export/            # PDF export (4 files)
│       └── utils/                     # Utility functions
│           ├── activity_logger.py     # Audit trail logging
│           ├── config.py              # Configuration management
│           └── validation.py          # Input validation
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
├── docs/                              # Documentation
│   ├── ai/                            # AI feature documentation
│   ├── development/                   # Developer documentation
│   ├── guides/                        # User guides (20+)
│   ├── infrastructure/                # Infrastructure guides
│   ├── modules/                       # Module documentation
│   └── security/                      # Security documentation
│
├── templates/                         # All templates (consolidated)
│   ├── assignments/                   # Assignment templates
│   ├── backup_templates/              # 6 pre-configured backup templates
│   ├── course_evaluation/             # Evaluation templates
│   ├── email/                         # 227 email templates in 30 categories
│   │   ├── academics/
│   │   ├── authentication/
│   │   ├── finance/
│   │   ├── health/
│   │   ├── housing/
│   │   ├── security/
│   │   └── ...                        # 24 more category directories
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
└── run.py                             # Main entry point
```

### Directory Consolidation Notes (January 2026)

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
from university_system.modules.shared.constants import paths

# Correct usage
backup_dir = paths.BACKUP_DIR
analytics_plots = paths.ANALYTICS_PLOTS_DIR
qr_codes = paths.QR_CODES_DIR
templates = paths.TEMPLATES_DIR
db_path = paths.DEFAULT_DB_PATH
```

**Internationalization (i18n)**: All user-facing strings should use the translation function for multi-language support:

```python
from university_system.modules.shared.utils.i18n import get_text as _t

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
- **flask** (≥2.0.0) - Web framework (legacy support)
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
from university_system.infrastructure.auth.user_authentication import UserAuthentication

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
- **PBKDF2-SHA256 hashing** with unique salts per user (1,000,000 iterations - OWASP recommended)
- Never stores plaintext passwords
- Automatic salt generation and secure random number generation
- Password complexity requirements enforced at registration

### Multi-Factor Authentication
- **TOTP (Time-based One-Time Password)**: Google Authenticator compatible
- **Email OTP**: One-time codes via email (sends to user's configured email)
- **SMS OTP**: Text message verification (optional, via Twilio or free Email-to-SMS gateway)
- **PIN Verification**: 4-digit on-screen PIN for users without MFA setup
- QR code generation for easy 2FA setup

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
from university_system.infrastructure.auth.mfa_service import MFAService
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
- **Fine-grained permissions**: Over 200 distinct permissions across all modules
- **Permission decorators**: `@require_permission('permission_name')`
- **Global auth context**: Shared authentication state across modules
- **UI-Level Access Control**: Dynamic interface filtering based on user roles

#### Role-Based UI Access Control (2025 Update)

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
from university_system.modules.shared.utils.activity_logger import log_activity

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

# 4. Run the application (CLI or GUI)
# Note: Web interface is being refactored - use CLI/GUI for now
python run.py --gui  # For GUI
python run.py --cli  # For CLI
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

The codebase was refactored in October 2025. If you see import errors:

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
| **Web Interface** | Currently being refactored - use CLI or GUI for production |
| **Multi-tenancy** | Single-tenant design; multi-institution hosting planned for v6.0 |
| **SQLite Concurrency** | May have performance limits with high concurrent writes; use PostgreSQL for high-traffic deployments |
| **i18n Coverage** | Some GUI modules have incomplete internationalization coverage |
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
| **5.17.0** | Feb 7, 2026 | Document Manager, AI Detector, Cinema, Plagiarism GUI modularization (26-52 files each) |
| **5.15.0** | Feb 7, 2026 | Housing & Shop management GUI packages, Cinema GUI 52-file refactor |
| **5.14.x** | Feb 6, 2026 | Quiet startup mode, improved student record UX, auth fixes |
| **5.12.0** | Feb 1, 2026 | Observability, automated backups, LRU caching, Remember Me auth |
| **5.5.0** | Jan 2026 | Student Success Platform (18 modules, 40+ tables) |
| **5.4.0** | Jan 2026 | Staff HR Management (15 managers, 23 tables, CLI + GUI) |
| **5.3.0** | Jan 2026 | Mobility i18n, taxi/train payment integration |
| **5.2.0** | Dec 2025 | Extras & Tools (90+ games, utilities, mini-projects) |
| **5.1.0** | Dec 2025 | Charity Shop, Research Grants, enhanced Finance GUI |
| **5.0.0** | Oct 2024 | Major modularization (91% reduction in max file size) |

See [CHANGELOG.md](CHANGELOG.md) for complete version history with detailed release notes.

---

## Roadmap

### Version 5.17.0 (February 7, 2026) - CURRENT
- [x] **Document Manager GUI**: 26-file modular package (from 18,953-line monolith)
- [x] **AI Detector**: 49-file modular package (from 10,864-line monolith)
- [x] **Cinema GUI**: 52-file modular package (from 11,086-line monolith)
- [x] **Plagiarism GUI**: 20-file modular package (from 7,132-line monolith)
- [x] **Housing & Shop GUIs**: Converted to modular packages
- [x] Quiet startup mode (verbose output moved to log files)
- [x] Improved student record update UX
- [x] Python 3.8-3.11 f-string compatibility fixes

### Version 5.12.0 (February 2026) - COMPLETED
- [x] **Observability & Monitoring** - Metrics, health checks, alerts
- [x] **Automated Data Management** - Backup scheduler with retention
- [x] **Performance Optimization** - LRU cache with TTL
- [x] **Remember Me Authentication** - 30-day persistent tokens
- [x] Admin CLI monitoring integration (8 features)

### Version 5.5.0 (January 2026) - COMPLETED
- [x] **Student Success & Engagement Platform** - 18 comprehensive modules
- [x] AI Study Companion, Peer Study Matching, Academic Progress Dashboard
- [x] Course Planning, Student Job Board, Budget Tracker, Scholarship Finder
- [x] Roommate Finder, Campus Navigation, Lost & Found, Marketplace
- [x] Wellness Hub, Accessibility Portal, Event Discovery, Social Matching
- [x] Portfolio System, Notifications Hub, Feedback System
- [x] 40+ new database tables, full CLI and GUI interfaces

### Version 5.4.0-5.4.1 (January 2026) - COMPLETED
- [x] **Staff HR Management System** - 15 specialized managers
- [x] 23 new database tables, 14 CLI menus + 14 GUI interfaces
- [x] Integration tests and input validation for all HR modules

### Version 5.0.x (January 2026) - COMPLETED
- [x] Entertainment & Commerce CLIs (betting, cinema, barber, butcher, nail bar)
- [x] Flexible login verification system (email OTP, PIN, password-only)
- [x] Staff CRUD management, 68+ bug fixes
- [x] Email template organization (227 templates in 30 categories)

### Version 6.0 (Q2-Q3 2026)
- [ ] Mobile application (React Native)
- [ ] Advanced analytics dashboard with real-time data
- [ ] Integration with external LMS systems (Canvas, Blackboard, Moodle)
- [ ] Web interface completion (FastAPI refactoring)
- [ ] Complete i18n support for all remaining GUI modules

### Version 7.0 (Q4 2026)
- [ ] Microservices architecture
- [ ] GraphQL API alongside REST
- [ ] Real-time collaboration features (live sessions, chat)
- [ ] Advanced security features (biometric auth, blockchain credentials)

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

- **Version**: 5.17.0
- **Status**: Active Development & Maintenance
- **Total Lines of Code**: 1,180,000+
- **Total Python Files**: 2,130+
- **Core System**: 1,160,000+ lines across ~2,010 files
- **Extras Module**: 19,678 lines across ~120 files
- **Python**: 3.8+ (tested on 3.8, 3.9, 3.10, 3.11, 3.12)
- **Last Updated**: February 7, 2026
- **Actively Maintained**: Yes
- **Production Ready**: Yes (with appropriate security configuration)
- **Test Coverage**: 85%+ for core functionality (Staff HR: 90%+, Student Success: 80%+)
- **Code Quality**: Black formatted, Ruff linted, mypy type-checked
- **Database Tables**: 120+ (including 23 Staff HR + 40 Student Success tables)
- **Major Functional Domains**: 53+ (18 student success modules)
- **Internationalization**: 10 languages (ar, de, en, es, fr, ja, ko, pt, ru, zh)
- **Student Success Modules**: AI Study, Peer Matching, Progress Tracking, Job Board, Budget, Scholarships, Roommate Finder, Navigation, Lost & Found, Marketplace, Wellness, Accessibility, Events, Social Matching, Portfolio, Notifications, Feedback
- **Staff HR Managers**: 15 specialized managers with full input validation
- **Extras Included**: 90+ games, utilities, and mini-projects

---

**Made with dedication for educational institutions worldwide**

For questions, suggestions, or support, please [open an issue](https://github.com/sean1352636/university_system/issues) or contact the development team.