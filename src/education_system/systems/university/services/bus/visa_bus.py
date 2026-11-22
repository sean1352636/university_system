"""Port onto the Governance visa-sponsorship window for other slices.

Learners' Create Student opens the full visa window for a student who is
still being entered; the slice rules keep it from importing Governance's
GUI directly, so it comes through here (as ``risks_panel`` does for the
risk register).

Usage::

    from education_system.systems.university.services.bus import visa_bus
    visa_bus.open_new_student_visa(dialog, intake={"name": ..., "course": ...},
                                   on_save=lambda profile: ...)
"""

from __future__ import annotations


def open_new_student_visa(parent, *, intake: dict, on_save, on_close=None):
    """Open the visa window in new-student mode and return its Toplevel.

    ``on_save(profile)`` gets the entered visa profile (the keys of
    ``visa_service.VisaRecord`` except ``student_id``) when the user saves;
    the window then closes. ``on_close()`` runs whenever the window goes,
    saved or not, after ``on_save``.
    """
    from education_system.systems.university.domains.governance.interfaces.gui.compliance.international_compliance.visa_compliance_gui import (
        VisaComplianceGUI,
    )
    gui = VisaComplianceGUI(parent=parent, intake=intake, on_save=on_save)
    if on_close is not None:
        gui.window.bind(
            "<Destroy>",
            lambda e: on_close() if e.widget is gui.window else None, add="+")
    return gui.window
