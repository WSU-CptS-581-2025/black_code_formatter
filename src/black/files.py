import io
import os
import sys
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING, Any, Optional, Union

from mypy_extensions import mypyc_attr
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError

if sys.version_info >= (3, 11):
    try:
        import tomllib
    except ImportError:
        # Help users on older alphas
        if not TYPE_CHECKING:
            import tomli as tomllib
else:
    import tomli as tomllib

from black.handle_ipynb_magics import jupyter_dependencies_are_installed
from black.mode import TargetVersion
from black.output import err
from black.report import Report

if TYPE_CHECKING:
    import colorama  # noqa: F401


@lru_cache
def _load_toml(path: Union[Path, str]) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


@lru_cache
def _cached_resolve(path: Path) -> Path:
    return path.resolve()


@lru_cache
def find_project_root(
    srcs: Sequence[str], stdin_filename: Optional[str] = None
) -> tuple[Path, str]:
    """Return a directory containing .git, .hg, or pyproject.toml."""
    if stdin_filename is not None:
        srcs = tuple(stdin_filename if s == "-" else s for s in srcs)
    if not srcs:
        srcs = [str(_cached_resolve(Path.cwd()))]

    path_srcs = [_cached_resolve(Path(Path.cwd(), src)) for src in srcs]

    src_parents = [
        list(path.parents) + ([path] if path.is_dir() else []) for path in path_srcs
    ]

    common_base = max(
        set.intersection(*(set(parents) for parents in src_parents)),
        key=lambda path: path.parts,
    )

    for directory in (common_base, *common_base.parents):
        if (directory / ".git").exists():
            return directory, ".git directory"

        if (directory / ".hg").is_dir():
            return directory, ".hg directory"

        if (directory / "pyproject.toml").is_file():
            pyproject_toml = _load_toml(directory / "pyproject.toml")
            if "black" in pyproject_toml.get("tool", {}):
                return directory, "pyproject.toml"

    return directory, "file system root"


def parse_pyproject_toml(path_config: str) -> dict[str, Any]:
    """Parse a pyproject.toml file, pulling out relevant parts for Black."""
    pyproject_toml = _load_toml(path_config)
    config: dict[str, Any] = pyproject_toml.get("tool", {}).get("black", {})
    config = {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}

    if "target_version" not in config:
        inferred_target_version = infer_target_version(pyproject_toml)
        if inferred_target_version is not None:
            config["target_version"] = [v.name.lower() for v in inferred_target_version]

    return config


def infer_target_version(
    pyproject_toml: dict[str, Any],
) -> Optional[list[TargetVersion]]:
    """Infer Black's target version from the project metadata in pyproject.toml."""
    project_metadata = pyproject_toml.get("project", {})
    requires_python = project_metadata.get("requires-python", None)
    if requires_python is not None:
        try:
            return parse_req_python_version(requires_python)
        except InvalidVersion:
            pass
        try:
            return parse_req_python_specifier(requires_python)
        except (InvalidSpecifier, InvalidVersion):
            pass

    return None


def parse_req_python_version(requires_python: str) -> Optional[list[TargetVersion]]:
    
    version = Version(requires_python)
    if version.release[0] != 3:
        return None
    try:
        return [TargetVersion(version.release[1])]
    except (IndexError, ValueError):
        return None


def parse_req_python_specifier(requires_python: str) -> Optional[list[TargetVersion]]:
    
    specifier_set = strip_specifier_set(SpecifierSet(requires_python))
    if not specifier_set:
        return None

    target_version_map = {f"3.{v.value}": v for v in TargetVersion}
    compatible_versions: list[str] = list(specifier_set.filter(target_version_map))
    if compatible_versions:
        return [target_version_map[v] for v in compatible_versions]
    return None


def strip_specifier_set(specifier_set: SpecifierSet) -> SpecifierSet:
    
    specifiers = []
    for s in specifier_set:
        if "*" in str(s):
            specifiers.append(s)
        elif s.operator in ["~=", "==", ">=", "==="]:
            version = Version(s.version)
            stripped = Specifier(f"{s.operator}{version.major}.{version.minor}")
            specifiers.append(stripped)
        elif s.operator == ">":
            version = Version(s.version)
            if len(version.release) > 2:
                s = Specifier(f">={version.major}.{version.minor}")
            specifiers.append(s)
        else:
            specifiers.append(s)

    return SpecifierSet(",".join(str(s) for s in specifiers))


@lru_cache
def find_user_pyproject_toml() -> Path:
    """Return the path to the top-level user configuration for black."""
    if sys.platform == "win32":
        user_config_path = Path.home() / ".black"
    else:
        config_root = os.environ.get("XDG_CONFIG_HOME", "~/.config")
        user_config_path = Path(config_root).expanduser() / "black"
    return _cached_resolve(user_config_path)


@lru_cache
def get_gitignore(root: Path) -> PathSpec:
    
    gitignore = root / ".gitignore"
    lines: list[str] = []
    if gitignore.is_file():
        with gitignore.open(encoding="utf-8") as gf:
            lines = gf.readlines()
    try:
        return PathSpec.from_lines("gitwildmatch", lines)
    except GitWildMatchPatternError as e:
        err(f"Could not parse {gitignore}: {e}")
        raise


def best_effort_relative_path(path: Path, root: Path) -> Path:
   
    try:
        return path.absolute().relative_to(root)
    except ValueError:
        pass
    root_parent = next((p for p in path.parents if _cached_resolve(p) == root), None)
    if root_parent is not None:
        return path.relative_to(root_parent)
    return _cached_resolve(path).relative_to(root)


def wrap_stream_for_windows(
    f: io.TextIOWrapper,
) -> Union[io.TextIOWrapper, "colorama.AnsiToWin32"]:
    """Wrap stream with colorama's wrap_stream so colors are shown on Windows."""
    try:
        from colorama.initialise import wrap_stream
    except ImportError:
        return f
    else:
        return wrap_stream(f, convert=None, strip=False, autoreset=False, wrap=True)
