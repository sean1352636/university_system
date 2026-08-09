"""Audit or externalize hardcoded strings passed to recognized GUI sinks."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

IMPORT = (
    "from education_system.systems.university.infrastructure.i18n "
    "import get_text as _t"
)

TEXT_KEYWORD_CALLS = {
    "Button",
    "Checkbutton",
    "Label",
    "LabelFrame",
    "Labelframe",
    "Menu",
    "Menubutton",
    "Radiobutton",
    "add",
    "add_cascade",
    "add_checkbutton",
    "add_command",
    "config",
    "configure",
    "heading",
}
TITLE_CALLS = {"title"}
DIALOG_CALL_PREFIXES = ("ask", "show")
DIALOG_OWNERS = {"messagebox", "simpledialog", "filedialog"}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str


@dataclass(frozen=True)
class SemanticOccurrence:
    path: Path
    key_node: ast.Constant
    old_key: str
    default: str
    base_key: str


def _call_name(node: ast.Call) -> tuple[str, str | None]:
    if isinstance(node.func, ast.Name):
        return node.func.id, None
    if isinstance(node.func, ast.Attribute):
        owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
        return node.func.attr, owner
    return "", None


def _is_translatable(value: ast.AST) -> bool:
    return (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and bool(value.value.strip())
        and bool(re.search(r"[A-Za-z]", value.value))
    )


def _targets(call: ast.Call) -> list[ast.Constant]:
    name, owner = _call_name(call)
    values: list[ast.AST] = []
    if name in TEXT_KEYWORD_CALLS:
        values.extend(
            kw.value for kw in call.keywords if kw.arg in {"text", "label"}
        )
    if name == "StringVar":
        values.extend(kw.value for kw in call.keywords if kw.arg == "value")
    if name in TITLE_CALLS:
        values.extend(call.args[:1])
    if owner in DIALOG_OWNERS and name.startswith(DIALOG_CALL_PREFIXES):
        values.extend(call.args[:2])
        values.extend(
            kw.value for kw in call.keywords if kw.arg in {"title", "message", "prompt"}
        )
    return [value for value in values if _is_translatable(value)]  # type: ignore[list-item]


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _inside_translation(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.Call):
            name, _ = _call_name(current)
            if name in {"_t", "get_text", "t", "_"}:
                return True
        current = parents.get(current)
    return False


def findings(path: Path) -> tuple[str, list[ast.Constant]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    parents = _parent_map(tree)
    nodes: list[ast.Constant] = []
    seen: set[tuple[int, int, int, int]] = set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        for target in _targets(call):
            location = (
                target.lineno,
                target.col_offset,
                target.end_lineno or target.lineno,
                target.end_col_offset or target.col_offset,
            )
            if location not in seen and not _inside_translation(target, parents):
                seen.add(location)
                nodes.append(target)
    return source, nodes


def _char_offset(lines: list[str], line: int, byte_column: int) -> int:
    prefix = "".join(lines[: line - 1])
    current = lines[line - 1].encode("utf-8")[:byte_column].decode("utf-8")
    return len(prefix) + len(current)


def _insert_import(source: str) -> str:
    if IMPORT in source:
        return source
    tree = ast.parse(source)
    insert_line = 0
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            insert_line = body[0].end_lineno or body[0].lineno
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_line = max(insert_line, node.end_lineno or node.lineno)
    lines = source.splitlines(keepends=True)
    lines.insert(insert_line, f"\n{IMPORT}\n")
    return "".join(lines)


def externalize(path: Path) -> int:
    source, nodes = findings(path)
    if not nodes:
        return 0
    lines = source.splitlines(keepends=True)
    replacements: list[tuple[int, int, str]] = []
    for node in nodes:
        start = _char_offset(lines, node.lineno, node.col_offset)
        end = _char_offset(
            lines,
            node.end_lineno or node.lineno,
            node.end_col_offset or node.col_offset,
        )
        literal = source[start:end]
        key = hashlib.sha256(node.value.encode("utf-8")).hexdigest()[:16]
        replacements.append(
            (start, end, f'_t("gui.auto.{key}", default={literal})')
        )
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    path.write_text(_insert_import(source), encoding="utf-8")
    return len(nodes)


def scan(root: Path) -> list[Finding]:
    result: list[Finding] = []
    for path in sorted(root.rglob("*.py")):
        try:
            _, nodes = findings(path)
        except (OSError, SyntaxError, UnicodeError):
            continue
        result.extend(Finding(path, node.lineno, node.value) for node in nodes)
    return result


def catalog_entries(root: Path) -> dict[str, str]:
    """Return literal ``gui.auto`` keys and their English default strings."""
    entries: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name, _ = _call_name(node)
            if name not in {"_t", "get_text", "t", "_"} or not node.args:
                continue
            key_node = node.args[0]
            if not (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
                and key_node.value.startswith("gui.auto.")
            ):
                continue
            default_node = next(
                (kw.value for kw in node.keywords if kw.arg == "default"), None
            )
            if not (
                isinstance(default_node, ast.Constant)
                and isinstance(default_node.value, str)
            ):
                continue
            previous = entries.setdefault(key_node.value, default_node.value)
            if previous != default_node.value:
                raise ValueError(
                    f"conflicting defaults for {key_node.value!r}: "
                    f"{previous!r} and {default_node.value!r}"
                )
    return entries


def merge_catalog(catalog_file: Path, entries: dict[str, str]) -> int:
    """Merge generated entries into a locale JSON file without dropping data."""
    if catalog_file.exists():
        data = json.loads(catalog_file.read_text(encoding="utf-8"))
    else:
        data = {}
    auto = data.setdefault("gui", {}).setdefault("auto", {})
    before = len(auto)
    for key, value in sorted(entries.items()):
        auto.setdefault(key.removeprefix("gui.auto."), value)
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    catalog_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return len(auto) - before


def _key_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not slug:
        slug = "text"
    if slug[0].isdigit():
        slug = f"value_{slug}"
    return slug[:64].rstrip("_")


def _semantic_category(call: ast.Call | None) -> str:
    if call is None:
        return "text"
    name, owner = _call_name(call)
    if owner in DIALOG_OWNERS:
        return "dialogs"
    if name == "title":
        return "windows"
    if name in {"Button", "Checkbutton", "Radiobutton", "Menubutton"}:
        return "buttons"
    if name in {"Menu", "add_cascade", "add_checkbutton", "add_command"}:
        return "menus"
    if name == "heading":
        return "headings"
    if name in {"Label", "LabelFrame", "Labelframe"}:
        return "labels"
    if name == "StringVar":
        return "values"
    if name == "add":
        return "tabs"
    return "text"


def semantic_occurrences(root: Path, key_root: Path | None = None) -> list[SemanticOccurrence]:
    """Discover generated keys and propose module/context semantic keys."""
    result: list[SemanticOccurrence] = []
    key_root = key_root or root
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        parents = _parent_map(tree)
        module_parts = list(path.relative_to(key_root).with_suffix("").parts)
        if module_parts[-1] == "__init__":
            module_parts.pop()
        elif module_parts[-1].endswith("_gui"):
            module_parts[-1] = module_parts[-1][:-4]
        module = ".".join(_key_slug(part) for part in module_parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name, _ = _call_name(node)
            if name not in {"_t", "get_text", "t", "_"} or not node.args:
                continue
            key_node = node.args[0]
            if not (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
                and key_node.value.startswith("gui.auto.")
            ):
                continue
            default_node = next(
                (kw.value for kw in node.keywords if kw.arg == "default"), None
            )
            if not (
                isinstance(default_node, ast.Constant)
                and isinstance(default_node.value, str)
            ):
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(parent, ast.Call):
                parent = parents.get(parent)
            outer = parent if isinstance(parent, ast.Call) else None
            base = (
                f"gui.{module}.{_semantic_category(outer)}."
                f"{_key_slug(default_node.value)}"
            )
            result.append(
                SemanticOccurrence(
                    path, key_node, key_node.value, default_node.value, base
                )
            )
    return result


def semantic_key_map(occurrences: list[SemanticOccurrence]) -> dict[SemanticOccurrence, str]:
    """Resolve readable-key collisions consistently within each module/context."""
    defaults_by_base: dict[str, set[str]] = {}
    for item in occurrences:
        defaults_by_base.setdefault(item.base_key, set()).add(item.default)
    result: dict[SemanticOccurrence, str] = {}
    for item in occurrences:
        key = item.base_key
        variants = sorted(defaults_by_base[key])
        if len(variants) > 1:
            variant = variants.index(item.default) + 1
            if variant > 1:
                key = f"{key}_variant_{variant}"
        result[item] = key
    return result


def _set_nested(data: dict[str, object], key: str, value: str) -> None:
    current = data
    parts = key.split(".")
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"catalog path conflicts at {part!r} for {key!r}")
        current = child
    current.setdefault(parts[-1], value)


def semanticize(
    root: Path, catalog_dir: Path, key_root: Path | None = None
) -> tuple[int, int]:
    """Replace generated hashes and migrate their locale values to semantic keys."""
    occurrences = semantic_occurrences(root, key_root)
    key_map = semantic_key_map(occurrences)
    by_path: dict[Path, list[SemanticOccurrence]] = {}
    for item in occurrences:
        by_path.setdefault(item.path, []).append(item)
    for path, items in by_path.items():
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        replacements: list[tuple[int, int, str]] = []
        for item in items:
            start = _char_offset(lines, item.key_node.lineno, item.key_node.col_offset)
            end = _char_offset(
                lines,
                item.key_node.end_lineno or item.key_node.lineno,
                item.key_node.end_col_offset or item.key_node.col_offset,
            )
            replacements.append(
                (start, end, repr(key_map[item]))
            )
        for start, end, replacement in sorted(replacements, reverse=True):
            source = source[:start] + replacement + source[end:]
        path.write_text(source, encoding="utf-8")

    semantic_defaults = {
        key_map[item]: item.default for item in occurrences
    }
    for locale_dir in sorted(path for path in catalog_dir.iterdir() if path.is_dir()):
        catalog = locale_dir / "gui_auto.json"
        data = json.loads(catalog.read_text(encoding="utf-8")) if catalog.exists() else {}
        old_auto = data.get("gui", {}).pop("auto", {})
        for item in occurrences:
            old_hash = item.old_key.removeprefix("gui.auto.")
            value = old_auto.get(old_hash, item.default)
            _set_nested(data, key_map[item], value)
        catalog.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return len(occurrences), len(semantic_defaults)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--catalog-dir", type=Path)
    parser.add_argument("--semanticize", action="store_true")
    parser.add_argument("--key-root", type=Path)
    args = parser.parse_args()
    if args.semanticize:
        if args.catalog_dir is None:
            parser.error("--semanticize requires --catalog-dir")
        occurrences, keys = semanticize(args.root, args.catalog_dir, args.key_root)
        print(f"Replaced {occurrences} generated references with {keys} semantic keys")
        return 0
    if args.catalog_dir:
        entries = catalog_entries(args.root)
        added = 0
        locale_dirs = sorted(path for path in args.catalog_dir.iterdir() if path.is_dir())
        for locale_dir in locale_dirs:
            added += merge_catalog(locale_dir / "gui_auto.json", entries)
        print(
            f"Merged {len(entries)} GUI keys into {len(locale_dirs)} locales "
            f"({added} new locale entries)"
        )
        return 0
    if args.fix:
        files = strings = 0
        for path in sorted(args.root.rglob("*.py")):
            try:
                count = externalize(path)
            except (OSError, SyntaxError, UnicodeError) as exc:
                print(f"SKIP {path}: {exc}")
                continue
            files += bool(count)
            strings += count
        print(f"Externalized {strings} GUI strings across {files} files")
        return 0
    uncovered = scan(args.root)
    for item in uncovered:
        print(f"{item.path}:{item.line}: {item.text!r}")
    print(f"Uncovered GUI strings: {len(uncovered)}")
    return 1 if uncovered else 0


if __name__ == "__main__":
    raise SystemExit(main())
