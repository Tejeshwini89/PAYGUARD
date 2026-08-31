import hashlib
import hmac
import json
from datetime import datetime, timezone

from app.gateway import RazorpayGatewayClient, SimulatedGatewayClient
from app.razorpay_webhook import razorpay_event_to_payguard_event, verify_razorpay_signature, build_webhook_event
from app.ingest import EventIngestor


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


def test_invalid_webhook_cannot_reserve_event_id_before_valid_delivery():
    body = json.dumps({"event": "payment.captured"}).encode()
    invalid = build_webhook_event(body, "evt_reuse", "bad", "secret", received_at=datetime.now(timezone.utc))
    valid_sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    valid = build_webhook_event(body, "evt_reuse", valid_sig, "secret", received_at=datetime.now(timezone.utc))

    ingestor = EventIngestor()
    rejected = ingestor.ingest(invalid)
    accepted = ingestor.ingest(valid)

    assert rejected.accepted is False
    assert rejected.duplicate is False
    assert rejected.reason == "signature_verification_failed"
    assert accepted.accepted is True
    assert accepted.duplicate is False
    assert accepted.reason == "accepted"


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
