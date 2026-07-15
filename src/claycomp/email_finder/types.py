from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailFinderResult:
    email: str | None
    provider: str
    status: str  # found | miss | skipped | error
    detail: str | None = None
    verification: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.email) and self.status == "found"
