"""Smoke tests for TextbookStoreGUI import."""


def test_textbook_gui_importable():
    from education_system.post_18.university_system.modules.domain.commerce.textbooks.gui.textbook_gui import TextbookStoreGUI
    assert TextbookStoreGUI is not None


def test_textbook_gui_has_init():
    from education_system.post_18.university_system.modules.domain.commerce.textbooks.gui.textbook_gui import TextbookStoreGUI
    assert callable(TextbookStoreGUI)
    assert hasattr(TextbookStoreGUI, "__init__")
