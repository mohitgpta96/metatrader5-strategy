"""
News / Economic Event Blackout Filter.

Prevents signals during ±30 minutes of high-impact economic events.
Even the best technical signal fails if a surprise news spike hits.

Events covered:
  - US NFP         : First Friday of every month, 13:30 UTC
  - FOMC           : 8 meetings/year, announcement at 19:00 UTC
  - RBI MPC        : 6 meetings/year, announcement at ~04:30 UTC
                     (only applied to Indian instruments: .NS, ^NSEI)
"""
import calendar
from datetime import datetime, timezone, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import NEWS_BLACKOUT_MINUTES


# ── FOMC dates — announcement day (second day of 2-day meeting) ───────────────
# Federal Reserve announces at 2 PM ET.
#   EST (Nov–Mar): 2 PM ET = 19:00 UTC
#   EDT (Mar–Nov): 2 PM ET = 18:00 UTC
# We use 18:30 UTC as the midpoint and a wide buffer to cover both.
#
# !! ANNUAL UPDATE REQUIRED — add next year's dates every January !!
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_DATES = {
    # 2025 (complete)
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (complete — verified 2026-02-28)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027 — ADD IN JANUARY 2027 from federalreserve.gov
}
FOMC_UTC_HOUR   = 18
FOMC_UTC_MINUTE = 30

# ── RBI MPC dates — announcement day ─────────────────────────────────────────
# RBI Governor announces around 10:00 AM IST = 04:30 UTC.
#
# !! ANNUAL UPDATE REQUIRED — add next year's dates every January !!
# Source: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx
RBI_MPC_DATES = {
    # 2025 (complete)
    "2025-02-07", "2025-04-09", "2025-06-06",
    "2025-08-07", "2025-10-01", "2025-12-05",
    # 2026 (complete — verified 2026-02-28)
    "2026-02-07", "2026-04-03", "2026-06-05",
    "2026-08-07", "2026-10-09", "2026-12-04",
    # 2027 — ADD IN JANUARY 2027 from rbi.org.in
}
RBI_UTC_HOUR   = 4
RBI_UTC_MINUTE = 30

# Indian instrument identifiers (for RBI filter)
_INDIAN_SUFFIXES = (".NS", "^NSEI", "^NSEBANK")


def _get_nfp_datetime(year, month):
    """Return UTC datetime of NFP release for given year+month.
    NFP = first Friday of month, 8:30 AM ET.
    We use 13:30 UTC (conservative — covers both EST and EDT).
    """
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        friday = week[calendar.FRIDAY]
        if friday != 0:
            return datetime(year, month, friday, 13, 30, tzinfo=timezone.utc)
    return None


def is_news_blackout(ticker=None, buffer_minutes=None):
    """
    Check if the current time is within the blackout window of a major event.

    Args:
        ticker:         Optional ticker string. If provided, RBI MPC filter
                        is applied only to Indian instruments (.NS / indices).
        buffer_minutes: Override default NEWS_BLACKOUT_MINUTES from settings.

    Returns:
        (bool, str) — (True if blackout, reason string or "")

    Examples:
        blocked, reason = is_news_blackout("GC=F")
        if blocked:
            print(f"Signal blocked: {reason}")
    """
    buf = timedelta(minutes=buffer_minutes if buffer_minutes is not None else NEWS_BLACKOUT_MINUTES)
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # ── US NFP ────────────────────────────────────────────────────────────────
    nfp_dt = _get_nfp_datetime(now.year, now.month)
    if nfp_dt and abs(now - nfp_dt) <= buf:
        mins = int(abs((now - nfp_dt).total_seconds()) / 60)
        return True, f"US NFP release (T{'+' if now > nfp_dt else '-'}{mins}min — ±{buffer_minutes or NEWS_BLACKOUT_MINUTES}min blackout)"

    # ── FOMC ──────────────────────────────────────────────────────────────────
    if today_str in FOMC_DATES:
        fomc_dt = datetime(now.year, now.month, now.day,
                           FOMC_UTC_HOUR, FOMC_UTC_MINUTE, tzinfo=timezone.utc)
        if abs(now - fomc_dt) <= buf:
            mins = int(abs((now - fomc_dt).total_seconds()) / 60)
            return True, f"FOMC announcement (T{'+' if now > fomc_dt else '-'}{mins}min — ±{buffer_minutes or NEWS_BLACKOUT_MINUTES}min blackout)"

    # ── RBI MPC — Indian instruments only ────────────────────────────────────
    is_indian = ticker and any(ind in ticker for ind in _INDIAN_SUFFIXES)
    if is_indian and today_str in RBI_MPC_DATES:
        rbi_dt = datetime(now.year, now.month, now.day,
                          RBI_UTC_HOUR, RBI_UTC_MINUTE, tzinfo=timezone.utc)
        if abs(now - rbi_dt) <= buf:
            mins = int(abs((now - rbi_dt).total_seconds()) / 60)
            return True, f"RBI MPC announcement (T{'+' if now > rbi_dt else '-'}{mins}min — ±{buffer_minutes or NEWS_BLACKOUT_MINUTES}min blackout)"

    return False, ""


def get_upcoming_events(hours_ahead=24):
    """
    List major events coming in the next N hours.
    Useful for logging / pre-scan warnings.

    Returns: list of (event_name, utc_datetime) tuples
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=hours_ahead)
    upcoming = []

    # Check NFP for current and next month
    for delta_months in (0, 1):
        year  = now.year + (now.month + delta_months - 1) // 12
        month = (now.month + delta_months - 1) % 12 + 1
        nfp_dt = _get_nfp_datetime(year, month)
        if nfp_dt and now < nfp_dt <= horizon:
            upcoming.append(("US NFP", nfp_dt))

    # FOMC
    for date_str in FOMC_DATES:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        event_dt = d.replace(hour=FOMC_UTC_HOUR, minute=FOMC_UTC_MINUTE)
        if now < event_dt <= horizon:
            upcoming.append(("FOMC", event_dt))

    # RBI MPC
    for date_str in RBI_MPC_DATES:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        event_dt = d.replace(hour=RBI_UTC_HOUR, minute=RBI_UTC_MINUTE)
        if now < event_dt <= horizon:
            upcoming.append(("RBI MPC", event_dt))

    upcoming.sort(key=lambda x: x[1])
    return upcoming


if __name__ == "__main__":
    print("News Filter — Current Status")
    print("=" * 45)

    blocked, reason = is_news_blackout("GC=F")
    print(f"Gold (GC=F):       {'BLOCKED — ' + reason if blocked else 'OK'}")

    blocked, reason = is_news_blackout("RELIANCE.NS")
    print(f"Reliance (.NS):    {'BLOCKED — ' + reason if blocked else 'OK'}")

    events = get_upcoming_events(hours_ahead=48)
    if events:
        print(f"\nUpcoming events (next 48h):")
        for name, dt in events:
            print(f"  {name:<12} {dt.strftime('%Y-%m-%d %H:%M UTC')}")
    else:
        print("\nNo major events in next 48 hours.")
