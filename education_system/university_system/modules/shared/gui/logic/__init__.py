"""GUI Logic Layer — canonical package aggregator.

Separates testable business-logic classes from Tk UI so the logic can be
exercised without instantiating any widgets. Currently exposes
``StudentFormLogic``; add new logic classes here as the layer grows.

This is the public API for the subpackage, not a deprecated shim.

Example usage::

    from education_system.university_system.modules.shared.gui.logic import StudentFormLogic
    valid, errors = StudentFormLogic().validate_student_data({'name': 'John'})
"""

from education_system.university_system.modules.shared.gui.logic.student_form_logic import StudentFormLogic

__all__ = ['StudentFormLogic']
