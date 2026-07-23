"""
Staff HR GUI Components.

Sub-feature GUI classes (Leave, Time & Attendance, Payroll, …) are not
imported eagerly — doing so cost ~11 s on first touch of this package.
Import them directly from their submodules when needed, e.g.:

    from education_system.post_18.university_system.modules.domain.operations.staff_hr.gui.payroll_gui import PayrollGUI
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.gui.staff_hr_gui import StaffHRGUI

__all__ = ['StaffHRGUI']
