from black import format_str, FileMode

# Running instruction: pytest tests/data/cases/parathesize_yield_expression.py -v
# Issue number: 3851
def test_parathesize_yield_expression():
    src = """for a, in b:
    pass

c = d,


def e():
    yield f,
    return g,"""

    expected = (
        "for (a,) in b:\n"
        "    pass\n"
        "\n"
        "c = (d,)\n"
        "\n"
        "\n"
        "def e():\n"
        "    yield (f,)\n"
        "    return (g,)\n"
    )

    result = format_str(src, mode=FileMode())
    print("Expected:")
    print(repr(expected))
    print("Result:")
    print(repr(result))
    assert result == expected