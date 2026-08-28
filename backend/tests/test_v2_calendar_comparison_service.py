from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.v2_calendar_comparison import BusyBlock, _merge_busy


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
