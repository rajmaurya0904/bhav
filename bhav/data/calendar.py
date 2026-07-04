"""NSE trading calendar. Holidays list must be maintained per year."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

NSE_HOLIDAYS: set[date] = {
    date(2024, 1, 22), date(2024, 3, 25), date(2024, 3, 29),
    date(2024, 4, 14), date(2024, 4, 17), date(2024, 5, 23),
    date(2024, 6, 17), date(2024, 7, 17), date(2024, 8, 15),
    date(2024, 10, 2), date(2024, 10, 24), date(2024, 11, 15),
    date(2024, 12, 25),
    date(2025, 2, 26), date(2025, 3, 14), date(2025, 4, 14),
    date(2025, 4, 17), date(2025, 8, 15), date(2025, 10, 2),
    date(2026, 1, 1), date(2026, 1, 26), date(2026, 3, 3),
    date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 24),
}


class NSECalendar:
    """Trading day / session utilities. All times are IST."""

    def __init__(self, holidays: set[date] | None = None):
        self.holidays = holidays if holidays is not None else NSE_HOLIDAYS

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def trading_days(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        d = start
        while d <= end:
            if self.is_trading_day(d):
                out.append(d)
            d += timedelta(days=1)
        return out

    def is_market_open(self, ts: datetime) -> bool:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        else:
            ts = ts.astimezone(IST)
        if not self.is_trading_day(ts.date()):
            return False
        t = ts.time()
        return MARKET_OPEN <= t <= MARKET_CLOSE

    @staticmethod
    def to_ist(ts: datetime) -> datetime:
        return ts.astimezone(IST) if ts.tzinfo else ts.replace(tzinfo=IST)
