from datetime import datetime, timezone, timedelta
from typing import Optional

TEHRAN_OFFSET_SECONDS = 3 * 3600 + 30 * 60


def normalize_datetime_filter(value: str, *, end: bool = False) -> str:
    value = (value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not value:
        return ""
    date_part, sep, time_part = value.replace("-", "/").partition(" ")
    parts = date_part.split("/")
    if len(parts) == 3 and len(parts[0]) == 4:
        year, month, day = map(int, parts)
        if year < 1700:
            year, month, day = jalali_to_gregorian(year, month, day)
        date_part = f"{year:04d}-{month:02d}-{day:02d}"
        clock = time_part or ("23:59:59" if end else "00:00:00")
        local_dt = datetime.fromisoformat(date_part + "T" + clock)
        utc_dt = local_dt - timedelta(seconds=TEHRAN_OFFSET_SECONDS)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S")
    return value

def jalali_to_gregorian(jy: int, jm: int, jd: int):
    jy += 1595
    days = -355668 + 365*jy + (jy//33)*8 + ((jy%33)+3)//4 + jd
    days += (jm-1)*31 if jm < 7 else (jm-7)*30 + 186
    gy = 400*(days//146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100*(days//36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4*(days//1461)
    days %= 1461
    if days > 365:
        gy += (days-1)//365
        days = (days-1)%365
    gd = days + 1
    leap = gy%4 == 0 and (gy%100 != 0 or gy%400 == 0)
    month_days = [0,31,29 if leap else 28,31,30,31,30,31,31,30,31,30,31]
    gm = 1
    while gm <= 12 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return gy, gm, gd


def format_tehran_jalali(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        raw = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
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
