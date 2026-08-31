import pytest

from app.main import app
from app.approval import ApprovalService
from app.executor import MerchantRecoveryStore, RecoveryExecutor
from app.ledger import DecisionLedger


@pytest.fixture(autouse=True)
def isolate_recovery_state(monkeypatch):
    """Give each API test a fresh recovery store, ledger, and approval secret."""
    monkeypatch.setenv("PAYGUARD_APPROVAL_SECRET", "test-api-approval-secret")
    app.state.payguard_recovery_store = MerchantRecoveryStore()
    app.state.payguard_executor = RecoveryExecutor(app.state.payguard_recovery_store)
    app.state.payguard_ledger = DecisionLedger()
    app.state.payguard_approval_service = ApprovalService(secret="test-api-approval-secret")
    yield
