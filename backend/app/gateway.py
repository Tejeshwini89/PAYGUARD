from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GatewayResponse:
    ok: bool
    status_code: int
    data: Dict[str, Any]
    error: Optional[str] = None


class GatewayClient:
    """Small gateway abstraction so PAYGUARD's core stays gateway-independent."""

    name = "base"

    def health(self) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_payment(self, payment_id: str) -> GatewayResponse:
        raise NotImplementedError

    def fetch_order(self, order_id: str) -> GatewayResponse:
        raise NotImplementedError

    def fetch_order_payments(self, order_id: str) -> GatewayResponse:
        raise NotImplementedError


class RazorpayGatewayClient(GatewayClient):
    """Read/verify integration against Razorpay APIs.

    Financial mutation remains outside this adapter in the MVP. PAYGUARD uses
    this layer for authoritative state verification and keeps recovery execution
    behind the merchant-side executor/policy boundary.
    """

    name = "razorpay"

    def __init__(self, key_id: Optional[str] = None, key_secret: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: float = 8.0) -> None:
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
        self.base_url = (base_url or os.getenv("RAZORPAY_API_BASE_URL") or "https://api.razorpay.com/v1").rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def health(self) -> Dict[str, Any]:
        return {
            "gateway": self.name,
            "configured": self.configured,
            "mode": "test-keys" if self.configured else "unconfigured",
            "base_url": self.base_url,
        }

    def _get(self, path: str) -> GatewayResponse:
        if not self.configured:
            return GatewayResponse(False, 503, {}, "Razorpay credentials are not configured")

        url = f"{self.base_url}/{path.lstrip('/')}"
        token = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body) if body else {}
                return GatewayResponse(True, response.status, data)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}
            return GatewayResponse(False, exc.code, data, f"Razorpay API returned HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError) as exc:
            return GatewayResponse(False, 502, {}, f"Razorpay API request failed: {exc}")

    def fetch_payment(self, payment_id: str) -> GatewayResponse:
        return self._get(f"payments/{payment_id}")

    def fetch_order(self, order_id: str) -> GatewayResponse:
        return self._get(f"orders/{order_id}")

    def fetch_order_payments(self, order_id: str) -> GatewayResponse:
        return self._get(f"orders/{order_id}/payments")


class SimulatedGatewayClient(GatewayClient):
    """Gateway adapter used by the benchmark and local demo."""

    name = "simulator"

    def __init__(self, payments: Optional[Dict[str, Dict[str, Any]]] = None,
                 orders: Optional[Dict[str, Dict[str, Any]]] = None,
                 order_payments: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.payments = payments or {}
        self.orders = orders or {}
        self.order_payments = order_payments or {}

    def health(self) -> Dict[str, Any]:
        return {"gateway": self.name, "configured": True, "mode": "simulated"}

    def fetch_payment(self, payment_id: str) -> GatewayResponse:
        data = self.payments.get(payment_id)
        if data is None:
            return GatewayResponse(False, 404, {}, "payment_not_found")
        return GatewayResponse(True, 200, data)

    def fetch_order(self, order_id: str) -> GatewayResponse:
        data = self.orders.get(order_id)
        if data is None:
            return GatewayResponse(False, 404, {}, "order_not_found")
        return GatewayResponse(True, 200, data)

    def fetch_order_payments(self, order_id: str) -> GatewayResponse:
        data = self.order_payments.get(order_id, {"entity": "collection", "count": 0, "items": []})
        return GatewayResponse(True, 200, data)
