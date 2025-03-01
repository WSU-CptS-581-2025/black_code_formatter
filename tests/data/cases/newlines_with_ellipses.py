from black import format_str, FileMode

def test_two_newlines_after_method_end_with_ellipsis():
    """Test that two newlines are added between top-level classes when the last method ends with ellipses (issue #4420)"""
    """Run "pytest tests/data/cases/newlines_with_ellipses.py -v" to run this test."""
    src = """class Foo:
    def test(): ...
class Bar:
    pass"""

    expected = """class Foo:
    def test(): ...


class Bar:
    pass
"""
    result = format_str(src, mode=FileMode())
    print(result)
    print(expected)
    assert result == expected