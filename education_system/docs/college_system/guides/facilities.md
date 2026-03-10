# Facilities Guide

This guide covers the assets, library, resource booking, transport, lettings, visitors, health and safety, and accessibility modules within the Sixth Form College Management System.

## Overview

The facilities modules manage the physical infrastructure, equipment, and support services that underpin daily college operations. Together they provide tracking and management for everything from laptop loans to visitor sign-in procedures.

| Module | Purpose |
|--------|---------|
| `assets` | Equipment and device loan tracking |
| `library` | Library catalogue, loans, renewals, and overdue management |
| `resource_booking` | Room and resource reservation system |
| `transport` | Student transport records and bus pass management |
| `lettings` | External hire of college facilities |
| `visitors` | Visitor sign-in, DBS checks, and safeguarding |
| `health_safety` | Health and safety compliance and incident tracking |
| `accessibility` | Accessibility provisions and reasonable adjustments |


## Asset Management

The assets module (`AssetsService`) tracks equipment loans to students, primarily laptops and other devices issued for learning support.

### Creating an Asset Loan

1. Navigate to the Assets section.
2. Click "New Loan".
3. Enter the asset details:
   - **Asset Name** -- Descriptive name (e.g., "Dell Latitude 5540").
   - **Asset Tag** -- Unique identifier label affixed to the device.
   - **Asset Type** -- Category of equipment (default: `laptop`).
   - **Loaned To** -- Select the student receiving the device.
   - **Condition Out** -- Record the condition at time of issue (default: `good`).
   - **Issued By** -- Staff member processing the loan.
   - **Notes** -- Any additional information.
4. Save the loan record.

### Returning an Asset

1. Locate the loan record by searching or browsing active loans.
2. Click "Return Asset".
3. Record the condition on return (`condition_in`).
4. Add any notes about damage or issues.
5. The system automatically sets the return date and updates the status to `returned`.

### Loan Status Tracking

| Status | Meaning |
|--------|---------|
| `on_loan` | Asset is currently issued to a student |
| `returned` | Asset has been returned and processed |
| `overdue` | Asset has not been returned by the expected date |
| `damaged` | Asset returned with damage noted |

### Filtering and Reporting

- Filter loans by status (e.g., view all currently on-loan items).
- Filter by asset type to manage specific equipment categories.
- View all loans for a specific student using `get_student_loans`.
- Use `count_active_loans` to get a quick count of all outstanding loans.


## Library System

The library module (`LibraryService`) provides a full library management system covering catalogue management, loans, renewals, and overdue tracking.

### Catalogue Management

**Adding a library item:**

1. Navigate to the Library section.
2. Click "Add Item".
3. Enter the item details:

| Field | Description | Required |
|-------|-------------|----------|
| `title` | Item title | Yes |
| `author` | Author name | No |
| `isbn` | ISBN number | No |
| `category` | Item category (default: `textbook`) | No |
| `location` | Shelf or section location | No |
| `total_copies` | Number of copies held (default: 1) | No |

The `available_copies` count is automatically set to match `total_copies` on creation.

**Searching the catalogue:**

- Search by title, author, or ISBN using the search function.
- Filter by category (e.g., textbook, reference, journal, fiction).
- Filter to show only items with available copies.

### Loan Management

**Checking out an item:**

1. Select the item from the catalogue.
2. Select the student borrower.
3. Optionally set a custom due date (default: 14 days from today).
4. Confirm the checkout.

The system automatically decrements the available copies count. If no copies are available, the checkout is refused.

**Returning an item:**

1. Locate the loan record.
2. Click "Return".
3. The system sets the returned date, updates the status to `returned`, and increments the available copies.

Items that have already been returned cannot be returned again.

**Renewing a loan:**

1. Find the active loan.
2. Click "Renew".
3. The due date is extended by 14 days (configurable).

Only loans with `on_loan` status can be renewed.

### Overdue Management

The `get_overdue` method returns all loans where the due date has passed and the item has not been returned. This list should be reviewed regularly to:

- Send overdue notifications to students.
- Escalate persistent overdue items to tutors.
- Apply any applicable fines or restrictions.


## Resource Booking

The resource booking module manages room and resource reservations across the college campus.

### Booking a Resource

1. Select the resource type (e.g., meeting room, computer lab, sports hall).
2. Choose the date and time slot.
3. Check availability -- the system prevents double-booking.
4. Confirm the booking with a purpose description.

### Managing Bookings

- View bookings by date, room, or staff member.
- Cancel bookings that are no longer needed.
- Set up recurring bookings for regular meetings or activities.
- Review room utilisation reports to optimise space usage.


## Student Transport

The transport module (`TransportService`) manages student transport arrangements, including bus passes, travel subsidies, and route information.

### Creating a Transport Record

1. Navigate to the Transport section.
2. Click "New Record".
3. Enter the transport details:

| Field | Description |
|-------|-------------|
| `student_id` | The student this record applies to |
| `transport_type` | Type of transport (default: `bus_pass`) |
| `route` | Bus route or travel route description |
| `pass_number` | Bus pass or travel card number |
| `provider` | Transport provider name |
| `eligible` | Whether the student is eligible for subsidised transport |
| `start_date` | Start date of the transport arrangement |
| `end_date` | End date of the transport arrangement |
| `cost` | Cost of the transport arrangement |
| `status` | Current status (default: `active`) |
| `notes` | Additional notes |

### Transport Queries

- List all transport records, filtered by type or status.
- View a specific student's active transport arrangement using `get_student_transport`.
- Update records when routes change, passes are renewed, or eligibility changes.
- Delete records that are no longer relevant.


## Campus Lettings

The lettings module manages the hire of college facilities to external organisations and community groups.

### Lettings Workflow

1. **Enquiry** -- Record the external organisation's request, including dates, times, and facilities required.
2. **Availability Check** -- Verify the requested spaces are available and not conflicting with college activities.
3. **Quotation** -- Generate a quote based on the facilities, duration, and any additional services required.
4. **Booking Confirmation** -- Confirm the booking and issue a hire agreement.
5. **Event Day** -- Manage access, key handover, and any on-site support.
6. **Post-Event** -- Record any issues, process invoicing, and update the calendar.


## Visitor Management

The visitors module (`VisitorService`) provides a comprehensive visitor sign-in and tracking system with safeguarding compliance features.

### Registering a Visitor

1. Navigate to the Visitors section.
2. Click "Sign In Visitor" or "New Visitor".
3. Enter the required details:
   - **First Name** and **Last Name** (required).
   - **Purpose** of visit (required).
   - **Organisation** -- The visitor's company or affiliation.
   - **Visiting Staff ID** -- The staff member being visited.
4. Complete safeguarding checks:
   - **DBS Checked** -- Whether the visitor has a current DBS check.
   - **Safeguarding Briefed** -- Whether the visitor has received the college safeguarding briefing.
5. Issue a **Badge Number** for the duration of the visit.
6. Record the **Sign In Time**.
7. Optionally record a **Vehicle Registration** for parking management.

### Signing Out

When the visitor leaves:

1. Locate their record in the active visitors list.
2. Record the Sign Out Time.
3. Update the status to indicate the visit is complete.
4. Collect the visitor badge.

### Safeguarding Compliance

All visitors must be verified against safeguarding requirements before being granted access to the college site. The system tracks:

- Whether a DBS check has been confirmed.
- Whether the visitor has received a safeguarding briefing.
- The staff member responsible for the visitor during their time on site.

### Visitor Reports

- List all visitors with optional filters by status, date, or purpose.
- Count visitors for reporting on site usage and security metrics.
- Review visitor logs for safeguarding audits.


## Health and Safety

The health and safety module tracks compliance with health and safety regulations across the college estate.

### Key Features

- **Risk Assessments** -- Record and review risk assessments for rooms, activities, and equipment.
- **Incident Reporting** -- Log health and safety incidents with details, witnesses, and follow-up actions.
- **Fire Safety** -- Track fire drill schedules, completion records, and evacuation times.
- **First Aid** -- Link to the first aid module for medical incident recording.
- **Equipment Checks** -- Schedule and record periodic safety checks on equipment (e.g., PAT testing, fire extinguisher inspections).
- **COSHH** -- Manage Control of Substances Hazardous to Health records where applicable.


## Accessibility

The accessibility module manages reasonable adjustments and accessibility provisions for students and staff with additional needs.

### Accessibility Provisions

- Record individual accessibility requirements linked to student or staff profiles.
- Track reasonable adjustments such as exam accommodations, assistive technology, and physical access arrangements.
- Ensure room bookings account for accessibility requirements (e.g., wheelchair access, hearing loop availability).
- Generate reports on accessibility provision for equality and diversity monitoring.


## Best Practices

- Audit active asset loans at the end of each term to ensure all devices are accounted for.
- Run the library overdue report weekly and follow up promptly to maintain stock availability.
- Ensure all visitors are signed out before the end of each day; review any unsigned-out records the following morning.
- Keep transport records up to date when routes or providers change mid-year.
- Schedule regular health and safety walkthroughs and record findings in the system.
- Review resource booking utilisation data termly to identify underused or overbooked spaces.
