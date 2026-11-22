"""SQL for reading academic calendar events in the calendar GUI.

Calendar events are stored in ``unified_events`` tagged
``source_type = 'academic_calendar'``. The legacy ``academic_calendar_events``
table is retired and empty, so any screen that still read it showed nothing or
could not find the event it was asked about.

``CALENDAR_EVENTS`` exposes the unified rows under the legacy column names —
the same projection the domain calendar manager uses — so it can stand in for
the old table in a ``FROM`` clause.
"""

CALENDAR_EVENTS = (
    "(SELECT source_event_id AS id, title AS name, event_date AS date, "
    "start_datetime AS date_start, end_datetime AS date_end, description, event_type, "
    "created_at AS date_added, updated_at AS last_modified, created_by, start_time, "
    "end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, "
    "participants, status, country_code, region, is_active "
    "FROM unified_events WHERE source_type = 'academic_calendar')"
)

#: Classes mirrored from Course Management's timetable. They show on the calendar
#: but are looked up separately: they aren't editable here, because the next sync
#: would overwrite the change.
CLASS_EVENTS = CALENDAR_EVENTS.replace("'academic_calendar'", "'section_meeting'")

__all__ = ["CALENDAR_EVENTS", "CLASS_EVENTS"]
