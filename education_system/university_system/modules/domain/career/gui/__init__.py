"""Career Services GUI Module — lazy imports to avoid circular dependencies."""


def __getattr__(name):
    if name in ("CareerServicesGUI", "launch_career_services_gui"):
        from education_system.university_system.modules.domain.career.gui.career_services_gui import (
            CareerServicesGUI,
            launch_career_services_gui,
        )
        _exports = {
            "CareerServicesGUI": CareerServicesGUI,
            "launch_career_services_gui": launch_career_services_gui,
        }
        globals().update(_exports)
        return _exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["CareerServicesGUI", "launch_career_services_gui"]
