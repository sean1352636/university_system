"""Install Argos models and localize generated university GUI catalogs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LANGUAGES = ("ar", "de", "es", "fr", "ja", "ko", "pt", "ru", "zh")
TOKEN_RE = re.compile(r"\{[^{}]+\}|%\([^)]+\)[#0 +\-]?[0-9.*]*[a-zA-Z]|%[sdif]")


def install_models(languages: tuple[str, ...]) -> None:
    from argostranslate import package

    package.update_package_index()
    available = package.get_available_packages()
    installed = {(item.from_code, item.to_code) for item in package.get_installed_packages()}
    for language in languages:
        if ("en", language) in installed:
            print(f"en -> {language}: already installed", flush=True)
            continue
        model = next(
            item
            for item in available
            if item.from_code == "en" and item.to_code == language
        )
        print(f"en -> {language}: downloading", flush=True)
        package.install_from_path(model.download())
        print(f"en -> {language}: installed", flush=True)


def _flatten(value: dict, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            result.update(_flatten(child, path))
        elif isinstance(child, str):
            result[path] = child
    return result


def _set_nested(value: dict, key: str, text: str) -> None:
    current = value
    parts = key.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = text


def _protect(text: str) -> tuple[str, dict[str, str]]:
    tokens: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        marker = f"ARGOSTOKEN{len(tokens)}X"
        tokens[marker] = match.group(0)
        return marker

    return TOKEN_RE.sub(replace, text), tokens


def _restore(text: str, tokens: dict[str, str]) -> str:
    for marker, token in tokens.items():
        text = text.replace(marker, token)
        text = text.replace(marker.lower(), token)
    return text


def translate_catalog(locale_root: Path, language: str, checkpoint: int = 25) -> None:
    from argostranslate import translate

    english_path = locale_root / "en" / "gui_auto.json"
    target_path = locale_root / language / "gui_auto.json"
    english_data = json.loads(english_path.read_text(encoding="utf-8"))
    target_data = json.loads(target_path.read_text(encoding="utf-8"))
    english = _flatten(english_data)
    target = _flatten(target_data)
    cache_path = locale_root.parent.parent / "cache" / "i18n_argos" / f"{language}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    pending_values = sorted(
        {
            text
            for key, text in english.items()
            if language != "en" and target.get(key) == text and text.strip()
        }
    )
    translated = 0
    for source in pending_values:
        if source not in cache:
            protected, tokens = _protect(source)
            localized = _restore(translate.translate(protected, "en", language), tokens)
            if set(TOKEN_RE.findall(localized)) != set(TOKEN_RE.findall(source)):
                raise ValueError(f"placeholder mismatch for {source!r}: {localized!r}")
            cache[source] = localized
        translated += 1
        if translated % checkpoint == 0:
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"{language}: {translated}/{len(pending_values)} unique values", flush=True)
    for key, source in english.items():
        if target.get(key) == source and source in cache:
            _set_nested(target_data, key, cache[source])
    target_path.write_text(
        json.dumps(target_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{language}: catalog complete ({len(cache)} cached translations)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("locale_root", type=Path)
    parser.add_argument("--install-models", action="store_true")
    parser.add_argument("--language", choices=LANGUAGES)
    args = parser.parse_args()
    if args.install_models:
        install_models(LANGUAGES)
    if args.language:
        translate_catalog(args.locale_root, args.language)
    if not args.install_models and not args.language:
        parser.error("select --install-models or --language")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
