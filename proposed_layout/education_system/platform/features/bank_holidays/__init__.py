"""Shared bank-holiday calendar.

Used by absence/attendance/timetable code that needs to know which dates are
non-working days. ``BankHolidayService`` is the public surface; the service
auto-seeds the next two years of UK England-and-Wales holidays on first run.
"""

from education_system.platform.features.bank_holidays.service import (
    BankHolidayService,
    DEFAULT_REGION,
)

__all__ = ["BankHolidayService", "DEFAULT_REGION"]
