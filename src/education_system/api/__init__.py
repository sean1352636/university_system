"""HTTP API surface for the education-system schools estate.

One package per system, each holding that system's route blueprints and
schemas. The shared API platform
(``education_system.platform.delivery.api``) remains the kernel: hosting,
middleware, security and the mount table in ``registry.py``. It must not
import from this package or from ``education_system.systems``; the
dependency runs the other way.
"""
