"""Smoke tests for PrintingServicesGUI import."""


def test_printing_gui_importable():
    from education_system.systems.university.interfaces.gui.operations.campus.printing.printing_gui import PrintingServicesGUI
    assert PrintingServicesGUI is not None


def test_printing_gui_has_init():
    from education_system.systems.university.interfaces.gui.operations.campus.printing.printing_gui import PrintingServicesGUI
    assert callable(PrintingServicesGUI)
    assert hasattr(PrintingServicesGUI, "__init__")
