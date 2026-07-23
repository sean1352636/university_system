"""
Mobility GUI Module

GUI interfaces for mobility and transportation management.
"""

from __future__ import annotations

__all__ = [
    'launch_mobile_app_pwa_gui',
]

# Import main launchers
try:
    from education_system.post_18.university_system.modules.domain.campus.mobility.gui.mobile_app_pwa_gui import launch_mobile_app_pwa_gui
except ImportError:
    launch_mobile_app_pwa_gui = None
