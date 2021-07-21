"""
Request class.

Represents a JSON-RPC request object.
"""
from typing import Any, Dict, List, NamedTuple, Union


class NoId:
    def __repr__(self) -> str:
        return "<NoId>"


NOID = NoId()


Request = NamedTuple(
    "Request",
    [
        ("method", str),
        ("params", Union[List[Any], Dict[str, Any]]),
        ("id", Any),  # Use NOID for a Notification.
    ],
)
