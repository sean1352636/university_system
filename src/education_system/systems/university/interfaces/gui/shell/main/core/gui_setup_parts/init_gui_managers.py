"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_gui_managers(self):
    """Initialize modular GUI managers"""
    # Initialize each GUI manager individually to prevent cascade failures
    for attr, cls_name in [
        ("finance_gui", "FinanceManagementGUI"),
        ("student_union_gui", "StudentUnionManagementGUI"),
        ("health_portal_gui", "HealthPortalManagementGUI"),
        ("grade_tracking_gui", "GradeTrackingManagementGUI"),
        ("email_manager_gui", "EmailManagerManagementGUI"),
    ]:
        try:
            cls = _lazy_import(cls_name)
            if cls:
                setattr(self, attr, cls(self.root, self.auth))
            else:
                setattr(self, attr, None)
        except Exception as e:
            print(f"Warning: Error initializing {cls_name}: {e}")
            setattr(self, attr, None)
