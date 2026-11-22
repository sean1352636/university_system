"""Communications: how the sixth form talks to learners, parents and staff.

Owns parent contacts, parents' evenings, notices & bulletins, announcements,
notifications (including multi-channel delivery), the activity feed, internal
messaging and e-mail (outbox delivery and e-mail templates), letter templates,
the document hub and file attachments.

The parent portal is not part of this slice — it stays under
``domain/operations/communications/parent_portal`` and will become the portals
slice. The shared operations UI helpers (``interfaces/gui/operations/_ops_ui.py``
and ``interfaces/cli/operations/_ops_cli.py``) are used by other areas too, so
they stay in the system-wide interfaces tree.
"""
