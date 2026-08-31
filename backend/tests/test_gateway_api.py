from fastapi.testclient import TestClient

from app.approval import ApprovalService
from app.main import app

client = TestClient(app)


def signed_approval(*, incident_id, transaction_id, action_type, approver, secret):
    return ApprovalService(secret=secret).issue(
        incident_id=incident_id,
        transaction_id=transaction_id,
        action_type=action_type,
        approver=approver,
    )


def test_recovery_api_rejects_bare_human_approval(monkeypatch):
    response = client.post('/recover/fulfillment_failure/RETRY_FULFILLMENT?human_approved=true')
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'REQUIRE_HUMAN'
    assert outcome['execution']['status'] == 'REJECTED'
    assert outcome['verification']['revenue_recovered'] == 0


def test_recovery_api_rejects_forged_approval_token(monkeypatch):
    secret = 'api-approval-secret-forged'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    app.state.payguard_approval_service = ApprovalService(secret=secret)
    response = client.post(
        '/recover/fulfillment_failure/RETRY_FULFILLMENT'
        '?human_approved=true&approval_token=forged.token'
    )
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['execution']['status'] == 'REJECTED'
    assert outcome['verification']['revenue_recovered'] == 0


def test_recovery_api_rejects_expired_approval_token(monkeypatch):
    secret = 'api-approval-secret-expired'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    app.state.payguard_approval_service = ApprovalService(secret=secret)
    service = ApprovalService(secret=secret, clock=lambda: 1000)
    token = service.issue(
        incident_id='fulfillment_failure:txn_fulfillment_failure:RETRY_FULFILLMENT',
        transaction_id='txn_fulfillment_failure',
        action_type='RETRY_FULFILLMENT',
        approver='operator@example.com',
        ttl_seconds=1,
    )
    expired_service = ApprovalService(secret=secret, clock=lambda: 1002)
    expired_token = expired_service._encode({})
    # Build a genuinely expired signed grant with the same service contract.
    expired_service = ApprovalService(secret=secret, clock=lambda: 1000)
    token = expired_service.issue(
        incident_id='fulfillment_failure:txn_fulfillment_failure:RETRY_FULFILLMENT',
        transaction_id='txn_fulfillment_failure',
        action_type='RETRY_FULFILLMENT',
        approver='operator@example.com',
        ttl_seconds=1,
    )
    app.state.payguard_approval_service = ApprovalService(secret=secret, clock=lambda: 1002)
    response = client.post(
        '/recover/fulfillment_failure/RETRY_FULFILLMENT'
        f'?human_approved=true&approval_token={token}'
    )
    assert response.status_code == 200
    assert response.json()['outcome']['execution']['status'] == 'REJECTED'


def test_recovery_api_accepts_matching_signed_approval(monkeypatch):
    secret = 'api-approval-secret-valid'
    monkeypatch.setenv('PAYGUARD_APPROVAL_SECRET', secret)
    app.state.payguard_approval_service = ApprovalService(secret=secret)
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
    app.state.payguard_approval_service = ApprovalService(secret=secret)
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
    app.state.payguard_approval_service = ApprovalService(secret=secret)
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
    assert second.json()['outcome']['ledger']['details']['policy_reason']


def test_recovery_api_autonomous_action_does_not_need_human_token():
    response = client.post('/recover/orphaned_payment_recoverable/RECONSTRUCT_ORDER')
    assert response.status_code == 200
    outcome = response.json()['outcome']
    assert outcome['policy']['decision'] == 'ALLOW_AUTONOMOUS'
    assert outcome['execution']['status'] in {'EXECUTED', 'ALREADY_EXECUTED'}
    assert outcome['verification']['status'] == 'VERIFIED'
    assert outcome['verification']['revenue_recovered'] == 7499
