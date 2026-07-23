"""Smoke tests for StudentIDGUI import."""


def test_student_id_gui_importable():
    from education_system.post_18.university_system.modules.domain.student_affairs.student_id.gui.student_id_gui import StudentIDGUI
    assert StudentIDGUI is not None


def test_student_id_gui_has_init():
    from education_system.post_18.university_system.modules.domain.student_affairs.student_id.gui.student_id_gui import StudentIDGUI
    assert callable(StudentIDGUI)
    assert hasattr(StudentIDGUI, "__init__")
