# University Management System

A comprehensive higher-education management platform built with Python, tkinter (GUI), Flask (REST API), and SQLite. Provides CLI, GUI, API, and web portal interfaces with 51+ domain modules organised in a 4-layer Domain-Driven Design architecture.

---

## Key Features

- Student lifecycle management (admissions through alumni)
- Academic modules: courses, enrollment, grades, attendance, timetable, exams, dissertations
- Finance: invoicing, payments, scholarships, bursaries
- Health and wellbeing services
- Student housing and accommodation
- Commerce: campus shop, marketplace
- HR and staff management
- Student services: careers, counselling, disability support (23 modules)
- Role-based portals: student, staff, instructor, parent
- Digital library and document management
- Analytics and reporting dashboards

---

## Directory Layout

```
university_system/
    core/              # Application core, config, database connections
    modules/           # 51+ domain modules (service + GUI + CLI per module)
    infrastructure/    # Auth wrappers, DB, email, integrations
    templates/         # Web portal HTML templates
    data/              # SQLite databases, config, uploads
    tests/             # Unit and integration tests
    scripts/           # Maintenance and migration scripts
    utils/             # Shared utility functions
    extras/            # Optional add-ons
    extensions/        # Plugin system
    digital_library/   # Library content management
```

---

## Entry Points

- **GUI:** `python run.py --university --gui` (from repository root)
- **CLI:** `python run.py --university --cli`
- **API:** `python run.py --university --api`

---

## Documentation

Full documentation is available at `docs/university_system/`.
