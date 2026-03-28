# Secondary School Management System

A secondary school (Years 7-11) management platform built with Python, tkinter (GUI), and SQLite. Provides CLI and GUI interfaces with 50 domain modules covering KS3 and KS4 curricula with GCSE grades 9-1.

---

## Key Features

- **Academics:** students, subjects, enrollment, grades, attendance, timetable, homework, exams, progress tracking, interventions, reports
- **Pastoral care:** behaviour, detentions, exclusions, rewards, pastoral support, safeguarding, SEND
- **Staff:** HR, CPD, cover management, staff directory
- **Admin:** users, settings, admissions, finance, data export, audit log, policies, documents
- **Student life:** clubs, meals, transport, trips, careers, library, medical, form groups, consent
- **Facilities:** room booking, assets, seating plans, visitors, incidents
- **Communication:** email, notifications, announcements, calendar, communication log, parents' evening

---

## Directory Layout

```
secondary_school/
    core/              # Application core, config, database connections
    modules/           # 50 domain modules organised by category
    infrastructure/    # Auth wrappers, DB connections
    cli/               # CLI interface
    data/              # SQLite databases, config
    tests/             # Unit and integration tests
    logs/              # Application logs
    main_gui.py        # GUI entry point
```

---

## Entry Points

- **GUI:** `python run.py --school --gui` (from repository root)
- **CLI:** `python run.py --school --cli`

---

## Documentation

Full documentation is available at `education_system/docs/secondary_school/`.
