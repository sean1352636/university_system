# Primary School — Administration Guide

> Covers 8 modules: Users, Settings, Admissions, Finance, Data Export, Audit Log, Policies, Documents

Last Updated: March 2026

---

## Users

Manage user accounts, roles, and access permissions.

### Roles

| Role | Access Level |
|---|---|
| **admin** | Full system access, all modules |
| **teacher** | Academics, pastoral care, pupil records, own staff records |
| **student** | Not typically used in primary (no pupil login) |
| **parent** | Parent portal: view own child's attendance, homework, reports |

### Key Workflows

- **Create account** — Click Add User, enter name, email, and assign a role. The system generates a temporary password.
- **Password reset** — Select the user and click Reset Password. A new temporary password is generated.
- **Deactivate account** — Disable access without deleting the account. Useful for staff who have left.
- **Role assignment** — Each user has a single primary role. Admins can adjust roles at any time.
- **View active sessions** — See who is currently logged in.

### Authentication

- Passwords are hashed with bcrypt.
- MFA (multi-factor authentication) is available via TOTP.
- Sessions expire after inactivity.
- Authentication is handled via the shared auth module (see shared auth documentation).

---

## Settings

Configure school-wide system settings.

### School Details

| Setting | Description |
|---|---|
| School Name | Official school name |
| Address | Full postal address |
| Phone/Email | Main contact details |
| Headteacher | Name of the headteacher |
| URN | Unique Reference Number (DfE) |
| School Type | Academy, Maintained, Free School, etc. |

### Academic Year Setup

- Define the current academic year (e.g., 2025-26).
- Set term dates: Autumn, Spring, Summer with half-term breaks.
- Mark INSET days (non-pupil days).
- **Year group promotion** — At the start of a new academic year, bulk-promote all pupils to the next year group. Year 6 leavers are archived.

### System Configuration

- Default attendance codes and thresholds.
- Assessment period labels (terms).
- Notification preferences.
- Backup schedule settings.

---

## Admissions

Manage pupil admissions and intake.

### Application Workflow

1. **Receive application** — Add a new application with pupil details, parent information, and preferred start date.
2. **Review** — Assess against admissions criteria. Record any SEND or medical information.
3. **Offer place** — Change status to Offered. Generate offer letter.
4. **Accept/Decline** — Record the parent's response.
5. **Enrol** — On acceptance, convert the application to a pupil record (PRI ID assigned automatically).

### Application Statuses

| Status | Description |
|---|---|
| Received | Application submitted |
| Under Review | Being assessed |
| Offered | Place offered to parent |
| Accepted | Parent accepted the offer |
| Declined | Parent declined |
| Waiting List | On the waiting list |
| Enrolled | Pupil admitted and active |
| Withdrawn | Application withdrawn |

### Waiting Lists

- Maintain ordered waiting lists by year group.
- Automatically offer places when vacancies arise (configurable).

---

## Finance

Track school budgets, income, and expenditure.

### Budget Management

| Category | Examples |
|---|---|
| Staffing | Salaries, supply costs, NI, pensions |
| Resources | Books, equipment, materials |
| Premises | Utilities, maintenance, cleaning |
| Services | IT support, catering contract, HR services |
| CPD | Training costs |
| SEND | Specialist provision, resources |

### Key Features

- **Budget setup** — Define annual budget by category with planned amounts.
- **Record transactions** — Log income and expenditure against budget lines.
- **Pupil Premium tracking** — Track Pupil Premium funding allocation and spending. Record the impact of interventions funded by PP.
- **Sports Premium** — Track PE and Sport Premium spending and impact.
- **Reports** — Generate budget vs. actual reports, projected year-end position, and funding breakdowns.
- **Export** — Export financial data for submission to the local authority or trust.

---

## Data Export

Export data for statutory returns and reporting.

### Export Formats

| Format | Use Case |
|---|---|
| CSV | General-purpose data export |
| Excel (.xlsx) | Formatted reports with multiple sheets |

### Statutory Returns

- **School Census** — Generate termly census data in the required format (pupil demographics, attendance, FSM eligibility, SEND status).
- **Attendance returns** — Export attendance data for the local authority.
- **Workforce census** — Export staff data for the annual workforce census.

### Custom Exports

- Select data fields from any module (pupils, attendance, assessment, etc.).
- Apply filters (year group, class, date range).
- Save export templates for repeated use.

---

## Audit Log

Maintain a complete trail of system activity.

### What Is Logged

| Event Type | Examples |
|---|---|
| User Activity | Login, logout, failed login attempts |
| Data Changes | Record created, updated, deleted |
| Access | Module accessed, report generated |
| Admin Actions | User created, role changed, password reset |
| Export | Data exported, report downloaded |

### Features

- **Search** — Filter by user, date range, event type, or module.
- **Immutable records** — Audit log entries cannot be edited or deleted.
- **Retention** — Logs are retained for the configured period (default: 7 years).
- **Export** — Export audit logs for compliance or investigation purposes.

---

## Policies

Manage school policy documents.

### Policy Records

| Field | Description |
|---|---|
| Policy Name | e.g., Safeguarding Policy, Behaviour Policy |
| Category | Statutory, Non-statutory |
| Owner | Staff member responsible for the policy |
| Approved Date | Date of governing body approval |
| Review Date | Next scheduled review date |
| Version | Version number |
| Document | Attached policy document file |

### Key Features

- **Review reminders** — The system alerts when policies are approaching their review date.
- **Version control** — Maintain previous versions. Compare changes between versions.
- **Statutory tracking** — Flag mandatory policies and track compliance.

---

## Documents

General document storage and template management.

### Features

- **Document storage** — Upload and organise documents in a folder structure.
- **Categories** — Governance, safeguarding, HR, curriculum, forms, letters, reports.
- **Template management** — Create and store letter templates (e.g., absence letters, trip consent forms, report templates).
- **Search** — Find documents by name, category, or date.
- **Access control** — Set document visibility by role (admin only, all staff, or public).

---

## Quick Reference

| Module | Access Path | Key Roles |
|---|---|---|
| Users | Sidebar → Admin → Users | admin |
| Settings | Sidebar → Admin → Settings | admin |
| Admissions | Sidebar → Admin → Admissions | admin |
| Finance | Sidebar → Admin → Finance | admin |
| Data Export | Sidebar → Admin → Data Export | admin |
| Audit Log | Sidebar → Admin → Audit Log | admin |
| Policies | Sidebar → Admin → Policies | admin |
| Documents | Sidebar → Admin → Documents | admin, teacher |
