"""Business dates come from the lodge's zone, never the VPS's local date."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def lodge_day(lodge, now=None):
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Business time must be timezone-aware')
    try:
        zone = ZoneInfo(getattr(lodge, 'timezone', None) or 'Africa/Johannesburg')
    except ZoneInfoNotFoundError:
        # Historical rows predate time-zone validation; retain the product default.
        zone = ZoneInfo('Africa/Johannesburg')
    return instant.astimezone(zone).date()
