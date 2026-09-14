from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class NormalizedItem:
    source_id: str
    uid: str
    title: str
    url: str
    kind: str
    raw_text: str = ""
    published_at: datetime | None = None
    payload: dict[str, Any] = field(default_factory=dict)
