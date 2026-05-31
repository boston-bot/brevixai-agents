from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    transaction_id: str
    vendor: str
    amount: float
    date: str
    invoice_number: str | None = None
    memo: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
