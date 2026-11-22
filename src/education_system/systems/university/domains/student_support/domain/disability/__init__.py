"""Disability & Accessibility Services.

One service behind the Disability & Accessibility portal: students ask for
reasonable adjustments (``accommodation_requests``), disability services and
the health team decide them, and an approved request becomes the health
portal's ``accommodations`` row that exams and assessments read (through
``services/bus/accommodation_bus``).

* :mod:`.accessibility_service` — the tables and the raw operations (moved
  here from operations/campus/accessibility on 2026-10-19).
* :mod:`.access` — who may see and decide what.
* :mod:`.portal` — the operations the GUI and CLI call, each taking the
  signed-in user first and checking it.
"""
