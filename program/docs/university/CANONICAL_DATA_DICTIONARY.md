# Canonical University Data Dictionary

These records are the only supported write models for the
applicant-to-enrolment core. Legacy tables remain read-compatible during the
deprecation window but must not receive new writes.

## Applicant and application

| Record | Identity | Required fields | Lifecycle |
|---|---|---|---|
| `admission_prospects` | `prospect_id` | legal name, email | enquiry/contact only |
| `admission_applications` | `application_id` | prospect, application type, entry year | submitted → review → offer → accepted → ready-to-enrol → enrolled |
| `admission_application_choices` | `choice_id` | application, programme, rank | active/accepted/declined |
| `admission_requirements` | `requirement_id` | application, type, description | outstanding/verified/rejected |
| `admission_conditions` | `condition_id` | application, type, description | outstanding/satisfied/waived |

An applicant is not a student. `converted_student_id` is populated exactly
once by guarded conversion after every required check and condition succeeds.

## Student

`students.student_id` identifies a person in the university student-record
domain. Identity, contact and lifecycle corrections are effective-dated and
audited. Current summary fields on `students` are projections; authoritative
registration history is not overwritten.

## Programme registration

`programme_registrations.registration_id` represents one student's registration
against a programme occurrence, academic year and immutable regulation
version. Money values never live on this record.

Required semantic fields:

- `student_id`, `programme_code`, `academic_year`, `occurrence_code`
- `mode_of_study`, `status`, `effective_from`
- `regulation_version_id` once governance data is assigned

## Module enrolment

`module_enrolments.module_enrolment_id` represents an attempt at a module within
one programme registration. The uniqueness key is student, module, year,
teaching period and attempt number.

Legacy `student_modules` and `enrollments` are read-only compatibility sources.

## Attendance event

`attendance_events.attendance_event_id` is append-only. Corrections point to
the superseded event rather than rewriting history. Status is one of `present`,
`late`, `absent`, `authorised` or `unknown`.

## Charge, payment and allocation

- `student_charges` records an immutable amount due in integer minor currency
  units and has an idempotent `(source_type, source_id)` origin.
- `student_payments` records provider receipts with unique provider reference
  and idempotency key.
- `payment_allocations` applies part or all of a payment to a charge.

Amounts use integer minor units; floating-point currency is prohibited.
Reversals create compensating records rather than deleting ledger history.

## Ownership and compatibility

| Canonical record | Write owner | Legacy source |
|---|---|---|
| Application | admissions lifecycle service | direct CRM status updates |
| Programme registration | student lifecycle service | `enrollments` |
| Module enrolment | enrolment service | `student_modules` |
| Attendance event | attendance service | `attendance_records`, `attendance` |
| Charge/payment/allocation | finance ledger | `payments`, `financial_transactions` |

Compatibility views are named `legacy_*_compat`. Their use is logged and
measured. Removal requires 30 consecutive days with no production reads and a
successful reconciliation report.

