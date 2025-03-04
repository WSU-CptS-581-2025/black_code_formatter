# Efficient Black Formatting: Configuration and Inline Comments

This document outlines how to effectively use Black code formatting, focusing on configuration via `pyproject.toml` and utilizing inline comments for granular control.

## Introduction

Black is an opinionated code formatter that helps maintain consistent code style across projects. This guide covers its basic usage, advanced configuration, and how to leverage inline comments for fine-grained formatting control.

## Basic Usage

Black reformats entire Python files in place. To format a file or directory, use:

```bash
black {source_file_or_directory}
```

Alternatively, run Black as a module:

```bash
python -m black {source_file_or_directory}
```

## Config with pyproject.toml

Black reads configuration from pyproject.toml, allowing project-specific settings.

### File Location
Black searches for pyproject.toml starting from the common base directory of the input files, then moves up the directory tree. It stops at the first found file, a .git or .hg directory, or the filesystem root.

For global configuration, use:

 - Windows: ~\.black
 - Unix-like: $XDG_CONFIG_HOME/black or ~/.config/black

You can also specify a configuration file with --config.

## Config Format

The pyproject.toml file uses the [tool.black] section for Black settings. Options match the command-line flags.

Example:
```TOML
[tool.black]
line-length = 120
target-version = ['py311', 'py312']
include = '\.pyi?$'
extend-exclude = '''
(
    ^/tests/  # Exclude tests directory
    | .*_pb2.py  # Exclude Protocol Buffer files
)
'''
```

### Key Config Options

- line-length: Sets the maximum line length.
- target-version: Specifies supported Python versions.
- include: Regular expression for files to include.
- exclude / extend-exclude / force-exclude: Regular expressions for files to exclude


### Command-Line Options

- --line-length: Overrides the line length from the config.
- --target-version: Specifies target Python versions.
- --check: Checks if files need reformatting without modifying them.
- --diff: Outputs a diff of changes.
- --include / --exclude: Specify files to include/exclude.
- --skip-string-normalization: Prevents string normalization.
- --skip-magic-trailing-comma: Ignores magic trailing commas.
- --line-ranges: formats only specified line ranges.
- --fast / --safe: Disables or enables AST safety check.
- --verbose / --quiet: Controls output verbosity.

### Environment Variables

- BLACK_CACHE_DIR: Sets the cache directory.
- BLACK_NUM_WORKERS: Sets the number of parallel workers.

## Inline Comments for Control

Black provides inline comments for granular control over formatting.

Skip
```
# fmt: skip
```

Skips formatting a specific line.

```python
long_variable_name = very_long_function_call(argument1, argument2)  # fmt: skip
```

Off and On
```
# fmt: off 
# fmt: on
```
Skips formatting a block of code
```python
# fmt: off
long_variable_name = very_long_function_call(
    argument1, argument2, argument3, argument4
)
# fmt: on
```

## Efficient Usage Tips:

1. Start with Sensible Defaults: Black's default settings are well-chosen.
2. Configure pyproject.toml: Set project-specific options for consistency.
3. Use Inline Comments Sparingly: Employ # fmt: skip and # fmt: off/# fmt: on only when necessary.
4. Integrate with Editors and Pre-commit: Automate Black formatting.
5. Use --check in CI: Ensure code is formatted correctly.
6. Leverage --diff for Code Reviews: Review formatting changes easily.
7. Understand Target Versions: Ensure Black's output is compatible with your project's Python versions.
8. Use --line-ranges for partial formatting: Especially useful for editor integrations.

## Get Started Quickly

1. Install Black: pip install black (or pip install "black[jupyter]" for notebooks).
2. Run Black: black {source_file_or_directory}.
3. Configure pyproject.toml: Add project-specific settings.
4. Use Inline Comments: Control formatting where needed.
5. Integrate with Tools: Set up editor integrations and pre-commit hooks.