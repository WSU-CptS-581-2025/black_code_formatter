from collections.abc import Iterator
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import pytest

import black
from black.mode import TargetVersion
from tests.util import (
    all_data_cases,
    assert_format,
    dump_to_stderr,
    read_data,
    read_data_with_mode,
)


@pytest.fixture(autouse=True)
def patch_dump_to_file(request: Any) -> Iterator[None]:
    with patch("black.dump_to_file", dump_to_stderr):
        yield


def check_file(subdir: str, filename: str, *, data: bool = True) -> None:
    args, source, expected = read_data_with_mode(subdir, filename, data=data)
    assert_format(
        source,
        expected,
        args.mode,
        fast=args.fast,
        minimum_version=args.minimum_version,
        lines=args.lines,
        no_preview_line_length_1=args.no_preview_line_length_1,
    )
    if args.minimum_version is not None:
        major, minor = args.minimum_version
        target_version = TargetVersion[f"PY{major}{minor}"]
        mode = replace(args.mode, target_versions={target_version})
        assert_format(
            source,
            expected,
            mode,
            fast=args.fast,
            minimum_version=args.minimum_version,
            lines=args.lines,
            no_preview_line_length_1=args.no_preview_line_length_1,
        )


@pytest.mark.filterwarnings("ignore:invalid escape sequence.*:DeprecationWarning")
@pytest.mark.parametrize("filename", all_data_cases("cases"))
def test_simple_format(filename: str) -> None:
    check_file("cases", filename)


@pytest.mark.parametrize("filename", all_data_cases("line_ranges_formatted"))
def test_line_ranges_line_by_line(filename: str) -> None:
    args, source, expected = read_data_with_mode("line_ranges_formatted", filename)
    assert (
        source == expected
    ), "Test cases in line_ranges_formatted must already be formatted."
    line_count = len(source.splitlines())
    for line in range(1, line_count + 1):
        assert_format(
            source,
            expected,
            args.mode,
            fast=args.fast,
            minimum_version=args.minimum_version,
            lines=[(line, line)],
        )





def test_empty() -> None:
    """
    Error prevention for formatting an empty file.
    """
    source = expected = ""
    assert_format(source, expected)


def test_patma_invalid() -> None:
    """
    Ensure Black properly raises an error on invalid pattern matching syntax.
    """
    source, expected = read_data("miscellaneous", "pattern_matching_invalid")
    mode = black.Mode(target_versions={black.TargetVersion.PY310})
    with pytest.raises(black.parsing.InvalidInput) as exc_info:
        assert_format(source, expected, mode, minimum_version=(3, 10))

    exc_info.match(
        "Cannot parse for target version Python 3.10: 10:11:     case a := b:"
    )



@pytest.mark.parametrize(
    "source, expected",
    [
        (
            # Unformatted version with concatenated list comprehensions
            """matching_routes = [r for r in routes if r.get("dst") and ip in ipaddress.ip_network(r.get("dst"))] + [
                r for r in routes if r.get("dst") == "" and r.get("family") == family
            ]""",
            # Expected correctly formatted version
            """matching_routes = (
                [r for r in routes if r.get("dst") and ip in ipaddress.ip_network(r.get("dst"))] +
                [r for r in routes if r.get("dst") == "" and r.get("family") == family]
            )"""
        )
    ]
)
def test_concatenated_list_comprehensions(source: str, expected: str) -> None:
    """
    Ensure concatenated list comprehensions are formatted onto separate lines with parentheses.

    """
    mode = black.Mode()
    formatted_code = black.format_file_contents(source, fast=False, mode=mode)
    
    assert formatted_code.strip() == expected.strip(), (
        f"Expected:\n{expected}\nGot:\n{formatted_code}"
    )
