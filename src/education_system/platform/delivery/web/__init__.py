"""Web delivery: HTML, static assets, PWA manifests and service workers.

A sibling of ``delivery/api``, not a child of it. Serving a page is a
different channel from serving JSON: different caching, different
content types, different failure modes, and a different audience — a
browser rather than a client library. Keeping them in one package meant
the API tree carried HTML, and a change to either risked the other.

    parent_portal/  the parent-facing PWA (manifest + service worker)
    portal/         the multi-system staff portal
    university/     university pages and assets

``university/`` has no routes module: the blueprint that served those
pages lived in the university API tree that was removed. The assets are
kept here so they are not lost, and so the module-by-module rebuild has
something to serve.
"""

__all__: list[str] = []
