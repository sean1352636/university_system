"""
University System Extras Module

Thin wrapper that delegates to education_system.shared.extras.
All extras utilities are now shared across all education systems.
"""

from education_system.shared.extras import get_extras_path, launch_extras_gui, EXTRAS_DIR

__all__ = ['get_extras_path', 'launch_extras_gui', 'EXTRAS_DIR']
