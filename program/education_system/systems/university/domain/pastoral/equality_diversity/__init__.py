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

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "EqualityDiversityGUI": "education_system.systems.university.interfaces.gui.pastoral.equality_diversity",
    "open_equality_diversity_gui": "education_system.systems.university.interfaces.gui.pastoral.equality_diversity",
    "submit_anonymous_record": "education_system.systems.university.interfaces.gui.pastoral.equality_diversity",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
