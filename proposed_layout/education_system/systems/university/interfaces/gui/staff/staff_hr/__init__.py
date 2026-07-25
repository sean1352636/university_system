"""
Staff HR GUI Components.

Sub-feature GUI classes (Leave, Time & Attendance, Payroll, …) are not
imported eagerly — doing so cost ~11 s on first touch of this package.
Import them directly from their submodules when needed, e.g.:

    from education_system.systems.university.interfaces.gui.staff.staff_hr.payroll_gui import PayrollGUI
"""

from education_system.systems.university.interfaces.gui.staff.staff_hr.staff_hr_gui import StaffHRGUI

__all__ = ['StaffHRGUI']
