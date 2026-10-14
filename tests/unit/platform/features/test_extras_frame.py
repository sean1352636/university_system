"""Tests for the shared Extras & Tools navigation entry point."""

from unittest.mock import Mock, patch


def test_university_extras_action_opens_shared_frame_in_workspace():
    from education_system.systems.university.shell.gui.main.features import (
        student_success_gui,
    )

    app = Mock()
    host = Mock()

    with patch(
        "education_system.platform.features.extras.extras_frame.ExtrasFrame"
    ) as extras_frame:
        student_success_gui.show_extras_launcher(app)

    app.open_in_workspace.assert_called_once()
    title, builder = app.open_in_workspace.call_args.args
    assert title == "Extras & Games"

    builder(host)
    extras_frame.assert_called_once_with(host, auth=app.auth)
    extras_frame.return_value.pack.assert_called_once_with(fill="both", expand=True)


def test_university_extras_action_falls_back_without_workspace():
    from education_system.systems.university.shell.gui.main.features import (
        student_success_gui,
    )

    app = Mock(spec=["root", "auth"])

    with patch(
        "education_system.platform.features.extras.extras_frame.launch_as_toplevel"
    ) as launch:
        student_success_gui.show_extras_launcher(app)

    launch.assert_called_once_with(app.root, auth=app.auth)


@patch("education_system.platform.features.extras.extras_frame.ExtrasFrame")
@patch("education_system.platform.features.extras.extras_frame.tk.Toplevel")
def test_launch_as_toplevel_embeds_extras_frame(toplevel, extras_frame):
    from education_system.platform.features.extras.extras_frame import (
        launch_as_toplevel,
    )

    parent = Mock()
    auth = Mock()
    window = toplevel.return_value
    frame = extras_frame.return_value

    assert launch_as_toplevel(parent, auth=auth) is window

    toplevel.assert_called_once_with(parent)
    extras_frame.assert_called_once_with(window, auth=auth)
    frame.pack.assert_called_once_with(fill="both", expand=True)
