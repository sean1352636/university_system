# Restaurant Management - Inventory, Payroll & Waste Tracking Integration Guide

## Overview

Three comprehensive GUI modules have been fully integrated into the Restaurant Management system, providing complete operational tracking capabilities.

**Date**: 2026-01-25
**Version**: 5.0.78
**Status**: ✅ Fully Integrated & Operational

---

## 🎯 Quick Access

### From Restaurant Management GUI:

1. **Purchase Orders** → Inventory Tab → "Purchase Orders" button
2. **Shifts & Payroll** → Staff Tab → "Manage Schedules" button
3. **Waste Tracking** → Inventory Tab → "Waste Tracking" button

---

## 📦 Purchase Orders Management

### Access
**Inventory Tab** → **"Purchase Orders"** button

### Features

**Main Window** - Two-tab interface:

#### Tab 1: Purchase Orders
- **Create New PO**: Multi-item purchase orders with line items
- **Edit Existing**: Update PO details, add/remove items
- **Status Management**: Pending → Approved → Ordered → Received → Completed
- **Payment Tracking**: Record payment method and payment date
- **Receive Items**: Track received quantities vs ordered quantities
- **Cancel Orders**: Cancel with reason tracking

**PO Information Tracked**:
- PO Number (auto-generated)
- Supplier selection from dropdown
- Order date & expected delivery date
- Line items: item name, quantity, unit of measure, unit cost
- Tax amount & total cost
- Payment method & status
- Notes

#### Tab 2: Suppliers
- **Add Suppliers**: Name, contact person, email, phone, address
- **Edit Suppliers**: Update supplier information
- **Deactivate Suppliers**: Mark inactive instead of deleting
- **Payment Terms**: Track payment arrangements
- **Category Classification**: Organize suppliers by type

**Actions Available**:
- Double-click PO to view/edit
- Right-click for context menu (Edit, Receive, Cancel)
- Export PO list to CSV
- Search and filter POs

### Database Tables Created

1. **restaurant_suppliers**
   - Supplier master data
   - Contact information
   - Payment terms & status

2. **restaurant_purchase_orders**
   - PO header information
   - Dates, totals, status
   - Payment tracking

3. **restaurant_purchase_order_items**
   - Line item details
   - Quantities ordered & received
   - Unit costs & totals

### Benefits

✅ Accurate expense tracking for Financial Reports
✅ Supplier performance monitoring
✅ Inventory cost management
✅ Payment tracking for cash flow
✅ Historical purchase analysis

---

## 👥 Shifts Management & Payroll

### Access
**Staff Tab** → **"Manage Schedules"** button

### Features

**Main Window** - Three-tab interface:

#### Tab 1: Shifts
- **Add New Shift**: Schedule employee shifts with dates and times
- **Edit Shifts**: Modify shift details
- **Clock In/Out**: Record actual work times
- **Auto-Calculate Hours**: Automatic hours worked calculation
- **Pay Calculation**: Hourly rate × hours worked
- **Break Time**: Deduct unpaid break minutes
- **Status Tracking**: Scheduled → Clocked In → Completed → No Show

**Shift Information Tracked**:
- Staff member (dropdown selection)
- Shift date
- Scheduled start/end times
- Actual clock in/out times
- Break minutes
- Hours worked (auto-calculated)
- Hourly rate (from staff record)
- Total pay (auto-calculated)
- Status & notes

#### Tab 2: Staff
- **Add Staff**: Name, position, hourly rate, contact info
- **Edit Staff**: Update employee information
- **Deactivate Staff**: Mark inactive (preserves history)
- **Position Management**: Server, Chef, Bartender, Manager, etc.
- **Hire Date Tracking**: Employment history

#### Tab 3: Weekly Schedule
- **Grid View**: Visual weekly schedule
- **Staff Assignment**: See who's working when
- **Shift Coverage**: Identify gaps in scheduling
- **Conflict Detection**: Avoid double-booking staff

**Actions Available**:
- Double-click shift to edit
- Right-click for quick actions (Clock In, Clock Out, Cancel)
- Filter by date range, staff member, or status
- Export shift data to CSV

### Database Tables Created

1. **restaurant_staff**
   - Employee master data
   - Position & hourly rate
   - Contact information
   - Active/inactive status

2. **restaurant_shifts**
   - Shift scheduling
   - Clock in/out times
   - Hours & pay calculations
   - Status tracking

3. **restaurant_shift_swaps**
   - Shift swap requests
   - Approval workflow
   - Coverage tracking

### Benefits

✅ Accurate payroll calculations for Financial Reports
✅ Labor cost tracking and analysis
✅ Schedule optimization
✅ Time theft prevention (clock in/out)
✅ Historical shift data for staffing decisions

---

## 🗑️ Waste Tracking & Analysis

### Access
**Inventory Tab** → **"Waste Tracking"** button

### Features

**Main Window** - Three-tab interface:

#### Tab 1: Waste Entries
- **Record Waste**: Item name, quantity, unit, cost value
- **Waste Type**: Classification by category
- **Reason Tracking**: Why the waste occurred
- **Staff Accountability**: Record responsible staff member
- **Date Tracking**: When waste occurred
- **Notes**: Additional context

**Waste Information Tracked**:
- Waste date
- Item name & description
- Quantity & unit of measure
- Cost value (monetary impact)
- Waste type (from categories)
- Reason for waste
- Responsible staff (optional)
- Notes

#### Tab 2: Analytics
- **Date Range Reports**: Analyze waste over time periods
- **Cost Analysis**: Total waste costs and trends
- **Category Breakdown**: Which categories have most waste
- **Top Wasted Items**: Identify problem areas
- **Trend Analysis**: Is waste increasing or decreasing?
- **Recommendations**: Smart suggestions based on patterns

**Analytics Metrics**:
- Total waste cost
- Total waste quantity
- Average daily/weekly waste
- Waste by category percentages
- Trend indicators (↑ increasing, ↓ decreasing, → stable)
- Target vs actual comparisons

#### Tab 3: Categories
- **Manage Categories**: Add, edit, delete waste categories
- **Target Percentages**: Set goals for each category
- **Category Descriptions**: Define what belongs in each

**Default Categories**:
- **Spoilage**: Items that went bad before use
- **Preparation Waste**: Trimming, peeling, inedible parts
- **Over-production**: Made too much food
- **Plate Waste**: Customer leftovers
- **Storage Issues**: Improper storage damage
- **Other**: Miscellaneous waste

**Actions Available**:
- Double-click entry to edit
- Right-click for quick delete
- Export waste data to CSV
- Generate analytics reports
- View category-specific trends

### Database Tables Created

1. **restaurant_waste**
   - Individual waste entries
   - Cost and quantity tracking
   - Category classification
   - Staff responsibility

2. **restaurant_waste_categories**
   - Category definitions
   - Target percentages
   - Descriptions

### Benefits

✅ Accurate waste costs for Profit Analysis Reports
✅ Identify waste reduction opportunities
✅ Track staff accountability
✅ Monitor improvement over time
✅ Support sustainability initiatives
✅ Reduce food costs through awareness

---

## 🔗 Integration with Reports

These three new modules enable accurate data for all Financial Reports:

### Previously Unavailable Reports - Now Working

1. **Expense Report** ✅
   - Uses: `restaurant_purchase_orders` data
   - Shows: All supplier purchases, expense breakdown

2. **Payroll Report** ✅
   - Uses: `restaurant_shifts` data
   - Shows: Staff hours worked, shift counts, gross pay

3. **Profit Analysis Report** ✅ Enhanced
   - Uses: Purchase order costs for accurate COGS
   - Uses: Waste data for waste cost deduction
   - Shows: True profit margins instead of estimates

4. **Financial Forecast** ✅ Enhanced
   - Uses: Actual expense data instead of estimates
   - Shows: More accurate projections

5. **VAT Report** ✅ Enhanced
   - Uses: Purchase data for input VAT calculations
   - Shows: Accurate VAT position

### Data Flow

```
Purchase Orders → Expense Tracking → Financial Reports
Shifts Data → Payroll Costs → Profit Analysis
Waste Data → Cost Deductions → Operating Profit
```

---

## 📊 Database Schema

### Tables Created Automatically

When you first launch each GUI, the required database tables are created automatically with proper schema:

**Purchase Orders Module** (3 tables):
- `restaurant_suppliers` - Supplier master data
- `restaurant_purchase_orders` - PO headers
- `restaurant_purchase_order_items` - PO line items

**Shifts Module** (3 tables):
- `restaurant_staff` - Employee records
- `restaurant_shifts` - Shift records
- `restaurant_shift_swaps` - Swap requests

**Waste Tracking Module** (2 tables):
- `restaurant_waste` - Waste entries
- `restaurant_waste_categories` - Category definitions

**Total**: 8 new tables added to `student_records.db`

All tables use proper foreign keys, constraints, and indexes for data integrity and performance.

---

## 🎓 Usage Best Practices

### Purchase Orders

**Daily**:
- Record incoming deliveries (Receive PO)
- Check for pending approvals

**Weekly**:
- Review received but unpaid POs
- Create POs for upcoming week

**Monthly**:
- Analyze supplier performance
- Review total purchasing costs
- Export for accounting

### Shifts & Payroll

**Daily**:
- Staff clock in when starting shift
- Staff clock out when ending shift
- Manager reviews no-shows

**Weekly**:
- Create next week's schedule
- Review schedule conflicts
- Approve shift swap requests

**Monthly**:
- Export shift data for payroll
- Analyze labor cost percentages
- Review staff hours and overtime

### Waste Tracking

**Daily**:
- Record all waste as it occurs
- Categorize waste by type
- Note responsible staff when relevant

**Weekly**:
- Review waste analytics
- Identify top wasted items
- Discuss reduction strategies

**Monthly**:
- Generate comprehensive waste report
- Compare to previous months
- Set reduction targets
- Export for cost analysis

---

## ⚙️ Technical Details

### Implementation

**Architecture**:
- Object-oriented GUI classes
- Notebook (tab) interface for organization
- Treeview widgets for data display
- Dialog-based CRUD operations
- Automatic table initialization

**Database**:
- SQLite with proper foreign keys
- Automatic schema creation
- Transaction safety
- Data validation

**Error Handling**:
- User-friendly error messages
- Graceful failure handling
- Import error protection
- Database connection checks

**Code Quality**:
- 3,000+ lines of new code
- Comprehensive docstrings
- Input validation
- Consistent styling

---

## 🚀 Getting Started

### First Time Setup

1. **Launch Restaurant Management GUI**
2. **Purchase Orders**: Click "Purchase Orders" in Inventory tab
   - Tables auto-created on first launch
   - Add your first supplier
   - Create your first purchase order

3. **Shifts Management**: Click "Manage Schedules" in Staff tab
   - Tables auto-created on first launch
   - Add your staff members
   - Create your first shift schedule

4. **Waste Tracking**: Click "Waste Tracking" in Inventory tab
   - Tables auto-created on first launch
   - Default categories already created
   - Record your first waste entry

### Sample Workflow

**Morning Opening**:
1. Staff clocks in via Shifts GUI
2. Manager reviews deliveries in Purchase Orders
3. Record any overnight waste in Waste Tracking

**During Service**:
1. Record prep waste as it occurs
2. Note plate waste from returns

**Evening Closing**:
1. Staff clocks out
2. Manager records closing waste
3. Receive any late deliveries (PO GUI)

**End of Week**:
1. Review waste analytics
2. Export shift data for payroll
3. Create purchase orders for next week

**End of Month**:
1. Generate all Financial Reports (now with real data!)
2. Analyze profit margins
3. Review supplier and staff performance

---

## 📞 Support

### For Questions About:

- **Purchase Orders**: Contact procurement team
- **Shifts/Payroll**: Contact HR or shift managers
- **Waste Tracking**: Contact kitchen managers
- **Database Issues**: Contact IT support
- **Financial Reports**: See `REPORTS_USER_GUIDE.md`

### Documentation References:

- Reports Guide: `REPORTS_USER_GUIDE.md`
- Email Integration: `EMAIL_RECEIPTS_QUICK_GUIDE.md`
- Changelog: `/CHANGELOG.md` (version 5.0.78)

---

**Last Updated**: 2026-01-25
**Version**: 5.0.78
**Status**: ✅ Fully Operational

All three GUI modules are fully integrated and ready for production use!

# Accessibility Services Portal

## Overview

The Accessibility Services Portal provides comprehensive support for students with disabilities, enabling them to request accommodations, manage documentation, communicate with disability services staff, and track their active accommodations. The system ensures FERPA compliance and privacy throughout all operations.

## Features

### Core Functionality

1. **Accommodation Request Workflow**
   - Streamlined request submission process
   - Support for multiple accommodation types
   - Document upload for medical documentation
   - Real-time status tracking

2. **Status Tracking**
   - Submitted
   - Under Review
   - Approved
   - Denied
   - Active

3. **Accommodation Types**
   - Extended Time
   - Note-Taking
   - Sign Language Interpreter
   - Accessible Seating
   - Adaptive Technology
   - Other (custom accommodations)

4. **Direct Messaging**
   - Two-way communication with disability services staff
   - Message threading by request
   - Read/unread status tracking
   - Privacy-protected conversations

5. **Document Management**
   - Secure upload of medical documentation
   - Support for multiple file formats (PDF, images)
   - Document type categorization
   - Timestamp tracking

6. **Faculty Notification System**
   - Automated notifications to instructors
   - Privacy-aware accommodation summaries
   - Acknowledgment tracking
   - Course-specific notifications

7. **Renewal Management**
   - Expiration tracking with alerts
   - Renewal request workflow
   - Automatic expiration date extension
   - Renewal history

## Architecture

### Database Schema

The module uses the following database tables:

#### accommodation_requests
Stores all accommodation requests from students.
- `request_id` (PRIMARY KEY)
- `student_id` (FOREIGN KEY)
- `student_name`
- `student_email`
- `accommodation_type`
- `description`
- `status`
- `submitted_date`
- `reviewed_date`
- `reviewer_id`
- `reviewer_notes`

#### accommodations
Stores active and approved accommodations.
- `accommodation_id` (PRIMARY KEY)
- `request_id` (FOREIGN KEY)
- `student_id` (FOREIGN KEY)
- `accommodation_type`
- `description`
- `start_date`
- `expiration_date`
- `approved_by`
- `is_active`

#### accommodation_documentation
Stores uploaded documentation files.
- `doc_id` (PRIMARY KEY)
- `request_id` (FOREIGN KEY)
- `student_id`
- `filename`
- `file_path`
- `upload_date`
- `document_type`

#### accessibility_messages
Stores messages between students and staff.
- `message_id` (PRIMARY KEY)
- `request_id` (FOREIGN KEY)
- `sender_id`
- `sender_type` (student/staff)
- `message`
- `sent_date`
- `is_read`

#### faculty_notifications
Tracks notifications sent to faculty.
- `notification_id` (PRIMARY KEY)
- `accommodation_id` (FOREIGN KEY)
- `student_id`
- `faculty_id`
- `course_id`
- `accommodation_summary`
- `sent_date`
- `acknowledged`

#### accommodation_renewals
Tracks renewal requests.
- `renewal_id` (PRIMARY KEY)
- `accommodation_id` (FOREIGN KEY)
- `student_id`
- `renewal_request_date`
- `status`
- `processed_date`
- `processed_by`
- `notes`

## File Structure

```
accessibility/
├── __init__.py                          # Package initialization
├── README.md                            # This file
├── services/
│   ├── __init__.py
│   └── accessibility_service.py         # Service layer (business logic)
├── cli/
│   ├── __init__.py
│   └── accessibility_cli.py             # Command-line interface
└── gui/
    ├── __init__.py
    └── accessibility_gui.py             # Graphical user interface
```

## Usage

### Service Layer

```python
from university_system.modules.domain.accessibility.services import AccessibilityService

# Initialize service
service = AccessibilityService()

# Submit accommodation request
request_id = service.submit_accommodation_request(
    student_id="12345",
    student_name="John Doe",
    student_email="john.doe@university.edu",
    accommodation_type="Extended Time",
    description="Need extra time on exams due to documented learning disability"
)

# Upload documentation
with open("medical_doc.pdf", "rb") as f:
    doc_id = service.upload_documentation(
        request_id=request_id,
        student_id="12345",
        filename="medical_doc.pdf",
        file_content=f.read()
    )

# Check request status
requests = service.get_student_requests("12345")

# Get active accommodations
accommodations = service.get_active_accommodations("12345")

# Send message to staff
message_id = service.send_message(
    request_id=request_id,
    sender_id="12345",
    sender_type="student",
    message="Can you provide an update on my request?"
)

# Request renewal
renewal_id = service.request_renewal(
    accommodation_id=1,
    student_id="12345",
    notes="Would like to renew for next semester"
)
```

### CLI Interface

```python
from university_system.modules.domain.accessibility.cli import AccessibilityCLI

# Run CLI
cli = AccessibilityCLI()
cli.run()
```

Or run directly:
```bash
python -m university_system.modules.domain.accessibility.cli.accessibility_cli
```

**CLI Features:**
1. Submit Accommodation Request
2. Upload Documentation
3. View My Requests and Status
4. Message Disability Services
5. View Approved Accommodations
6. Request Renewal
7. View Faculty Notifications Sent
8. View Expiring Accommodations

### GUI Interface

```python
from university_system.modules.domain.accessibility.gui import AccessibilityGUI

# Run GUI (standalone)
app = AccessibilityGUI()
app.run()

# Or as part of larger application
app = AccessibilityGUI(parent=main_window)
```

Or run directly:
```bash
python -m university_system.modules.domain.accessibility.gui.accessibility_gui
```

**GUI Features:**
- **Dashboard Tab**: Status overview and recent requests
- **Submit Request Tab**: Wizard for submitting new requests
- **Messages Tab**: Communication with disability services staff
- **My Accommodations Tab**: View active accommodations with expiration dates
- **Renewals Tab**: Submit renewal requests and view expiring accommodations

## Privacy & Compliance

### FERPA Compliance

The Accessibility Services Portal is designed with FERPA compliance in mind:

1. **Access Control**: Only the student and authorized staff can view accommodation details
2. **Privacy-Aware Notifications**: Faculty notifications contain only essential information
3. **Secure Document Storage**: Medical documentation stored in protected directories
4. **Activity Logging**: All actions are logged for audit purposes
5. **Data Minimization**: Only necessary information is shared with faculty

### Security Features

1. **Authentication Required**: All operations require valid user authentication
2. **Authorization Checks**: Permission-based access to sensitive operations
3. **Secure File Storage**: Documents stored outside web-accessible directories
4. **Encrypted Communications**: Messages stored securely in database
5. **Audit Trail**: Complete logging of all data access and modifications

## Integration Points

### Authentication
Uses the centralized authentication system:
```python
from university_system.infrastructure.shared_context import get_auth

auth = get_auth()
if auth.is_logged_in():
    current_user = auth.get_current_user()
```

### Database
Uses the centralized database connection pool:
```python
from university_system.infrastructure.database.db import get_connection, transaction

with transaction() as conn:
    # Database operations
    pass
```

### Activity Logging
All operations are logged:
```python
from university_system.modules.shared.utils.activity_logger import log_activity

log_activity('create', 'accommodation_request', request_id=request_id)
```

### File Storage
Uses centralized path management:
```python
from university_system.modules.shared.constants import paths

upload_dir = paths.UPLOAD_DIR
```

## Staff Functions

The service layer includes staff-only functions for managing requests:

```python
# Update request status (staff only)
service.update_request_status(
    request_id=1,
    new_status="Under Review",
    reviewer_id="staff123",
    reviewer_notes="Reviewing documentation"
)

# Approve and activate accommodation (staff only)
accommodation_id = service.approve_and_activate_accommodation(
    request_id=1,
    approved_by="staff123",
    duration_months=12
)

# Notify faculty (staff only)
notification_id = service.notify_faculty(
    accommodation_id=1,
    student_id="12345",
    faculty_id="prof456",
    course_id="CS101",
    accommodation_summary="Student has approved accommodations for extended time on exams"
)

# Process renewal (staff only)
service.process_renewal(
    renewal_id=1,
    status="Approved",
    processed_by="staff123",
    extend_months=12
)

# Get all pending requests (staff only)
pending = service.get_all_pending_requests()

# Get statistics (staff only)
stats = service.get_statistics()
```

## Testing

The module can be tested using the following approaches:

### Unit Testing
```python
import unittest
from university_system.modules.domain.accessibility.services import AccessibilityService

class TestAccessibilityService(unittest.TestCase):
    def setUp(self):
        self.service = AccessibilityService()

    def test_submit_request(self):
        request_id = self.service.submit_accommodation_request(
            student_id="test123",
            student_name="Test Student",
            student_email="test@test.edu",
            accommodation_type="Extended Time",
            description="Test description"
        )
        self.assertIsNotNone(request_id)
```

### Manual Testing
1. Run the GUI: `python -m university_system.modules.domain.accessibility.gui.accessibility_gui`
2. Run the CLI: `python -m university_system.modules.domain.accessibility.cli.accessibility_cli`
3. Test each feature systematically

## Error Handling

The module includes comprehensive error handling:

```python
try:
    request_id = service.submit_accommodation_request(...)
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Error submitting request: {e}")
```

## Future Enhancements

Potential future enhancements include:

1. **Email Notifications**: Automatic email alerts for status changes
2. **Mobile App**: Mobile interface for on-the-go access
3. **Analytics Dashboard**: Statistics and trends for staff
4. **Integration with LMS**: Direct integration with learning management systems
5. **Automated Renewals**: Automatic renewal for continuous accommodations
6. **Document OCR**: Automatic extraction of information from uploaded documents
7. **Multi-language Support**: Support for multiple languages
8. **Accessibility Features**: Enhanced accessibility for users with disabilities

## Support

For support or questions about the Accessibility Services Portal:

1. Contact disability services staff
2. Submit a support ticket
3. Review the system documentation
4. Contact IT support

## License

This module is part of the University Management System and is subject to the same license terms.

## Version History

- **1.0.0** (2026-01-11): Initial implementation
  - Core accommodation request workflow
  - Document upload functionality
  - Messaging system
  - Faculty notification system
  - Renewal tracking
  - CLI and GUI interfaces

# Portfolio System - Quick Start Guide

## Student Quick Start

### 1. Create Your Portfolio (First Time)
```python
from university_system.modules.domain.portfolio import PortfolioService

service = PortfolioService()
service.create_portfolio(
    student_id="your_id",
    title="Your Name - Professional Portfolio",
    headline="Your Major | Your Interests",
    bio="A brief professional summary about yourself"
)
```

### 2. Add Your First Project
```python
service.add_portfolio_item(
    portfolio_id=your_portfolio_id,
    category='project',
    title="Project Name",
    description="What you built and why",
    technologies="Python, React, etc.",
    url="github.com/yourproject",
    is_featured=True  # Highlight your best work
)
```

### 3. Add Your Skills
```python
# Add technical skills
service.add_skill(
    student_id="your_id",
    skill_name="Python",
    skill_category='technical',
    proficiency_level='advanced',
    years_experience=2.0,
    is_featured=True
)

# Add soft skills
service.add_skill(
    student_id="your_id",
    skill_name="Leadership",
    skill_category='soft_skill',
    proficiency_level='advanced'
)
```

### 4. Make Your Portfolio Public
```python
service.update_public_profile(
    student_id="your_id",
    visibility='public',
    show_projects=True,
    show_skills=True,
    show_endorsements=True
)

# Get your shareable URL
url = service.get_portfolio_url("your_id")
print(f"Share this URL: {url}")
```

### 5. Generate Your Resume
```python
service.generate_resume(
    student_id="your_id",
    resume_name="Software Engineering Resume",
    template_type='technical'
)
```

## CLI Quick Commands

```bash
# Launch portfolio system
python -m university_system.modules.domain.portfolio.cli.portfolio_cli

# Navigation:
# 1 - Manage portfolio (create/edit)
# 2 - Add items (projects, research, etc.)
# 3 - View complete portfolio
# 4 - Manage skills
# 5 - View badges
# 8 - Generate resume
# 10 - Get shareable URL
```

## GUI Quick Launch

```python
from university_system.modules.domain.portfolio import PortfolioGUI

app = PortfolioGUI()
app.run()
```

## Common Tasks

### Add Research Experience
```python
service.add_portfolio_item(
    portfolio_id=portfolio_id,
    category='research',
    title="Research Project Title",
    description="Your research contribution",
    organization="University Research Lab",
    role="Research Assistant",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

### Add Leadership Role
```python
service.add_portfolio_item(
    portfolio_id=portfolio_id,
    category='leadership',
    title="President, Student Organization",
    organization="CS Club",
    role="President",
    start_date="2024-01-01",
    is_current=True,  # Still in this role
    achievements="Led 50+ members, organized 10 events"
)
```

### Request Skill Endorsement
```python
service.request_endorsement(
    skill_id=skill_id,
    endorser_id="professor@university.edu",
    message="Could you endorse my Python skills from CS301?"
)
```

### Check Portfolio Completeness
```python
stats = service.get_portfolio_stats("your_id")
print(f"Completeness: {stats['completeness_score']}%")
print(f"Items: {stats['total_items']}")
print(f"Skills: {stats['total_skills']}")
print(f"Endorsements: {stats['total_endorsements']}")
```

## Tips for Success

### Boost Your Completeness Score
- ✅ Add bio (15%)
- ✅ Add 1+ portfolio item (30%)
- ✅ Add 5+ skills (20%)
- ✅ Get 1+ verified badge (20%)
- ✅ Get 1+ endorsement (15%)

### Make Your Portfolio Stand Out
1. **Feature Your Best Work**: Mark top 3-5 items as featured
2. **Use Action Verbs**: "Built", "Designed", "Led", "Achieved"
3. **Quantify Results**: "Improved performance by 40%"
4. **Add Technologies**: List specific tools and languages
5. **Include Links**: GitHub, live demos, publications
6. **Get Endorsements**: Ask faculty and peers
7. **Keep It Current**: Update every semester

### Categories Explained
- **Project**: Personal or team software/engineering projects
- **Research**: Academic research, publications, presentations
- **Leadership**: Student organizations, clubs, team lead roles
- **Work Experience**: Jobs, internships, co-ops
- **Award**: Competitions, scholarships, honors
- **Certification**: Professional certifications, licenses
- **Publication**: Papers, articles, blog posts
- **Presentation**: Conference talks, guest lectures

### Privacy Settings Guide
- **Public**: Anyone can find and view your portfolio
- **Unlisted**: Only people with the link can view
- **Private**: Only you can view (for drafts)

Choose what to show:
- Contact info: Use for job applications
- GPA: Show if 3.5+
- Projects: Always show your best work
- Skills: Always show
- Endorsements: Show to build credibility

## Troubleshooting

### "Portfolio already exists"
- You can only have one portfolio per student
- Use update methods instead of create

### "Foreign key constraint failed"
- Make sure you're logged in as a valid student
- Check that referenced items exist

### "Permission denied"
- Ensure you're logged in
- Only students can create portfolios
- Faculty can award badges and endorse

### Portfolio not showing up
- Check visibility settings
- Ensure portfolio is public or unlisted
- Verify URL is correct

## Next Steps

1. **Complete Your Profile**: Aim for 80%+ completeness
2. **Add Content**: At least 5 portfolio items
3. **Build Skills**: Add 10+ relevant skills
4. **Get Endorsed**: Request 3+ endorsements
5. **Generate Resume**: Create 2-3 targeted resumes
6. **Share It**: Add URL to email signature, LinkedIn
7. **Keep Updated**: Monthly review and updates

## Resources

- Full Documentation: See README.md
- API Reference: Check docstrings in portfolio_service.py
- Examples: Run test_portfolio_system.py
- Support: Contact system administrator

---

**Your portfolio is your professional story - make it compelling!**

# Portfolio System - Feature List

## Core Features

### 1. Digital Portfolio Management
- Create professional digital portfolios
- Customizable title, headline, and bio
- Profile image support
- Social media integration (LinkedIn, GitHub, personal website)
- Automatic public URL generation
- Last updated timestamp tracking
- Portfolio visibility controls

### 2. Portfolio Items (8 Categories)

#### Projects
- Title and description
- Technologies used
- Project URL (GitHub, live demo, etc.)
- Start and end dates
- Featured project highlighting
- Attachments support

#### Research
- Research title and description
- Organization/lab name
- Role (Research Assistant, PI, etc.)
- Timeline tracking
- Publication information
- Research URLs

#### Leadership
- Position title
- Organization name
- Role and responsibilities
- Achievement highlights
- Current position tracking
- Duration calculation

#### Work Experience
- Job title and company
- Role description
- Employment dates
- Skills used
- Achievements and impact
- Reference links

#### Awards
- Award name and description
- Issuing organization
- Date received
- Award criteria
- Recognition level

#### Certifications
- Certification name
- Issuing authority
- Issue and expiry dates
- Verification information
- Certification ID

#### Publications
- Publication title
- Journal/conference name
- Publication date
- Co-authors
- DOI/URL
- Citation information

#### Presentations
- Presentation title
- Event/conference name
- Date presented
- Audience size
- Presentation materials

### 3. Verified Badge System (12 Types)

1. **Dean's List**: Academic excellence recognition
2. **Club Officer**: Student organization leadership
3. **Volunteer Hours**: Community service milestone
4. **Certification**: Professional certifications
5. **Competition Winner**: Hackathons, contests, competitions
6. **Scholarship**: Merit-based awards
7. **Research Publication**: Published research
8. **Leadership**: Leadership development programs
9. **Academic Excellence**: Course/program honors
10. **Community Service**: Service learning recognition
11. **Skill Mastery**: Advanced skill achievement
12. **Innovation**: Creative/innovative projects

**Badge Features:**
- Unique verification codes
- Cryptographic verification
- Issuer authentication
- Issue and expiry dates
- Badge metadata (JSON)
- Custom icon URLs
- Status tracking (pending, verified, expired, revoked)

### 4. Skills Management

#### Skill Categories (5)
1. **Technical**: Programming, tools, platforms
2. **Soft Skills**: Communication, leadership, teamwork
3. **Languages**: Human languages, programming languages
4. **Tools**: Software, frameworks, IDEs
5. **Domain**: Industry-specific knowledge

#### Proficiency Levels (4)
1. **Beginner**: Learning fundamentals
2. **Intermediate**: Practical application
3. **Advanced**: Deep expertise
4. **Expert**: Mastery level

**Skill Features:**
- Years of experience tracking
- Featured skill highlighting
- Automatic endorsement counting
- Category filtering
- Proficiency progression tracking

### 5. Endorsement System

#### Endorser Roles (4)
1. **Faculty**: Professors, instructors, advisors
2. **Peer**: Classmates, team members
3. **Employer**: Supervisors, managers
4. **Mentor**: Industry mentors, coaches

**Endorsement Features:**
- Written comments/feedback
- Relationship context
- Endorsement date tracking
- Role-based credibility
- Multiple endorsements per skill
- Endorsement request workflow
- Faculty vs. peer counts
- Endorsement notifications (planned)

### 6. Achievement Tracking
- Achievement types and categories
- Points system (gamification)
- Date achieved tracking
- Verification status
- Verified by attribution
- Achievement descriptions
- Category classification
- Points leaderboard (planned)

### 7. Public Profile System

#### Visibility Options (3)
1. **Public**: Searchable, fully accessible
2. **Unlisted**: Link-only access
3. **Private**: Owner-only access

#### Privacy Controls
- Show/hide contact information
- Show/hide GPA
- Show/hide courses
- Show/hide projects
- Show/hide skills
- Show/hide endorsements
- Custom sections (JSON)
- Theme selection

**Profile Features:**
- View count tracking
- Last viewed timestamp
- Unique public URLs
- QR code generation (planned)
- SEO optimization (planned)
- Social media cards (planned)

### 8. Resume Builder

#### Template Types (5)
1. **Traditional**: Classic chronological format
2. **Modern**: Contemporary design
3. **Creative**: Design-focused layout
4. **Technical**: Developer-optimized
5. **Academic**: Research-focused

**Resume Features:**
- Auto-generation from portfolio data
- Customizable sections:
  - Education
  - Experience
  - Projects
  - Skills
  - Achievements
  - Certifications
- Multiple resume versions
- Template switching
- Last generated tracking
- Export formats (PDF, DOCX, HTML - planned)
- LinkedIn import (planned)
- ATS optimization (planned)

### 9. Analytics & Statistics

#### Completeness Score
Calculated from:
- Portfolio bio (15%)
- Portfolio items (30%)
- Skills count (20%)
- Verified badges (20%)
- Endorsements (15%)

#### Statistics Tracked
- Total portfolio items
- Items by category breakdown
- Total skills added
- Total endorsements received
- Faculty vs. peer endorsements
- Verified badge count
- Achievement points total
- Profile views count
- Profile visibility status
- Last updated date

#### Analytics Dashboard
- Portfolio completeness meter
- Category distribution charts
- Skill proficiency matrix
- Endorsement trends
- View analytics
- Engagement metrics

### 10. Search & Discovery (Planned)
- Portfolio search by skills
- Find students by expertise
- Industry-specific filtering
- Project showcase gallery
- Research collaboration matching
- Skill-based recommendations

## User Interfaces

### CLI Interface Features
- Interactive menu system
- Guided input workflows
- Data validation
- Professional formatting
- Progress indicators
- Error handling
- Help documentation
- Quick commands
- Batch operations

### GUI Interface Features
- Tabbed navigation (7 tabs)
- TreeView data displays
- Modal dialogs for editing
- Real-time statistics header
- Category filtering
- Search functionality
- Drag-and-drop (planned)
- Keyboard shortcuts (planned)
- Context menus (planned)
- Tooltips (planned)
- Professional theming
- Responsive layout

## Integration Features

### Database Integration
- 8 optimized tables
- 6 performance indexes
- Foreign key constraints
- Transaction safety
- Connection pooling
- WAL mode support

### Authentication Integration
- Session management
- User context awareness
- Role-based access
- Permission checking
- Activity attribution

### LinkedIn Integration (Planned)
- Profile export
- Skill synchronization
- Work experience import
- Endorsement sharing
- Connection suggestions

### Career Services Integration
- Resume export formats
- Portfolio PDF generation
- Skills gap analysis
- Job matching
- Internship applications
- Employer sharing

### External Verification
- Badge verification API
- QR code verification
- Blockchain credentials (planned)
- Third-party validation
- Issuer authentication

## Security & Privacy

### Security Features
- Cryptographic verification codes
- Secure URL generation
- SQL injection prevention
- Transaction rollback
- Input validation
- Activity logging
- Audit trails

### Privacy Features
- Granular visibility controls
- FERPA compliance
- GDPR support (planned)
- Data export rights
- Deletion support
- Consent management

## Performance Features

### Optimization
- Indexed queries
- Efficient JOINs
- Lazy loading
- Query result caching
- Connection pooling
- Batch operations

### Scalability
- Concurrent access support
- Large portfolio handling
- Pagination support
- CDN integration (planned)
- Distributed caching (planned)

## Accessibility Features (Planned)
- Screen reader support
- Keyboard navigation
- High contrast themes
- Font size adjustment
- Alt text for images
- ARIA labels
- WCAG 2.1 compliance

## Mobile Features (Planned)
- Responsive design
- Mobile app
- Touch optimization
- Offline mode
- Push notifications
- QR code scanning

## Collaboration Features (Planned)
- Team project portfolios
- Shared research profiles
- Collaborative resumes
- Peer review system
- Mentor feedback
- Group endorsements

## Export Features

### Current
- Resume generation (multiple formats planned)
- Portfolio URL sharing
- Badge verification codes

### Planned
- PDF portfolio export
- LinkedIn profile sync
- JSON data export
- CSV skill export
- Portfolio archive
- Batch resume generation

## Notification Features (Planned)
- Endorsement requests
- Badge awards
- Profile views
- Resume downloads
- Skill endorsements
- Achievement milestones

## Reporting Features (Planned)
- Portfolio analytics
- Skill trend analysis
- Endorsement reports
- Career progress tracking
- Engagement metrics
- Success analytics

## Administrative Features (Planned)
- Badge issuance workflows
- Template management
- System analytics
- User activity reports
- Compliance reporting
- Quality assurance

---

**Over 50+ Features Implemented and Planned**

This comprehensive feature set makes the Portfolio System suitable for:
- Student professional development
- Career services operations
- Faculty endorsement workflows
- Alumni networking
- Employer recruitment
- Institutional branding
- Compliance requirements
- Research collaboration
- Skill development tracking

# Social Matching Module - Quick Start Guide

## 5-Minute Quick Start

### 1. Import the Service

```python
from university_system.modules.domain.social_matching import SocialMatchingService

service = SocialMatchingService()
```

### 2. Add Some Interests

```python
# Add interests to a user profile
service.add_user_interest("student123", "Sports", "Basketball", 8, True)
service.add_user_interest("student123", "Music", "Rock", 7, True)
service.add_user_interest("student123", "Technology", "Programming", 9, True)
```

### 3. Find Matches

```python
# Find students with similar interests
matches = service.find_interest_matches("student123", min_score=30.0, max_results=20)

for match in matches:
    print(f"Student: {match['user_id']}")
    print(f"Compatibility: {match['compatibility_score']:.1f}%")
    print(f"Shared Interests: {', '.join(match['shared_interests'][:3])}")
    print()
```

### 4. Send a Buddy Request

```python
# Send a buddy request to a matched student
request_id = service.send_buddy_request(
    sender_id="student123",
    receiver_id="student456",
    request_type="general",
    message="Hey! I see we both love basketball. Want to play sometime?"
)
```

### 5. Create a Team

```python
# Create an intramural sports team
team_id = service.create_team(
    creator_id="student123",
    team_name="Court Kings",
    sport_type="Basketball",
    team_size=5,
    skill_level="Intermediate",
    description="Looking for fun but competitive players"
)
```

## Running the Interfaces

### CLI Interface

```bash
python -m university_system.modules.domain.social_matching.cli.social_matching_cli
```

### GUI Interface

```python
import tkinter as tk
from university_system.modules.domain.social_matching.gui import SocialMatchingGUI

root = tk.Tk()
app = SocialMatchingGUI(root)
root.mainloop()
```

## Common Use Cases

### Use Case 1: Find Study Abroad Buddies

```python
# Find students going to the same destination
buddies = service.find_study_abroad_buddies(
    user_id="student123",
    destination="Spain",
    semester="Fall 2026"
)

for buddy in buddies:
    print(f"{buddy['user_id']} - Compatibility: {buddy['compatibility_score']:.1f}%")
```

### Use Case 2: Get Club Recommendations

```python
# Generate personalized club recommendations
recommendations = service.generate_club_recommendations("student123")

for rec in recommendations[:5]:
    print(f"{rec['club_name']} ({rec['club_category']})")
    print(f"Match Score: {rec['match_score']}")
    print(f"Reason: {rec['reason']}")
    print()
```

### Use Case 3: Create and Join Activities

```python
# Create a social activity
activity_id = service.create_social_activity(
    creator_id="student123",
    activity_name="Weekend Hike",
    activity_type="Outdoor",
    description="Easy 5-mile trail",
    location="Mountain Park",
    activity_date="2026-01-25",
    activity_time="09:00",
    max_participants=15,
    interests_matched=["Hiking", "Outdoor"]
)

# Join an activity
service.join_activity(activity_id, "student456", rsvp_status="going")
```

### Use Case 4: Set Personality Profile

```python
# Create a personality profile for better matching
service.set_personality_profile(
    user_id="student123",
    personality_type="Extrovert",
    extroversion_score=8,
    openness_score=7,
    social_preference="Love meeting new people and trying new things",
    group_size_pref="Medium Group (6-10)",
    activity_level="High"
)
```

### Use Case 5: Manage Privacy

```python
# Configure privacy settings
service.set_privacy_settings(
    user_id="student123",
    allow_matching=True,        # Allow others to match with you
    show_profile=True,          # Show your profile to matches
    allow_messages=True,        # Accept buddy requests
    show_interests=True,        # Display your interests publicly
    show_in_search=True,        # Appear in search results
    match_same_major=False,     # Match with any major
    match_same_year=False       # Match with any year
)
```

## Key Concepts

### Interest Categories
```python
from university_system.modules.domain.social_matching import INTEREST_CATEGORIES

# Available categories:
# Sports, Music, Arts, Gaming, Outdoor, Technology,
# Academic, Career, Travel, Other
```

### Compatibility Scoring

- **0-29%**: Low compatibility
- **30-49%**: Moderate compatibility
- **50-69%**: Good compatibility
- **70-89%**: High compatibility
- **90-100%**: Excellent compatibility

Score is based on:
- Number of shared interests
- Interest levels (1-10)
- Level similarity

### Privacy Levels

**Public Profile** (Default):
- Visible in searches
- Can receive buddy requests
- Interests shown to others
- Can be matched

**Private Profile**:
- Hidden from searches
- No buddy requests
- Interests hidden
- Matching disabled

**Custom**:
- Mix and match individual settings

## Sample Workflow

### Complete Student Journey

```python
from university_system.modules.domain.social_matching import SocialMatchingService

service = SocialMatchingService()

# 1. Setup profile
service.add_user_interest("alice", "Sports", "Basketball", 9, True)
service.add_user_interest("alice", "Music", "Rock", 8, True)
service.add_user_interest("alice", "Academic", "Computer Science", 10, True)

service.set_personality_profile(
    "alice", "Extrovert", 9, 8,
    "Love socializing", "Medium Group (6-10)", "High"
)

# 2. Find matches
matches = service.find_interest_matches("alice", min_score=50.0)
print(f"Found {len(matches)} highly compatible students!")

# 3. Send buddy request to top match
if matches:
    top_match = matches[0]
    request_id = service.send_buddy_request(
        "alice", top_match['user_id'], "general",
        message="Love your interests! Want to connect?"
    )

# 4. Get club recommendations
clubs = service.generate_club_recommendations("alice")
print(f"Recommended {len(clubs)} clubs based on your interests")

# 5. Create a team
team_id = service.create_team(
    "alice", "Hoops Heroes", "Basketball", 5,
    "Advanced", "Competitive team looking for skilled players"
)

# 6. View statistics
stats = service.get_user_statistics("alice")
print(f"Profile complete! {stats['total_interests']} interests, "
      f"{stats['total_matches']} matches")
```

## CLI Quick Reference

### Main Menu Options

1. **Manage My Interests**: Add, view, update, remove interests
2. **Find Interest Matches**: Search for compatible students
3. **View My Matches**: See saved matches
4. **Buddy Requests**: Send/receive/respond to requests
5. **Team Formation**: Create/join teams
6. **Club Recommendations**: Get personalized suggestions
7. **Social Activities**: Browse/create/join activities
8. **Personality Profile**: Set personality preferences
9. **Privacy Settings**: Configure visibility and permissions
10. **My Statistics**: View engagement metrics

### Navigation

- Enter option number to select
- Enter `0` to go back or exit
- Follow on-screen prompts

## GUI Quick Reference

### Tabs

1. **My Interests**: Manage your interest profile
2. **Find Matches**: Search and view compatible students
3. **Buddy Requests**: Inbox/outbox for requests
4. **Teams**: Create or join sports teams
5. **Club Recommendations**: View suggested clubs
6. **Social Activities**: Discover and RSVP to events
7. **Profile & Settings**: Personality and privacy

### Tips

- Click on items to view details
- Use "Refresh" buttons to reload data
- Double-click to select in some views
- Hover over buttons for tooltips

## Troubleshooting

### No matches found?
- Add more interests
- Make interests public
- Lower minimum score
- Check privacy settings

### Can't send buddy request?
- Check receiver's privacy settings
- Verify receiver ID is correct
- Ensure you're logged in

### Team creation failed?
- Check team name isn't taken
- Verify all required fields
- Ensure valid team size

### Activity suggestions empty?
- Add more interests
- Increase date range
- Check activity availability

## Best Practices

### For Students

1. **Add diverse interests**: More interests = better matches
2. **Set realistic levels**: Be honest about your interest levels
3. **Update regularly**: Keep your profile current
4. **Respect privacy**: Honor others' privacy preferences
5. **Be genuine**: Authentic profiles lead to better connections

### For Developers

1. **Check authentication**: Always verify user is logged in
2. **Handle errors**: Use try/except for service calls
3. **Validate input**: Check user input before service calls
4. **Respect privacy**: Always check privacy settings
5. **Log activities**: Use activity logger for audit trail

## Performance Tips

- **Batch operations**: Add multiple interests at once
- **Cache results**: Store match results temporarily
- **Use filters**: Limit search scope with filters
- **Optimize queries**: Use indexes, limit result sets
- **Background processing**: Run heavy computations async

## Security Reminders

- ✓ Never expose user IDs publicly
- ✓ Validate all user input
- ✓ Check permissions before displaying data
- ✓ Use parameterized queries (done automatically)
- ✓ Respect privacy settings
- ✓ Log all data modifications
- ✓ Handle errors gracefully

## Next Steps

1. Read the full [README.md](../../README.md) for detailed documentation
2. Review [SUMMARY.md](../../../../education_system/systems/university/interfaces/cli/shell/SUMMARY.md) for implementation details
3. Run the test script to verify installation
4. Integrate into your application

## Support

- **Documentation**: See README.md
- **Examples**: Check test_social_matching.py
- **Issues**: Review troubleshooting section
- **Code**: Inspect service layer for advanced usage

---

**Happy Matching! 🤝**

*Connect students, build community, foster friendships.*

