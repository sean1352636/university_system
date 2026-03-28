# Education System

The `education_system` package is the top-level Python package for the Education System platform. It contains four independent subsystems and a shared module layer that provides cross-cutting concerns such as authentication, API, and data portability.

For full documentation, installation instructions, and usage guides, see the [root README](../README.md).

---

## Subsystems

| Package | Description |
|---------|-------------|
| `university_system/` | University Management System -- higher education (51+ domain modules) |
| `college_system/` | Sixth Form College Management System -- FE 16-19 (112 domain modules) |
| `secondary_school/` | Secondary School Management System -- Years 7-11 (50 domain modules) |
| `primary_school/` | Primary School Management System -- Reception-Year 6 (46 domain modules) |
| `shared/` | Shared modules -- unified auth, GUI, API, data portability |

---

## Directory Layout

```
education_system/
    __init__.py
    switch.py                  # Cross-system switching logic
    university_system/         # University (HE)
    college_system/            # Sixth Form College (FE 16-19)
    secondary_school/          # Secondary School (KS3/KS4)
    primary_school/            # Primary School (EYFS/KS1/KS2)
    shared/                    # Shared auth, GUI, API, utilities
    docs/                      # Per-system documentation
    data/                      # Shared data files
```

---

## Key Entry Point

All four systems are launched via the unified launcher at the repository root:

```bash
python run.py                    # Interactive selection
python run.py --university --gui # Direct launch
```

See each subsystem's README for system-specific details.
