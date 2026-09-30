from datetime import datetime, timezone
from typing import Optional

TEHRAN_OFFSET_SECONDS = 3 * 3600 + 30 * 60


def normalize_datetime_filter(value: str, *, end: bool = False) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) == 10:
        return value + ("T23:59:59" if end else "T00:00:00")
    return value


def format_tehran_jalali(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        raw = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            from datetime import timedelta
            dt = dt.astimezone(timezone(timedelta(seconds=TEHRAN_OFFSET_SECONDS)))
        gy, gm, gd = dt.year, dt.month, dt.day
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        return f"{jy:04d}/{jm:02d}/{jd:02d} {dt.hour:02d}:{dt.minute:02d}"
    except (ValueError, TypeError):
        return value


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 + gd + g_d_m[gm-1]
    jy = -1595 + 33*(days//12053)
    days %= 12053
    jy += 4*(days//1461)
    days %= 1461
    if days > 365:
        jy += (days-1)//365
        days = (days-1)%365
    if days < 186:
        jm = 1 + days//31
        jd = 1 + days%31
    else:
        jm = 7 + (days-186)//30
        jd = 1 + (days-186)%30
    return jy, jm, jd
