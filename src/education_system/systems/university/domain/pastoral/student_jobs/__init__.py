"""
Student Job Board Module

On-campus employment management system with job postings, work-study tracking,
skill-based matching, and performance management.
"""

from education_system.systems.university.domain.pastoral.student_jobs.services.job_service import (
    JobPostingManager,
    JobApplicationManager,
    EmploymentManager,
    WorkHoursManager,
    SkillMatchingManager,
    PerformanceManager
)

from education_system.systems.university.interfaces.cli.pastoral.student_jobs.jobs_cli import (
    StudentJobsCLI
)


__all__ = [
    # Service layer
    'JobPostingManager',
    'JobApplicationManager',
    'EmploymentManager',
    'WorkHoursManager',
    'SkillMatchingManager',
    'PerformanceManager',
    # Interface layer
    'StudentJobsCLI',
    'StudentJobsGUI'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "StudentJobsGUI": "education_system.systems.university.interfaces.gui.pastoral.student_jobs.jobs_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
