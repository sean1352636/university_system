"""Compatibility shim — web delivery moved to ``platform/delivery/web``.

HTML, static assets and PWA files are a different delivery channel from
JSON endpoints, so they are now a sibling of this package rather than a
child of it. Import from ``education_system.platform.delivery.web``.
"""

__all__: list[str] = []
