"""中文相对时间词归一化：把「昨天 / 上周一 / 3天前 / 上个月」等换算成具体日期。

设计原则：
- 纯规则、零依赖、确定性——不经过大模型，杜绝换算幻觉
- 时区固定为东八区（比赛场景在国内）
- 替换形如「2026年10月24日（昨天）」：检索式拿到具体日期，原词保留在括号里
  （意图识别用的关键词如「今天」仍可命中，且人读起来不突兀）
- 单趟正则替换（alternation），插入的日期文本不会被再次匹配
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8), "CST")

CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

WEEK_CN = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "日": 7, "天": 7, "末": 6}  # 周末按周六处理


def _cn2int(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("十"):
        rest = s[1:]
        return 10 + (CN_NUM.get(rest, 0) if rest else 0)
    if "十" in s:
        a, _, b = s.partition("十")
        return CN_NUM.get(a, 1) * 10 + CN_NUM.get(b, 0)
    return 0


def _d(y: int, m: int, dd: int) -> str:
    return f"{y}年{m}月{dd}日"


def _short(dt: datetime) -> str:
    return f"{dt.month}月{dt.day}日"


def _day(dt: datetime, orig: str, period: str = "") -> str:
    base = _d(dt.year, dt.month, dt.day)
    return f"{base}{period}（{orig}）" if period else f"{base}（{orig}）"


def _last_weekday(today: datetime, target: int, weeks_back: int = 0) -> datetime:
    """距离 today 最近的上一个 target 星期（1=周一），可选再往前推几周。"""
    delta = (today.weekday() - target) % 7
    if delta == 0:
        delta = 7
    return today - timedelta(days=delta + weeks_back * 7)


def _this_weekday(today: datetime, target: int) -> datetime:
    """本周的 target 星期；若在未来则视为刚过去的那个。"""
    d = today + timedelta(days=target - 1 - today.weekday())
    if d.date() > today.date():
        d -= timedelta(days=7)
    return d


def _next_weekday(today: datetime, target: int, weeks_ahead: int = 1) -> datetime:
    delta = (target - 1 - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta + (weeks_ahead - 1) * 7)


# 单趟替换用的组合正则（长词在前，避免被短词抢先）
_NUM = r"[0-9一二两三四五六七八九十]{1,3}"
PATTERN = re.compile(
    "|".join([
        r"大前天", r"大后天",
        r"昨晚", r"今早", r"今晨", r"今晚",
        r"前天", r"昨天", r"昨日", r"今天", r"今日", r"明天", r"明日", r"后天",
        r"近几天", r"最近几天", r"这几天",
        r"上上个月", r"上个月", r"上月", r"这个月", r"本月",
        r"前年", r"去年", r"今年",
        rf"(上|下)?(?:星期|礼拜|周)([一二两三四五六日天末])",
        r"上周末",
        rf"{_NUM}天前", rf"{_NUM}个月前", rf"{_NUM}周前", rf"{_NUM}年前",
        r"上周", r"上周六", r"这周", r"本周", r"下周",
        r"最近",
    ])
)


def normalize(text: str) -> tuple[str, list[str]]:
    """返回（归一化后的文本, 换算说明列表）。无命中时原样返回。"""
    now = datetime.now(TZ)
    notes: list[str] = []

    def repl(m: re.Match) -> str:
        w = m.group(0)
        try:
            if w == "大前天":
                r = _day(now - timedelta(days=3), w)
            elif w == "大后天":
                r = _day(now + timedelta(days=3), w)
            elif w == "昨晚":
                r = _day(now - timedelta(days=1), w, "晚上")
            elif w in ("今早", "今晨"):
                r = _day(now, w, "早上")
            elif w == "今晚":
                r = _day(now, w, "晚上")
            elif w in ("前天",):
                r = _day(now - timedelta(days=2), w)
            elif w in ("昨天", "昨日"):
                r = _day(now - timedelta(days=1), w)
            elif w in ("今天", "今日"):
                r = _day(now, w)
            elif w in ("明天", "明日"):
                r = _day(now + timedelta(days=1), w)
            elif w == "后天":
                r = _day(now + timedelta(days=2), w)
            elif w in ("近几天", "最近几天", "这几天"):
                a, b = now - timedelta(days=2), now
                r = f"{_short(a)}至{_short(b)}（{w}）"
            elif w == "上上个月":
                first = now.replace(day=1)
                prev = first - timedelta(days=1)
                prev2 = prev.replace(day=1) - timedelta(days=1)
                r = f"{prev2.year}年{prev2.month}月（{w}）"
            elif w in ("上个月", "上月"):
                first = now.replace(day=1)
                prev = first - timedelta(days=1)
                r = f"{prev.year}年{prev.month}月（{w}）"
            elif w in ("这个月", "本月"):
                r = f"{now.year}年{now.month}月（{w}）"
            elif w == "前年":
                r = f"{now.year - 2}年（{w}）"
            elif w == "去年":
                r = f"{now.year - 1}年（{w}）"
            elif w == "今年":
                r = f"{now.year}年（{w}）"
            elif w == "上周末":
                r = _day(_last_weekday(now, 6), w)
            elif w.startswith(("上周六",)):
                r = _day(_last_weekday(now, 6), w)
            else:
                mw = PATTERN.match  # noqa: F841
                # 前缀 + 星期X
                mm = re.match(r"(上|下)?(?:星期|礼拜|周)([一二两三四五六日天末])$", w)
                if mm:
                    prefix, cn = mm.group(1), mm.group(2)
                    target = WEEK_CN[cn]
                    if prefix == "上":
                        d0 = _last_weekday(now, target, weeks_back=1)
                    elif prefix == "下":
                        d0 = _next_weekday(now, target)
                    else:
                        d0 = _this_weekday(now, target)
                    r = _day(d0, w)
                elif w == "上周":
                    mon = _last_weekday(now, 1, weeks_back=1)
                    sun = mon + timedelta(days=6)
                    r = f"{_short(mon)}至{_short(sun)}（上周）"
                elif w in ("这周", "本周"):
                    mon = now - timedelta(days=now.weekday())
                    sun = mon + timedelta(days=6)
                    r = f"{_short(mon)}至{_short(sun)}（{w}）"
                elif w == "下周":
                    mon = now + timedelta(days=7 - now.weekday())
                    sun = mon + timedelta(days=6)
                    r = f"{_short(mon)}至{_short(sun)}（下周）"
                elif w.endswith("天前"):
                    r = _day(now - timedelta(days=_cn2int(w[:-2])), w)
                elif w.endswith("周前"):
                    r = _day(now - timedelta(weeks=_cn2int(w[:-2])), w)
                elif w.endswith("个月前"):
                    n = max(1, _cn2int(w[:-3]))
                    m0 = now.month - n
                    y0 = now.year + (m0 - 1) // 12
                    m0 = (m0 - 1) % 12 + 1
                    r = f"{y0}年{m0}月（{w}）"
                elif w.endswith("年前"):
                    r = f"{now.year - max(1, _cn2int(w[:-2]))}年（{w}）"
                elif w == "最近":
                    a, b = now - timedelta(days=2), now
                    r = f"{_short(a)}至{_short(b)}（最近）"
                else:
                    return w
            notes.append(f"{w} → {r.split('（')[0]}")
            return r
        except Exception:
            return w

    out = PATTERN.sub(repl, text)
    return out, notes
