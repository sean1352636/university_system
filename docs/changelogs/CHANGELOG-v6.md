# Changelog Archive — Version 6.x

This file contains the version 6 history moved from the main
[CHANGELOG.md](../../CHANGELOG.md) to keep the current changelog focused.

For current changes and version 9, see [CHANGELOG.md](../../CHANGELOG.md).
Other historical versions are archived alongside this file.

---

## [6.24.0] — 2026-03-07

### Added
- **College: Baseline Assessment** — initial assessments with student joins, progress checkpoints linked to courses, student progress tracking, statistics dashboard (2 tables: `baseline_assessments`, `progress_checkpoints`)
- **College: Data Export** — export jobs with start/complete/fail workflow, reusable templates with active toggle, format/status filtering (2 tables: `data_export_jobs`, `data_export_templates`)
- **College: Disciplinary & Appeals** — case management with hearing scheduling and outcome recording, evidence tracking by type, appeals with lodge/schedule/outcome workflow, cascade deletes, status/type breakdowns (3 tables: `disciplinary_cases`, `disciplinary_evidence`, `disciplinary_appeals`)
- **College: Expense Claims** — claims with staff name joins, approve/reject/mark-paid workflow, pending approvals view, category breakdowns (1 table: `expense_claims`)
- **College: Functional Skills & GCSE Resits** — enrollments with subject/qualification type/level tracking, assessments with score/grade, exam booking, result recording, student progress view, condition of funding report, pass rate stats (2 tables: `functional_skills_enrollments`, `functional_skills_assessments`)
- **College: Health & Safety** — incident reporting with RIDDOR tracking and close workflow, inspections with certificate refs, risk assessments with hazard/control/rating, compliance checks with overdue detection, 5-tab GUI (4 tables: `hs_incidents`, `hs_inspections`, `hs_risk_assessments`, `hs_compliance_checks`)
- **College: Internal Verification** — IV plans linked to courses with sampling strategy, sample verification with decisions-agreed/grading-accurate tracking, assessment observations with grading, action completion tracking, accuracy rate stats (3 tables: `iv_plans`, `iv_samples`, `iv_observations`)
- **College: Letter Templates** — template management with body/placeholders, generated letters with send tracking, cascade deletes, active toggle (2 tables: `letter_templates`, `generated_letters`)
- **College: Lettings** — facility booking with DBS/insurance/risk-assessment verification, payment tracking, contracts with signing workflow, revenue statistics (2 tables: `lettings_bookings`, `lettings_contracts`)
- **College: Onboarding** — staff onboarding checklists with mentor assignment, categorised tasks with completion tracking, probation reviews with performance ratings and recommendations, cascade deletes, completion rate stats (3 tables: `onboarding_checklists`, `onboarding_tasks`, `probation_reviews`)
- **College: Student Council** — council members with role/term tracking, meetings with agenda/minutes and completion workflow, proposals with vote recording and management response, implementation status tracking (3 tables: `council_members`, `council_meetings`, `council_proposals`)
- **College: Student Wellbeing** — wellbeing referrals with risk levels and resolve workflow, wellbeing logs with mood/anxiety/sleep tracking, counselling sessions with risk assessment, high-risk student alerts, student wellbeing summaries, average mood stats (3 tables: `wellbeing_referrals`, `wellbeing_logs`, `counselling_sessions`)
- **College: Study Programmes** — ESFA-compliant study programmes with maths/english condition of funding, programme components by type, validation engine (checks requirements and minimum hours), delivered hours recalculation, funding hours reporting (2 tables: `study_programmes`, `study_programme_components`)
- **College: Tutorial System** — tutor-student assignments with group support, tutorial sessions with type/topic tracking and completion, 1-to-1 tutorial records with targets and follow-up tracking, tutor group views (3 tables: `tutor_assignments`, `tutorial_sessions`, `tutorial_records`)

### Changed
- All 27 placeholder/stub college modules now replaced with fully functional implementations (service + GUI + CLI each)
- Each module includes full CRUD operations, search/filter capabilities, statistics dashboards, and proper error handling

## [6.23.0] — 2026-03-07

### Added
- **College: Alumni Network** — fully functional module with alumni records (search/filter by year), events (type filter), surveys (joins alumni names), and statistics dashboard (3 tables: `alumni_records`, `alumni_events`, `alumni_surveys`)
- **College: Complaints** — complaints management with escalation workflow (informal → formal stage 1 → formal stage 2 → panel hearing → appeal), responses with user name joins, category/stage breakdowns (2 tables: `complaints`, `complaint_responses`)
- **College: DBS Checks** — DBS check tracking with staff/governor/volunteer support, expiry monitoring (configurable days), update service tracking, certificate management (1 table: `dbs_checks`)
- **College: Early Warning System** — student alerts with severity/type filtering, student name joins, resolve workflow, configurable rules engine, breakdowns by severity and type (2 tables: `early_warning_alerts`, `early_warning_rules`)
- **College: Equality & Diversity** — protected characteristics records, equality impact assessments, objectives tracking with status filtering, reusable form builder in GUI (3 tables: `protected_characteristics`, `equality_impact_assessments`, `equality_objectives`)
- **College: Discussion Forums** — forum categories, threads with pinning/locking, posts with solution marking, view count tracking, reply count auto-management (3 tables: `forum_categories`, `forum_threads`, `forum_posts`)
- **College: Marketing** — open day events with registration tracking (auto-increments counts), attendance marking, marketing campaigns with budget/spend tracking, utilisation stats (3 tables: `open_days`, `open_day_registrations`, `marketing_campaigns`)
- **College: Prevent Duty** — Prevent referrals with risk levels and Channel referral escalation, staff training tracking with expiry monitoring, risk-level breakdowns (2 tables: `prevent_referrals`, `prevent_training`)
- **College: Recruitment** — job vacancies with publish/close workflow, applications with shortlisting, interview scheduling/scoring, offer management, cascade deletes (2 tables: `job_vacancies`, `job_applications`)
- **College: Risk Management** — institutional risk register with auto-calculated risk scores (likelihood x impact), colour-coded rows in GUI, risk reviews with history, category/status breakdowns (2 tables: `institutional_risks`, `risk_reviews`)
- **College: Self-Assessment & Ofsted** — SEF sections with grade/strengths/improvements, improvement actions linked to sections with progress tracking, Ofsted prep checklist with ready/not-ready toggle (3 tables: `sef_sections`, `improvement_actions`, `ofsted_prep_checklist`)
- **College: Staff Absence** — absence tracking with staff name joins, close workflow (return-to-work), configurable triggers with breach checking (days/occasions within period), by-type breakdowns (2 tables: `staff_absences`, `staff_absence_triggers`)
- **College: Student Portal** — portal page management with slug-based routing and publish toggle, quick links with active toggle, category breakdowns (2 tables: `portal_pages`, `portal_links`)

### Changed
- 13 placeholder/stub college modules replaced with fully functional implementations (service + GUI + CLI each)
- Each module includes full CRUD operations, search/filter capabilities, statistics dashboards, and proper error handling

## [6.22.2] — 2026-03-06

### Added
- **Secondary School: System Switching (GUI)** — "Switch System" button in the sidebar opens a dialog to switch to College or University GUI
- **Secondary School: System Switching (CLI)** — `[G] Switch to GUI` and `[S] Switch System` options added to admin, teacher, and student menus
- **College CLI: Switch to Secondary School** — `[W] Switch to Secondary School` option added to all role menus (admin, instructor, student, parent)
- **College GUI: Secondary School in Switch Dialog** — Switch System dialog now includes Secondary School alongside University

### Fixed
- **Secondary School CLI: `configure_logging` import error** — `cli_main.py` imported `configure_logging` but the function is named `setup_logging`; fixed the import
- **Secondary School CLI: `ValueError` on non-numeric input** — added input validation to 8 CLI view functions (attendance, grades, enrollment, behaviour) that crashed when given non-numeric student PK input
- **University System: Chatbot `AttributeError`** — `display_chatbot_integration_menu` called chatbot functions as methods on `UserAuth` (e.g. `auth.launch_chatbot_interface()`) but they are standalone functions; fixed 5 call sites to use the correct function imports
- **University System: Chatbot GUI quick-action buttons** — fixed SQL queries in `context.py` and `dashboard.py` that used wrong table/column names vs actual DB schema (`enrollments` → `student_modules`, `read` → `is_read`, `day_of_week` → `days_of_week`, `room_number`/`building` → `classroom`, `application_type`/`amount` → `academic_year`/`application_date`, `visibility` → `is_active`/`target_audience`); all 12 quick-action buttons now query correctly
- **University System: Admin user_id FK mismatch** — `user_accounts.user_id` for admin pointed to a student record; added auto-repair in `_create_default_accounts_if_needed()` to detect and fix FK mismatches on startup

## [6.22.1] — 2026-03-06

### Fixed
- **University System: Missing `__init__.py` files** — added 12 missing `__init__.py` files across domain modules (`academic_progress`, `admissions`, `alumni`, `campus`, `career`, `facilities`, `finance`, `marketplace`, `academic_progress/services`, `ai_study/gui`, `ai_study/services`, `shared/gui/main/core`)
- **University System: Module-level `get_auth()` crash** — 8 files in finance and commerce modules called `get_auth()` at import time before auth was initialised, preventing GUI/CLI/API from loading. Wrapped in try/except to allow graceful fallback to `None`
  - `finance/core/account_management.py`, `finance/core/security_automation.py`
  - `finance/billing/fee_structure.py`, `finance/billing/payment_plans.py`
  - `finance/reporting/budget_analysis.py`, `finance/reporting/revenue_analytics/app.py`
  - `finance/scholarships/scholarship_programs.py`
  - `commerce/services/restaurant/operations/restaurant_context.py`
- **University System: Missing `.env` file** — created `.env` from `.env.example` with development defaults

## [6.22.0] — 2026-03-06

### Added
- **Secondary School Attendance: 100 New GUI Functions** — comprehensive attendance management overhaul across two batches (50 + 50 functions)

- **Filtering & Search** (Batch 1)
  - Real-time name search, form group filter, status filter, clear all filters
  - Jump to student by ID lookup

- **Bulk Actions** (Batch 1)
  - Mark all present/absent, mark selected present/absent/late

- **Data Validation** (Batch 1)
  - ISO date format validation, unsaved changes warning, period validation
  - Duplicate entry detection, visual flagging of missing entries

- **Navigation** (Batch 1)
  - Previous/next school day (auto-skips weekends), go to today
  - Previous/next period navigation

- **Reporting & Export** (Batch 1)
  - CSV export, PDF export (via reportlab), summary statistics popup
  - Weekly attendance report, per-student attendance history with percentage

- **Undo / History** (Batch 1)
  - Full undo/redo stack, session change log, reset to last saved state
  - In-memory snapshot comparison

- **UI / Display** (Batch 1)
  - Dark mode toggle, auto-fit column widths, click-to-sort column headings
  - Colour-coded absent (red) and late (orange) rows, expandable notes side panel

- **Student Details** (Batch 1)
  - Student profile viewer, free-text attendance notes, pastoral follow-up flagging
  - Emergency contact display, medical notes viewer

- **Notifications & Alerts** (Batch 1)
  - Persistent absentee detection (configurable consecutive days)
  - Parent absence notification, late arrivals list view
  - Safeguarding alert integration (logs to SafeguardingService)
  - Timed unsaved reminder (2-minute interval)

- **Admin / Integration** (Batch 1)
  - Timetable sync (auto-select period by current time), CSV import
  - System printer support (lpr/Windows), register locking, audit log viewer

- **Attendance Patterns & Analytics** (Batch 2)
  - Canvas-based calendar heatmap of absences per student
  - YTD attendance percentage table for entire year group
  - Day-pattern absence detection (flags students always absent on specific days)
  - Year group comparison table, form group league table ranked by attendance rate
  - Canvas-based trend line chart (60-day rolling attendance rate)
  - Monday/Friday absence pattern detection (flags >60% Mon/Fri absences)
  - Punctuality statistics breakdown (on-time vs late)
  - Attendance vs grades correlation (cross-references GradeService data)
  - At-risk student predictor (flags students within 5% of threshold)

- **Thresholds & Interventions** (Batch 2)
  - Configurable absence threshold percentage (default 90%)
  - Below-threshold student listing
  - Intervention list export to CSV with urgency levels
  - Parent meeting flag with reason tracking
  - Return-to-school interview logging

- **Authorisation** (Batch 2)
  - Mark authorised/unauthorised absence with reason picker dialog
  - Bulk authorise selected students
  - Standard authorisation reasons reference view
  - Custom free-text authorisation reason entry

- **Registration Codes** (Batch 2)
  - DfE registration codes: B (off-site), C (holiday), D (dual reg), E (excluded)
  - Manual DfE code entry with full code reference (18 standard codes)
  - Codes auto-map to appropriate attendance status

- **Multi-class / Cover** (Batch 2)
  - Cover register loading, cover teacher assignment
  - AM/PM register merge into daily summary view
  - Set/band split filter, subject-based register loading

- **Communication** (Batch 2)
  - In-app absence email composer with parent email pre-fill
  - Phone call logging, bulk SMS trigger for absent students
  - Absence warning letter template generator with attendance stats
  - Per-student communication history viewer

- **Timetable & Calendar Integration** (Batch 2)
  - Bank holiday configuration (auto-skip in date navigation)
  - Term dates import from JSON config
  - Remaining school days calculator (excludes weekends & bank holidays)
  - Exam period flagging, ICS calendar export

- **Accessibility** (Batch 2)
  - Font size increase/decrease (range 7-20)
  - High-contrast mode (black/yellow theme)
  - Keyboard navigation (P=present, A=absent, L=late, Enter/Space=toggle)
  - Text-to-speech for selected student (macOS/Linux/Windows)

- **Backup & Recovery** (Batch 2)
  - Auto-save draft (configurable interval, default 5 min)
  - Draft recovery from `~/.school_attendance_drafts/`
  - Full session export/import via JSON backup
  - Clear all saved drafts

### Changed
- Attendance treeview changed to `selectmode="extended"` for multi-select support
- Attendance service expanded with 16 new query methods for analytics, patterns, thresholds, communication logging, and subject-based filtering

## [6.21.0] — 2026-03-06

### Added
- **College System: 14 More Modules** — internal verification, functional skills, study programmes, tutorial, student wellbeing, student council, lettings, health & safety, letter templates, disciplinary, onboarding, expense claims, baseline assessment, data export (110 total modules)

- **Internal Verification** — IV plans, sampling, assessor observations (instructor)
  - Create IV plans per course with lead verifier and sampling strategy
  - Record sample outcomes: assessment decisions, feedback quality, grading accuracy
  - Schedule and record assessor observations with grades and actions

- **Functional Skills & GCSE Resits** — condition of funding tracking (staff)
  - Enroll students in GCSE resit / Functional Skills qualifications
  - Track entry grade, target grade, exam board, exam series and date
  - Record mock assessments with scores, grades, and feedback
  - Monitor condition of funding compliance

- **Study Programmes** — 16-19 study programme validation (staff)
  - Track programme components: substantive qualification, maths, English, work experience, enrichment, tutorial
  - Validate maths/English condition of funding requirements
  - Monitor planned vs delivered hours per component
  - Programme-level validation status

- **Tutorial System** — personal tutor management (instructor)
  - Assign personal tutors to students with tutor group tracking
  - Schedule group and 1-to-1 tutorial sessions
  - Record meeting notes, targets set, student concerns
  - Follow-up tracking for outstanding actions

- **Student Wellbeing** — mental health and counselling support (staff)
  - Wellbeing referrals: internal/external, risk levels, consent tracking
  - Wellbeing logs: mood rating, anxiety level, sleep quality monitoring
  - Counselling sessions: session notes, risk assessment, appointment scheduling

- **Student Council** — student voice and representation (student)
  - Council member management with roles and term dates
  - Meeting scheduling with agendas and minutes
  - Proposal submission, voting, management responses, implementation tracking

- **Facility Lettings** — external hire management (admin)
  - Booking management: facility, dates, times, fees, recurrence
  - DBS, insurance, and risk assessment verification for hirers
  - Contract management with terms and agreed fees
  - Payment status and invoice tracking

- **Health & Safety** — H&S compliance and incident reporting (admin)
  - Incident reporting: accidents, near misses, RIDDOR reportable events
  - Inspection tracking: fire, electrical, gas, legionella, asbestos with certificates
  - Risk assessments: hazards, controls, risk ratings, review dates
  - Compliance checks: PAT testing, fire equipment, gas safety with due dates

- **Letter Templates** — document generation with mail merge (staff)
  - Template management with merge fields and categories
  - Generate letters for individual or bulk recipients
  - Track send status via email/post

- **Disciplinary & Appeals** — formal disciplinary procedures (admin)
  - Case management: allegations, investigating officer, hearing panels
  - Evidence collection with file attachments
  - Hearing outcomes, sanctions with start/end dates
  - Appeal process: grounds, panel, hearing, outcome

- **Staff Onboarding** — new starter checklists and probation (admin)
  - Onboarding checklists with task categories and due dates
  - Mentor assignment for new staff
  - Probation reviews: performance rating, strengths, development areas, recommendations

- **Expense Claims** — staff expenses and mileage (staff)
  - Submit claims with category, amount, mileage calculations (45p/mile)
  - Approval workflow and payment tracking
  - Receipt attachment support

- **Baseline Assessment** — entry-level student assessment (instructor)
  - Record initial assessments: English, maths, ICT scores, learning styles
  - GCSE grade capture and prior attainment tracking
  - Progress checkpoints: current vs target grade, effort, attendance, concerns

- **Data Export & ILR** — regulatory data submission (admin)
  - ILR export functionality for ESFA submission
  - School census data extracts
  - Custom export templates with field mapping
  - Validation with error/warning logging

## [6.20.0] — 2026-03-06

### Added
- **College System: 19 New Modules** — ILP, UCAS, T-Levels, apprenticeships, value-added, governance, DBS checks, risk management, prevent duty, complaints, equality & diversity, staff absence, recruitment, marketing, early warning, self-assessment, alumni, student portal, forums (96 total modules)

- **Individual Learning Plans (ILP)** — personalised learning pathways (instructor)
  - Create ILPs with long-term goals, support needs, review frequency
  - Add subject-specific targets with current/target grades and success criteria
  - Schedule and record ILP reviews with student voice and agreed actions
  - Track due reviews across all active plans

- **UCAS Applications** — university application tracking (staff)
  - Application management: UCAS ID, personal statement status, predicted tariff
  - Up to 5 university choices with offer tracking (conditional/unconditional)
  - Firm and insurance choice management
  - Reference request and submission workflow
  - Application statistics dashboard

- **T-Level Pathways** — T-Level qualification management (staff)
  - Route setup: pathway, awarding body, GLH, industry placement hours (315 minimum)
  - Student enrollment with occupational specialism tracking
  - Industry placement logging: hours, activities, supervisor feedback
  - Automatic placement hours accumulation

- **Apprenticeships** — apprenticeship programme management (staff)
  - Standards library: level, sector, duration, EPA provider, OTJ hours
  - Enrollment with employer details, start/end dates, OTJ targets
  - Off-the-job training log with activity types and evidence
  - Progress reviews with employer attendance and target setting
  - EPA status and gateway tracking

- **Value-Added Analysis** — GCSE baseline to A-Level outcome comparison (instructor)
  - Set GCSE baselines: average score, English, maths grades
  - Predicted and target grade tracking per student per course
  - Calculate value-added score (actual vs predicted)
  - Subject-level and college-level value-added reporting

- **Governance & Board** — governor and board management (admin)
  - Governor records: type, role, appointment dates, DBS status, skills
  - Board meeting scheduling with agendas, minutes, quorum tracking
  - Action item tracking with assignment and due dates
  - Strategic plan management with priority areas and progress

- **DBS Checks** — disclosure and barring service tracking (admin)
  - Staff and governor DBS records with certificate numbers
  - Check types: enhanced, enhanced with barred list, basic
  - Update service registration and ID tracking
  - Expiry date monitoring and renewal alerts

- **Risk Management** — institutional risk register (admin)
  - Risk records: category, likelihood, impact, risk score
  - Current controls and mitigation strategies
  - Risk owner assignment and review scheduling
  - Risk review history with score progression

- **Prevent Duty** — counter-terrorism compliance (staff)
  - Referral recording: concern type, risk level, Channel referral tracking
  - Staff Prevent training records with certification and expiry
  - Action tracking and outcome recording

- **Complaints** — formal complaints handling (admin)
  - Complaint logging: stage (informal/formal/appeal), category, description
  - Investigation officer assignment and notes
  - Response tracking with resolution and outcome
  - Appeal process support

- **Equality & Diversity** — protected characteristics monitoring (admin)
  - Protected characteristics data collection with consent tracking
  - Equality impact assessments for policies and practices
  - Equality objectives with targets and progress tracking

- **Staff Absence** — sickness and absence management (admin)
  - Absence records: type, dates, days lost, reason
  - Fit note and self-certification tracking
  - Return-to-work interview management
  - Trigger point monitoring with configurable thresholds
  - Occupational health referral tracking

- **Staff Recruitment** — vacancy and application management (admin)
  - Job vacancy creation: title, department, contract type, salary range
  - Application tracking: shortlisting, interview scheduling, scoring
  - Reference and offer management workflow

- **Marketing & Open Days** — recruitment and marketing (admin)
  - Open day/evening event management with registration tracking
  - Attendee tracking with school, interests, follow-up status
  - Marketing campaign management: budget, spend, channels
  - Conversion tracking: impressions → enquiries → applications

- **Early Warning System** — at-risk student identification (instructor)
  - Configurable alert rules: attendance thresholds, grade trends, behaviour counts
  - Alert generation with severity levels and recommended actions
  - Assignment to staff with action tracking and resolution

- **Self-Assessment & Ofsted** — SEF and improvement planning (admin)
  - SEF section management with self-grades, strengths, areas for improvement
  - Improvement action tracking: responsible person, target dates, success criteria
  - Ofsted preparation checklist with readiness status

- **Alumni Network** — graduate engagement (staff)
  - Alumni records: graduation year, current employment, further education
  - Willingness to mentor/speak flags
  - Alumni events and reunion management
  - Destination surveys with satisfaction ratings

- **Student Portal** — self-service information hub (student)
  - Portal pages with categories and publishing controls
  - Useful links management with descriptions and icons

- **Discussion Forums** — student community (student)
  - Forum categories with threaded discussions
  - Thread pinning, locking, and view counting
  - Post management with solution marking

## [6.19.0] — 2026-03-05

### Changed
- **Domain directory reorganisation** — grouped 50 modules into 7 logical categories for cleaner structure
  - `academics/` — students, subjects, enrollment, grades, attendance, timetable, homework, exams, progress, interventions, reports (11)
  - `pastoral_care/` — behaviour, detentions, exclusions, rewards, pastoral, safeguarding, send (7)
  - `staff/` — hr, cpd, cover, staff_directory (4)
  - `admin/` — users, settings, admissions, finance, data_export, audit_log, policies, documents (8)
  - `student_life/` — clubs, meals, transport, trips, careers, library, medical, form_groups, consent (9)
  - `facilities/` — room_booking, assets, seating_plans, visitors, incidents (5)
  - `communication/` — email, notifications, announcements, calendar, communication_log, parents_evening (6)
- Updated all import paths across 54 files (services, GUIs, main_gui.py, seed_subjects.py)

## [6.18.0] — 2026-03-05

### Added
- **Secondary School: 5 More Modules** — exclusions, progress tracking, seating plans, consent, incidents (51 total modules)

- **Exclusions** — statutory exclusion tracking (admin only)
  - Types: fixed-term, permanent, lunchtime, internal
  - DfE categories: persistent disruptive, physical assault, verbal abuse, bullying, drugs/alcohol, etc.
  - Track parent/LA notification, governor review dates, reintegration meetings
  - Alternative provision tracking, close/reopen workflow

- **Progress Tracking** — target grades and flight paths (teachers + admin)
  - Set baseline and target grades per student per subject per academic year
  - Update termly grades (autumn/spring/summer) with effort grades (1-4)
  - GCSE grade scale (9-1, U), current grade tracking
  - Filter by year group, view all progress across subjects

- **Seating Plans** — classroom layout management (teachers + admin)
  - Create plans with room, year group, teacher, configurable grid (rows x columns)
  - Assign students to specific row/column positions
  - View all seat assignments per plan
  - Unique seat enforcement (one student per position)

- **Permissions & Consent** — GDPR and safeguarding consent (admin only)
  - Consent types: photo (internal/external/social media/press), medical treatment, trip blanket, data sharing, biometric, online platforms, contact preferences
  - Toggle consent granted/not granted per student
  - Summary tab showing consent rates by type with percentages
  - Track granted by, date, and expiry

- **Incident Log** — health & safety incident reporting (admin only)
  - Types: accident, near miss, fire, medical emergency, security breach, property damage, violence, intruder
  - Severity levels: minor, moderate, serious, major, critical
  - RIDDOR reportable flag, investigation notes
  - Open/closed status workflow, filter by type and status

## [6.17.0] — 2026-03-05

### Added
- **Secondary School: 6 More Modules** — rewards, careers, form groups, audit, policies, communication log (46 total modules)

- **Rewards & Merits** — positive behaviour recognition (all roles)
  - Award merits, commendations, certificates, headteacher awards, house points
  - Categories: academic, effort, behaviour, attendance, community, sport, arts, leadership, kindness
  - Leaderboard tab with year group filter and top-20 rankings
  - Students can view leaderboard; teachers/admin can give awards

- **Careers & Work Experience** — CEIAG guidance and placements (teachers + admin)
  - Careers Meetings tab: log meetings with adviser, career interests, action points, destination
  - Work Experience tab: manage placements with employer, role, dates, contact details
  - Track risk assessment, parent consent, and insurance confirmation per placement
  - Status workflow: planned → confirmed → in_progress → completed / cancelled

- **Form Groups** — tutor/registration group management (teachers + admin)
  - Create form groups with year group, form tutor, room, max students, registration time
  - Add/view students per group, filter by year group
  - Student uniqueness enforced (one form group per student)

- **Audit Log** — system activity tracking (admin only)
  - Log actions: login, logout, create, update, delete, view, export, import, config_change
  - Filter by action type and module, shows timestamp, user, details
  - Entry count display, auto-cleanup of old entries

- **Policies** — school policy document management (admin only)
  - Categories: general, safeguarding, H&S, HR, curriculum, behaviour, admissions, SEND, data protection, complaints
  - Track version, approved by, approval/review dates
  - Staff acknowledgement tracking with count display
  - View all acknowledgements per policy

- **Communication Log** — parent/guardian contact records (teachers + admin)
  - Log phone calls, emails, letters, meetings, home visits, text messages
  - Track direction (incoming/outgoing), contact with, subject, summary, outcome
  - Follow-up tracking with date and done flag
  - Filter by contact type and follow-up needed

## [6.16.0] — 2026-03-05

### Added
- **Secondary School: 6 More Modules** — system configuration, admissions, notifications, interventions, staff CPD and transport (40 total modules)

- **Settings** — school-wide configuration management (admin only)
  - Seed default settings on first use (school name, academic year, term dates, periods per day, etc.)
  - Scrollable form with all settings grouped by category
  - Save all button persists changes to database

- **Admissions** — student application workflow (admin only)
  - Create applications with student details, year group, previous school, SEN/PP/EAL flags
  - Status workflow: submitted → under_review → interview → offered → accepted → enrolled / rejected / withdrawn
  - Status summary bar showing counts per status
  - Filter by status, search by name

- **Notifications** — in-app notification system (all roles)
  - Create notifications with title, message, priority (low/normal/high/urgent), target audience
  - Mark read / mark all read, unread filter
  - Bold unread rows, preview pane for message content

- **Interventions** — academic intervention group tracking (teachers + admin)
  - Create intervention groups with subject, type (academic/behaviour/attendance/wellbeing/literacy/numeracy), lead staff, review date
  - Add students with baseline and target grades
  - Track progress updates per student, close groups when complete

- **CPD / Staff Training** — continuing professional development records (teachers + admin)
  - Log training with title, category (safeguarding/first_aid/curriculum/leadership/SEN/ICT etc.), provider, date, hours, cost
  - Certificate received tracking
  - Staff summary view showing total courses and hours per staff member
  - Filter by category

- **Transport** — school bus routes and student assignments (teachers + admin)
  - Create routes with operator, vehicle type (bus/minibus/coach/taxi), capacity, driver details, departure/return times
  - Add stops with pickup and drop-off times per route
  - Assign students to routes, view students per route
  - Student count displayed in route list

## [6.15.0] — 2026-03-05

### Added
- **Secondary School: 10 Additional Modules** — completing the full school management suite (34 total modules)

- **Medical / First Aid** — student health records and incident logging
  - Medical Conditions tab: record conditions with severity, medications, allergies, care plans, doctor details
  - First Aid Log tab: log incidents with date/time, location, treatment, treated by
  - Track parent notification, sent home, ambulance called flags

- **School Meals** — catering and free school meals management
  - Registrations tab: register students with meal preference (standard/vegetarian/vegan/halal/kosher/gluten_free), dietary requirements, allergies, FSM flag
  - Bookings tab: book meals by date with meal type and menu choice, cancel bookings
  - FSM count displayed in status bar, filter by FSM only

- **Trips & Visits** — school trip planning and management
  - Create trips with destination, dates, times, year group, lead teacher, max students, cost, transport
  - Add students to trips with emergency contact details
  - Track consent received and payment status per student
  - Mark risk assessment as completed

- **Clubs & Extracurricular** — after-school activities management
  - Create clubs with category (sport/arts/music/drama/academic/stem/community), day, time, location, teacher
  - Add/view members, member count tracking, max member limits
  - Year group targeting

- **Detentions** — sanctions scheduling and tracking
  - Schedule detentions with type (lunchtime/after_school/saturday/internal_exclusion)
  - Link to behaviour records, assign room and supervisor
  - Mark attended/missed, filter by status (scheduled/completed/missed)

- **Document Store** — school document and policy management
  - Upload documents with category (policy/procedure/consent_form/safeguarding/curriculum/student_record/staff_record/template)
  - Version tracking, document acknowledgement system
  - Filter by category, acknowledgement count display

- **Visitor Management** — site security and visitor tracking
  - Sign in visitors with name, organisation, purpose, visiting, badge number, DBS check, car registration
  - Sign out visitors, on-site count in status bar
  - Filter to show on-site visitors only
  - Admin-only access

- **Room Booking** — facility booking with clash detection
  - Book rooms with date, time range, purpose, equipment needed
  - Automatic clash detection prevents double-booking
  - Cancel and delete bookings

- **Staff Directory** — school-wide staff profiles
  - View all staff with title, name, role, department, email, phone extension, room, subjects
  - Admin can add/delete entries; all roles can view
  - Available to students, teachers, and admin

- **Asset Management** — equipment and resource tracking
  - Register assets with tag, name, category (IT/furniture/textbooks/science_equipment/sports_equipment/audio_visual/musical_instruments/vehicles)
  - Track serial number, location, assigned to, purchase date/cost, warranty, condition
  - Search by name, tag, or serial number; filter by category
  - Admin-only access

### Changed
- **Scrollable sidebar** — sidebar now scrolls with mousewheel to accommodate all 34 modules; logout/shutdown buttons fixed at bottom
- **Role-based access expanded**: admin sees all 34 modules; teachers see 27 modules (everything except HR, Finance, Users, Data Export, Safeguarding, Visitors, Assets); students see 11 modules (Dashboard, Grades, Timetable, Exams, Homework, Calendar, Announcements, Library, Clubs, Staff Directory, Email)

## [6.14.0] — 2026-03-05

### Added
- **Secondary School: 12 New Modules** — major expansion of the school management system

- **Reports** — analytics and summary reports
  - Attendance summary, grade summary, behaviour summary by year group
  - Subject performance and year group overview reports
  - Year group filter for all report types

- **SEND (Special Educational Needs)** — SEN register and provisions
  - Create SEND records with SEN type, primary need, EHCP status, key worker, diagnosis, strategies, access arrangements
  - Track provisions per student: type, frequency, responsible staff, outcomes
  - Filter by active/inactive status

- **Safeguarding** — child protection concern management
  - Log concerns with type (welfare/abuse/neglect/bullying/online_safety/radicalisation/self_harm/other), severity, description
  - Track actions taken, referrals, outcomes, resolution status
  - Filter by open/resolved, confidential by default
  - Admin-only access

- **Parents Evening** — event and appointment management
  - Create events with year group, date, time range, slot duration
  - Book appointment slots: teacher, student, parent name, time
  - View and cancel individual slots

- **Cover** — cover lesson management
  - Log absent teachers with date, period, subject, work set
  - Assign cover teachers, mark lessons as completed
  - Filter by status (pending/assigned/completed)

- **Homework** — homework setting and submission tracking
  - Set homework linked to subjects with year group, due date, max marks
  - View submissions per homework: student, submitted date, marks, feedback, status
  - Delete homework and all associated submissions

- **Calendar** — school events calendar
  - Add events with type (general/term_date/inset_day/exam_period/parents_evening/sports_day/trip/assembly/open_day/holiday)
  - Date, time, location, year group, whole-school flag
  - Filter by event type

- **Announcements** — school-wide announcement system
  - Create announcements with title, body, audience (all/staff/students/year_group/admin), priority (low/normal/high/urgent)
  - Toggle publish/unpublish, preview body text
  - Priority-ordered display

- **User Management** — admin panel for user accounts
  - Create users with username, password, role, email
  - Reset passwords, toggle active/inactive, change roles
  - Filter by role, delete users
  - Admin-only access

- **Pastoral Care** — form tutor and pastoral support
  - Pastoral Notes tab: add notes with type (general/welfare/academic/behaviour/attendance/family/medical), follow-up dates, confidential flag
  - Mark follow-ups as done, filter by type
  - House Points tab: award points by house with reason, house points summary leaderboard

- **Library** — book catalogue and loan management
  - Catalogue tab: add books with title, author, ISBN, category (fiction/non-fiction/textbook/reference/graphic_novel/poetry/drama/other), location, copies
  - Search books by title, author, or ISBN
  - Loans tab: issue loans with configurable loan days, return books
  - Overdue loans view with student details

- **Data Export** — CSV data exports
  - Export students, grades, attendance, behaviour, and timetable to CSV files
  - File save dialog with default filenames
  - Admin-only access

### Changed
- **Role-based access expanded**: admin sees all 24 modules; teachers see everything except HR, Finance, Users, Data Export, and Safeguarding; students see Dashboard, Grades, Timetable, Exams, Homework, Calendar, Announcements, Library, and Email
- **Sidebar navigation** updated with all 24 modules in logical order

## [6.13.0] — 2026-03-05

### Added
- **Secondary School: Internal Email System** — DB-based messaging between all system users
  - Compose, inbox, sent views with recipient picker (all active users)
  - Reply with quoted original message, soft-delete per user, mark as read
  - Unread count badge in header, bold unread rows, preview pane
  - Available to all roles (admin, teacher, student)

- **Secondary School: Exam Management** — schedule exams and record results
  - Create exams with subject, type (end_of_term, mock, gcse, class_test, practical, oral, coursework), date/time, duration, room, invigilator, total marks
  - Record results for all students in a year group (marks, grade, absent flag, special consideration)
  - View results table per exam, filter by year group and status (scheduled/in_progress/completed/cancelled)
  - Students can view their own exam results

- **Secondary School: HR System** — staff management for admin users
  - Staff Records tab: full CRUD with auto-generated IDs (STF0001+), title, contact details, department, job title, contract type (permanent/fixed_term/part_time/supply/volunteer), salary, DBS check info, emergency contacts
  - Leave Management tab: request leave (annual/sick/maternity/paternity/compassionate/unpaid/training), approve/reject with approver tracking
  - Admin-only access

- **Secondary School: Finance System** — school finance management for admin users
  - Summary cards: total income, total expenses, balance (colour-coded)
  - Transactions tab: add income/expenses with categories (tuition_fees, government_funding, salaries, utilities, equipment, etc.), filter by type, delete
  - Budgets tab: set department budgets with allocated amounts, track spent vs remaining
  - All amounts displayed in GBP (£)
  - Admin-only access

- **Shutdown button** — dark red button at bottom of sidebar, confirms then closes application completely (no re-login)

### Changed
- **Role-based access updated**: admin sees all modules; teachers see everything except HR and Finance; students see Dashboard, Grades, Timetable, Exams, and Email


## [6.12.0] — 2026-03-05

### Added
- **Secondary School: Auto-generate timetables** — automatic timetable generation for year groups
  - Core subject allocation per key stage: KS3 (22 core periods/week), KS4 (19 core periods/week)
  - KS3 core: Maths (5), English Language (4), English Literature (3), Science (4), PE (2), PSHE (1), RE (1), ICT (2)
  - KS4 core: GCSE Maths (5), GCSE English Language (4), GCSE English Literature (3), GCSE Combined Science (5), PE (2)
  - Remaining slots filled by cycling through option subjects (shuffled for variety)
  - "Generate Year" button — generates full weekly timetable for selected year group with confirmation dialog
  - "Generate All Years" button — generates timetables for all Years 7-11 in one action
  - Summary dialog shows total slots, core/option split, and per-subject period counts
  - `clear_timetable()` method to wipe and regenerate cleanly
  - 30 slots per week (5 days × 6 periods) fully allocated

### Fixed
- **sqlite3.Row `.get()` errors** — fixed in enrollment, grade, and behaviour GUIs by converting Row objects to dicts before accessing with `.get()`
- **Parent/guardian details** — student form now collects parent name, email, and phone instead of student phone/email
- **Auto-enrollment** — new students are automatically enrolled in core subjects (Maths, English Lang/Lit, Science) plus 4 randomly-selected unique option subjects


## [6.11.1] — 2026-03-05

### Added
- **Secondary School: Subject seeding** — 50 UK secondary school subjects auto-seeded on first run
  - 18 KS3 subjects (core + options) and 32 KS4 subjects (GCSE + BTEC)
  - Covers Maths, English, Sciences, Humanities, MFL (French, Spanish, German, Italian), Arts, Technology, Computing, Business, and more
  - Each subject includes department, teacher, room, capacity, and core/option flag
  - `seed_subjects.py` is re-runnable (skips existing subjects)
  - `main_gui.run()` detects first run (DB file absent) and auto-seeds subjects after schema init


## [6.11.0] — 2026-03-05

### Added
- **Secondary School System (rebuilt)** — full Python tkinter GUI application at `education_system/secondary_school/`
  - **Core infrastructure**: paths, exceptions, defaults, logging — mirrors college system architecture
  - **Database**: SQLite with WAL mode, connection pooling, full schema (users, sessions, students, staff, subjects, enrollments, grades, attendance, timetable, behaviour, notifications)
  - **Authentication**: login with lockout, session tokens, role-based access (admin/teacher/student), password hashing with salted SHA-256
  - **Student Management**: CRUD with auto-generated IDs (SEC0001+), year group filter (7-11), auto key stage assignment (KS3: Years 7-9, KS4: Years 10-11), SEN status tracking (None/SEN Support/EHCP), pupil premium flag, emergency contacts, auto user account creation
  - **Subject Management**: CRUD with subject codes, KS3/KS4 filter, core subject flag, department/teacher/room, capacity limits
  - **Enrollment Management**: enroll/drop students in subjects, capacity checking, duplicate prevention
  - **Grade Management**: record assessments (classwork, homework, test, mock_exam, coursework, end_of_term), GCSE grades (9-1/U), scores, terms, academic years, teacher comments
  - **Attendance**: register by year group and period (AM/PM/1-6), double-click to cycle status (present/absent/late/authorised_absent/unauthorised_absent), bulk save, attendance summary with percentage
  - **Timetable**: visual grid display (Monday-Friday, 6 periods), clash detection, add/view slots per year/form group
  - **Behaviour Management**: positive/negative records, categories (achievement, effort, disruption, bullying, etc.), merit points, sanctions (verbal_warning through exclusion), parent notification tracking, resolve incidents, recent incidents view
  - **Dashboard**: welcome screen with stat cards (total/active students, per-year counts, subject count)
  - **Login screen**: modal dialog with default credentials hint, error display
  - **Sidebar navigation**: role-restricted (students see only Dashboard/Grades/Timetable)
  - **Default accounts**: admin/Admin@123, teacher/Teacher@123, student/Student@123
  - Seed data auto-created on first run

### Fixed
- **run.py**: school system launcher updated to import from `education_system.secondary_school.main_gui` (was referencing non-existent `education_system.school_system`)


## [6.10.0] — 2026-02-28

### Added
- **Secondary School System** — integrated into the Education System launcher
  - Moved `secondary_school_management` package into `education_system/school_system/`
  - CLI interface via `click` with commands for students, teachers, courses, enrollments, grades, attendance, timetable, behaviour, dashboard, and user auth (login, register, MFA)
  - GUI interface via tkinter with dashboard-driven frame-switching layout (matching college system design)
  - REST API via stdlib `http.server` with full CRUD endpoints for all resources
  - i18n support for 10 languages (en, es, fr, de, it, pt, ru, zh, hi, ar)
  - PBKDF2 password hashing and TOTP-based MFA authentication
  - Added `--school` flag and `[3] Secondary School` menu option to `run.py`
  - GUI launcher button (purple) added to system selector window
  - Logout, Exit, and Switch System buttons in school system GUI top bar

### Changed
- **Switch System** — all three systems now use a generic "Switch System" picker dialog
  - University GUI: "College System" button replaced with "Switch System" offering College and School options
  - College GUI: "Switch to University System" menu item replaced with "Switch System" offering University and School options
  - School GUI: "Switch System" button in top bar offers University and College options


## [6.9.0] — 2026-02-28

### Added
- **College System: Funding & ILR** — ILR funding records, evidence, rules, and English/Maths resit tracking
  - `FundingService` with funding records (CRUD, complete/withdraw lifecycle, hours summary, ILR export), evidence (add/list/verify), rules (CRUD, eligibility checking), resits (CRUD, summary stats)
  - GUI `FundingFrame` with 4-tab Notebook (Funding Records, Evidence, Rules, Resit Tracking)
  - CLI `funding_menu` with 9 options covering all four areas
  - API routes at `/api/funding` with 11 endpoints
  - 9 unit tests
- **College System: Destinations & NEET** — destination tracking and NEET risk assessment
  - `DestinationService` with destination CRUD, confirmation workflow, NEET risk flagging, risk score calculation (0-4 based on: no confirmed destination, withdrawal history, attendance <85%, no contact made), contact recording, pending follow-ups, and destination statistics
  - GUI `DestinationsFrame` with 3-tab Notebook (Destinations, NEET Risk, Statistics)
  - CLI `destinations_menu` with 9 options including risk scoring and follow-up tracking
  - API routes at `/api/destinations` with 9 endpoints
  - 9 unit tests
- **College System: Student Support** — interventions, risk register, and student documents
  - `StudentSupportService` with interventions (CRUD, session tracking, impact reports), risk register (CRUD, resolve/escalate workflows, student risk profiles), documents (upload/list/verify, expiry tracking)
  - GUI `StudentSupportFrame` with 3-tab Notebook (Interventions, Risk Register, Documents)
  - CLI `student_support_menu` with 9 options across all three areas
  - API routes at `/api/support` with 9 endpoints
  - 6 unit tests
- **College System: Finance** — fees, invoicing, payments, and payroll
  - `FinanceService` with fee items (CRUD), invoices (CRUD, status tracking, student balance, overdue detection), payments (record with auto-update of invoice paid_amount/status), payroll (CRUD, status lifecycle, period summary)
  - GUI `FinanceFrame` with 4-tab Notebook (Fee Items, Invoices, Payments, Payroll)
  - CLI `finance_menu` with 9 options covering all four areas
  - API routes at `/api/finance` with 10 endpoints
  - 8 unit tests
- **College System: Departments & Groups** — departments, tutor groups, teaching groups, and membership
  - `DepartmentService` with department CRUD (soft delete), course/staff lookups
  - `GroupService` with tutor groups (CRUD), teaching groups (CRUD), member management (add/remove with left_date), student group lookups
  - GUI `DepartmentsFrame` with 3-tab Notebook (Departments, Tutor Groups, Teaching Groups)
  - CLI `departments_menu` with department and group management options
  - API routes at `/api/departments` and `/api/groups` (2 blueprints) with 11 endpoints
  - 5 unit tests (DepartmentService) + 5 unit tests (GroupService)
- **College System: Room Management** — rooms, resources, availability, and utilization
  - `RoomService` with room CRUD, status management, resource tracking (add/list/update/remove), available room finder (filtered by day/time/capacity/features), utilization reporting
  - Rooms tab added to Timetable GUI with treeview and add room dialog
  - CLI room management and availability search added to timetable menu (options 8-9)
  - API routes at `/api/rooms` with 8 endpoints
  - 8 unit tests
- **College System: Timetable clash detection** — student timetable clash identification
  - `TimetableService.check_student_clashes()` — finds overlapping slots via enrollment data
  - `TimetableService.get_instructor_schedule()` — retrieves all slots for an instructor
  - CLI option `A` (Check Student Clashes) in timetable menu
  - API endpoints: `GET /api/timetable/student/<id>/clashes`, `GET /api/timetable/instructor/<name>`
- **College System: Attendance register generation** — timetable-linked session creation
  - `AttendanceService.create_session_from_slot()` — create session linked to a timetable slot
  - `AttendanceService.generate_registers_for_date()` — auto-create sessions for all slots on a given day
  - `AttendanceService.get_session_by_slot()` — find linked session by slot and date
  - `AttendanceService.pre_populate_register()` — create absent records for all enrolled students
  - "Generate from Timetable" tab added to Attendance GUI
  - CLI options 7-8 (Generate Registers, Pre-populate Register) in attendance menu
  - API endpoints: `POST /api/attendance/generate-registers`, `POST /api/attendance/sessions/from-slot`, `POST /api/attendance/sessions/<id>/populate`
- **College System: 2 new exception classes** — `FundingError`, `DestinationError`
- **College System: 7 new test fixtures** in conftest.py — `department_service`, `group_service`, `finance_service`, `student_support_service`, `funding_service`, `destination_service`, `room_service`

### Changed
- **College System: API blueprint count** — increased from 11 to 18 (7 new: funding, destinations, student_support, finance, departments, groups, rooms)
- **College System: Dashboard navigation** — added 5 new nav buttons (Funding & ILR, Destinations, Student Support, Finance, Departments) with role gates (38 total items)
- **College System: Admin CLI menu** — added 5 new module options (lowercase keys a-e) with case-sensitive handling
- **College System: GUI frame map** — registered 5 new frames in `CollegeApp._FRAME_MAP` (39 total frames)
- **College System: Timetable GUI** — refactored to use `ttk.Notebook` with Timetable and Rooms tabs
- **College System: Attendance GUI** — added 4th tab "Generate from Timetable" for staff/admin
- **College System: Dashboard GUI** — navigation section now uses a scrollable canvas with vertical scrollbar and mousewheel support so all 38 nav buttons are accessible regardless of window size

## [6.8.0] — 2026-02-27

### Added
- **College System: Admissions** — full application lifecycle management
  - `applications`, `inductions`, `withdrawals` tables
  - `AdmissionsService` with CRUD for applications (draft/submitted/conditional/unconditional/rejected/enrolled), inductions (with student JOIN), and withdrawals (with student JOIN and reason tracking)
  - GUI `AdmissionsFrame` with 3-tab Notebook (Applications, Inductions, Withdrawals) — treeviews with status filters, add/update dialogs
  - CLI `admissions_menu` with 7 options covering applications, inductions, and withdrawals
- **College System: Safeguarding** — DSL workflow for safeguarding concerns
  - `safeguarding_concerns` table with concern types (disclosure/observation/allegation/online/other), risk levels, DSL actions, and outcome tracking
  - `SafeguardingService` with report concern, list/get/update with student JOINs, dynamic status/type filtering
  - GUI `SafeguardingFrame` with 2-tab Notebook and red header (#c0392b) — Report Concern form and Concerns Log with filters
  - CLI `safeguarding_menu` with 4 options; restricted to staff+ roles
- **College System: Behaviour** — incident recording and conduct tracking
  - `behaviour_records` table with behaviour types (positive/negative/bullying/attendance/uniform) and severity levels
  - `BehaviourService` with record incident, list/get/update, count by type aggregate
  - GUI `BehaviourFrame` with 2-tab Notebook (Record Incident, Behaviour Log) — type/severity filters, detail pane
  - CLI `behaviour_menu` with 5 options including student summary
- **College System: Pastoral** — pastoral notes, wellbeing, and LAC records
  - `pastoral_notes`, `wellbeing_records`, `lac_records` tables
  - `PastoralService` with pastoral notes (add/list/get), wellbeing recording (with mood_score 1-10), LAC records (CRUD with PEP dates, social worker)
  - GUI `PastoralFrame` with 3-tab Notebook (Pastoral Notes, Wellbeing, LAC Records)
  - CLI `pastoral_menu` with 6 options across all three areas
- **College System: SEND/ALS** — special educational needs and interventions
  - `send_records` table with SEND type, EHCP flag, support plans; `interventions` table with targets and outcomes
  - `SENDService` with SEND records (CRUD, EHCP filtering), interventions (CRUD with target tracking)
  - GUI `SENDFrame` with 2-tab Notebook (SEND Records, Interventions)
  - CLI `send_menu` with 6 options for SEND records and interventions
- **College System: Exams** — exam entries, timetable, access arrangements, and results
  - `exam_entries`, `exam_timetable`, `exam_access`, `exam_results` tables
  - `ExamsService` with exam entries (CRUD), timetable slots, JCQ access arrangements (extra time, reader, scribe), and results recording
  - GUI `ExamsFrame` with 4-tab Notebook (Exam Entries, Exam Timetable, Access Arrangements, Results)
  - CLI `exams_menu` with 8 options covering all four areas
- **College System: Compliance/Funding** — ILR funding, resit tracking, and destinations
  - `funding_records`, `resit_tracking`, `destinations` tables
  - `ComplianceService` with funding records (ILR reference, status tracking), resit tracking (English & Maths), destination recording
  - GUI `ComplianceFrame` with 3-tab Notebook (Funding Records, Resit Tracking, Destinations)
  - CLI `compliance_menu` with 6 options; restricted to admin role
- **College System: Reports** — progress reports with per-student entries
  - `progress_reports` table with report periods and status (draft/open/closed); `report_entries` table with grades, effort scores, attendance, and comments
  - `ReportsService` with reports (CRUD), report entries (CRUD with student JOIN)
  - GUI `ReportsFrame` with 2-tab Notebook (Reports, Report Entries)
  - CLI `reports_menu` with 5 options; accessible to instructor+ roles
- **College System: Parents Evening** — evening events, time slots, and booking management
  - `parents_evenings`, `parents_evening_slots` tables
  - `ParentsEveningService` with evenings (CRUD), slot creation/listing, booking and cancellation
  - GUI `ParentsEveningFrame` with 2-tab Notebook (Evenings, Slots & Bookings)
  - CLI `parents_evening_menu` with 6 options; accessible to all roles including parents and students
- **College System: Careers** — careers activities (Gatsby benchmarks), UCAS records, and work experience
  - `careers_activities`, `ucas_records`, `work_experience` tables
  - `CareersService` with careers activities (Gatsby benchmark tracking), UCAS records (personal statement, predicted grades, reference), work experience (placement tracking with employer/supervisor)
  - GUI `CareersFrame` with 3-tab Notebook (Careers Activities, UCAS, Work Experience)
  - CLI `careers_menu` with 7 options; accessible to student+ roles
- **College System: Bursary** — bursary records and free meal eligibility
  - `bursary_records` table with bursary types and amounts; `meal_eligibility` table
  - `BursaryService` with bursary records (CRUD, status tracking), meal eligibility (set/check/list)
  - GUI `BursaryFrame` with 2-tab Notebook (Bursary Records, Free Meals)
  - CLI `bursary_menu` with 5 options; restricted to admin role
- **College System: Transport** — student transport arrangements
  - `transport_records` table with transport types (bus/train/walk/cycle/car/taxi), route, pass number, and pickup/dropoff
  - `TransportService` with CRUD and type filtering
  - GUI `TransportFrame` with treeview, type filter toolbar, add/edit/delete dialogs
  - CLI `transport_menu` with 4 options; restricted to admin role
- **College System: Assets** — device and equipment loan tracking
  - `asset_loans` table with asset type, serial number, condition tracking (new/good/fair/poor/damaged), checkout and return dates
  - `AssetsService` with loan creation, return processing, list with status filter, condition tracking
  - GUI `AssetsFrame` with treeview, status filter, return asset dialog
  - CLI `assets_menu` with 4 options; restricted to staff+ roles
- **College System: Library** — catalogue, loans, renewals, and overdue tracking
  - `library_items` table with catalogue data (ISBN, author, category, availability count); `library_loans` table with checkout/due/return dates and renewals
  - `LibraryService` with catalogue (CRUD, availability management), loans (checkout/return/renew), overdue tracking
  - GUI `LibraryFrame` with 3-tab Notebook (Catalogue, Loans, Overdue)
  - CLI `library_menu` with 7 options; accessible to student+ roles
- **College System: Staff HR** — staff HR record management
  - `staff_hr` table with department, position, employment type, contract dates, salary, DBS check dates
  - `StaffHRService` with CRUD, department listing, DBS check tracking
  - GUI `StaffHRFrame` with treeview and department filter
  - CLI `staff_hr_menu` with 5 options; restricted to admin role
- **College System: Cover/Substitution** — cover arrangement management
  - `cover_arrangements` table with absent staff, covering staff, date, period, subject, room, and notes
  - `CoverService` with CRUD, today's cover listing, staff cover count
  - GUI `CoverFrame` with 2-tab Notebook (Today's Cover, All Arrangements)
  - CLI `cover_menu` with 5 options; restricted to staff+ roles
- **College System: 16 new exception classes** — `AdmissionsError`, `SafeguardingError`, `BehaviourError`, `PastoralError`, `SENDError`, `ExamsError`, `ComplianceError`, `ReportsError`, `ParentsEveningError`, `CareersError`, `BursaryError`, `TransportError`, `AssetsError`, `LibraryError`, `StaffHRError`, `CoverError`

### Changed
- **College System: Dashboard navigation** — added 16 new nav buttons with role gates (33 total items in multi-row grid)
- **College System: Admin CLI menu** — added 16 new module options (keys H-Z)
- **College System: Instructor CLI menu** — added Reports, Exams, Behaviour, Pastoral, Parents Evening, Careers, Cover, Library options (keys C-K)
- **College System: Student CLI menu** — added Parents Evening, Careers, Library options (keys B-D)
- **College System: Parent CLI menu** — added Parents Evening option (key 6)
- **College System: GUI frame map** — registered 16 new frames in `CollegeApp._FRAME_MAP` (34 total frames)

## [6.7.0] — 2026-02-27

### Added
- **College System: To-Do List** — personal task management for all users
  - `todo_items` table with priority (low/medium/high), due date, and completion tracking
  - `TodoService` with create, list (sorted by priority + due date), toggle complete, update, and delete (ownership-verified)
  - GUI `TodoFrame` with treeview, priority/completion filters, add/edit dialog, toggle complete and delete buttons
  - CLI `todo_menu` with view, add, mark complete/incomplete, edit, and delete options
- **College System: Calendar** — event management with monthly grid view
  - `calendar_events` table with event types (personal/academic/college/deadline), time range, and all-day flag
  - `CalendarService` with create, list by month/year, get events for date, update, and delete (ownership or admin verified)
  - GUI `CalendarFrame` with monthly grid navigation (prev/next/today), colour-coded cells (today green, events amber), click-to-view detail pane, and add event dialog
  - CLI `calendar_menu` with view month (ASCII calendar with event markers), view day, add/edit/delete event
  - Admin/staff can create "college" type events visible to all users
- **College System: First Aid** — incident reporting and tracking for staff
  - `first_aid_incidents` table with severity (minor/moderate/severe/emergency), status (open/treated/referred/closed), treatment, and parent notification tracking
  - `FirstAidService` with report incident, list/filter by status, get with student name, update treatment/status, and get student history
  - GUI `FirstAidFrame` with two-tab Notebook: Report (form with student lookup, severity, location, description) and Log (treeview with status filter, detail pane, inline update controls)
  - CLI `first_aid_menu` with report, list, view details, and update incident
  - Restricted to staff+ roles in dashboard navigation
- **College System: Helpdesk** — ticket system with threaded responses
  - `helpdesk_tickets` table with category (general/it/facilities/academic/finance/other), priority (low/medium/high/urgent), status (open/in_progress/resolved/closed), and assignment tracking
  - `helpdesk_responses` table for threaded ticket conversations
  - `HelpdeskService` with create ticket, list (user-scoped or all), get with joined responses and display names, update status/priority/assignment, add response, and assign
  - GUI `HelpdeskFrame` with two-tab Notebook: My Tickets (treeview, new ticket dialog, detail pane with reply entry) and All Tickets (admin/staff only, status filter, update status, reply)
  - CLI `helpdesk_menu` with my tickets, create, view with responses, reply, all tickets (staff), and update status (staff)
- **College System: Parent Portal** — parent access to child academic data
  - `parent_links` table with parent-student relationship tracking and unique constraint
  - `ParentService` with link/unlink parent, get linked students, get child grades/attendance/timetable (all link-verified), get all parents, and admin link management
  - GUI `ParentFrame` with role-adaptive tabs: parent role sees Overview/Grades/Attendance/Timetable tabs with child selector dropdown; admin role sees Manage Links tab with link/unlink controls and treeview
  - CLI with role dispatch: parent gets view children/grades/attendance/timetable; admin gets list/link/unlink management
  - New `parent_menu_main` in CLI for parent-role users with portal, messages, to-do, calendar, and settings
- **College System: Settings** — user preferences and system configuration
  - `user_settings` table with per-user key-value pairs (theme, notifications, language, items per page)
  - `system_settings` table with admin-managed key-value pairs (college name, academic year, default capacity)
  - `SettingsService` with get/set user settings, get/set system settings (all using INSERT OR REPLACE via ON CONFLICT)
  - GUI `SettingsFrame` with two-tab Notebook: User Preferences (theme, notifications, language, items per page) and System Settings (admin only, college name, academic year, default capacity)
  - CLI `settings_menu` with view settings, change theme, toggle notifications, and system settings (admin sub-menu)
- **College System: Parent role** — new `parent` role at hierarchy level 30 (between student at 25 and instructor at 50)
  - Added to `ROLE_HIERARCHY` in role manager and seeded in `roles` table
  - Parent role handling in CLI `main()` dispatches to `parent_menu_main`
  - Dashboard shows Parent Portal button for parent+ roles
- **College System: 6 new exception classes** — `TodoError`, `CalendarError`, `FirstAidError`, `HelpdeskError`, `ParentPortalError`, `SettingsError`

### Changed
- **College System: Attendance GUI rewrite** — replaced flat form layout with tabbed Notebook interface
  - **Take Attendance tab** (staff/instructor): course dropdown selector (not raw code entry), date picker with today pre-filled, topic entry, "Create Session & Load Roster" button that creates a session and shows a scrollable roster grid with radio buttons (Present/Absent/Late/Excused, default Present), "Submit All" button for bulk recording — hidden for students
  - **View Records tab** (all roles): cascading course dropdown → session dropdown (auto-populated on course selection), treeview of attendance records that auto-loads on session selection
  - **Reports tab** (all roles): student ID + course code entry with summary display showing total sessions, present, absent, late, excused, and attendance rate with colour coding (green >=90%, amber >=75%, red <75%)
- **College System: Dashboard multi-row navigation** — button grid now wraps at 5 columns per row to accommodate 17 navigation items without overflow
- **College System: Admin CLI menu** — added To-Do List, Calendar, First Aid, Helpdesk, Parent Portal, and Settings options (keys A-F)
- **College System: Instructor CLI menu** — added To-Do List, Calendar, Helpdesk, and Settings options (keys 8-9, A-B)
- **College System: Student CLI menu** — added To-Do List, Calendar, Helpdesk, and Settings options (keys 7-9, A)

## [6.6.0] — 2026-02-27

### Added
- **College System: Role-based access control** — differentiated permissions for admin, staff, instructor, and student roles
  - **Dashboard nav gates**: Students, Enrollment restricted to staff+; Grades, Attendance restricted to instructor+; Staff restricted to admin
  - **CourseFrame**: Add/Edit/Delete buttons hidden for students (view-only access)
  - **TimetableFrame**: Add/Delete Slot form hidden for non-admin; Generate button remains admin-only
  - **AssignmentFrame**: Create and Grade tabs hidden for students; Submit tab hidden for non-students
  - **Course CLI**: Add Course, Manage Prerequisites, Delete Course options hidden for instructors (view/update/roster only)
  - **Timetable CLI**: Add/Update/Delete Slot and Generate options hidden for instructors (view and My Timetable only)

## [6.5.0] — 2026-02-27

### Added
- **College System: Structured logging** — Python `logging` throughout the entire college system (81 log calls across 24 files)
  - `core/logs.py` with `configure_logging()` — file handler (`logs/app.log`) at INFO level, console handler at WARNING level
  - Logging automatically initialized from all three entry points: GUI (`main_gui.main`), CLI (`cli_main.main`), API (`api_server.run_server`)
  - **Infrastructure layer**: database connections/errors, schema init, connection pool lifecycle, query failures
  - **Auth layer**: login success/failure, account lockout, MFA setup/verify/disable, session lifecycle, user creation, password changes, role assignment
  - **Service layer**: all CRUD operations across all 10 domain services (students, courses, enrollment, grades, attendance, timetable, assignments, notifications, messaging, staff)
  - **API layer**: JWT token generation, auth failures (missing/expired/invalid tokens), access denied, error handler logging for validation/auth/database/system errors
  - **GUI/CLI layer**: login success/failure, logout, application startup

## [6.4.0] — 2026-02-27

### Added
- **College System: Internal Messaging** — full two-way user-to-user messaging system
  - `messages` table with sender/recipient, subject, body, read status, and per-user soft-delete flags
  - `MessageService` with send, inbox, sent, get, mark read, count unread, soft-delete, and recipient picker
  - Display name resolution via COALESCE across staff, students, and username fallback
  - GUI `MessageFrame` with inbox/sent toggle, treeview, detail pane, and delete button
  - GUI `_ComposeDialog` modal with recipient combobox, subject entry, and multi-line body
  - CLI `messaging_menu` with inbox, sent, read, compose, and delete options
  - Dashboard navigation: "Messages" button available to all roles (student and above)
  - Messaging menu added to all three CLI role menus (admin, instructor, student)
  - Soft-delete on user removal: deleting a student or staff member marks their messages as deleted for that user while preserving them for the other party
- **College System: New exception** — `MessageError(CollegeSystemError)`

## [6.3.1] — 2026-02-27

### Fixed
- **Restaurant test imports** — corrected 7 test files that imported submodules from `connection.py` (a file) instead of from the `operations` package where `audit`, `backup`, `exports`, `financials`, `forecasting`, and `connection` modules actually live
- **Health services re-exports** — added missing re-exports (`_sqlite_main_db_path`, `backup_before_operation`, `cipher_suite`, `encrypt_sensitive_data`, `decrypt_sensitive_data`, `truthy`, and 5 report generators) to `health/services/__init__.py` so the `miscellaneous.py` shim can resolve them
- **Logs shim re-export** — added `LOG_MANAGEMENT_AVAILABLE` to `modules/shared/utils/logs.py` backward-compatibility shim

## [6.3.0] — 2026-02-26

### Added
- **College System: Timetable Management** — schedule course slots with conflict detection
  - `timetable_slots` table with day-of-week, start/end times, room, and instructor
  - `TimetableService` with room and instructor conflict checking, student timetable via enrollments
  - CLI menu (add/view/update/delete slots, "My Timetable" for students)
  - GUI frame with form, treeview, and "My Timetable" button
  - API routes: `POST/PUT/DELETE /api/timetable/slots`, `GET /api/timetable/course/<id>`, `GET /api/timetable/student/<id>`, `GET /api/timetable/room/<room>`, `POST /api/timetable/conflicts`
- **College System: Assignment Management** — create, submit, and grade assignments
  - `assignments` and `submissions` tables with late-detection and configurable late-submission policy
  - `AssignmentService` with enrollment validation, auto-late-detection, and grading
  - CLI menu (create/list/submit/grade assignments, "My Submissions" for students)
  - GUI frame with tabbed interface (Create, Assignments, Submit, Grade)
  - API routes: CRUD at `/api/assignments`, `POST /<id>/submit`, `GET /<id>/submissions`, `POST /submissions/<id>/grade`, `GET /student/<pk>`
- **College System: Notifications** — in-app notification system with read/unread tracking
  - `notifications` table with type (info/success/warning/alert) and read status
  - `NotificationService` with send, bulk send, count unread, mark read/all, and delete old
  - Notification hooks: enrollment and grade recording automatically notify students
  - CLI menu (view/filter/mark read notifications)
  - GUI frame with treeview, unread filter toggle, detail pane, and mark read buttons
  - API routes: `GET /api/notifications`, `GET /count`, `POST /<id>/read`, `POST /read-all`, `POST /send`
- **College System: Multi-Factor Authentication (MFA)** — TOTP-based MFA with recovery codes
  - `mfa_secrets` and `mfa_recovery_codes` tables; secrets stored as TOTP base32, recovery codes SHA-256 hashed
  - `MFAService` using `pyotp` with 1-step window tolerance and 10 recovery codes in `XXXX-XXXX` format
  - Auth integration: `login()` returns `mfa_required` when MFA enabled; `verify_mfa()` completes login via TOTP or recovery code
  - CLI: MFA prompt during login, MFA Settings menu (setup/disable/view recovery count)
  - GUI: `MFAVerifyDialog` shown during login, `MFASettingsFrame` for setup/disable with provisioning URI display
  - API routes: `POST /api/auth/mfa/verify` (with short-lived mfa_token), `POST /setup`, `POST /disable`, `GET /status`, `GET /recovery-count`
  - `mfa_token_required` decorator for MFA verification endpoint
- **College System: New validators** — `validate_day_of_week()`, `validate_time()`, `validate_time_range()` in `validators.py`
- **College System: New exceptions** — `TimetableError`, `AssignmentError`, `NotificationError`, `MFAError`
- **College System: 27 new tests** — 7 timetable, 7 assignment, 6 notification, 7 MFA (111 total, all passing)
- Added `pyotp>=2.9` dependency to `requirements.txt` and `pyproject.toml`

### Fixed
- **College System: broken import in `system_routes.py`** — `from college_system import __version__` failed when launched via `run.py`; fixed to `from education_system.college_system import __version__`

## [6.2.0] — 2026-02-26

### Added
- **Cross-system switching** — switch between University and College systems without restarting
  - College CLI: "Switch to GUI" and "Switch to University System" options in all role menus (admin, instructor, student)
  - College GUI: "Switch to CLI" and "Switch to University System" in the File menu
  - University CLI: "Switch to College System" option in the Infrastructure & System menu
  - University GUI: "College System" button in the header control bar
  - `education_system/switch.py` shared state module coordinates transitions via `request_switch()` / `consume()`
  - `run.py` dispatch loop automatically re-launches the target system/mode after a switch

## [6.1.0] — 2026-02-26

### Changed
- **Unified launcher** — rewrote `run.py` as a two-step launcher: select mode (CLI/GUI/API/Test), then select system (University/College)
  - CLI mode: text menus for both mode and system selection
  - GUI mode: Tkinter system-picker window with styled University (blue) and College (green) buttons
  - Full CLI flag support to skip menus: `python run.py --cli --university`, `python run.py --gui --college`, etc.
  - Hybrid usage supported — pass one flag and pick the rest interactively

### Removed
- `college_run.py` — consolidated into `run.py`; use `python run.py --college` instead

## [6.0.0] — 2026-02-26

### Added
- **College Management System** — fully independent system at `education_system/college_system/` with the same 4-layer architecture (core, infrastructure, modules, api) and tech stack (Tkinter, Flask, SQLite, bcrypt)
  - 5 domain modules: Students, Courses, Enrollment, Grades, Attendance
  - Service-first design — all business logic in service classes, never in CLI/GUI/API
  - Auto-waitlist enrollment: `enroll_student()` auto-adds to waitlist when a course is full; dropping auto-promotes the next waitlisted student
  - Credit-weighted GPA calculation, score-to-letter conversion, full transcript generation
  - Circular prerequisite detection in the course prerequisite graph
  - CLI interface with role-based menus (admin, instructor, student)
  - Tkinter GUI with login, dashboard, and 5 domain frames (Treeview + CRUD dialogs)
  - Flask REST API with JWT auth (`@token_required`, `@role_required`), 7 route blueprints, pagination, error handlers
  - Auth system: bcrypt password hashing, session tokens for CLI/GUI, JWT for API, RBAC hierarchy (admin > staff > instructor > student), account lockout after 5 failed attempts
  - 84 tests covering all services, auth, and API endpoints
  - Default admin credentials: `admin` / `Admin@123`
  - Only 4 external dependencies: flask, flask-cors, bcrypt, PyJWT

### Changed
- **Monorepo restructure** — created `education_system/` top-level package and moved both systems into it
  - `university_system/` → `education_system/university_system/`
  - `college_system/` → `education_system/college_system/`
  - Updated all Python imports across 2,570 files (`from X.` → `from education_system.X.`)
  - Updated `run.py`, `pyproject.toml`, `security_scan.sh`, and test path configs
