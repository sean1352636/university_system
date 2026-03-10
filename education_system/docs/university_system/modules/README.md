# Module Documentation

Complete documentation for all system modules.

> **Note:** In v5.41–v5.42, 49 single-file modules were restructured into package directories.
> All existing imports remain backward-compatible. See the
> [Migration Guide](../development/MIGRATION_GUIDE.md) for the complete file mapping and
> refactoring patterns.

## Infrastructure Modules

Core infrastructure services that power the entire system.

### [Authentication System](AUTHENTICATION.md)
**Location**: `infrastructure/auth/user_authentication.py`

Centralized authentication system used across 92 files.

- **Features**: PBKDF2 password hashing, 2FA support, role-based access control
- **Users**: Admin, Faculty, Staff, Student, Parent roles
- **Security**: Salt-based hashing with 100,000 iterations
- **Sessions**: Secure session management with automatic expiration

### [Email System](EMAIL.md)
**Location**: `infrastructure/email/email_service/`

Centralized SMTP email service with automated notifications.

- **Features**: Professional templates, delivery tracking, queue management
- **Integration**: 11+ modules use centralized email service
- **Notifications**: Automated emails for all major system events
- **Configuration**: Supports Gmail, Outlook, custom SMTP servers

### [Database System](DATABASE.md)
**Location**: `infrastructure/database/`

Centralized database management with SQLite.

- **Features**: Connection pooling, schema management, migrations
- **Databases**: Multiple specialized databases (student, health, financial, etc.)
- **Utilities**: Backup, restore, integrity checking
- **Performance**: Optimized indexes and query patterns

## Academic Modules

Student and course management features.

### [Academic Management](ACADEMIC.md)

- **Student Records**: Comprehensive profile management
- **Course Management**: Catalog, prerequisites, enrollment
- **Grading System**: Multi-scale grading with GPA calculation
- **Attendance Tracking**: QR codes, geofencing, face recognition
- **Assignment System**: Submission portal with plagiarism detection
- **Academic Calendar**: Terms, events, deadlines, exam scheduling

## Financial Modules

Complete financial management suite.

### [Financial Management](FINANCE.md)

- **Student Billing**: Automated fee calculation, payment plans
- **Scholarship Management**: Applications, awards, eligibility
- **Payment Processing**: Multiple payment methods, receipts
- **Financial Reporting**: Revenue analytics, budget analysis
- **Refund Processing**: Automated refund workflows

## Student Life Modules

Campus life and student engagement.

### [Student Union](STUDENT_UNION.md)
**Location**: `modules/domain/student_affairs/student_union/`

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

### [Health Services](HEALTH.md)

- **Medical Records**: HIPAA-compliant electronic health records
- **Appointment System**: Online booking, reminders, cancellations
- **Health Screenings**: Preventive care, vaccinations
- **Health Analytics**: Population health reporting, trend analysis
- **Medical History**: Medications, allergies, conditions

## Library Modules

Library management and book checkout.

### [Library System](LIBRARY.md)

- **Catalog Management**: Book inventory, ISBN tracking
- **Checkout System**: Automated lending with email confirmations
- **Fine Management**: Late fee calculation and notifications
- **Library Cards**: Digital card generation with barcodes
- **Reservations**: Book reservation system

## Interface Modules

User interface components.

### GUI Modules
**Location**: `modules/domain/<domain>/gui/` and `modules/shared/gui/`

30+ graphical user interface modules organized by domain:

- `modules/shared/gui/main/` - Main application launcher and dashboard
- `modules/domain/academics/gui/` - Course management, assignments, grading, library
- `modules/domain/finance/gui/` - Financial management, financial aid, reporting
- `modules/domain/health/gui/` - Health portal, medical accommodations
- `modules/domain/student_affairs/gui/` - Helpdesk, internships, student union
- `modules/domain/housing/gui/` - Housing and accommodation management
- `modules/domain/mobility/gui/` - Parking, trip management
- `modules/domain/commerce/gui/` - Cafe system, shop management
- `modules/domain/campus/gui/` - Security, campus services
- `modules/domain/campus_navigation/gui/` - Campus map and navigation
- `modules/shared/gui/advanced_search/` - Advanced search interface
- `modules/shared/gui/batch_operations/` - Batch operations interface
- `modules/shared/gui/document_manager_gui/` - Document management interface

### CLI Module
**Location**: `modules/shared/cli/`

Command-line interface for administrative tasks and automation.

### [REST API](../development/API.md)
**Location**: `api/routes/`

59 REST API endpoint groups for web-based access, covering authentication, academics, finance, student life, campus services, health, career, support, and administration. See the [API Documentation](../development/API.md) for the complete endpoint reference.

## AI & Automation Modules

Intelligent features and automation.

### AI Chatbot
**Location**: `utils/ai/university_chatbot/`

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
**Location**: `modules/shared/utils/`

- Common helper functions
- Data validation
- File handling
- Date/time utilities

### Extensions
**Location**: `modules/extensions/`

- Database extensions
- Custom plugins
- Third-party integrations

## Module Development

### Adding New Modules

1. **Create Module Structure**
   ```
   modules/domain/your_domain/
   ├── __init__.py
   ├── services/
   │   └── your_service.py
   ├── gui/
   │   └── your_gui.py
   └── models/
       └── your_model.py
   ```

2. **Integrate Authentication**
   ```python
   from university_system.infrastructure.auth.user_authentication import UserAuth
   auth = UserAuth()
   ```

3. **Integrate Email**
   ```python
   from university_system.infrastructure.email.smtp import send_email_via_smtp
   ```

4. **Create GUI Interface**
   ```
   modules/domain/your_domain/gui/your_gui.py
   ```

5. **Add API Routes** (optional)
   ```
   api/routes/your_domain.py
   ```

6. **Add Documentation**
   Create `docs/modules/YOUR_MODULE.md`

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

**Total Modules**: 80+ modules across 12 domains
**GUI Modules**: 30+ interface modules
**API Endpoint Groups**: 59 REST route blueprints
**CLI Modules**: Domain-specific and shared CLI tools
**Integration**: Centralized auth (92 files), Email (11 files)
