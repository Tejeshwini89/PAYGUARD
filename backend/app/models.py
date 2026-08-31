from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Event:
    event_id: str
    transaction_id: str
    event_type: str
    source: str
    entity_id: str
    occurred_at: datetime
    received_at: datetime
    payload: Dict[str, Any] = field(default_factory=dict)
    signature_verified: bool = True


@dataclass
class PaymentState:
    status: str = "UNKNOWN"
    payment_id: Optional[str] = None
    amount: Optional[int] = None
    currency: str = "INR"
    method: Optional[str] = None


@dataclass
class OrderState:
    status: str = "UNKNOWN"
    order_id: Optional[str] = None
    amount: Optional[int] = None
    currency: str = "INR"


@dataclass
class InventoryState:
    status: str = "UNKNOWN"
    product_id: Optional[str] = None
    available_quantity: int = 0
    reserved_quantity: int = 0


@dataclass
class FulfillmentState:
    status: str = "NOT_STARTED"
    attempt_count: int = 0
    last_error: Optional[str] = None


@dataclass
class TransactionState:
    transaction_id: str
    payment: PaymentState = field(default_factory=PaymentState)
    order: OrderState = field(default_factory=OrderState)
    inventory: InventoryState = field(default_factory=InventoryState)
    fulfillment: FulfillmentState = field(default_factory=FulfillmentState)
    risk_flags: List[str] = field(default_factory=list)
    event_ids_applied: List[str] = field(default_factory=list)
    last_occurred_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=utcnow)

    def add_risk_flag(self, flag: str) -> None:
        if flag and flag not in self.risk_flags:
            self.risk_flags.append(flag)


@dataclass(frozen=True)
class Incident:
    incident_type: str
    transaction_id: str
    severity: str
    expected_state: Dict[str, str]
    observed_state: Dict[str, str]
    revenue_at_risk: int
    reason: str
    confidence: float
