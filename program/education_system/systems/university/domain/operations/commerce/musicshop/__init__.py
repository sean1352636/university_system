"""Music Shop Module"""

__all__ = ['MusicShopGUI', 'launch_musicshop_gui']

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "MusicShopGUI": "education_system.systems.university.interfaces.gui.operations.commerce.musicshop.musicshop_gui",
    "launch_musicshop_gui": "education_system.systems.university.interfaces.gui.operations.commerce.musicshop.musicshop_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
