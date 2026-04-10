#!/usr/bin/env python
"""Generate static OpenAPI 3.0.3 spec files from the live Flask URL maps.

The runtime API server already serves the spec at ``/api/v1/openapi.json``
via ``education_system.shared.api.docs.build_openapi_spec``. This script
calls the same generator against each subsystem's app factory and writes
the result to ``docs/api/openapi-<system>.json`` (and a single combined
``docs/api/openapi.json`` from the unified server) so the spec is
available offline, in version control, and to SDK generators / contract
tests.

Usage::

    python scripts/generate_openapi_spec.py            # writes all five
    python scripts/generate_openapi_spec.py --system college
    python scripts/generate_openapi_spec.py --check    # exit non-zero if specs are stale

The output paths are deterministic, so this script is safe to wire into
CI as ``--check`` to fail builds when route changes haven't been
followed by a regeneration.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_API_DIR = REPO_ROOT / "docs" / "api"

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger("generate_openapi_spec")


def _build_university() -> dict:
    from education_system.shared.api.university.api_server import create_app
    from education_system.shared.api.docs import build_openapi_spec

    app = create_app()
    spec = build_openapi_spec(app)
    spec["info"]["title"] = "Education System API — University"
    return spec


def _build_college() -> dict:
    from education_system.shared.api.college.api_server import create_app
    from education_system.shared.api.docs import build_openapi_spec

    app = create_app()
    spec = build_openapi_spec(app)
    spec["info"]["title"] = "Education System API — College"
    return spec


def _build_secondary() -> dict:
    from education_system.shared.api.secondary.api_server import create_app
    from education_system.shared.api.docs import build_openapi_spec

    app = create_app()
    spec = build_openapi_spec(app)
    spec["info"]["title"] = "Education System API — Secondary School"
    return spec


def _build_primary() -> dict:
    from education_system.shared.api.primary.api_server import create_app
    from education_system.shared.api.docs import build_openapi_spec

    app = create_app()
    spec = build_openapi_spec(app)
    spec["info"]["title"] = "Education System API — Primary School"
    return spec


def _build_unified() -> dict:
    from education_system.shared.api.unified_server import create_unified_app
    from education_system.shared.api.docs import build_openapi_spec

    app = create_unified_app()
    spec = build_openapi_spec(app)
    spec["info"]["title"] = "Education System API — Unified"
    return spec


BUILDERS = {
    "university": (_build_university, "openapi-university.json"),
    "college": (_build_college, "openapi-college.json"),
    "secondary": (_build_secondary, "openapi-secondary.json"),
    "primary": (_build_primary, "openapi-primary.json"),
    "unified": (_build_unified, "openapi.json"),
}


def _write_spec(spec: dict, out_path: Path) -> bool:
    """Write *spec* to *out_path*; return True if file changed."""
    new_text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    if out_path.exists() and out_path.read_text() == new_text:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_text)
    return True


def _run_one(system: str, check_only: bool = False) -> tuple[bool, int]:
    """Generate one system's spec. Returns (changed, endpoint_count)."""
    builder, filename = BUILDERS[system]
    try:
        spec = builder()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build %s spec: %s", system, exc)
        return (False, 0)

    out_path = DOCS_API_DIR / filename
    endpoint_count = sum(len(methods) for methods in spec["paths"].values())

    if check_only:
        existing = out_path.read_text() if out_path.exists() else ""
        new_text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
        changed = existing != new_text
        status = "STALE" if changed else "OK"
        print(f"  {system:<12} {status:<6} ({endpoint_count} endpoints) {out_path.relative_to(REPO_ROOT)}")
        return (changed, endpoint_count)

    changed = _write_spec(spec, out_path)
    status = "WROTE" if changed else "UNCHANGED"
    print(f"  {system:<12} {status:<10} ({endpoint_count} endpoints) {out_path.relative_to(REPO_ROOT)}")
    return (changed, endpoint_count)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--system",
        choices=list(BUILDERS) + ["all"],
        default="all",
        help="Which subsystem to generate (default: all).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Don't write; exit non-zero if any spec on disk is stale.",
    )
    args = parser.parse_args()

    systems = list(BUILDERS) if args.system == "all" else [args.system]

    print("Generating OpenAPI specs..." if not args.check else "Checking OpenAPI specs...")
    any_changed = False
    total_endpoints = 0
    for system in systems:
        changed, count = _run_one(system, check_only=args.check)
        any_changed = any_changed or changed
        total_endpoints += count

    print(f"\nTotal endpoints documented: {total_endpoints}")

    if args.check and any_changed:
        print("\nERROR: one or more specs are stale. Run:")
        print("  python scripts/generate_openapi_spec.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
