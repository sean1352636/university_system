"""Smoke tests for AdvisingPortalGUI import."""


def test_advising_gui_importable():
    from education_system.systems.university.interfaces.gui.pastoral.advising.advising_gui import AdvisingPortalGUI
    assert AdvisingPortalGUI is not None


def test_advising_gui_has_init():
    from education_system.systems.university.interfaces.gui.pastoral.advising.advising_gui import AdvisingPortalGUI
    assert callable(AdvisingPortalGUI)
    assert hasattr(AdvisingPortalGUI, "__init__")
