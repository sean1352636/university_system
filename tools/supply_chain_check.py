#!/usr/bin/env python3
"""Static supply-chain checks that do not need the network.

Run by the ``supply-chain`` CI job before the (slower, network-bound)
pip-audit and SBOM steps, so an obvious regression fails in seconds:

1. **No install-time code execution.** ``setup.py``/``setup.cfg`` scripts and
   custom PEP 517 backends can run arbitrary code on ``pip install`` — on the
   installing machine, as the installing user, before any of our tests run.
   This project is declarative-only (``pyproject.toml`` +
   ``setuptools.build_meta``) and this check keeps it that way.
2. **Locks are fully hashed and in sync.** Direct dependencies are declared as
   ranges in ``pyproject.toml``; reproducibility comes from the two resolved
   locks it generates. Every entry in each lock must carry at least one
   ``--hash=sha256:``, every declared core dependency must appear in
   ``requirements.lock``, and the development lock must be a superset of it.
3. **The retired requirements files stay retired.** ``requirements.txt`` and
   ``requirements-dev.txt`` were replaced by pyproject plus the two locks; if
   one reappears the dependency story is ambiguous again.
4. **No direct-URL or VCS requirements.** ``git+https://`` and ``file://``
   dependencies bypass the index, cannot be hash-pinned, and are not
   reproducible.

Exit status is 0 when every check passes and 1 otherwise, with each failure
printed as a GitHub Actions ``::error`` annotation.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

# supply_chain_check.py -> tools -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK = REPO_ROOT / "requirements.lock"
DEV_LOCK = REPO_ROOT / "requirements-dev.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: Files that were replaced by pyproject.toml plus the two resolved locks. If
#: one reappears the dependency story is ambiguous again, so fail loudly.
RETIRED_FILES = ("requirements.txt", "requirements-dev.txt")

#: Backends that only read declarative metadata. Anything else can run code.
ALLOWED_BUILD_BACKENDS = {"setuptools.build_meta", "setuptools.build_meta:__legacy__"}

_REQUIREMENT_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$")
_DIRECT_REFERENCE = re.compile(r"(^|\s)(git\+|hg\+|svn\+|bzr\+|https?://|file://)", re.IGNORECASE)


def _iter_requirements(path: Path) -> list[tuple[int, str]]:
    """Yield ``(line_number, requirement)`` for real requirement lines only."""
    entries: list[tuple[int, str]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        # Continuation lines belong to the preceding requirement (hashes), and
        # pip options (-r, --index-url, ...) are not requirements.
        if not line or line.startswith(("-", "\\")) or line.endswith("\\"):
            continue
        entries.append((number, line))
    return entries


def _normalise(name: str) -> str:
    """PEP 503 name normalisation, so ``Flask_Cors`` matches ``flask-cors``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def check_no_install_time_code(failures: list[str]) -> None:
    """Fail if the package could run code during ``pip install``."""
    for script in ("setup.py", "setup.cfg"):
        if (REPO_ROOT / script).exists():
            failures.append(
                f"{script} exists: it executes on install. Keep packaging "
                f"declarative in pyproject.toml."
            )

    if not PYPROJECT.exists():
        failures.append("pyproject.toml is missing; the build is not declarative.")
        return

    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    backend = data.get("build-system", {}).get("build-backend")
    if backend not in ALLOWED_BUILD_BACKENDS:
        failures.append(
            f"build-backend {backend!r} is not in the reviewed allow-list "
            f"{sorted(ALLOWED_BUILD_BACKENDS)}; a custom backend runs arbitrary "
            f"code at install time."
        )
    # A local backend path means the build imports code from this repo, which
    # is exactly the install-time execution we are excluding.
    if data.get("build-system", {}).get("backend-path"):
        failures.append("build-system.backend-path runs in-tree code at install time.")


def check_declared_dependencies(failures: list[str]) -> None:
    """Fail on direct URL/VCS references among the declared dependencies.

    Exact versions are no longer asserted here: pyproject.toml deliberately
    declares *ranges*, and reproducibility comes from the resolved locks, which
    :func:`check_lock` verifies are fully hash-pinned. What would still break
    reproducibility is a direct reference, which cannot be hashed.
    """
    if not PYPROJECT.exists():
        return
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})
    groups = {"dependencies": project.get("dependencies", [])}
    for name, deps in (project.get("optional-dependencies") or {}).items():
        groups[f"optional-dependencies.{name}"] = deps

    for group, deps in groups.items():
        for dep in deps:
            if _DIRECT_REFERENCE.search(dep):
                failures.append(
                    f"pyproject.toml [{group}]: {dep!r} is a direct URL/VCS "
                    f"requirement and cannot be hash-pinned or reproduced."
                )


def check_retired_files(failures: list[str]) -> None:
    """Fail if a retired requirements file has come back."""
    for name in RETIRED_FILES:
        if (REPO_ROOT / name).exists():
            failures.append(
                f"{name} is back. Direct dependencies belong in pyproject.toml; "
                f"the resolved environments are requirements.lock and "
                f"requirements-dev.lock, both generated by `make lock`."
            )


def _parse_lock(path: Path) -> tuple[set[str], list[str]]:
    """Return ``(locked_names, unhashed_names)`` for a pip-compile lock file."""
    locked: set[str] = set()
    has_hash: dict[str, bool] = {}
    current: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("--hash="):
            if current:
                has_hash[current] = True
            continue
        if stripped.startswith("-"):
            continue
        candidate = stripped.split("\\")[0].strip()
        match = _REQUIREMENT_LINE.match(candidate)
        if not match:
            continue
        current = _normalise(match.group(1))
        locked.add(current)
        has_hash.setdefault(current, False)
        if "--hash=" in raw:
            has_hash[current] = True

    return locked, sorted(name for name, hashed in has_hash.items() if not hashed)


def check_lock(failures: list[str]) -> None:
    """Fail if either lock is missing, unhashed, or stale against pyproject."""
    locks = {"requirements.lock": LOCK, "requirements-dev.lock": DEV_LOCK}
    parsed: dict[str, set[str]] = {}

    for name, path in locks.items():
        if not path.exists():
            failures.append(
                f"{name} is missing. Regenerate both locks with `make lock` so "
                f"installs can be verified with pip install --require-hashes."
            )
            continue
        locked, unhashed = _parse_lock(path)
        parsed[name] = locked
        if unhashed:
            failures.append(
                f"{name} has {len(unhashed)} entries without a hash "
                f"(first few: {unhashed[:5]}). --require-hashes rejects the "
                f"whole file if any entry is unhashed."
            )

    # Staleness: every core runtime dependency declared in pyproject must have
    # been resolved into the production lock. Optional extras are not checked —
    # the locks resolve a chosen subset, not every extra.
    if "requirements.lock" in parsed and PYPROJECT.exists():
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        for dep in data.get("project", {}).get("dependencies", []):
            match = _REQUIREMENT_LINE.match(dep)
            if not match:
                continue
            name = _normalise(match.group(1))
            if name not in parsed["requirements.lock"]:
                failures.append(
                    f"pyproject.toml declares {match.group(1)} but it is not in "
                    f"requirements.lock — the lock is stale. Run `make lock`."
                )

    # The development environment is a superset of production.
    if {"requirements.lock", "requirements-dev.lock"} <= parsed.keys():
        missing = sorted(parsed["requirements.lock"] - parsed["requirements-dev.lock"])
        if missing:
            failures.append(
                f"requirements-dev.lock is missing {len(missing)} package(s) that "
                f"requirements.lock pins (first few: {missing[:5]}). The dev "
                f"environment must contain production. Run `make lock`."
            )


def main() -> int:
    failures: list[str] = []
    check_no_install_time_code(failures)
    check_declared_dependencies(failures)
    check_retired_files(failures)
    check_lock(failures)

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        print(f"\n{len(failures)} supply-chain check(s) failed.", file=sys.stderr)
        return 1

    print("Supply-chain checks passed: declarative build, no direct references, "
          "both locks fully hashed and in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
