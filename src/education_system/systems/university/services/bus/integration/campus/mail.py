"""Campus mail integration API."""
from education_system.systems.university.services.bus.jobs.overdue_mail import sweep_overdue_mail

__all__ = ["sweep_overdue_mail"]
