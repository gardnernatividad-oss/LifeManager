from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import uuid

from unittest.mock import MagicMock, patch

from app.models.enums import CalendarVisibility
from app.services.v2_calendar_comparison import BusyBlock, compare_calendar, _merge_busy


def test_busy_blocks_merge_overlap_and_contiguous_without_identity() -> None:
    start = datetime(2027, 1, 4, 10, tzinfo=timezone.utc)
    events = [
        SimpleNamespace(activity=SimpleNamespace(starts_at=start, ends_at=start + timedelta(hours=1))),
        SimpleNamespace(activity=SimpleNamespace(starts_at=start + timedelta(minutes=30), ends_at=start + timedelta(hours=2))),
        SimpleNamespace(activity=SimpleNamespace(starts_at=start + timedelta(hours=2), ends_at=start + timedelta(hours=3))),
        SimpleNamespace(activity=SimpleNamespace(starts_at=start + timedelta(hours=4), ends_at=start + timedelta(hours=5))),
    ]
    assert _merge_busy(events) == [
        BusyBlock(starts_at=start, ends_at=start + timedelta(hours=3)),
        BusyBlock(starts_at=start + timedelta(hours=4), ends_at=start + timedelta(hours=5)),
    ]


def test_show_details_is_scoped_to_the_shared_workspace_but_availability_is_opaque_global() -> None:
    workspace_id, viewer_id, target_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    start = datetime(2027, 1, 4, 10, tzinfo=timezone.utc)
    membership = SimpleNamespace(calendar_visibility=CalendarVisibility.SHOW_DETAILS)
    with patch("app.services.v2_calendar_comparison._lock_comparison_context", return_value=membership), patch("app.services.v2_calendar_comparison.list_my_calendar", return_value=[]) as listing:
        compare_calendar(MagicMock(), workspace_id=workspace_id, viewer_id=viewer_id, target_id=target_id, range_start=start, range_end=start + timedelta(days=1), now=start)
    assert listing.call_args.kwargs["workspace_id"] == workspace_id

    membership.calendar_visibility = CalendarVisibility.AVAILABILITY_ONLY
    with patch("app.services.v2_calendar_comparison._lock_comparison_context", return_value=membership), patch("app.services.v2_calendar_comparison.list_my_calendar", return_value=[]) as listing:
        compare_calendar(MagicMock(), workspace_id=workspace_id, viewer_id=viewer_id, target_id=target_id, range_start=start, range_end=start + timedelta(days=1), now=start)
    assert "workspace_id" not in listing.call_args.kwargs
