import token

def is_type_comment(leaf):
    """Return True if the given leaf is a type comment. This function should only
    be used for general type comments (excluding ignore annotations, which should
    use `is_type_ignore_comment`). Note that general type comments are no longer
    used in modern version of Python, this function may be deprecated in the future.

    This version checks for "#" followed by any number of spaces and then "type:",
    and changes the value to have only one space between # and type if it is a type comment.
    """
    t = leaf.type
    v = leaf.value

    if t in {token.COMMENT}:
        if v.startswith("#"):
            comment_body = v[1:]  # Remove the initial "#"
            trimmed_body = comment_body.lstrip() # Remove leading spaces

            if trimmed_body.startswith("type:"):
                suffix = trimmed_body[len("type:"):] # Get the part after "type:"
                leaf.value = "# type:" + suffix.lstrip() # Keep one space, remove leading suffix spaces
                return True
    return False


from collections import namedtuple

class Leaf:
    """
    A simple class representing a leaf node with a type and a value.
    This is for testing purposes and is meant to mimic a leaf object
    that might be found in an AST or token stream.
    """

    def __init__(self, type, value):
        """
        Initializes a Leaf object.

        Args:
            type: The type of the leaf (e.g., token.COMMENT, token.NAME).
            value: The string value of the leaf (e.g., "# type: int", "variable_name").
        """
        self.type = type
        self.value = value

# Test cases
leaves = [
    Leaf(type=token.COMMENT, value="# type: int"),
    Leaf(type=token.COMMENT, value="#  type: str"),
    Leaf(type=token.COMMENT, value="#\ttype: float"),
    Leaf(type=token.COMMENT, value="#   \t  type: bool"),
    Leaf(type=token.COMMENT, value="#not-a-type-comment"),
    Leaf(type=token.COMMENT, value="#type: but no space"),
    Leaf(type=token.NAME, value="variable"), # Not a comment
    Leaf(type=token.COMMENT, value="# ignore[mypy]"), # Not a general type comment
]

for leaf in leaves:
    if is_type_comment(leaf):
        print(f"'{leaf.value}' is a type comment")
    else:
        print(f"'{leaf.value}' is NOT a type comment")