# Administration Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Administration domain covers 8 modules for system management, school configuration, admissions, finance, and compliance. Admin-role users have full access; other roles have limited or no access to most modules. All data is stored in `secondary_school.db`.

---

## Users

Manage user accounts and role-based access.

| Role | Description | Default Permissions |
|---|---|---|
| admin | School administrators and SLT | Full system access |
| teacher | Teaching and support staff | Class-level access |
| student | Students (Years 7-11) | Own-record access |

- Create, edit, and deactivate user accounts
- Assign roles: admin, teacher, student
- Password management: reset, enforce complexity rules
- Session management: view active sessions, force logout
- Authentication via shared auth module (bcrypt hashing, MFA support)
- Link user accounts to staff records (STF IDs) or student records (SEC IDs)
- Bulk user creation via CSV import for start-of-year setup

## Settings

Configure school-wide parameters and academic year structure.

### School Details
- School name, address, URN, DfE number, and contact information
- Headteacher and chair of governors details
- School type and phase (secondary, 11-16)

### Academic Year
- Define academic year start and end dates
- Set up terms with start/end dates and half-term breaks
- Configure INSET days (non-pupil days)
- Roll over to new academic year: advance year groups, archive leavers

### Term Dates

| Term | Typical Dates |
|---|---|
| Autumn 1 | September - October half-term |
| Autumn 2 | October half-term - December |
| Spring 1 | January - February half-term |
| Spring 2 | February half-term - March/April |
| Summer 1 | April - May half-term |
| Summer 2 | May half-term - July |

### System Preferences
- Default attendance codes and thresholds
- Grading scale configuration (9-1 GCSE)
- Notification preferences and email settings
- Data retention policies

## Admissions

Manage student applications and intake processes.

### Year 7 Intake
- Record applications with student details, feeder primary school, and preferences
- Track application status: received, under review, offered, accepted, declined
- Manage oversubscription criteria and waiting lists
- Generate offer letters from templates
- Import applicant data from local authority feeds
- Transition support: record KS2 SATs results for incoming Year 7

### In-Year Transfers
- Process mid-year applications
- Record previous school, reason for transfer, and year group
- Check capacity against Published Admission Number (PAN)
- Create student record on admission (auto-generates SEC ID)
- Notify relevant staff: form tutor, Head of Year, SENCO (if applicable)

| Status | Description |
|---|---|
| Received | Application submitted |
| Under Review | Being assessed against criteria |
| Offered | Place offered to applicant |
| Accepted | Offer accepted, place confirmed |
| Declined | Offer declined or withdrawn |
| Waiting List | On waiting list for available place |

## Finance

Track school budget, funding streams, and expenditure.

- Set annual budget with income and expenditure categories
- Record and track Pupil Premium funding allocation and spend
- Log purchase orders and invoices
- Budget vs actual comparison reports by cost centre
- Department budget delegation and monitoring
- Track additional funding: Sports Premium, SEN funding, grants
- Generate financial summary reports for governors
- Petty cash management

| Funding Stream | Description |
|---|---|
| GAG (General Annual Grant) | Core school funding |
| Pupil Premium | Disadvantaged students (FSM, LAC, service) |
| SEN Top-up | Additional EHCP funding |
| Sports Premium | PE and sport improvement |
| Catch-up Premium | Targeted academic catch-up |

## Data Export

Export school data for statutory returns and analysis.

- **School Census**: generate termly census returns (autumn, spring, summer) in the required DfE format
- Export student data, attendance, and exclusions for local authority returns
- CSV and Excel export for any data view in the system
- Filtered exports: by year group, form group, or custom criteria
- GDPR-compliant data exports: redact sensitive fields as configured
- Scheduled export templates for recurring reports
- Export workforce census data (staff details, qualifications, absences)

## Audit Log

Track all significant system actions for accountability.

- Automatic logging of: user logins/logouts, record creation, edits, deletions
- Log entries include: timestamp, user ID, action type, module, record ID, before/after values
- Search and filter logs by date range, user, module, or action type
- Tamper-resistant: log entries cannot be edited or deleted by any user
- Retention period configurable (default: 7 years)
- Export audit logs for external review or inspection

| Logged Action | Details Captured |
|---|---|
| Login / Logout | User, timestamp, IP |
| Record Created | Module, record ID, created by |
| Record Edited | Field changed, old value, new value |
| Record Deleted | Full record snapshot before deletion |
| Report Generated | Report type, parameters, generated by |

## Policies

Manage school policy documents and review cycles.

- Upload and store policy documents (PDF, Word)
- Record policy metadata: title, owner, approval date, review date
- Automated reminders for upcoming policy reviews
- Version history: track policy revisions
- Categorise policies: safeguarding, behaviour, HR, health and safety, curriculum
- Staff acknowledgement tracking: confirm policies have been read
- Publish policies for staff and parent access

## Documents

Central document management for the school.

- Upload, categorise, and store school documents
- Folder structure by category: governance, compliance, templates, correspondence
- Search documents by title, category, or upload date
- Access control: restrict documents by role
- Template library: letter templates, form templates, report templates
- Version tracking for regularly updated documents
- Bulk download and archive functionality

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Users | Full CRUD | No access | No access |
| Settings | Full CRUD | View only | No access |
| Admissions | Full CRUD | No access | No access |
| Finance | Full CRUD | View department budget | No access |
| Data Export | Full access | Limited exports | No access |
| Audit Log | View all | No access | No access |
| Policies | Full CRUD | View and acknowledge | No access |
| Documents | Full CRUD | View permitted | No access |

---

*Secondary School Management System -- Administration Domain Guide*
