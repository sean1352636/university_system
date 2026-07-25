"""Domain package: calendar (school events).

This package is the school events calendar — it shadows Python's
stdlib ``calendar`` module name, so reach for ``import calendar as
_stdcalendar`` if you need the stdlib alongside.
"""
from education_system.systems.sixth_form.domain.academics.calendar.calendar import *  # noqa: F401,F403
