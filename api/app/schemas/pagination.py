from pydantic import BaseModel


class Page[T](BaseModel):
    """Envelope for list endpoints: consumers page with ?limit=&offset=."""

    items: list[T]
    total: int
    limit: int
    offset: int
