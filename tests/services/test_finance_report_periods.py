from datetime import datetime, timedelta, timezone

import pytest

from api.routes.finance import ReportPeriod, _resolve_report_period
from services.finance_service import previous_report_period


def test_previous_report_period_is_adjacent_and_equal_duration():
    current_from = datetime(2026, 8, 10, 7, 30, tzinfo=timezone.utc)
    current_to = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)

    previous_from, previous_to = previous_report_period(current_from, current_to)

    assert previous_to == current_from - timedelta(microseconds=1)
    assert previous_to - previous_from == current_to - current_from


def test_month_report_starts_at_midnight_in_tenant_timezone():
    start, end = _resolve_report_period(
        ReportPeriod.MONTH,
        from_date=None,
        to_date=None,
        now=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
    )

    assert start == datetime(2026, 7, 31, 21, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def test_custom_report_rejects_reversed_dates_after_timezone_normalization():
    with pytest.raises(Exception) as exc_info:
        _resolve_report_period(
            ReportPeriod.CUSTOM,
            from_date=datetime(2026, 8, 12, 12, 0),
            to_date=datetime(2026, 8, 11, 12, 0),
        )

    assert getattr(exc_info.value, "status_code", None) == 422
