# Module Documentation

Complete documentation for all system modules.

> **Note:** In v5.41–v5.42, 49 single-file modules were restructured into package directories.
> See the [Migration Guide](../development/MIGRATION_GUIDE.md) for that file mapping and
> the refactoring patterns.

## Infrastructure Modules

Core infrastructure services that power the entire system.

### [Authentication System](../security/AUTHENTICATION.md)
**Location**: `src/education_system/platform/identity/auth/` (shared) and `src/education_system/systems/university/infrastructure/auth/` (university façade)

Centralized authentication system shared by all seven systems.

- **Features**: bcrypt password hashing, 2FA support, role-based access control
- **Users**: Admin, Instructor, Staff, Student, Parent roles
- **Security**: bcrypt hashes in the central `auth.db`; legacy PBKDF2 hashes still verify
- **Sessions**: Secure session management with automatic expiration

### Email System
**Location**: `src/education_system/systems/university/infrastructure/email/email_service/`

Centralized SMTP email service with automated notifications.

- **Features**: Professional templates, delivery tracking, queue management
- **Integration**: 11+ modules use centralized email service
- **Notifications**: Automated emails for all major system events
- **Configuration**: Supports Gmail, Outlook, custom SMTP servers

### [Database System](../infrastructure/DATABASE.md)
**Location**: `src/education_system/systems/university/infrastructure/database/`

Centralized database management with SQLite.

- **Features**: Connection pooling, schema management, migrations
- **Databases**: Multiple specialized databases (student, health, financial, etc.)
- **Utilities**: Backup, restore, integrity checking
- **Performance**: Optimized indexes and query patterns

## Academic Modules

Student and course management features.

### Academic Management

- **Student Records**: Comprehensive profile management
- **Course Management**: Catalog, prerequisites, enrollment
- **Grading System**: Multi-scale grading with GPA calculation
- **Attendance Tracking**: QR codes, geofencing, face recognition
- **Assignment System**: Submission portal with plagiarism detection
- **Academic Calendar**: Terms, events, deadlines, exam scheduling

## Financial Modules

Complete financial management suite.

### Financial Management

- **Student Billing**: Automated fee calculation, payment plans
- **Scholarship Management**: Applications, awards, eligibility
- **Payment Processing**: Multiple payment methods, receipts
- **Financial Reporting**: Revenue analytics, budget analysis
- **Refund Processing**: Automated refund workflows

## Student Life Modules

Campus life and student engagement.

### Student Union
**Location**: `src/education_system/systems/university/domains/student_life/domain/student_life/student_union/`

26 fully implemented features for student life management.

#### Club Management
- Member directory with email integration
- Discussion forums and announcements
- Media gallery for club photos/videos
- Event planning and scheduling

#### Competitions System
- Browse and register for competitions
- Team management
- Results tracking and leaderboards
- Personal competition history

#### Peer Support Groups
- Mental health, academic, career support
- Group facilitation and scheduling
- Wellness resources and hotlines
- Member management

#### Equipment Management
- Equipment catalog (AV, Sports, Tech)
- Checkout and return system
- Usage tracking and history

#### Gamification
- Points and badges system
- Leaderboards and rankings
- Achievement tracking
- Engagement metrics

#### Mentorship Program
- Find and request mentors
- Become a mentor
- Session scheduling and tracking
- Progress monitoring

## Health Services Modules

Medical records and health management.

### Health Services

- **Medical Records**: HIPAA-compliant electronic health records
- **Appointment System**: Online booking, reminders, cancellations
- **Health Screenings**: Preventive care, vaccinations
- **Health Analytics**: Population health reporting, trend analysis
- **Medical History**: Medications, allergies, conditions

## Library Modules

Library management and book checkout.

### Library System

- **Catalog Management**: Book inventory, ISBN tracking
- **Checkout System**: Automated lending with email confirmations
- **Fine Management**: Late fee calculation and notifications
- **Library Cards**: Digital card generation with barcodes
- **Reservations**: Book reservation system

## Interface Modules

User interface components.

### GUI Modules
**Location**: `src/education_system/systems/university/domains/<slice>/interfaces/gui/` and `src/education_system/systems/university/shell/gui/`

Graphical user interface modules organized by domain slice:

- `shell/gui/main/` - Main application window, navigation and portals
- `domains/curriculum/interfaces/gui/` - Course and module management
- `domains/assessment/interfaces/gui/` - Assignments, exams, grading
- `domains/teaching/interfaces/gui/` - Attendance, timetabling, academic calendar
- `domains/library/interfaces/gui/` - Library
- `domains/finance/interfaces/gui/` - Financial management, financial aid, reporting
- `domains/health/interfaces/gui/` - Health portal
- `domains/student_support/interfaces/gui/` - Helpdesk, disability, wellbeing
- `domains/student_life/interfaces/gui/` - Internships, student union
- `domains/operations/interfaces/gui/campus/housing/` - Housing and accommodation management
- `domains/operations/interfaces/gui/campus/mobility/` - Parking, trip management
- `domains/operations/interfaces/gui/campus/security/` - Campus security
- `domains/operations/interfaces/gui/campus/campus_navigation/` - Campus map and navigation
- `plugins/campus_commerce/interfaces/gui/` - Cafe system, shop management
- `domains/learners/interfaces/gui/students/advanced_search.py` - Advanced search interface
- `shell/gui/batch_operations.py` - Batch operations interface
- `shell/gui/document_manager/` - Document management interface

### CLI Module
**Location**: `src/education_system/systems/university/shell/cli/` and `src/education_system/systems/university/domains/<slice>/interfaces/cli/`

Command-line interface for administrative tasks and automation.

### [REST API](../development/API.md)
**Location**: `src/education_system/api/university/<area>/`

REST API endpoint groups for web-based access, covering authentication, academics, finance, student life, campus services, health, career, support, and administration. See the [API Documentation](../development/API.md) for the complete endpoint reference.

## AI & Automation Modules

Intelligent features and automation.

### AI Chatbot
**Location**: `src/education_system/systems/university/shared/ai/chatbot/`

- Natural language query handling
- 24/7 student assistance
- Information retrieval
- Context-aware responses

### Plagiarism Detection
- Document analysis and comparison
- Similarity checking with detailed reports
- Batch processing support
- Email notifications for violations

### AI Content Detection
- Identify AI-generated content
- Authenticity verification
- Confidence scoring
- Alert system for instructors

## Analytics & Reporting Modules

Data analysis and reporting tools.

### Analytics Dashboard
- Custom report generation (PDF, Excel, CSV)
- Interactive charts and graphs
- Real-time metrics and dashboards
- Predictive analytics for student success

### Audit System
- Complete activity logging
- User action tracking
- Security event monitoring
- Compliance reporting (FERPA, HIPAA)

## Utility Modules

Supporting utilities and extensions.

### Shared Utilities
**Location**: `src/education_system/systems/university/infrastructure/utils/`

- Common helper functions
- Data validation
- File handling
- Date/time utilities

### Plugins
**Location**: `src/education_system/systems/university/plugins/`

- `campus_commerce/` - Restaurant, shops, bar, gym, betting and more
- `community_services/` - Community services
- `registry.py` and `plugin.json` manifests

## Module Development

### Adding New Modules

1. **Create Module Structure**
   ```
   src/education_system/systems/university/domains/<slice>/
   ├── __init__.py
   ├── domain/
   │   └── your_module/
   │       └── your_service.py
   └── interfaces/
       ├── cli/
       └── gui/
           └── your_module/
               └── your_gui.py
   ```

2. **Integrate Authentication**
   ```python
   from education_system.systems.university.infrastructure.auth import UserAuth
   auth = UserAuth()
   ```

3. **Integrate Email**
   ```python
   from education_system.systems.university.infrastructure.email.smtp import send_email_via_smtp
   ```

4. **Create GUI Interface**
   ```
   src/education_system/systems/university/domains/<slice>/interfaces/gui/your_module/your_gui.py
   ```

5. **Add API Routes** (optional)
   ```
   src/education_system/api/university/<area>/your_routes.py
   ```

6. **Add Documentation**
   Create `docs/university/guides/<area>/YOUR_MODULE.md`

### Module Standards

- Use centralized authentication (UserAuth)
- Use centralized email (send_email_via_smtp)
- Follow PEP 8 coding standards
- Include comprehensive docstrings
- Add unit and integration tests
- Update documentation

## Related Documentation

- [Developer Guide](../development/README.md) - Setup, workflow, and coding standards
- [API Documentation](../development/API.md) - REST API reference
- [Migration Guide](../development/MIGRATION_GUIDE.md) - Module restructuring reference

---

**Domain Slices**: 18 under `domains/`
**CLI Modules**: Domain-specific and shared CLI tools
**Integration**: Centralized auth and email
