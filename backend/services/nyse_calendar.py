"""
NYSE 交易日历（exchange_calendars / XNYS）：热门股计分、简讯归属、是否生成盘前/盘后简报。
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

_ET = ZoneInfo("America/New_York")
_cal = None


def _xnys():
    global _cal
    if _cal is None:
        _cal = xcals.get_calendar("XNYS")
    return _cal


def is_nyse_trading_day_et(now: datetime | None = None) -> bool:
    """
    给定时刻对应的美东「日历日」是否为 NYSE 交易日（周末、联邦假日等为 False）。
    用于决定是否生成盘前/盘后简报。
    """
    cal = _xnys()
    if now is None:
        t = datetime.now(_ET)
    else:
        tn = pd.Timestamp(now)
        if tn.tzinfo is None:
            from datetime import timezone as _tz

            tn = tn.tz_localize(_tz.utc)
        t = tn.tz_convert(_ET)
    d = pd.Timestamp(t.date())
    return bool(cal.is_session(d))


def next_nyse_session_datetime_et(
    hour: int,
    minute: int,
    *,
    now: datetime | None = None,
) -> datetime:
    """
    返回下一个 NYSE 交易日上的指定美东时间。

    如果今天是交易日且该时间尚未过去，返回今天；否则向后找下一个交易日。
    用于定时任务真正只排交易日，而不是每天触发后再跳过。
    """
    cal = _xnys()
    if now is None:
        et_now = datetime.now(_ET)
    else:
        tn = pd.Timestamp(now)
        if tn.tzinfo is None:
            tn = tn.tz_localize("UTC")
        et_now = tn.tz_convert(_ET).to_pydatetime()

    start_day = pd.Timestamp(et_now.date())
    for offset in range(0, 31):
        day = start_day + pd.Timedelta(days=offset)
        if not cal.is_session(day):
            continue
        candidate = datetime.combine(day.date(), time(hour=hour, minute=minute), tzinfo=_ET)
        if candidate > et_now:
            return candidate

    raise RuntimeError("Unable to find next NYSE session within 31 days")


def nyse_session_dates_last_n(n: int) -> frozenset[str]:
    """最近 n 个美股交易日（含当前周期内最后一个已存在的会话日），YYYY-MM-DD。"""
    if n <= 0:
        return frozenset()
    cal = _xnys()
    et_now = datetime.now(_ET)
    end = pd.Timestamp(et_now.date())
    start = end - pd.Timedelta(days=n * 3 + 21)
    sessions = cal.sessions_in_range(start, end)
    if len(sessions) == 0:
        return frozenset()
    tail = sessions[-n:] if len(sessions) >= n else sessions
    return frozenset(s.strftime("%Y-%m-%d") for s in tail)


def datetime_to_nyse_session_date_str(ts) -> str:
    """
    将一条简讯的发布时间映射到「归属」的 NYSE 交易日（美东日历上的会话日）。
    非交易日（周末、休市）归到 direction=previous 的最近一个交易日。
    """
    cal = _xnys()
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert(_ET)
    d = pd.Timestamp(t.date())
    if cal.is_session(d):
        return d.strftime("%Y-%m-%d")
    sess = cal.date_to_session(d, direction="previous")
    return sess.strftime("%Y-%m-%d")
