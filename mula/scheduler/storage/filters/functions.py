import sqlalchemy
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty
from sqlalchemy.orm.query import Query
from sqlalchemy.sql.elements import BinaryExpression

from .casting import cast_expression
from .comparison import Comparator
from .errors import FilterError, MismatchedTypeError, UnsupportedTypeError
from .filters import FilterRequest
from .operators import FILTER_OPERATORS


def apply_filter(entity: DeclarativeBase, query: Query, filter_request: FilterRequest) -> Query:
    """Apply the filter criteria to a SQLAlchemy query.

    This function takes a SQLAlchemy entity (model), an existing query, and a
    FilterRequest object containing filter criteria, then applies those filters
    to create a refined query.

    The function supports:
      - Multiple filter operations combined with logical operators (AND, OR, etc.)
      - Filtering on model attributes and relationships
      - Nested field filtering using the "__" notation (e.g., "address__city")
      - JSON field filtering

    Filter operations are applied based on the operators defined in the
    FILTER_OPERATORS dictionary.

    Args:
        entity: The SQLAlchemy entity (model class) to apply the filter to.
        query: The existing SQLAlchemy query to refine with filters.
        filter_request: The FilterRequest object containing the filter criteria structure.

    Returns:
        A filtered SQLAlchemy query with all requested conditions applied.

    Raises:
        FilterError: When the filter specification is invalid (wrong type, field not found, etc.)
    """
    # Ensure the filters attribute is a dictionary mapping operators to filter lists
    if not isinstance(filter_request.filters, dict):
        raise FilterError("Filter request must be a dict")

    # Iterate through each operator in the filter request (AND, OR, etc.)
    for operator in filter_request.filters:
        # Create a list to hold all expressions for this operator
        expressions = []

        # Process each filter condition for the current operator
        for filter_ in filter_request.filters[operator]:
            column = filter_.column

            # Verify the column exists on the entity
            if not hasattr(entity, column):
                raise FilterError(f"Invalid filter field: {column} (error: not found)")

            # If the filter field is not specified we will use the column name
            # as the filter_field
            filter_field = filter_.field if filter_.field else column

            #  Get the attribute object from the entity, e.g. MyModel.selected_attr
            entity_attr = getattr(entity, column)

            # Handle relationships - if the column is a relationship, we need to join
            # the related entity to the query
            if is_relationship_property(entity_attr):
                related_entity = entity_attr.property.mapper.class_
                query = query.join(related_entity)

            # Handle nested fields using the "__" notation (e.g., "address__city")
            # This allows drilling down into relationships or JSON fields
            if len(filter_field.split("__")) > 1:
                for nested_field in filter_field.split("__"):
                    if is_relationship_property(entity_attr):
                        # For relationships, get the attribute from the related class
                        entity_attr = getattr(entity_attr.property.mapper.class_, nested_field)
                    else:
                        # For JSON fields, use indexing to access nested keys
                        entity_attr = entity_attr[nested_field]
            else:
                # Handle non-nested fields
                if is_relationship_property(entity_attr):
                    # For relationships, get the attribute from the related class
                    entity_attr = getattr(entity_attr.property.mapper.class_, filter_field)
                elif filter_field != column:
                    # For JSON fields, use indexing to access the specified key
                    entity_attr = entity_attr[filter_field]

            # For BinaryExpressions (typically JSON fields), cast to the
            # appropriate type based on the filter value's type
            if isinstance(entity_attr, BinaryExpression):
                try:
                    entity_attr = cast_expression(entity_attr, filter_)
                except (UnsupportedTypeError, MismatchedTypeError) as exc:
                    raise FilterError(f"Invalid filter value: {filter_.value} (error: {exc})")

            # Apply the comparison operator (==, >, <, etc.) to create the
            # filter expression
            try:
                expression = Comparator(filter_.operator).compare(entity_attr, filter_.value)
            except sqlalchemy.exc.ArgumentError as exc:
                raise FilterError(f"Invalid filter value: {filter_.value} (sql error: {exc})")

            # Add the expression to our list for this operator group
            expressions.append(expression)

        # Apply all expressions for this operator (AND, OR, etc.) to the query
        # The FILTER_OPERATORS dict maps string operator names to SQLAlchemy functions
        query = query.filter(FILTER_OPERATORS[operator](*expressions))

    return query


def is_relationship_property(attr) -> bool:
    """Check if an attribute is a relationship property.

    Determines whether the given SQLAlchemy attribute represents a relationship
    to another model rather than a simple column.

    Args:
        attr: The SQLAlchemy attribute to check.

    Returns:
        bool: True if the attribute is a relationship property, False otherwise.
    """
    return hasattr(attr, "property") and isinstance(attr.property, RelationshipProperty)
