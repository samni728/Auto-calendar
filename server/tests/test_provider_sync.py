import os
from datetime import date

os.environ.setdefault("APP_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "test-password-only")

from app.models import ProviderConnection, TimelineEvent
from app.services.providers import _event_body, event_fingerprint


class EmptySession:
    def get(self, _model, _identifier):
        return None


def event() -> TimelineEvent:
    return TimelineEvent(
        id="event-1",
        workspace_id="workspace-1",
        room_id=None,
        title="王女士 · 官网预订",
        guest_name="王女士",
        event_type="reservation",
        status="reserved",
        start_date=date(2026, 8, 19),
        end_date=date(2026, 8, 21),
        notes="延迟入住",
        is_deleted=False,
    )


def connection(provider: str) -> ProviderConnection:
    return ProviderConnection(
        id=f"{provider}-connection",
        user_id="user-1",
        workspace_id="workspace-1",
        provider=provider,
        selected_calendar_id=f"{provider}-calendar",
        sync_label="Auto Calendar · 酒店订房",
    )


def test_event_fingerprint_changes_with_business_data():
    first = event()
    original = event_fingerprint(first)
    first.end_date = date(2026, 8, 22)
    assert event_fingerprint(first) != original


def test_google_payload_uses_all_day_dates_and_private_mapping():
    payload = _event_body(EmptySession(), connection("google"), event())
    assert payload["start"] == {"date": "2026-08-19"}
    assert payload["end"] == {"date": "2026-08-21"}
    assert payload["extendedProperties"]["private"]["autoCalendarEventId"] == "event-1"
    assert payload["extendedProperties"]["private"]["autoCalendarTag"] == (
        "Auto Calendar · 酒店订房"
    )


def test_microsoft_payload_uses_category_and_internal_marker():
    payload = _event_body(EmptySession(), connection("microsoft"), event())
    assert payload["isAllDay"] is True
    assert payload["categories"] == ["Auto Calendar · 酒店订房"]
    assert "AutoCalendar-ID: event-1" in payload["body"]["content"]
