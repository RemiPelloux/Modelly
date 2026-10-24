"""The ``[tool.modelly.lint]`` table of pyproject.toml: which findings to keep.

```toml
[tool.modelly.lint]
select = ["MDL0", "MDL101"]           # only these codes or prefixes (default: all)
ignore = ["MDL105"]                   # drop these codes or prefixes
per-file-ignores = { "tests/*" = ["MDL001"], "setup_*.py" = ["MDL1"] }
```

The file is the first ``pyproject.toml`` found from the working directory upwards;
per-file patterns are globs on the path relative to that file's folder, or on the bare
file name. ``--select`` and ``--ignore`` on the command line replace the file's values.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modelly.lint import Finding

KEYS = frozenset({"select", "ignore", "per-file-ignores"})


class ConfigError(ValueError):
    """The ``[tool.modelly.lint]`` table has a key or value the linter does not know."""


def prefixes(value: str | list[str]) -> tuple[str, ...]:
    """Normalise ``"MDL0, MDL101"`` or ``["MDL0", "MDL101"]`` to upper-case prefixes."""
    if not isinstance(value, str | list):
        raise ConfigError(f"expected a list of codes, got {value!r}")
    items = value.split(",") if isinstance(value, str) else value
    return tuple(str(item).strip().upper() for item in items if str(item).strip())


def matches(code: str, codes: tuple[str, ...]) -> bool:
    """Whether ``code`` starts with one of ``codes``."""
    return any(code.startswith(prefix) for prefix in codes)


@dataclass(frozen=True)
class Config:
    """Which findings to keep: the select, ignore and per-file-ignores settings."""

    select: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    per_file_ignores: tuple[tuple[str, tuple[str, ...]], ...] = ()
    root: Path = Path()

    def keeps(self, finding: Finding) -> bool:
        """Whether ``finding`` survives select, ignore and its file's ignores."""
        code = finding.rule.code
        if self.select and not matches(code, self.select):
            return False
        if matches(code, self.ignore):
            return False
        return not matches(code, self.file_ignores(finding.path))

    def file_ignores(self, path: str) -> tuple[str, ...]:
        """The codes ignored for ``path`` by the per-file-ignores patterns it matches."""
        try:
            relative = Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            relative = Path(path).as_posix()
        name = Path(path).name
        return tuple(
            code
            for pattern, codes in self.per_file_ignores
            if fnmatch(relative, pattern) or fnmatch(name, pattern)
            for code in codes
        )


def find_pyproject(start: Path) -> Path | None:
    """The first ``pyproject.toml`` in ``start`` or one of its parents."""
    for folder in (start, *start.parents):
        candidate = folder / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_config(start: Path | None = None) -> Config:
    """Read ``[tool.modelly.lint]`` from the nearest pyproject.toml; empty when there is none.

    Raises:
        ConfigError: on an unknown key or a value that is not a list of codes.
        tomllib.TOMLDecodeError: when the file is not valid TOML.
    """
    path = find_pyproject((start or Path.cwd()).resolve())
    if path is None:
        return Config()
    with path.open("rb") as handle:
        table = tomllib.load(handle).get("tool", {}).get("modelly", {}).get("lint", {})
    unknown = set(table) - KEYS
    if unknown:
        raise ConfigError(
            f"{path}: unknown [tool.modelly.lint] key(s): {sorted(unknown)}"
        )
    per_file = table.get("per-file-ignores", {})
    if not isinstance(per_file, dict):
        raise ConfigError(f"{path}: per-file-ignores must be a table of glob = [codes]")
    return Config(
        select=prefixes(table.get("select", [])),
        ignore=prefixes(table.get("ignore", [])),
        per_file_ignores=tuple(
            (glob, prefixes(codes)) for glob, codes in per_file.items()
        ),
        root=path.parent,
    )
