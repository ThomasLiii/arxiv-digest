"""Load digest.toml and the research-interests file it points to."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Every setting digest.toml accepts, as "section.key" -> type. Anything else is a typo.
KEYS = {
    "categories": list,
    "include_cross_lists": bool,
    "include_replacements": bool,
    "interests_file": str,
    "batch_size": int,
    "output.directory": str,
    "output.list_skipped": bool,
}
KIND_NAMES = {list: "a list", bool: "true or false", str: "a quoted string", int: "a whole number"}


class ConfigError(Exception):
    pass


@dataclass
class Config:
    categories: list[str]
    interests: str
    include_cross_lists: bool = True
    include_replacements: bool = False
    batch_size: int = 40
    output_dir: Path = Path("digests")
    list_skipped: bool = True


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"{path} not found. Run from your digest repo, or pass --config.")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e

    flat = _flatten(raw)
    for key, value in flat.items():
        if key not in KEYS:
            raise ConfigError(f"{path}: unknown setting '{key}'")
        kind = KEYS[key]
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            raise ConfigError(f"{path}: '{key}' should be {KIND_NAMES[kind]}")

    categories = flat.get("categories")
    if not categories or not all(isinstance(c, str) and c for c in categories):
        raise ConfigError(f"{path}: 'categories' must list at least one arXiv category, e.g. [\"astro-ph.CO\"]")
    batch_size = flat.get("batch_size", Config.batch_size)
    if batch_size < 1:
        raise ConfigError(f"{path}: 'batch_size' must be at least 1")

    root = path.parent
    return Config(
        categories=list(dict.fromkeys(categories)),
        interests=_read_interests(root / flat.get("interests_file", "interests.md")),
        include_cross_lists=flat.get("include_cross_lists", Config.include_cross_lists),
        include_replacements=flat.get("include_replacements", Config.include_replacements),
        batch_size=batch_size,
        output_dir=root / flat.get("output.directory", str(Config.output_dir)),
        list_skipped=flat.get("output.list_skipped", Config.list_skipped),
    )


def _flatten(raw: dict) -> dict:
    flat = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            flat.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            flat[key] = value
    return flat


def _read_interests(path: Path) -> str:
    if not path.is_file():
        raise ConfigError(f"interests file {path} not found")
    # HTML comments are notes for the human editing the file, not for Claude.
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
    if not text:
        raise ConfigError(f"{path} is empty. Describe your research interests there.")
    return text
