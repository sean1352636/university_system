# Sixth Form College Management System

A further education (16-19) college management platform built with Python, tkinter (GUI), Flask (REST API), and SQLite. Provides CLI, GUI, and API interfaces with 112 domain modules covering the full breadth of FE college operations.

---

## Key Features

- Courses, enrollment, grades, attendance, and timetable management
- Safeguarding, SEND, pastoral care, and behaviour tracking
- T-levels and apprenticeship programme management
- UCAS application tracking and destinations data
- Bursary and funding administration
- Staff HR, CPD, and cover management
- Admissions and compliance (GDPR, quality assurance)
- Finance, departments, and student support services
- Messaging, notifications, calendar, and parents' evening
- Exams management and reporting

---

## Directory Layout

```
college_system/
    core/              # Application core, config, database connections
    modules/           # 112 domain modules (service + GUI + CLI per module)
    infrastructure/    # Auth wrappers, DB, integrations
    data/              # SQLite databases, config, uploads
    tests/             # Unit and integration tests
    logs/              # Application logs
```

---

## Entry Points

- **GUI:** `python run.py --college --gui` (from repository root)
- **CLI:** `python run.py --college --cli`
- **API:** `python run.py --college --api`

---

## Documentation

Full documentation is available at `education_system/docs/college_system/`.
