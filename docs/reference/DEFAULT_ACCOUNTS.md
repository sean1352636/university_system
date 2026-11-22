# Default Accounts

Pre-seeded development credentials across all **twelve** systems — Nursery, Primary School, Secondary School, Sixth Form College, FE College, Apprenticeships, University, Special Education (SEND), Adult Education, Alternative Provision, Training Provider and Local Authority Education. There are 36 accounts, defined in `_DEFAULT_ACCOUNTS` in `src/education_system/platform/identity/auth/schema.py`. **Change every password before deploying to any non-development environment.** After 3 failed login attempts an account is locked for 15 minutes — sign in as the system admin and clear the lockout from the admin panel.

These demo accounts are created **only** when `EDU_DEV_SEED=true` — including on a fresh `auth.db`. Without the flag they are never seeded, so a fresh production database starts empty. To bootstrap a production deployment, set `EDU_INITIAL_ADMIN_USER` and `EDU_INITIAL_ADMIN_PASSWORD` (password ≥12 chars) to create a single strong admin with access to all ten systems; leave `EDU_DEV_SEED` unset. Never enable `EDU_DEV_SEED` on a production or internet-facing deployment.

## Superadmin (cross-system)

| Username | Password | Role |
|----------|----------|------|
| `superadmin` | `SuperAdmin@123` | Admin across **all twelve** systems (nursery, primary, secondary, sixth form, FE college, apprenticeships, university, special education, adult education, alternative provision, training provider, local authority education) |

## Nursery

| Username | Password | Role |
|----------|----------|------|
| `admin4` | `admin1234` | Admin |

## Primary School

| Username | Password | Role |
|----------|----------|------|
| `admin3` | `admin1234` | Admin |
| `staff3` | `staff1234` | Teacher |
| `student3` | `student1234` | Student |
| `parent3` | `parent1234` | Parent |

## Secondary School

| Username | Password | Role |
|----------|----------|------|
| `admin2` | `admin1234` | Admin |
| `staff2` | `staff1234` | Teacher |
| `student2` | `student1234` | Student |
| `parent2` | `parent1234` | Parent |

## Sixth Form College

| Username | Password | Role |
|----------|----------|------|
| `admin1` | `admin1234` | Admin |
| `staff1` | `staff1234` | Teacher |
| `student1` | `student1234` | Student |
| `parent1` | `parent1234` | Parent |

## FE College

These accounts join to their FE College staff or learner record by email address, so their emails must match the records its demo seed creates.

| Username | Password | Role |
|----------|----------|------|
| `admin6` | `admin1234` | Admin |
| `lecturer1` | `lecturer1234` | Teacher |
| `learner1` | `learner1234` | Student |

## Special Education (SEND)

Added 2026-11-08 when SEND was linked to the shared login. SEND is a staff tool for now, so it has only the `admin` and `staff` roles (no learner or parent accounts). Staff can do everything except delete records.

| Username | Password | Role |
|----------|----------|------|
| `admin7` | `admin1234` | Admin |
| `senco1` | `senco1234` | Staff (SENCO) |

## Adult Education

Added 2026-11-08 when Adult Education was linked to the shared login. Like SEND it is staff-only for now (no learner portal), so it has only the `admin` and `staff` roles. Staff can do everything except delete records. The staff account is `aetutor1` because `tutor1` is the Apprenticeships tutor.

| Username | Password | Role |
|----------|----------|------|
| `admin8` | `admin1234` | Admin |
| `aetutor1` | `aetutor1234` | Staff (tutor) |

## Alternative Provision

Added 2026-11-08 when Alternative Provision was linked to the shared login. Staff-only for now (no pupil or parent screens), so it has only the `admin` and `staff` roles. Staff can do everything except delete records.

| Username | Password | Role |
|----------|----------|------|
| `admin9` | `admin1234` | Admin |
| `keyworker1` | `keyworker1234` | Staff (key worker) |

## Training Provider

Added 2026-11-08 when Training Provider was linked to the shared login. Staff-only for now (no learner or client portal), so it has only the `admin` and `staff` roles. Staff can do everything except delete records. The staff account is `tptrainer1` so that a plain `trainer1` stays free.

| Username | Password | Role |
|----------|----------|------|
| `admin10` | `admin1234` | Admin |
| `tptrainer1` | `tptrainer1234` | Staff (trainer) |

## Local Authority Education

Added 2026-11-09 when Local Authority Education was linked to the shared login. Council staff only for now (no parent or school portal), so it has only the `admin` and `staff` roles. Staff can do everything except delete records.

| Username | Password | Role |
|----------|----------|------|
| `admin11` | `admin1234` | Admin |
| `laofficer1` | `laofficer1234` | Staff (education officer) |

## Removed placeholder systems

`admin7`–`admin11` (Adult Education, Alternative Provision, Special Education,
Training Provider, Local Authority Education) were created on 2026-11-06 and
removed the same day when those five systems were taken out (code in `remove/`). All five were
later rebuilt and linked again (2026-11-08/09), reusing the `admin7`–`admin11` names (above). Their accounts, their
system grants and superadmin's grants to them were deleted from the live
auth.db; backup taken first at
`var/backups/maintenance/auth-before-park-placeholders-20261106.db`.

## Apprenticeships

| Username | Password | Role |
|----------|----------|------|
| `admin5` | `admin1234` | Admin |
| `tutor1` | `tutor1234` | Staff (tutor) |
| `apprentice1` | `apprentice1234` | Apprentice |
| `employer1` | `employer1234` | Employer |
| `assessor1` | `assessor1234` | End-point assessor |

## University

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin |
| `staff` | `staff123` | Staff |
| `S12345` | `student123` | Student |
| `parent` | `parent123` | Parent |
