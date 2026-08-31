import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def signed(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_gateway_status_endpoint():
    response = client.get('/gateway')
    assert response.status_code == 200
    data = response.json()
    assert data['active_adapter'] == 'simulator'
    assert 'razorpay' in data


def test_razorpay_webhook_rejects_without_secret(monkeypatch):
    monkeypatch.delenv('RAZORPAY_WEBHOOK_SECRET', raising=False)
    response = client.post('/webhooks/razorpay', content=b'{"event":"payment.captured"}', headers={
        'x-razorpay-signature': 'bad',
        'x-razorpay-event-id': 'evt-no-secret',
        'content-type': 'application/json',
    })
    assert response.status_code == 503


def test_razorpay_webhook_accepts_valid_signature(monkeypatch):
    secret = 'webhook-secret'
    monkeypatch.setenv('RAZORPAY_WEBHOOK_SECRET', secret)
    body = json.dumps({
        'event': 'payment.captured',
        'created_at': 1756135200,
        'payload': {'payment': {'entity': {
            'id': 'pay_api_1', 'order_id': 'order_api_1', 'amount': 5000,
            'currency': 'INR', 'method': 'upi', 'status': 'captured'
        }}}
    }).encode()
    headers = {
        'x-razorpay-signature': signed(body, secret),
        'x-razorpay-event-id': 'evt-api-1',
        'content-type': 'application/json',
    }
    first = client.post('/webhooks/razorpay', content=body, headers=headers)
    second = client.post('/webhooks/razorpay', content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()['accepted'] is True
    assert second.status_code == 200
    assert second.json()['duplicate'] is True
