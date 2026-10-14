#!/usr/bin/env python3
"""Build a dependency + structure map of the education_system source tree.

Walks every module under src/education_system, parses it with ``ast``, and emits
a compact JSON document describing the package hierarchy and the internal import
graph. The output feeds tools/docs/project_map.html, an interactive explorer.

Usage:
    python tools/project_map.py [--out PATH] [--src PATH]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO_ROOT / "src"
DEFAULT_OUT = REPO_ROOT / "tools" / "docs" / "project_map_data.json"
ROOT_PACKAGE = "education_system"

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache"}


@dataclass
class ModuleInfo:
    """Everything we record about a single .py file."""

    dotted: str
    relpath: str
    loc: int
    code_loc: int
    classes: list[str]
    functions: list[str]
    imports: set[str] = field(default_factory=set)
    external: set[str] = field(default_factory=set)
    is_package: bool = False
    parse_error: str | None = None


def iter_python_files(src_root: Path):
    pkg_root = src_root / ROOT_PACKAGE
    for path in sorted(pkg_root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def dotted_name(path: Path, src_root: Path) -> tuple[str, bool]:
    """Return (dotted module name, is_package) for a file path."""
    rel = path.relative_to(src_root)
    parts = list(rel.parts)
    is_package = parts[-1] == "__init__.py"
    if is_package:
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts), is_package


def resolve_relative(module: str, node: ast.ImportFrom, is_package: bool) -> str | None:
    """Turn a relative ``from .. import x`` into an absolute dotted prefix."""
    parts = module.split(".")
    # Inside a package's __init__, level 1 means the package itself; inside a
    # plain module, level 1 means the package that contains it.
    base = parts if is_package else parts[:-1]
    up = node.level - 1
    if up:
        if up > len(base):
            return None
        base = base[: len(base) - up]
    if not base:
        return None
    prefix = ".".join(base)
    return f"{prefix}.{node.module}" if node.module else prefix


def collect(src_root: Path) -> dict[str, ModuleInfo]:
    modules: dict[str, ModuleInfo] = {}
    for path in iter_python_files(src_root):
        dotted, is_package = dotted_name(path, src_root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - unreadable file
            continue
        lines = text.splitlines()
        loc = len(lines)
        code_loc = sum(1 for ln in lines if ln.strip() and not ln.lstrip().startswith("#"))

        info = ModuleInfo(
            dotted=dotted,
            relpath=str(path.relative_to(src_root)),
            loc=loc,
            code_loc=code_loc,
            classes=[],
            functions=[],
            is_package=is_package,
        )
        modules[dotted] = info

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            info.parse_error = f"line {exc.lineno}: {exc.msg}"
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info.functions.append(node.name)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record(info, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    target = resolve_relative(dotted, node, is_package)
                    if target:
                        _record(info, target)
                        for alias in node.names:
                            _record(info, f"{target}.{alias.name}")
                elif node.module:
                    _record(info, node.module)
                    if node.module.startswith(ROOT_PACKAGE):
                        for alias in node.names:
                            _record(info, f"{node.module}.{alias.name}")
    return modules


def _record(info: ModuleInfo, name: str) -> None:
    if name.split(".")[0] == ROOT_PACKAGE:
        info.imports.add(name)
    else:
        info.external.add(name.split(".")[0])


def narrow(target: str, known: set[str]) -> str | None:
    """Map an imported dotted path onto the nearest real module we know about."""
    parts = target.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in known:
            return candidate
        parts.pop()
    return None


def build_payload(modules: dict[str, ModuleInfo]) -> dict:
    known = set(modules)

    # --- node table: every package and module, parent-linked -----------------
    packages: dict[str, dict] = {}
    for dotted in modules:
        parts = dotted.split(".")
        for i in range(1, len(parts)):
            pkg = ".".join(parts[:i])
            packages.setdefault(pkg, {"dotted": pkg})

    order: list[str] = []
    seen: set[str] = set()
    for name in sorted(set(packages) | known, key=lambda s: (s.count("."), s)):
        if name not in seen:
            seen.add(name)
            order.append(name)
    index = {name: i for i, name in enumerate(order)}

    # Parallel arrays keep the payload small enough to inline in one HTML page.
    # Full dotted ids and file paths are derivable from label + parent + kind,
    # so they are reconstructed by the viewer rather than shipped.
    labels: list[str] = []
    parents: list[int] = []
    kinds: list[int] = []
    locs: list[int] = []
    codes: list[int] = []
    clss: list[int] = []
    fns: list[int] = []
    errors: dict[int, str] = {}

    for i, name in enumerate(order):
        parts = name.split(".")
        parent = ".".join(parts[:-1])
        mod = modules.get(name)
        is_pkg_dir = name in packages
        labels.append(parts[-1])
        parents.append(index.get(parent, -1) if parent else -1)
        # 0 = directory without __init__, 1 = plain module, 2 = package
        kinds.append(2 if (is_pkg_dir and mod) else (0 if is_pkg_dir else 1))
        locs.append(mod.loc if mod else 0)
        codes.append(mod.code_loc if mod else 0)
        clss.append(len(mod.classes) if mod else 0)
        fns.append(len(mod.functions) if mod else 0)
        if mod and mod.parse_error:
            errors[i] = mod.parse_error

    # --- edge table: module -> module, deduped -------------------------------
    edges: dict[tuple[int, int], int] = {}
    for dotted, info in modules.items():
        src = index[dotted]
        for raw in info.imports:
            resolved = narrow(raw, known)
            if resolved is None or resolved == dotted:
                continue
            dst = index[resolved]
            key = (src, dst)
            edges[key] = edges.get(key, 0) + 1

    edge_list = [[s, d, w] for (s, d), w in sorted(edges.items())]

    # --- external dependency tally ------------------------------------------
    external: dict[str, int] = {}
    for info in modules.values():
        for name in info.external:
            external[name] = external.get(name, 0) + 1

    totals = {
        "modules": len(modules),
        "packages": len(packages),
        "loc": sum(m.loc for m in modules.values()),
        "code": sum(m.code_loc for m in modules.values()),
        "classes": sum(len(m.classes) for m in modules.values()),
        "functions": sum(len(m.functions) for m in modules.values()),
        "edges": len(edge_list),
        "parse_errors": sum(1 for m in modules.values() if m.parse_error),
    }

    return {
        "root": ROOT_PACKAGE,
        "totals": totals,
        "nodes": {
            "label": labels,
            "parent": parents,
            "kind": kinds,
            "loc": locs,
            "code": codes,
            "cls": clss,
            "fn": fns,
            "err": errors,
        },
        "edges": edge_list,
        "external": sorted(external.items(), key=lambda kv: -kv[1])[:60],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    modules = collect(args.src)
    if not modules:
        print(f"no modules found under {args.src}", file=sys.stderr)
        return 1

    payload = build_payload(modules)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    t = payload["totals"]
    print(f"wrote {args.out}")
    print(
        f"  {t['modules']} modules, {t['packages']} packages, {t['loc']:,} lines, "
        f"{t['edges']:,} internal import edges, {t['parse_errors']} parse errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
