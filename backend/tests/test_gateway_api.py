import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.approval import ApprovalService
from app.main import app


client = TestClient(app)


def signed(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def signed_approval(*, incident_id: str, transaction_id: str, action_type: str, approver: str, secret: str) -> str:
    return ApprovalService(secret=secret).issue(
        incident_id=incident_id,
        transaction_id=transaction_id,
        action_type=action_type,
        approver=approver,
    )


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


def test_recovery_api_rejects_boolean_human_approval_without_token():
    response = client.post('/recover/fulfillment_failure/RETRY_FULFILLMENT?human_approved=true')
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'REQUIRE_HUMAN'
    assert outcome['execution']['status'] == 'REJECTED'
    assert outcome['verification']['revenue_recovered'] == 0


def test_recovery_api_rejects_forged_approval_token(monkeypatch):
    secret = 'api-approval-secret'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    forged = 'not-a-valid-token'
    response = client.post(
        '/recover/fulfillment_failure/RETRY_FULFILLMENT'
        f'?human_approved=true&approval_token={forged}'
    )
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'REQUIRE_HUMAN'
    assert outcome['execution']['status'] == 'REJECTED'
    assert outcome['verification']['revenue_recovered'] == 0


def test_recovery_api_accepts_matching_signed_approval(monkeypatch):
    secret = 'api-approval-secret-valid'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    transaction_id = 'txn_fulfillment_failure'
    action_type = 'RETRY_FULFILLMENT'
    incident_id = f'fulfillment_failure:{transaction_id}:{action_type}'
    token = signed_approval(
        incident_id=incident_id,
        transaction_id=transaction_id,
        action_type=action_type,
        approver='operator@example.com',
        secret=secret,
    )
    response = client.post(
        f'/recover/fulfillment_failure/{action_type}'
        f'?human_approved=true&approval_token={token}'
    )
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'REQUIRE_HUMAN'
    assert outcome['execution']['status'] == 'EXECUTED'
    assert outcome['verification']['status'] == 'VERIFIED'
    assert outcome['ledger']['details']['approver'] == 'operator@example.com'


def test_recovery_api_rejects_approval_bound_to_wrong_transaction(monkeypatch):
    secret = 'api-approval-secret-binding'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    token = signed_approval(
        incident_id='fulfillment_failure:wrong-tx:RETRY_FULFILLMENT',
        transaction_id='wrong-tx',
        action_type='RETRY_FULFILLMENT',
        approver='operator@example.com',
        secret=secret,
    )
    response = client.post(
        '/recover/fulfillment_failure/RETRY_FULFILLMENT'
        f'?human_approved=true&approval_token={token}'
    )
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['execution']['status'] == 'REJECTED'
    assert outcome['verification']['revenue_recovered'] == 0


def test_recovery_api_rejects_reused_approval_token(monkeypatch):
    secret = 'api-approval-secret-replay'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    transaction_id = 'txn_fulfillment_failure'
    action_type = 'RETRY_FULFILLMENT'
    incident_id = f'fulfillment_failure:{transaction_id}:{action_type}'
    token = signed_approval(
        incident_id=incident_id,
        transaction_id=transaction_id,
        action_type=action_type,
        approver='operator@example.com',
        secret=secret,
    )
    first = client.post(
        f'/recover/fulfillment_failure/{action_type}'
        f'?human_approved=true&approval_token={token}'
    )
    second = client.post(
        f'/recover/fulfillment_failure/{action_type}'
        f'?human_approved=true&approval_token={token}'
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['outcome']['execution']['status'] == 'REJECTED'
    assert second.json()['outcome']['verification']['revenue_recovered'] == 0
    # The token itself must be consumed even when a duplicate business action is
    # already complete; replaying it must never grant another authorization.
    assert second.json()['outcome']['ledger']['details']['policy_reason']


def test_recovery_api_autonomous_action_does_not_need_human_token():
    response = client.post('/recover/orphaned_payment_recoverable/RECONSTRUCT_ORDER')
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'ALLOW_AUTONOMOUS'
    assert outcome['execution']['status'] in {'EXECUTED', 'ALREADY_EXECUTED'}
    assert outcome['verification']['status'] == 'VERIFIED'
    assert outcome['verification']['revenue_recovered'] == 7499
