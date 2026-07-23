# Default Accounts

Pre-seeded development credentials across all **five** systems — Nursery, Primary School, Secondary School, Sixth Form College, and University. **Change every password before deploying to any non-development environment.** After 5 failed login attempts an account is locked for 15 minutes — sign in as the system admin and clear the lockout from the admin panel.

Accounts are only auto-created on a fresh `auth.db`, or when `EDU_DEV_SEED=true` on an existing one. Set `EDU_DEV_SEED=false` in production to prevent demo-account seeding.

## Superadmin (cross-system)

| Username | Password | Role |
|----------|----------|------|
| `superadmin` | `SuperAdmin@123` | Admin across **all five** systems (nursery, primary, school, college, university) |

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

## University

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin |
| `staff` | `staff123` | Staff |
| `S12345` | `student123` | Student |
| `parent` | `parent123` | Parent |
