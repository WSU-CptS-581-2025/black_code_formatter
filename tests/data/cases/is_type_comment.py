from black import format_str, FileMode
from black.nodes import is_type_comment, Leaf, STANDALONE_COMMENT

def test_is_type_comment_recognition():

    assert is_type_comment(Leaf(STANDALONE_COMMENT, "# type: int"))
    assert is_type_comment(Leaf(STANDALONE_COMMENT, "#  type: int"))
    assert is_type_comment(Leaf(STANDALONE_COMMENT, "#   type:   int"))
    assert not is_type_comment(Leaf(STANDALONE_COMMENT, "# nope: int"))

def test_type_comment_normalization():
   
    src = "x = 1  #   type:   int\n"
    expected = "x = 1  # type: int\n"
    result = format_str(src, mode=FileMode())
    assert result == expected

    src = "def foo():  #  type:  str\n    pass"
    expected = "def foo():  # type: str\n    pass\n"
    result = format_str(src, mode=FileMode())
    assert result == expected