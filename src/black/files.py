import ast
import io
import os
import sys
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING, Any, Optional, Union

try:
    import tomllib  # Python 3.11+
except ImportError:
    import toml as tomllib  # Fallback for older versions

from mypy_extensions import mypyc_attr
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError
from black import format_str, FileMode
from black.handle_ipynb_magics import jupyter_dependencies_are_installed
from black.mode import TargetVersion
from black.output import err
from black.report import Report

if TYPE_CHECKING:
    import colorama  # noqa: F401


@lru_cache
def _load_toml(path: Union[Path, str]) -> dict[str, Any]:
    """Loads and parses a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


@lru_cache
def _cached_resolve(path: Path) -> Path:
    """Returns the resolved absolute path."""
    return path.resolve()


def format_concatenated_comprehensions(code: str) -> str:
    """
    Formats concatenated list comprehensions to ensure they are properly enclosed in parentheses.
    """

    class ComprehensionConcatenationTransformer(ast.NodeTransformer):
        """AST Transformer to wrap concatenated list comprehensions in tuples."""

        def visit_BinOp(self, node):
            self.generic_visit(node)  # Recursively process children
            
            if isinstance(node.op, ast.Add):
                if isinstance(node.left, ast.ListComp) and isinstance(node.right, ast.ListComp):
                    return ast.copy_location(
                        ast.BinOp(
                            left=ast.Tuple(elts=[node.left], ctx=ast.Load()),
                            op=node.op,
                            right=ast.Tuple(elts=[node.right], ctx=ast.Load()),
                        ),
                        node,
                    )
            return node

    tree = ast.parse(code)  # Parse into AST
    transformed_tree = ComprehensionConcatenationTransformer().visit(tree)  # Transform AST
    formatted_code = format_str(ast.unparse(transformed_tree), mode=FileMode())  # Format using Black

    return formatted_code


@lru_cache
def find_project_root(srcs: Sequence[str], stdin_filename: Optional[str] = None) -> tuple[Path, str]:
    """Finds the project root directory based on .git, .hg, or pyproject.toml."""
    if stdin_filename is not None:
        srcs = tuple(stdin_filename if s == "-" else s for s in srcs)
    if not srcs:
        srcs = [str(_cached_resolve(Path.cwd()))]

    path_srcs = [_cached_resolve(Path(Path.cwd(), src)) for src in srcs]

    src_parents = [list(path.parents) + ([path] if path.is_dir() else []) for path in path_srcs]

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


def infer_target_version(pyproject_toml: dict[str, Any]) -> Optional[list[TargetVersion]]:
    """Infer Black's target version from `requires-python` in `pyproject.toml`."""
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
    """Parses a version string (e.g., `"3.7"`) into a list of `TargetVersion`."""
    version = Version(requires_python)
    if version.release[0] != 3:
        return None
    try:
        return [TargetVersion(version.release[1])]
    except (IndexError, ValueError):
        return None


def parse_req_python_specifier(requires_python: str) -> Optional[list[TargetVersion]]:
    """Parses a specifier string (e.g., `">=3.7,<3.10"`) into `TargetVersion` list."""
    specifier_set = SpecifierSet(requires_python)
    target_version_map = {f"3.{v.value}": v for v in TargetVersion}
    compatible_versions = list(specifier_set.filter(target_version_map))
    return [target_version_map[v] for v in compatible_versions] if compatible_versions else None


@lru_cache
def find_user_pyproject_toml() -> Path:
    """Finds the user-specific pyproject.toml for Black."""
    if sys.platform == "win32":
        return _cached_resolve(Path.home() / ".black")
    else:
        config_root = os.environ.get("XDG_CONFIG_HOME", "~/.config")
        return _cached_resolve(Path(config_root).expanduser() / "black")


def wrap_stream_for_windows(f: io.TextIOWrapper) -> Union[io.TextIOWrapper, "colorama.AnsiToWin32"]:
    """Wraps stream with colorama's ANSI support on Windows."""
    try:
        from colorama.initialise import wrap_stream
    except ImportError:
        return f
    return wrap_stream(f, convert=None, strip=False, autoreset=False, wrap=True)


# ================================
# ✅ **Basic Test for Concatenated List Comprehensions**
# ================================
if __name__ == "__main__":
    test_code = """
matching_routes = [r for r in routes if r.get("dst") and ip in ipaddress.ip_network(r.get("dst"))] + [
    r for r in routes if r.get("dst") == "" and r.get("family") == family
]
"""
    formatted_output = format_concatenated_comprehensions(test_code)
    print("🔹 **Formatted Code Output:**")
    print(formatted_output)
