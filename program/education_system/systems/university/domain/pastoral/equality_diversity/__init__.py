from education_system.systems.university.interfaces.gui.pastoral.equality_diversity import (
    EqualityDiversityGUI,
    open_equality_diversity_gui,
    submit_anonymous_record,
)
from education_system.systems.university.domain.pastoral.equality_diversity import (
    access,
    integrations,
    reports_engine,
    schema,
)

__all__ = [
    "EqualityDiversityGUI",
    "open_equality_diversity_gui",
    "submit_anonymous_record",
    "access",
    "integrations",
    "reports_engine",
    "schema",
]
