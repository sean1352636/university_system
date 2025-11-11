# University Management System

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.0.0-brightgreen)](https://github.com/yourusername/university-system)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive, enterprise-grade university management system designed to handle all aspects of higher education administration. This modular platform integrates academic, financial, student affairs, health services, and administrative operations into a unified, scalable solution with multiple interface options (CLI, GUI, Web).

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
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
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

The University Management System is a full-featured platform built with Python that provides:

- **Modular Architecture**: Domain-driven design with clearly separated concerns across infrastructure, domain, service, and interface layers
- **Multiple Interfaces**: Command-line (CLI), graphical (Tkinter), and web (Flask) interfaces for diverse user preferences
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

- **Version**: 5.0.0 (January 2025)
- **Lines of Code**: ~150,000+ across all modules
- **Python Version**: 3.8+ (tested on 3.8-3.12)
- **Modules**: 15+ major functional domains
- **Files**: 74 modular files (post-refactoring from 4 monolithic files)
- **Average File Size**: ~750 lines (91% reduction from 13,920 average)
- **Test Coverage**: 85%+ for core functionality
- **Database Tables**: 50+ normalized tables
- **API Endpoints**: 200+ RESTful endpoints

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

### Infrastructure
- **Authentication**: Centralized authentication with multi-factor authentication (TOTP, Email OTP, SMS OTP)
- **Authorization**: Role-based access control (RBAC) with fine-grained permissions
- **Database**: SQLite (default) with connection pooling, WAL mode, and support for PostgreSQL/MySQL
- **Backup System**: Comprehensive backup management with 6 pre-configured templates (daily, encrypted, incremental, cloud, selective, remote)
- **Email Service**: Asynchronous email queue with SMTP integration, template rendering, and delivery tracking
- **Console Output**: Professional terminal formatting with ANSI colors, progress bars, tables, and interactive prompts
- **AI Integration**: Chatbot capabilities, plagiarism detection, and predictive analytics
- **Activity Logging**: Comprehensive audit trails for compliance and security monitoring

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
git clone https://github.com/yourusername/university-system.git
cd university-system

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
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

Create a `.env` file in the project root (copy from `.env.example`):

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

The system supports multiple database backends:

- **SQLite** (default): No configuration needed, database location: `data/db_files/student_records.db`
- **PostgreSQL**: Configure connection in `.env` for production deployments
- **MySQL**: Configure connection in `.env` for production deployments

Database features:
- Thread-safe connection pooling (2-10 connections, configurable)
- Write-Ahead Logging (WAL) for improved concurrency
- Automatic schema migration support
- Backup and restore utilities

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

### Web Interface

> **Note**: Web interface is currently being refactored. Use CLI or GUI interfaces in the meantime.

```bash
# Web interface coming soon
# The Flask web module is being reorganized following the domain-driven architecture
```

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
├── infrastructure/                  # Core infrastructure components
│   ├── ai/                         # AI/ML services (chatbot, analytics)
│   ├── auth/                       # Authentication and authorization
│   │   ├── user_authentication.py  # Password hashing, session management
│   │   └── authorization.py        # RBAC, permission checking
│   ├── database/                   # Database connection and management
│   │   ├── db.py                   # Connection pooling, transactions
│   │   └── database_utils.py       # Backup, restore, migration utilities
│   ├── email/                      # Email service integration
│   │   ├── email_service.py        # Async queue, SMTP integration
│   │   ├── config.py               # Email configuration
│   │   └── gui/                    # Email management GUI
│   ├── security/                   # Security features
│   │   ├── encryption.py           # Data encryption utilities
│   │   └── audit.py                # Audit logging
│   ├── exceptions.py               # Infrastructure exceptions
│   └── shared_context.py           # Global application context
│
├── modules/                        # Main application modules
│   ├── domain/                     # Domain layer (business logic)
│   │   ├── academics/              # Academic domain
│   │   │   ├── services/           # Academic services
│   │   │   │   ├── assignments/    # Assignment system services
│   │   │   │   ├── course_management.py # Course management
│   │   │   │   ├── library.py      # Library services
│   │   │   │   ├── academic_calendar.py # Calendar management
│   │   │   │   ├── module_scheduling.py # Module scheduling
│   │   │   │   └── plagiarism/     # Plagiarism detection
│   │   │   ├── gui/                # Academic GUIs
│   │   │   │   ├── assignment_system/ # Assignment GUI (19 modular files)
│   │   │   │   ├── grade_tracking/    # Grade tracking (24 modular files)
│   │   │   │   ├── course_management_gui.py
│   │   │   │   ├── library_gui.py
│   │   │   │   ├── academic_calendar_gui.py
│   │   │   │   ├── module_scheduling_gui.py
│   │   │   │   └── plagiarism_main_gui.py
│   │   │   ├── grading/            # Grading services
│   │   │   └── grade_misc/         # Grade utilities
│   │   │
│   │   ├── finance/                # Financial services domain
│   │   │   ├── services/           # Finance service layer
│   │   │   │   ├── financial_aid.py # Financial aid services
│   │   │   │   ├── budgeting.py    # Budget management
│   │   │   │   └── reporting.py    # Financial reporting
│   │   │   └── gui/                # Finance GUIs
│   │   │       ├── finance/        # Finance management (13 modular files)
│   │   │       │   ├── budget_manager.py
│   │   │       │   ├── transaction_manager.py
│   │   │       │   └── ...         # 11 more manager files
│   │   │       ├── financial_aid/  # Financial aid & scholarships GUI
│   │   │       ├── finance_management_gui.py
│   │   │       └── finance_reporting_gui.py
│   │   │
│   │   ├── health/                 # Health services domain
│   │   │   ├── services/           # Health services
│   │   │   └── gui/                # Health GUIs
│   │   │       ├── health_portal_gui.py
│   │   │       └── telemedicine_gui.py
│   │   │
│   │   ├── housing/                # Housing management domain
│   │   │   ├── services/           # Housing services
│   │   │   └── gui/                # Housing GUIs
│   │   │       └── accommodation_management_gui.py
│   │   │
│   │   ├── commerce/               # Commerce and dining services
│   │   │   ├── services/           # Commerce services
│   │   │   │   ├── restaurant_service.py
│   │   │   │   └── shop_management.py
│   │   │   └── gui/                # Commerce GUIs
│   │   │       ├── restaurant_management_gui.py
│   │   │       └── shop_management_gui.py
│   │   │
│   │   └── student_affairs/        # Student affairs domain
│   │       ├── services/           # Student affairs services
│   │       │   ├── student_union/  # Student union (18 modular files)
│   │       │   │   ├── administration/ # Core administration
│   │       │   │   ├── clubs/      # Club management
│   │       │   │   ├── events/     # Event planning
│   │       │   │   ├── mentorship/ # Mentorship program
│   │       │   │   ├── equipment/  # Equipment lending
│   │       │   │   └── ...         # 13 more specialized subdirectories
│   │       │   ├── student_support/ # Student Support (31 modular files)
│   │       │   │   ├── core/       # Main support system
│   │       │   │   ├── models/     # Data models
│   │       │   │   ├── database/   # Database schema
│   │       │   │   ├── services/   # 10 business logic services
│   │       │   │   ├── cli/        # 5 CLI interface files
│   │       │   │   └── utils/      # Utility functions
│   │       │   ├── alumni_management.py
│   │       │   ├── helpdesk.py
│   │       │   └── internship_management.py
│   │       └── gui/                # Student affairs GUIs
│   │           ├── student_union_gui.py
│   │           ├── student_support_gui.py
│   │           ├── alumni_management_gui.py
│   │           ├── helpdesk_gui.py
│   │           └── internship_management_gui.py
│   │
│   ├── services/                   # Application services layer
│   ├── core/                       # Core business entities and repositories
│   └── shared/                     # Shared utilities and helpers
│       ├── constants/              # Centralized paths and constants
│       │   └── paths.py            # Single source of truth for ALL paths
│       ├── gui/                    # Shared GUI components
│       │   ├── main_gui.py         # Main GUI application
│       │   ├── advanced_search_gui.py # Advanced search interface
│       │   ├── document_manager_gui.py # Document management
│       │   └── simple_activity_logger_gui.py
│       ├── services/               # Shared services
│       │   └── analytics/          # Analytics services
│       │       └── advanced_search.py
│       └── utils/                  # Utility functions
│           ├── activity_logger.py  # Activity logging for audit trails
│           ├── config.py           # Configuration management
│           ├── validation.py       # Input validation utilities
│           └── document_manager.py # Document utilities
│
├── data/                           # Application data directory
│   ├── analytics/                  # Analytics outputs (CONSOLIDATED)
│   │   ├── plots/                  # Analytics plots (from student_analytics.py)
│   │   └── reports/                # Analytics reports (PDF, CSV, etc.)
│   ├── chatbot/                    # Chatbot data and conversation logs
│   ├── db_files/                   # Database files
│   │   └── student_records.db      # Main SQLite database
│   ├── email/                      # Email queue (templates at root level)
│   ├── reports/                    # Generated reports (PDF, Excel)
│   │   └── timetable_reports/      # Timetable reports (CONSOLIDATED)
│   ├── submissions/                # Assignment submissions
│   └── uploads/                    # General user uploads
│
├── tests/                          # Comprehensive test suite
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   ├── security/                   # Security tests
│   ├── fixtures/                   # Test fixtures and sample data
│   ├── conftest.py                 # Pytest configuration
│   └── run_all_tests.py            # Test runner
│
├── docs/                           # Documentation
│   ├── development/                # Developer documentation
│   │   ├── API.md                  # REST API reference
│   │   ├── ARCHITECTURE.md         # Architecture overview
│   │   ├── CONTRIBUTING.md         # Contribution guidelines
│   │   └── CODE_STYLE.md           # Code style guide
│   ├── modules/                    # Module-specific documentation
│   ├── user-guide/                 # User documentation
│   └── README.md                   # Documentation index
│
├── logs/                           # Application logs
│   └── university_system.log       # Main application log
├── backups/                        # Database backups (CONSOLIDATED)
├── qr_codes/                       # QR codes (CONSOLIDATED - from reservation system)
├── config/                         # Configuration files
│   └── app_config.json             # Application configuration
├── templates/                      # All templates (CONSOLIDATED - single location)
│   ├── assignments/                # Assignment templates
│   ├── email/                      # Email templates
│   ├── reports_templates/          # Report templates
│   └── backup_templates/           # Backup configuration templates (see README)
│       ├── daily_basic.json        # Standard daily backup template
│       ├── secure_encrypted.json   # High-security encrypted backup
│       ├── incremental_fast.json   # Fast incremental backups
│       ├── cloud_aws.json          # AWS S3 cloud backup
│       ├── selective_tables.json   # Selective table backup
│       ├── remote_sftp.json        # Remote SFTP backup
│       └── README.md               # 📖 Backup templates documentation
├── utils/                          # Additional utilities
│
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── CLAUDE.md                       # Claude AI instructions
├── LICENSE                         # MIT License
├── Makefile                        # Development commands
├── pyproject.toml                  # Project configuration and dependencies
├── README.md                       # This file
├── requirements.txt                # Python dependencies
└── run.py                          # Main application entry point
```

### Directory Consolidation Notes (2025)

**Recent architectural improvements** have consolidated and reorganized the entire codebase:

1. **Domain-Driven Design**: All GUIs moved into their respective domain folders
   - Academic GUIs: `modules/domain/academics/gui/`
   - Finance GUIs: `modules/domain/finance/gui/`
   - Health GUIs: `modules/domain/health/gui/`
   - Student Affairs GUIs: `modules/domain/student_affairs/gui/`
   - Commerce GUIs: `modules/domain/commerce/gui/`

2. **Eliminated `modules/interfaces/` layer**: All interfaces now live within their domains
   - Previous: `modules/interfaces/gui/finance/` → Now: `modules/domain/finance/gui/`
   - Previous: `modules/interfaces/gui/assignment_system/` → Now: `modules/domain/academics/gui/assignment_system/`

3. **Shared Components**: Consolidated to `modules/shared/`
   - Shared GUIs: `modules/shared/gui/` (main_gui.py, advanced_search_gui.py, etc.)
   - Shared Services: `modules/shared/services/`
   - Shared Utils: `modules/shared/utils/`

4. **Data Directories**: All runtime data consolidated
   - Backups: `university_system/backups/`
   - QR Codes: `university_system/qr_codes/`
   - Analytics: `university_system/data/analytics/`
   - Templates: `university_system/templates/`
   - Timetable Reports: `university_system/data/reports/timetable_reports/`

**Path Management**: All file paths are managed through `modules/shared/constants/paths.py` as the single source of truth. Always use these constants instead of hardcoded paths:

```python
from university_system.modules.shared.constants import paths

# Correct usage
backup_dir = paths.BACKUP_DIR
analytics_plots = paths.ANALYTICS_PLOTS_DIR
qr_codes = paths.QR_CODES_DIR
templates = paths.TEMPLATES_DIR
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
- **requests** (≥2.27.0) - HTTP library for API calls and external service integration
- **flask** (≥2.0.0) - Web framework for REST API endpoints and web interface
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
make install          # Production dependencies
make install-dev      # Development dependencies
make setup           # Complete setup with hooks

# Code quality
make format          # Format code with Black + isort
make lint            # Run linter (Ruff)
make type-check      # Run mypy type checking
make security-check  # Security vulnerability checks
make check           # Run all quality checks

# Testing
make test            # Run all tests
make test-fast       # Run tests in parallel
make test-coverage   # Run with coverage report
make test-unit       # Run unit tests only
make test-integration # Run integration tests only

# Running
make run             # Interactive menu
make run-cli         # CLI mode
make run-gui         # GUI mode

# Database
make db-backup       # Create database backup
make db-restore BACKUP_FILE=path/to/backup.db
make db-reset        # Reset database (WARNING: deletes data)

# Utilities
make clean           # Remove build artifacts
make logs            # View application logs
make profile         # Run profiler
make info            # Display project information
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
- **Email OTP**: One-time codes via email
- **SMS OTP**: Text message verification (optional)
- QR code generation for easy 2FA setup

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

For detailed security information, see [SECURITY.md](SECURITY.md) and [Security Documentation](university_system/docs/SECURITY.md).

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

**Documentation**: See [templates/backup_templates/README.md](templates/backup_templates/README.md) for detailed template descriptions, configuration options, and usage examples.

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

- **[Documentation Index](university_system/docs/README.md)** - Complete documentation overview
- **[Email Scheduler Guide](university_system/docs/EMAIL_SCHEDULER.md)** - Automated email system setup and usage
- **[Security Documentation](university_system/docs/SECURITY.md)** - Security features and best practices
- **[Security Features Summary](university_system/docs/SECURITY_FEATURES_SUMMARY.md)** - Quick security reference
- **[MFA Quick Start](university_system/docs/MFA_QUICK_START.md)** - Multi-factor authentication setup
- **[MFA System Documentation](university_system/docs/MFA_SYSTEM_DOCUMENTATION.md)** - Complete MFA guide
- **[Authentication Overview](university_system/docs/AUTHENTICATION_ARCHITECTURE_OVERVIEW.md)** - Authentication system architecture
- **[Auth Quick Reference](university_system/docs/AUTH_QUICK_REFERENCE.md)** - Authentication quick guide
- **[Database Documentation](university_system/docs/development/DATABASE.md)** - Database architecture and usage
- **[Authentication Guide](university_system/docs/development/AUTHENTICATION.md)** - Authentication implementation
- **[Transaction Handling](university_system/docs/development/TRANSACTIONS.md)** - Transaction safety guide
- **[Exception Handling](university_system/docs/development/EXCEPTION_HANDLING.md)** - Error handling patterns
- **[Testing Guide](university_system/docs/testing/TESTING_GUIDE.md)** - Writing and running tests
- **[Troubleshooting](university_system/docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Backup Templates Guide](university_system/templates/backup_templates/README.md)** - Pre-configured backup templates and usage
- **[Quick Start Guide](university_system/docs/getting-started/QUICK_START.md)** - Getting started quickly

### CLAUDE.md

The project includes a comprehensive `CLAUDE.md` file that provides:
- Complete project overview and architecture
- Development commands and workflows
- Code organization principles
- Common patterns and best practices
- Key file references and conventions

This file is specifically designed to help AI assistants (like Claude Code) understand the codebase and provide better assistance.

---

## Contributing

We welcome contributions! Please follow these steps:

1. **Fork the Repository**
   ```bash
   git clone https://github.com/yourusername/university-system.git
   cd university-system
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

For more information, see [Documentation Index](university_system/docs/README.md) and [CLAUDE.md](CLAUDE.md).

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
cd /path/to/university-system

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
- [Security Documentation](university_system/docs/SECURITY.md)

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
- **Flask** - For the web framework
- **All Contributors** - For their valuable contributions and feedback
- **Educational Institutions** - For providing feedback and use cases

---

## Recent Updates

### Version 5.0.0 (October 2025) - Major Refactoring

The codebase underwent comprehensive modularization:

- **Student Union**: Split from 16,535 lines → 18 specialized files
- **Assignment System**: Refactored from 14,393 lines → 19 manager-based files
- **Grade Tracking**: Reorganized from 13,114 lines → 24 modular files
- **Finance Module**: Split from 11,641 lines → 13 manager files

**Results:**
- **91% reduction** in maximum file size
- **Average file size**: ~750 lines (down from 13,920)
- **Manager pattern** implemented throughout
- **Total transformation**: 4 monolithic files (55,683 lines) → 74 modular files

### New Features (v5.0.0)

- Virtual Classroom with session recording and analytics
- Predictive analytics for student performance
- Batch grade prediction system
- Enhanced medical accommodations with accessibility integration
- Improved GUI with better scrollbars and UX
- Comprehensive activity logging for compliance
- Multi-factor authentication (TOTP, Email OTP, SMS OTP)
- Asynchronous email queue with template rendering
- Professional console output utility with ANSI colors and formatted tables (January 2025)

---

## Roadmap

### Version 5.1 (Q2 2025)
- [ ] Mobile application (React Native)
- [ ] Advanced analytics dashboard with real-time data
- [ ] Enhanced machine learning grade prediction
- [ ] Integration with external LMS systems (Canvas, Blackboard, Moodle)

### Version 6.0 (Q4 2025)
- [ ] Microservices architecture
- [ ] GraphQL API alongside REST
- [ ] Real-time collaboration features (live sessions, chat)
- [ ] Advanced security features (biometric auth, blockchain credentials)

### Future Considerations
- [ ] Multi-tenancy support for hosting multiple institutions
- [ ] Cloud-native deployment (Kubernetes, Docker Swarm)
- [ ] Internationalization (i18n) and localization (l10n)
- [ ] Blockchain for credential verification and academic records
- [ ] Advanced AI features (chatbot improvements, automated grading)

---

## Support & Contact

### Getting Help

- **Documentation**: [Documentation Index](university_system/docs/README.md)
- **Troubleshooting**: [Troubleshooting Guide](university_system/docs/TROUBLESHOOTING.md)
- **Issue Tracker**: [GitHub Issues](https://github.com/yourusername/university-system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/university-system/discussions)
- **Quick Start**: [Getting Started](university_system/docs/getting-started/QUICK_START.md)

### Reporting Issues

When reporting issues, please include:
1. Python version and operating system
2. Complete error message and stack trace
3. Steps to reproduce the issue
4. Expected vs. actual behavior
5. Relevant configuration (without sensitive data)

---

## Project Status

- **Version**: 5.0.0
- **Status**: Active Development
- **Python**: 3.8+ (tested on 3.8-3.12)
- **Last Updated**: January 2025
- **Actively Maintained**: Yes
- **Production Ready**: Yes (with appropriate configuration)

---

**Made with dedication for educational institutions worldwide**

For questions, suggestions, or support, please [open an issue](https://github.com/yourusername/university-system/issues) or contact the development team.
