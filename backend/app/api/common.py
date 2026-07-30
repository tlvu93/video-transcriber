from __future__ import annotations

from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Query as SqlAlchemyQuery


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: List[ItemT]
    total: int
    limit: int
    offset: int


def paginate_query(query: SqlAlchemyQuery, *, limit: int, offset: int) -> tuple[List[Any], int]:
    """Paginate an ORM query while preserving the caller's ordering for result rows."""
    total = query.order_by(None).count()
    items = query.limit(limit).offset(offset).all()
    return items, total


def paginate_items(items: List[Any], *, limit: int, offset: int) -> tuple[List[Any], int]:
    """Paginate an in-memory collection when SQL-level pagination is not practical."""
    total = len(items)
    return items[offset : offset + limit], total


def build_paginated_response(
    items: List[Any],
    *,
    total: int,
    limit: int,
    offset: int,
    **extra: Any,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    response.update(extra)
    return response
