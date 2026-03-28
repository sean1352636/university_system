# Primary School Management System

A primary school (Reception-Year 6) management platform built with Python, tkinter (GUI), and SQLite. Provides CLI and GUI interfaces with 46 domain modules covering EYFS, KS1, and KS2 curricula.

---

## Key Features

- **Academics:** pupils, subjects, classes, assessment, attendance, timetable, homework, SATs, phonics, reading records, progress tracking
- **Pastoral care:** behaviour, rewards, safeguarding, SEND, pastoral support
- **Staff:** HR, CPD, cover management, staff directory
- **Admin:** users, settings, admissions, finance, data export, audit log, policies, documents
- **Pupil life:** clubs, meals, transport, trips, library, medical, class groups, consent
- **Communication:** email, notifications, announcements, calendar, parents' evening, communication log
- **Facilities:** room booking, assets, visitors, incidents

Assessment levels: Emerging, Developing, Expected, Greater Depth.

Year groups: Reception, Year 1-6. Key stages: EYFS, KS1 (Y1-2), KS2 (Y3-6).

---

## Directory Layout

```
primary_school/
    core/              # Application core, config, database connections
    modules/           # 46 domain modules organised by category
    infrastructure/    # Auth wrappers, DB connections
    cli/               # CLI interface
    data/              # SQLite databases (primary_school.db), config
    tests/             # Unit and integration tests
    logs/              # Application logs
    main_gui.py        # GUI entry point
```

---

## Entry Points

- **GUI:** `python run.py --primary --gui` (from repository root)
- **CLI:** `python run.py --primary --cli`

---

## Documentation

Full documentation is available at `education_system/docs/primary_school/`.
