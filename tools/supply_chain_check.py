#!/usr/bin/env python3
"""Static supply-chain checks that do not need the network.

Run by the ``supply-chain`` CI job before the (slower, network-bound)
pip-audit and SBOM steps, so an obvious regression fails in seconds:

1. **No install-time code execution.** ``setup.py``/``setup.cfg`` scripts and
   custom PEP 517 backends can run arbitrary code on ``pip install`` — on the
   installing machine, as the installing user, before any of our tests run.
   This project is declarative-only (``pyproject.toml`` +
   ``setuptools.build_meta``) and this check keeps it that way.
2. **No unpinned runtime dependency.** Every requirement in the runtime file
   must carry ``==``. A ``>=`` line means two installs a week apart can get
   different code, which defeats the lock and the SBOM.
3. **Lock file is in sync and fully hashed.** Every entry in the lock must
   carry at least one ``--hash=sha256:``, and every top-level requirement must
   appear in it.
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
REQUIREMENTS = REPO_ROOT / "requirements.txt"
LOCK = REPO_ROOT / "requirements.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"

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


def check_runtime_pins(failures: list[str]) -> None:
    """Fail on unpinned or direct-reference runtime requirements."""
    for number, line in _iter_requirements(REQUIREMENTS):
        if _DIRECT_REFERENCE.search(line):
            failures.append(
                f"requirements.txt:{number}: direct URL/VCS requirement {line!r} "
                f"cannot be hash-pinned or reproduced."
            )
            continue
        match = _REQUIREMENT_LINE.match(line)
        if not match:
            continue
        name, spec = match.groups()
        if "==" not in spec:
            failures.append(
                f"requirements.txt:{number}: {name} is not pinned with '==' "
                f"(found {spec.strip() or 'no specifier'!r}); pin it so installs "
                f"are reproducible."
            )


def check_lock(failures: list[str]) -> None:
    """Fail if the lock is missing, unhashed, or missing a top-level package."""
    if not LOCK.exists():
        failures.append(
            "requirements.lock is missing. Regenerate it with `make lock` so "
            "installs can be verified with pip install --require-hashes."
        )
        return

    text = LOCK.read_text(encoding="utf-8")
    locked: set[str] = set()
    current: str | None = None
    has_hash: dict[str, bool] = {}

    for raw in text.splitlines():
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

    unhashed = sorted(name for name, hashed in has_hash.items() if not hashed)
    if unhashed:
        failures.append(
            f"requirements.lock has {len(unhashed)} entries without a hash "
            f"(first few: {unhashed[:5]}). --require-hashes rejects the whole "
            f"file if any entry is unhashed."
        )

    for number, line in _iter_requirements(REQUIREMENTS):
        match = _REQUIREMENT_LINE.match(line)
        if not match:
            continue
        name = _normalise(match.group(1))
        if name not in locked:
            failures.append(
                f"requirements.txt:{number}: {match.group(1)} is not in "
                f"requirements.lock — the lock is stale. Run `make lock`."
            )


def main() -> int:
    failures: list[str] = []
    check_no_install_time_code(failures)
    check_runtime_pins(failures)
    check_lock(failures)

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        print(f"\n{len(failures)} supply-chain check(s) failed.", file=sys.stderr)
        return 1

    print("Supply-chain checks passed: declarative build, pinned runtime, hashed lock.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
