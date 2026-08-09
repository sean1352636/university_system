"""FE College (Further Education) management system.

A Further Education college is distinct from the Sixth Form College system in
this repository: it enrols 16+ *and* adult learners onto vocational
qualifications (BTEC, T-Level, NVQ, Access to HE, Functional Skills) rather
than a two-year A-Level programme, and its funding, attendance and achievement
reporting follow the ESFA study-programme rules rather than school census.

Unlike the other systems, this package is laid out in strict 4-layer DDD:

    domain/         pure models and rules, no I/O
    infrastructure/ SQLite persistence (schema + repositories)
    services/       use-case orchestration over the repositories
    interfaces/     delivery — gui/, cli/, api/, portals/

Entry points are :mod:`gui_main` and :mod:`cli_main` at the package root,
matching the launcher's convention for every other system.
"""

SYSTEM_NAME = "FE College System"
SYSTEM_SLUG = "fe_college"

__all__ = ["SYSTEM_NAME", "SYSTEM_SLUG"]
