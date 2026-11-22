"""Extract the platform's real menu and endpoint inventory to JSON.

Usage:
    python tools/docs/extract_inventory.py [out.json]
    python tools/docs/build_user_guide.py out.json docs/PROGRAM_USER_GUIDE.docx

Everything the user guide lists is generated from this, so the guide cannot
drift from the code by hand-editing.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # repo root
SYS = ROOT / "src/education_system/systems"

out: dict = {"menus": {}, "university": {}, "api": {}}

# ── 1. CLI/GUI navigation for the four school-phase systems ──────────────
NAV_SOURCES = {
    "nursery": SYS / "nursery/menu.py",
    "primary": SYS / "primary/cli_main.py",
    "secondary": SYS / "secondary/app/cli_main.py",
    "sixth_form": SYS / "sixth_form/interfaces/cli/cli_main.py",
}
for key, path in NAV_SOURCES.items():
    src = path.read_text()
    cats = []
    for m in re.finditer(r'\(\s*"([^"]+)",\s*\[(.*?)\]\s*\)', src, re.S):
        items = re.findall(r'"([^"]+)"', m.group(2))
        # the GUI variants store (label, key) tuples; keep the labels only
        items = [i for i in items if not re.fullmatch(r"[a-z0-9_]+", i)]
        if items:
            cats.append({"category": m.group(1), "items": items})
    out["menus"][key] = cats

# GUI nav for primary/secondary lives in gui_main.py; confirm it matches
for key, path in {
    "primary": SYS / "primary/gui_main.py",
    "secondary": SYS / "secondary/app/gui_main.py",
    "sixth_form": SYS / "sixth_form/interfaces/gui/gui_main.py",
}.items():
    src = path.read_text()
    gui_cats = [m.group(1) for m in re.finditer(r'\(\s*"([^"]+)",\s*\[', src)]
    cli_cats = [c["category"] for c in out["menus"][key]]
    out["menus"][key + "_gui_matches_cli"] = (gui_cats == cli_cats)
out["menus"]["nursery_gui_matches_cli"] = True  # single shared NAV_CATEGORIES

# ── 2. University: feature modules per domain area ───────────────────────
def feature_map(domain: Path) -> dict[str, list[str]]:
    """feature -> [sub-features] for one domain directory, two levels deep."""
    feats: dict[str, list[str]] = {}
    if not domain.is_dir():
        return feats
    for child in sorted(domain.iterdir()):
        if child.name.startswith("_"):
            continue
        if child.is_dir():
            subs = sorted({
                (g.name if g.is_dir() else g.stem)
                for g in child.iterdir()
                if not g.name.startswith("_")
                and (g.is_dir() or g.suffix == ".py")
            })
            feats[child.name] = subs
        elif child.suffix == ".py":
            feats.setdefault(child.stem, [])
    return feats


UNI = SYS / "university"
SLICES = sorted(p for p in (UNI / "domains").iterdir() if p.is_dir()) if (UNI / "domains").is_dir() else []


def features(kind: str) -> dict[str, dict[str, list[str]]]:
    """domain -> feature -> [sub-features], read from the vertical slices.

    The university's user-facing modules live at ``domains/<domain>/interfaces/<kind>/``
    since the slice migration, so the domain level is the slice name rather than a
    subdirectory of a single shared ``interfaces/`` tree.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for slice_dir in SLICES:
        feats = feature_map(slice_dir / "interfaces" / kind)
        if feats:
            result[slice_dir.name] = feats
    return result


def module_count(kind: str) -> int:
    """Every university module of one interface kind, shell and slices together."""
    total = len(list((UNI / "shell" / kind).rglob("*.py")))
    return total + sum(len(list((s / "interfaces" / kind).rglob("*.py"))) for s in SLICES)


out["university"]["gui"] = features("gui")
out["university"]["cli"] = features("cli")
# The shell is the system-wide chrome (menus, session, launcher) that is not owned
# by any one domain; it is reported separately so it is not mistaken for a domain.
out["university"]["shell"] = {
    kind: feature_map(UNI / "shell" / kind) for kind in ("gui", "cli", "api")
}
out["university"]["counts"] = {
    "gui_modules": module_count("gui"),
    "cli_modules": module_count("cli"),
    "domain_modules": sum(len(list((s / "domain").rglob("*.py"))) for s in SLICES),
    "total": len(list(UNI.rglob("*.py"))),
}

# per-system source counts
out["counts"] = {}
for key in ["nursery", "primary", "secondary", "sixth_form", "university"]:
    base = SYS / key
    out["counts"][key] = {
        "total": len(list(base.rglob("*.py"))),
        "cli": len([p for p in base.rglob("*.py")
                    if "/cli/" in str(p) or p.name.endswith("_cli.py")
                    or p.name == "cli_main.py"]),
        "gui": len([p for p in base.rglob("*.py")
                    if "/gui/" in str(p) or p.name.endswith("_views.py")
                    or p.name.endswith("_gui.py") or p.name == "gui_main.py"]),
    }

# ── 3. API: every route the unified server actually publishes ────────────
os.environ.update(
    API_SECRET_KEY="extract-only",
    JWT_SECRET_KEY="extract-only",
    API_CORS_ORIGINS="http://localhost:5000",
    EDU_DEV_SEED="true",
)
from education_system.platform.delivery.api.unified_server import create_unified_app  # noqa

app = create_unified_app()
by_system: dict[str, dict[str, list]] = {}
shared: dict[str, list] = {}
for rule in app.url_map.iter_rules():
    path = str(rule.rule)
    methods = sorted(set(rule.methods) - {"HEAD", "OPTIONS"})
    if not path.startswith("/api/v1/"):
        continue
    rest = path[len("/api/v1/"):].split("/")
    head = rest[0]
    if head in ("nursery", "primary", "school", "sixthform", "university"):
        group = rest[1] if len(rest) > 1 and rest[1] else "(root)"
        by_system.setdefault(head, {}).setdefault(group, []).append(
            {"path": path, "methods": methods})
    else:
        shared.setdefault(head, []).append({"path": path, "methods": methods})

for system, groups in by_system.items():
    for g in groups:
        groups[g].sort(key=lambda r: r["path"])
for g in shared:
    shared[g].sort(key=lambda r: r["path"])

out["api"]["systems"] = by_system
out["api"]["shared"] = shared
out["api"]["summary"] = {
    s: {
        "groups": len(g),
        "paths": len({r["path"] for rs in g.values() for r in rs}),
        "operations": sum(len(r["methods"]) for rs in g.values() for r in rs),
    }
    for s, g in by_system.items()
}

dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "var" / "inventory.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, indent=1))
print("written", dest)
print(json.dumps(out["api"]["summary"], indent=1))
print({k: len(v) for k, v in out["menus"].items() if isinstance(v, list)})
print("uni gui domains", {k: len(v) for k, v in out["university"]["gui"].items()})
