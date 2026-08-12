import json

from sqlalchemy import Boolean, Numeric
from sqlalchemy.sql.elements import BinaryExpression

from .errors import MismatchedTypeError, UnsupportedTypeError
from .filters import Filter


def cast_expression(expression: BinaryExpression, filter_: Filter) -> BinaryExpression:
    """Cast the JSON value to the correct type based on the filter value type.

    Args:
        expression: The SQLAlchemy BinaryExpression to cast.
        filter: The filter containing the value to determine its type.

    Returns:
        A BinaryExpression with the appropriate cast applied.
    """
    # Handle lists
    if isinstance(filter_.value, list):
        if len(filter_.value) == 0:
            raise UnsupportedTypeError("Empty list not supported")

        # Ensure all list values have the same type
        for v in filter_.value:
            if not isinstance(v, filter_.value[0].__class__):
                raise MismatchedTypeError("List values must be of the same type")

        element_type = type(filter_.value[0])
        if element_type is str:
            expression = expression.astext
        elif element_type in [int, float]:
            expression = expression.cast(Numeric)
        elif element_type in [bool, None]:
            expression = expression.cast(Boolean)
        else:
            raise UnsupportedTypeError(f"Unsupported type {element_type}")

    # Handle strings
    elif isinstance(filter_.value, str):
        # Check if the value is a JSON object or just a string. We need to check
        # if the value can be decoded.
        try:
            decoded_value = json.loads(filter_.value)
            # If the string is a JSON object, return the expression as is.
            # We don't need to cast it.
            if isinstance(decoded_value, dict | list):
                return expression
            expression = expression.astext
        except json.JSONDecodeError:
            # If it can't be decoded, assume it's a string and cast it to text.
            expression = expression.astext

    # Handle other numeric types
    elif isinstance(filter_.value, int | float):
        expression = expression.cast(Numeric)

    # Handle booleans
    elif isinstance(filter_.value, bool):
        expression = expression.cast(Boolean)

    # Handle other unsupported types
    else:
        raise UnsupportedTypeError(f"Unsupported type {type(filter_.value)}")

    return expression
