"""Materialized-path helpers. A path is the chain of ids from the root, e.g. "1.4.9"."""

from sqlalchemy import ColumnElement, or_


def subtree_of(path_column, path: str) -> ColumnElement[bool]:
    """The node itself and every descendant: path = '1.4' OR path LIKE '1.4.%'.

    Paths contain only digits and dots, so there is nothing to escape for LIKE.
    """
    return or_(path_column == path, path_column.like(f"{path}.%"))


def depth_of(path: str) -> int:
    return path.count(".") + 1
