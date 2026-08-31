from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Set


@dataclass(frozen=True)
class ApprovalGrant:
    approval_id: str
    incident_id: str
    transaction_id: str
    action_type: str
    approver: str
    issued_at: int
    expires_at: int


class ApprovalService:
    """Validate short-lived, action-bound, one-time human approvals.

    In production, token issuance belongs behind authenticated operator/SSO controls.
    This MVP keeps the issued-token replay set in memory; durable approval storage is
    a documented production evolution point.
    """

    def __init__(self, secret: str | None = None, clock=None) -> None:
        self.secret = (secret or os.getenv("PAYGUARD_APPROVAL_SECRET", "")).encode()
        self.clock = clock or time.time
        self._used: Set[str] = set()

    def issue(self, *, incident_id: str, transaction_id: str, action_type: str, approver: str, ttl_seconds: int = 300) -> str:
        if not self.secret:
            raise RuntimeError("PAYGUARD_APPROVAL_SECRET is not configured")
        now = int(self.clock())
        payload = {
            "approval_id": token_urlsafe(12),
            "incident_id": incident_id,
            "transaction_id": transaction_id,
            "action_type": action_type,
            "approver": approver,
            "issued_at": now,
            "expires_at": now + ttl_seconds,
        }
        encoded = self._encode(payload)
        signature = hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def validate(self, token: str, *, incident_id: str, transaction_id: str, action_type: str) -> ApprovalGrant | None:
        if not self.secret or not token or token in self._used:
            return None
        try:
            encoded, signature = token.rsplit(".", 1)
            expected = hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(base64.urlsafe_b64decode(encoded.encode() + b"==").decode())
            now = int(self.clock())
            if payload["expires_at"] < now:
                return None
            if (
                payload["incident_id"] != incident_id
                or payload["transaction_id"] != transaction_id
                or payload["action_type"] != action_type
            ):
                return None
            self._used.add(token)
            return ApprovalGrant(**payload)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _encode(payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
