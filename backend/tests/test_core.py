from app.detector import IncidentDetector
from app.projector import StateProjector
from app.simulator import duplicate_webhook, fulfillment_failure, healthy, orphaned_payment


def project(events):
    return StateProjector().project(events[0].transaction_id, events)


def test_healthy_has_no_incident():
    state = project(healthy())
    assert state.payment.status == "CAPTURED"
    assert state.order.status == "PAID"
    assert state.fulfillment.status == "COMPLETED"
    assert IncidentDetector().detect(state) == []


def test_orphaned_payment_is_detected():
    state = project(orphaned_payment())
    incidents = IncidentDetector().detect(state)
    assert len(incidents) == 1
    assert incidents[0].incident_type == "ORPHANED_PAYMENT"
    assert incidents[0].revenue_at_risk == 7499


def test_duplicate_webhook_does_not_change_state_twice():
    state = project(duplicate_webhook())
    assert state.order.status == "PAID"
    assert state.event_ids_applied.count("d3") == 1


def test_fulfillment_failure_detected():
    state = project(fulfillment_failure())
    incidents = IncidentDetector().detect(state)
    assert len(incidents) == 1
    assert incidents[0].incident_type == "FULFILLMENT_FAILURE"


def test_out_of_order_arrival_uses_event_time():
    # delayed_webhook() intentionally arrives out of order: order.paid arrives before payment.captured.
    from app.simulator import delayed_webhook
    state = project(delayed_webhook())
    assert state.payment.status == "CAPTURED"
    assert state.order.status == "PAID"
    assert IncidentDetector().detect(state) == []


def test_ingestor_rejects_duplicate_event_id():
    from app.ingest import EventIngestor
    events = healthy()
    ingestor = EventIngestor()
    first = ingestor.ingest(events[0])
    second = ingestor.ingest(events[0])
    assert first.accepted is True
    assert second.duplicate is True
    assert second.accepted is False
