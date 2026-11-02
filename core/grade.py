"""来源分级：把「权威度」做成可计算、可解释的东西。

S(5) 政府/官方机构/权威辟谣平台；A(4) 央媒与专业机构；B(2~3) 主流门户/转载；C(1) 自媒体营销号。
规则：1 条 S 或 ≥2 个互不相同的 A 域名，才允许下「真 / 假」结论。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import config

S_SITES = {
    "中国互联网联合辟谣平台", "科学辟谣", "中国科协", "国家卫生健康委", "市场监管总局",
    "腾讯医典", "中国疾病预防控制中心", "央视新闻", "人民日报", "中国气象局",
}
# 站点名里带这些词、且不是长标题的，基本是官方号（"广州番禺发布""广州辟谣"这类）
S_SITE_HINTS = (
    "辟谣", "网信", "公安", "发布", "人民政府", "政府门户", "卫健委", "卫生健康",
    "疾控", "市场监管", "应急管理", "气象局", "检察院", "法院", "政务服务",
)
A_DOMAINS = (
    # 央媒 / 全国性
    "people.com.cn", "xinhuanet.com", "news.cn", "cctv.com", "chinanews.com.cn",
    "gmw.cn", "thepaper.cn", "caixin.com", "yicai.com", "jiemian.com", "cls.cn",
    "21jingji.com", "stcn.com", "nbd.com.cn", "bjnews.com.cn", "cnr.cn",
    "china.com.cn", "ce.cn", "cyol.com", "workercn.cn", "legaldaily.com.cn",
    "piyao.org.cn", "kepuchina.cn", "cast.org.cn", "sciencenet.cn",
    # 广东 / 广州本地主流媒体（本地传言的关键信源）
    "dayoo.com", "gzdaily.com", "ycwb.com", "ycwb.com.cn", "xkb.com.cn",
    "oeeee.com", "nfnews.com", "southcn.com", "xxsb.com", "gd.sina.com.cn",
    "sznews.com", "nfapp.southcn.com",
    # 医疗健康
    "dxy.com", "guokr.com", "cn-healthcare.com", "medsci.cn", "haodf.com",
)
B_DOMAINS = (
    "qq.com", "sina.com.cn", "sina.cn", "sohu.com", "163.com", "ifeng.com",
    "baijiahao.baidu.com", "toutiao.com", "zhihu.com", "douban.com", "bilibili.com",
)


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _hit(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def _official_site(site: str) -> bool:
    """站点名短且带官方标识词 → 视为官方号（如「广州番禺发布」「广州辟谣」）。"""
    if not site or len(site) > 16:
        return False
    return any(h in site for h in S_SITE_HINTS)


def grade(page: dict) -> dict:
    """返回 page 的 grade 字段（S/A/B/C）与 0~5 分值。"""
    host = domain_of(page.get("url", ""))
    site = (page.get("site") or "").strip()
    auth = int(page.get("authority_level") or 0)

    if (host.endswith(".gov.cn") or host.endswith(".gov") or site in S_SITES
            or auth >= 5 or _official_site(site)):
        g, s = "S", 5
    elif _hit(host, A_DOMAINS) or auth >= 4:
        g, s = "A", 4
    elif _hit(host, B_DOMAINS) or auth >= 2:
        g, s = "B", 2
    else:
        g, s = "C", 1

    page["grade"] = g
    page["grade_score"] = s
    page["domain"] = host
    page["date_ts"] = parse_ts(page.get("date", ""))
    return page


def parse_ts(s: str) -> int:
    if not s:
        return 0
    s = s.strip().replace("/", "-")
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(s[: len(fmt) + 2], fmt).replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            continue
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return int(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc).timestamp())
        except Exception:
            return 0
    return 0


def age_days(page: dict) -> int | None:
    ts = page.get("date_ts") or 0
    if not ts:
        return None
    return max(0, int((datetime.now(timezone.utc).timestamp() - ts) / 86400))


def evidence_ok(evidence: list[dict]) -> tuple[bool, str]:
    """是否满足「可下结论」的门槛。"""
    if not evidence:
        return False, "没有可引用的证据"
    best = max(p["grade_score"] for p in evidence)
    strong = [p for p in evidence if p["grade_score"] >= config.MIN_GRADE_FOR_VERDICT]
    domains = {p["domain"] for p in strong}
    if best < config.MIN_GRADE_FOR_VERDICT:
        return False, "最高权威来源仅为 B/C 级，不足以定论"
    if best < 5 and len(domains) < config.MIN_DISTINCT_DOMAINS:
        return False, "仅有单一权威来源，缺少交叉印证"
    return True, ""


def sort_key(page: dict) -> tuple:
    return (page.get("grade_score", 0), page.get("date_ts", 0), float(page.get("score") or 0))
