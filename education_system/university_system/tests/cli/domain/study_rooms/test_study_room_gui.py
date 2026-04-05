"""Smoke tests for StudyRoomBookingGUI import."""


def test_study_room_gui_importable():
    from education_system.university_system.modules.domain.study_rooms.gui.study_room_gui import StudyRoomBookingGUI
    assert StudyRoomBookingGUI is not None


def test_study_room_gui_has_init():
    from education_system.university_system.modules.domain.study_rooms.gui.study_room_gui import StudyRoomBookingGUI
    assert callable(StudyRoomBookingGUI)
    assert hasattr(StudyRoomBookingGUI, "__init__")
