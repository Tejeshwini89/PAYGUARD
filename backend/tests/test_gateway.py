import hashlib
import hmac
import json
from datetime import datetime, timezone

from app.gateway import RazorpayGatewayClient, SimulatedGatewayClient
from app.razorpay_webhook import razorpay_event_to_payguard_event, verify_razorpay_signature, build_webhook_event


def test_razorpay_signature_uses_raw_body():
    body = b'{"event":"payment.captured","payload":{}}'
    secret = "demo-secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, sig, secret) is True
    assert verify_razorpay_signature(body + b" ", sig, secret) is False


def test_razorpay_event_maps_payment_order_relationship():
    payload = {
        "event": "payment.captured",
        "created_at": 1756135200,
        "payload": {"payment": {"entity": {
            "id": "pay_123",
            "order_id": "order_123",
            "amount": 749900,
            "currency": "INR",
            "method": "upi",
        }}}
    }
    event = razorpay_event_to_payguard_event(payload, event_id="evt_123")
    assert event.transaction_id == "order_123"
    assert event.entity_id == "pay_123"
    assert event.event_type == "payment.captured"
    assert event.source == "razorpay"
    assert event.payload["payload"]["payment"]["entity"]["amount"] == 749900


def test_build_webhook_event_rejects_bad_signature():
    body = json.dumps({"event": "payment.captured"}).encode()
    event = build_webhook_event(body, "evt_123", "bad", "secret", received_at=datetime.now(timezone.utc))
    assert event.signature_verified is False


def test_simulated_gateway_reads_authoritative_state():
    gateway = SimulatedGatewayClient(
        payments={"pay_1": {"id": "pay_1", "status": "captured", "order_id": "order_1"}},
        orders={"order_1": {"id": "order_1", "status": "paid", "amount": 1000}},
    )
    assert gateway.fetch_payment("pay_1").data["status"] == "captured"
    assert gateway.fetch_order("order_1").data["status"] == "paid"
    assert gateway.fetch_payment("missing").ok is False


def test_razorpay_client_health_is_unconfigured_without_keys():
    gateway = RazorpayGatewayClient(key_id=None, key_secret=None)
    assert gateway.health()["configured"] is False
    assert gateway.fetch_payment("pay_missing").status_code == 503
