# Backward-compatible re-exports — code moved to health_portal/dentist_gui.py
from education_system.university_system.modules.domain.health.gui.health_portal.dentist_gui import (
    DentistGUI,
    launch_dentist_gui
)

__all__ = ['DentistGUI', 'launch_dentist_gui']
