"""FE College learner journey: one learner's record across every system."""

from __future__ import annotations

TITLE = "Learner journey (360)"


def open_window(host) -> None:
    # Imported on open: the journey frame is a platform screen that pulls in
    # the cross-system read models, which a college session may never use.
    from education_system.platform.cross_system.journey_gui import StudentJourneyFrame

    host.clear_content()
    StudentJourneyFrame(host.content_frame, db_path=None, auth=host.auth).pack(
        fill="both", expand=True)
    if hasattr(host, "set_status"):
        host.set_status(TITLE)
