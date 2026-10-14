"""Shared helpers for university API routes.

This package no longer exposes a Flask app. ``api_server.py`` (the
standalone university API) and ``systems/university/shell/api`` (its 62
route blueprints) were removed deliberately so the university API can be
rebuilt module by module.

What remains is a library, not an API surface — 128 domain modules import
it, across roughly 269 call sites:

    auth        JWT decorators, object-scope authorization  (117 imports)
    pagination  cursor/limit handling                        (99 imports)
    validators  request field validation                     (53 imports)

Rebuild route modules against these rather than reimplementing them.

Backup of the removed trees:
    var/backups/maintenance/api-removal-20260908_204628/api-trees.tar.gz
"""

__all__: list[str] = []
