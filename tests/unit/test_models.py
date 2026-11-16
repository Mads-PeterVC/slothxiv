from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from slothxiv.models import RetrievalWindow


def test_normalizes_timezone_and_uses_half_open_boundaries():
    end = datetime(2026, 11, 16, 1, tzinfo=timezone(timedelta(hours=1)))
    window = RetrievalWindow(start=end - timedelta(days=2), end=end)
    assert window.end == datetime(2026, 11, 16, tzinfo=UTC)
    assert window.end.tzinfo == UTC
    assert window.contains(window.start)
    assert not window.contains(window.end)
    assert not window.contains(window.start - timedelta(microseconds=1))


@pytest.mark.parametrize("start,end", [
    ("2026-11-16T00:00:00", "2026-11-17T00:00:00Z"),
    ("2026-11-16T00:00:00Z", "2026-11-16T00:00:00Z"),
    ("2026-11-17T00:00:00Z", "2026-11-16T00:00:00Z"),
])
def test_rejects_naive_and_invalid_windows(start, end):
    with pytest.raises(ValidationError):
        RetrievalWindow(start=start, end=end)
