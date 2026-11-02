"""五步调查流水线：拆解 → 首轮检索 → 补缺检索 → 交叉验证 → 出卡兜底。

每一步都写进 trace，前端把中间过程展示出来——这是"难度分"的来源。
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from . import config, grade, llm, timewords, yuanbao

LABEL = {
    "true": "真",
    "false": "假",
    "uncertain": "说不准",
    "partially_true": "部分属实",
    "not_found": "没查到",
}

STOP = set("的了是在有和与及吗呢吧啊我你他她它们这那个一不都会说要就还也很都")
FALSE_HINTS = ("谣言", "不实", "辟谣", "假的", "并非", "系谣言", "误读", "澄清", "未发现", "查无此事")
NEG_HINTS = ("不会", "没有证据", "并无证据", "远低于", "并不能", "无需担心", "不存在", "说法不准")
TRUE_HINTS = ("官方通报", "已确认", "证实", "确实", "回应称")

# 事件类（地震/台风等）：走专门的"事件核实"流水线
EVENT_RE = re.compile(r"地震|台风|暴雨|洪水|火灾|爆炸|滑坡|泥石流|海啸|暴雪|龙卷风|冰雹|沙尘暴|预警")
REPOST_DOMAINS = ("toutiao.com", "baijiahao.baidu.com", "zhihu.com", "weibo.com",
                  "weibo.cn", "douyin.com", "kuaishou.com")
REPOST_HINTS = ("网传", "网曝", "据传", "传言", "传闻", "转发", "网友爆料")
EVENT_SITE_MAP = {"地震": ("ceic.ac.cn", "news.cn"), "台风": ("cma.gov.cn", "news.cn")}
EVENT_DEFAULT_SITE = "news.cn"


# ---------------------------------------------------------------- 工具
def _clean(text: str) -> str:
    return re.sub(r"[\s\u3000]+", " ", text).strip(" ，。！？!?、~～\"'")


def _normalize_url(url: str) -> str:
    try:
        s = urlsplit(url)
        return urlunsplit((s.scheme, s.netloc, s.path, "", ""))
    except Exception:
        return url


def _dedupe(pages: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in pages:
        key = _normalize_url(p["url"])
        tkey = re.sub(r"\W+", "", p.get("title", ""))[:24]
        if key in seen or (tkey and tkey in seen):
            continue
        seen.add(key)
        if tkey:
            seen.add(tkey)
        out.append(p)
    return out


JUNK_RE = re.compile(r"(node_\d+|cms_node_post_list|/index\.(?:html?|php)|threadqr=|cms_node)")


def _is_junk(p: dict) -> bool:
    """过滤首页、栏目页、站内搜索页——它们有权威度但没有内容，会污染证据。"""
    url = p.get("url", "")
    path = urlsplit(url).path
    if path in ("", "/") or path.endswith("/index.html") or path.endswith("/index.htm"):
        return True
    if JUNK_RE.search(url):
        return True
    if "?" in url and re.search(r"(^|[?&])(id|tid|fid)=", url):
        return True
    if len((p.get("title") or "").strip()) < 8:
        return True
    if path.count("/") <= 1 and len(path) < 14:
        return True
    return False


def _relevance(p: dict, claim: str) -> float:
    """标题/摘要与主张的字面重合度，用来把「新但不相干」压下去。"""
    grams = set(re.findall(r"[\u4e00-\u9fa5]{2}", claim)) | set(
        w for w in re.findall(r"[A-Za-z0-9]{2,}", claim))
    if not grams:
        return 0.0
    text = (p.get("title") or "") + " " + (p.get("passage") or "")[:80]
    hit = sum(1 for g in grams if g in text)
    return round(hit / len(grams), 3)


def _rank(pages: list[dict], claim: str) -> list[dict]:
    for p in pages:
        p["relevance"] = _relevance(p, claim)
    # 有相关结果时，把「零相关」的权威页（政府提案答复、栏目页）清出去，否则它们会霸占证据位
    relevant = [p for p in pages if p["relevance"] > 0]
    if len(relevant) >= 4:
        pages = relevant
    pages.sort(key=lambda p: (p["relevance"] * 10 + p["grade_score"], p.get("date_ts", 0)),
               reverse=True)
    return pages


def _keywords(claim: str) -> str:
    words = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", claim)
    keep = [w for w in words if w[0] not in STOP]
    return " ".join(keep[:6]) or _clean(claim)[:20]


def heuristic_plan(claim: str) -> dict:
    c = _clean(claim)
    intent = "verify"
    if EVENT_RE.search(c):
        intent = "event"
    elif re.search(r"(叫什么|哪部|哪个|是谁|想找|求|有没有.*(店|剧|歌|游戏))", c):
        intent = "find"
    elif re.search(r"(今天|最新|现在|刚刚|还有票|进展)", c):
        intent = "latest"
    kw = _keywords(c)
    queries = [c[:40], f"{kw} 辟谣", f"{kw} 官方 通报"]
    return {"intent": intent, "claim": c, "queries": queries,
            "freshness": "d3" if intent == "event" else "d7" if intent == "latest" else "none",
            "why": "未配置大模型，采用关键词规则生成检索式"}


# ---------------------------------------------------------------- 主流程
def investigate(claim: str, *, intent: str = "auto", freshness: str | None = None) -> dict:
    t0 = time.time()
    claim = _clean(claim)
    if not claim:
        raise ValueError("请输入要查证的内容")
    # ---- Step 0 时间归一化：相对时间词 → 具体年月日（纯规则，防幻觉）
    orig_claim = claim
    claim, time_notes = timewords.normalize(claim)
    if not config.MOCK_SEARCH and (not config.SECRET_ID or not config.SECRET_KEY):
        raise ValueError(
            "未配置元宝搜索密钥：复制 .env.example 为 .env 并填入 "
            "TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY（调试可临时设 MOCK_SEARCH=1）"
        )
    trace: list[dict] = []
    warnings: list[str] = []
    searches = 0

    # ---- Step 1 拆解主张
    if llm.available():
        try:
            p = llm.plan(claim)
            mode_note = f"大模型判定的意图：{p.get('intent')}｜思路：{p.get('why', '')}"
        except Exception as e:  # 大模型挂了也要能跑
            p = heuristic_plan(claim)
            mode_note = f"大模型调用失败，回退规则模式（{e}）"
            warnings.append("规划阶段降级")
    else:
        p = heuristic_plan(claim)
        mode_note = "未配置大模型，使用关键词规则拆解"
        warnings.append("未配置大模型")

    if intent in ("verify", "find", "latest", "event"):
        p["intent"] = intent
    if freshness:
        p["freshness"] = freshness

    trace.append({
        "step": 1, "title": "拆解主张",
        "detail": f"「{p['claim']}」→ 意图 {p['intent']}，生成 {len(p['queries'])} 条检索式",
        "queries": p["queries"], "note": mode_note + (
            "；时间归一化（规则换算）：" + "，".join(time_notes) if time_notes else ""),
    })

    # 事件类（地震/台风等）：专门的"多轮 + 官方平台定向取证"流水线
    if p["intent"] == "event":
        p["claim_orig"] = orig_claim
        p["time_notes_joined"] = "；".join(time_notes)
        return _event_investigate(p, trace, warnings, t0)

    # ---- Step 2 首轮检索
    pages: list[dict] = []
    search_errors: list[str] = []
    calls = 0
    for q in p["queries"][:3]:
        try:
            calls += 1
            res = yuanbao.search(q, freshness=None if p.get("freshness") in (None, "none") else p["freshness"])
            searches += 1
            for x in res["pages"]:
                x["_query"] = q
            pages += res["pages"]
            trace.append({
                "step": 2, "title": "首轮检索", "detail": f"检索式「{q}」命中 {len(res['pages'])} 条",
                "query": q, "hits": len(res["pages"]), "note": f"版本 {res['version']}",
            })
        except Exception as e:
            search_errors.append(str(e))
            trace.append({"step": 2, "title": "首轮检索", "detail": f"检索式「{q}」失败",
                          "query": q, "hits": 0, "note": str(e)[:160]})
            warnings.append(f"检索失败：{q}")

    # 全部检索都失败时，绝不能伪装成「没查到」——必须把接口错误抛出去
    if not pages and search_errors and len(search_errors) == calls:
        raise RuntimeError("元宝搜索调用失败：" + search_errors[0])
    if search_errors:
        warnings.append(f"{len(search_errors)} 条检索式失败，结论可能不完整")
    pages = [grade.grade(p) for p in _dedupe(pages)]
    dropped = [x for x in pages if _is_junk(x)]
    pages = _rank([x for x in pages if not _is_junk(x)], p["claim"])
    counts = _counts(pages)
    trace.append({"step": 2, "title": "首轮去重分级",
                  "detail": f"去重后 {len(pages) + len(dropped)} 条，剔除 {len(dropped)} 个首页/栏目页，"
                            f"保留 {len(pages)} 条：S {counts['S']} / A {counts['A']} / B {counts['B']} / C {counts['C']}",
                  "note": "权威度由接口 authority_level + 域名白名单判定，再按相关度重排"})

    # ---- Step 3 补缺检索（多步调查的关键）
    kw = _keywords(p["claim"])
    extra: list[tuple[str, dict]] = []
    has_official = counts["S"] > 0
    has_a = counts["A"] > 0
    has_recent = any((grade.age_days(x) or 9999) <= 45 for x in pages)

    if not has_official:
        extra.append((f"{kw} 官方 通报", {"industry": "gov"}))
    if not has_a and not has_official:
        extra.append((f"{kw} 辟谣", {"site": "piyao.org.cn"}))
    if p.get("freshness") not in (None, "none") and not has_recent:
        extra.append((kw, {"freshness": "d7"}))
    # 权威来源只有一家时，再多要一轮独立信源，尽量凑齐交叉印证
    strong_domains = {x["domain"] for x in pages if x["grade_score"] >= config.MIN_GRADE_FOR_VERDICT}
    if 0 < len(strong_domains) < config.MIN_DISTINCT_DOMAINS:
        extra.append((f"{kw} 辟谣 不实", {}))

    for q, kwarg in extra[:2]:
        try:
            res = yuanbao.search(q, **kwarg)
            searches += 1
            for x in res["pages"]:
                x["_query"] = q
            before = len(pages)
            merged = _dedupe(pages + [grade.grade(x) for x in res["pages"]])
            pages = merged
            added = len(pages) - before
            label = "官方口径" if kwarg.get("industry") == "gov" else (
                "辟谣库" if kwarg.get("site") else "时效补查")
            trace.append({"step": 3, "title": f"补缺检索·{label}",
                          "detail": f"针对「{_gap_reason(counts)}」追加检索「{q}」，新增 {added} 条",
                          "query": q, "hits": added, "note": str(kwarg)})
        except Exception as e:
            trace.append({"step": 3, "title": "补缺检索", "detail": f"「{q}」失败",
                          "query": q, "hits": 0, "note": str(e)[:160]})
    if not extra:
        trace.append({"step": 3, "title": "补缺检索", "detail": "首轮已覆盖官方来源，无需补查",
                      "note": "覆盖检查通过"})

    pages = [grade.grade(x) for x in pages if not _is_junk(x)]
    pages = _rank(_dedupe(pages), p["claim"])
    counts = _counts(pages)

    # ---- Step 4 交叉验证
    card = None
    llm_sources = pages[:12]
    if llm.available() and llm_sources:
        try:
            card = _llm_card(p, llm_sources)
            trace.append({"step": 4, "title": "交叉验证",
                          "detail": f"把相关度最高的 {len(llm_sources)} 条交给模型比对，"
                                    f"选定 {len(card['evidence'])} 条证据",
                          "note": "模型只能选编号，链接由后端回填"})
        except Exception as e:
            warnings.append(f"结论生成失败：{str(e)[:80]}")
    if card is None:
        card = _heuristic_card(p, pages)
        trace.append({"step": 4, "title": "交叉验证",
                      "detail": f"规则模式：按权威度/时效排序，取前 {len(card['evidence'])} 条",
                      "note": "未配置大模型时的降级结果"})

    # ---- Step 5 门槛校验 + 兜底
    if card.get("intent") == "find":
        # 找东西本来就没有真/假，门槛规则不适用
        passed, why = True, ""
    else:
        passed, why = grade.evidence_ok(card["_evidence_pages"])
    if not pages:
        card["verdict"], card["one_line"] = "not_found", "没查到可靠来源"
    elif not passed and card["verdict"] in ("true", "false", "partially_true"):
        card["original_verdict"] = card["verdict"]
        card["verdict"] = "uncertain"
        card["one_line"] = card["one_line"] + "（来源不足以定论）"
        card["gate_note"] = why
        card["confidence"] = min(float(card.get("confidence") or 0.5), 0.6)
        warnings.append(f"结论被降级：{why}")

    if card["verdict"] == "not_found":
        card["one_line"] = "没查到可靠来源"
        card["reason"] = card.get("reason") or "检索未命中可引用的权威来源，不做猜测。"

    trace.append({
        "step": 5, "title": "门槛校验与兜底",
        "detail": ("通过：可下结论" if passed else f"未通过：{why or '证据不足'}") + 
                  ("；结论降级为「说不准」" if card.get("original_verdict") else ""),
        "note": f"规则：≥1 条 S，或 ≥{config.MIN_DISTINCT_DOMAINS} 个不同 A 级域名",
    })

    card.setdefault("candidates", [])
    label = LABEL.get(card["verdict"], "说不准")
    if card.get("intent") == "find":
        label = "待确认"
    card.update({
        "claim": orig_claim,
        "time_note": "；".join(time_notes),
        "verdict_label": label,
        "checked_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "counts": counts,
        "queries": p["queries"],
        "search_calls": searches,
        "gate": {"passed": passed, "reason": why},
        "warnings": warnings,
    })
    card.pop("_evidence_pages", None)
    return {
        "card": card,
        "trace": trace,
        "sources": [_public(x) for x in pages[:10]],
        "plan": p,
    }


def _gap_reason(counts: dict) -> str:
    if counts["S"] == 0:
        return "缺少官方/权威来源"
    if counts["A"] == 0:
        return "缺少专业媒体互证"
    return "缺少最新进展"


# ---------------------------------------------------------------- 事件核实（地震/台风等）
EVENT_LABEL = {"confirmed": "属实", "denied": "不实", "no_record": "无官方记录"}


def _is_repost(p: dict) -> bool:
    host = p.get("domain") or grade.domain_of(p.get("url", ""))
    if any(host == d or host.endswith("." + d) for d in REPOST_DOMAINS):
        return True
    return any(h in (p.get("title") or "") for h in REPOST_HINTS)


def _event_sites(claim: str) -> list[str]:
    for k, sites in EVENT_SITE_MAP.items():
        if k in claim:
            return list(sites)
    return [EVENT_DEFAULT_SITE]


def _event_investigate(p: dict, trace: list[dict], warnings: list[str], t0: float) -> dict:
    """多轮求证：全网快查 → 官方口径 → 权威媒体 → 定向到官方平台域名取证。
    全程剔除转发/自媒体，只留一手通报与权威报道。"""
    claim = p["claim"]
    kw = _keywords(claim)
    fresh = p.get("freshness") if p.get("freshness") not in (None, "none") else "d3"
    site_term = "震级" if "地震" in claim else "通报"
    rounds = [
        ("第一轮 · 全网快查", claim[:40], {"freshness": fresh}),
        ("第二轮 · 官方口径", f"{kw} 测定 通报", {"industry": "gov"}),
        ("第三轮 · 权威媒体", f"{kw} 官方 通报", {}),
    ] + [(f"第{'四五'[i]}轮 · 定向取证 · {s}", f"{kw} {site_term}", {"site": s})
         for i, s in enumerate(_event_sites(claim))]

    pages: list[dict] = []
    searches = 0
    errors: list[str] = []
    repost_dropped = 0
    for i, (title, q, kwarg) in enumerate(rounds[:6], start=2):
        try:
            searches += 1
            res = yuanbao.search(q, **kwarg)
            kept = [x for x in res["pages"] if not _is_repost(x)]
            repost_dropped += len(res["pages"]) - len(kept)
            for x in kept:
                x["_query"] = q
            pages += kept
            trace.append({
                "step": i, "title": title,
                "detail": f"「{q}」命中 {len(res['pages'])} 条，剔除转发/自媒体 {len(res['pages']) - len(kept)} 条，保留 {len(kept)} 条",
                "query": q, "hits": len(kept), "note": str(kwarg),
            })
        except Exception as e:
            errors.append(str(e))
            trace.append({"step": i, "title": title, "detail": f"「{q}」失败",
                          "query": q, "hits": 0, "note": str(e)[:160]})
            warnings.append(f"检索失败：{q}")
    if not pages and errors:
        raise RuntimeError("元宝搜索调用失败：" + errors[0])
    if errors:
        warnings.append(f"{len(errors)} 轮检索失败，结果可能不完整")

    pages = [grade.grade(x) for x in _dedupe(pages)]
    pages = _rank([x for x in pages if not _is_junk(x)], claim)
    counts = _counts(pages)
    trace.append({
        "step": 6, "title": "来源过滤与分级",
        "detail": f"累计剔除转发/自媒体 {repost_dropped} 条，可用来源 {len(pages)} 条："
                  f"S {counts['S']} / A {counts['A']} / B {counts['B']} / C {counts['C']}",
        "note": "只保留一手通报与权威报道，转发类信息不参与定论",
    })

    # 多源核对
    card = None
    llm_sources = pages[:14]
    if llm.available() and llm_sources:
        try:
            card = _llm_event_card(p, llm_sources)
            trace.append({
                "step": 7, "title": "多源核对",
                "detail": f"对相关度最高的 {len(llm_sources)} 条逐字段核对（发生与否/时间/位置/坐标/强度）",
                "note": "数字逐字摘自来源原文，禁止推算",
            })
        except Exception as e:
            warnings.append(f"事件核对失败：{str(e)[:80]}")
    if card is None:
        card = _heuristic_card(p, pages)
        card["intent"] = "event"
        trace.append({"step": 7, "title": "多源核对",
                      "detail": "大模型不可用，退化为规则模式",
                      "note": "未配置大模型时的降级结果"})

    # 事件门槛：确认/否认必须有官方级来源背书
    best = max((x["grade_score"] for x in card.get("_ev_pages", [])), default=0)
    if card["verdict"] in ("confirmed", "denied") and best < config.MIN_GRADE_FOR_VERDICT:
        card["original_verdict"] = card["verdict"]
        card["verdict"] = "no_record"
        card["one_line"] = "未找到官方级测定/通报记录"
        card["gate_note"] = "仅有 B/C 级来源，不足以确认或否认事件"
        card["confidence"] = min(float(card.get("confidence") or 0.5), 0.5)
        warnings.append("事件结论被降级：缺官方级来源")

    card.setdefault("candidates", [])
    card.update({
        "claim": p.get("claim_orig", p["claim"]),
        "time_note": p.get("time_notes_joined", ""),
        "verdict_label": EVENT_LABEL.get(card["verdict"], "无官方记录"),
        "checked_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "counts": counts,
        "queries": [r[1] for r in rounds[:6]],
        "search_calls": searches,
        "gate": {"passed": card["verdict"] in ("confirmed", "denied") and best >= config.MIN_GRADE_FOR_VERDICT,
                 "reason": card.get("gate_note", "")},
        "warnings": warnings,
        "repost_dropped": repost_dropped,
    })
    card.pop("_ev_pages", None)
    return {"card": card, "trace": trace, "sources": [_public(x) for x in pages[:10]], "plan": p}


def _llm_event_card(p: dict, pages: list[dict]) -> dict:
    data = llm.event_verdict(p["claim"], pages)
    ev_pages, evidence, seen = [], [], set()
    for e in (data.get("evidence") or [])[:4]:
        page = _map_idx(e.get("idx"), pages)
        if not page or page["url"] in seen:
            continue
        seen.add(page["url"])
        ev_pages.append(page)
        evidence.append({
            "point": f"{(e.get('field') or '')}：{(e.get('point') or '')[:70]}",
            "quote": (page.get("passage") or "")[:70],
            **_public(page),
        })

    fields = {}
    for k in ("time", "location", "lat", "lon", "magnitude", "depth"):
        v = str(data.get(k) or "").strip()
        if v:
            fields[k] = v[:40]

    status = str(data.get("status") or "no_record").lower()
    if status not in ("confirmed", "denied", "no_record"):
        status = "no_record"
    one_line = (data.get("one_line") or "").strip()[:40] or "未找到官方测定/通报记录"
    return {
        "claim": p["claim"], "intent": "event", "verdict": status,
        "one_line": one_line,
        "reason": (data.get("agreement") or "").strip()[:300],
        "confidence": round(float(data.get("confidence") or 0.5), 2),
        "evidence": evidence, "conflicts": [], "candidates": [],
        "event": {"fields": fields, "agreement": (data.get("agreement") or "")[:200]},
        "gaps": [str(g)[:80] for g in (data.get("gaps") or [])[:3]],
        "followups": [],
        "_ev_pages": ev_pages,
    }


def _counts(pages: list[dict]) -> dict:
    c = {"S": 0, "A": 0, "B": 0, "C": 0}
    for p in pages:
        c[p["grade"]] = c.get(p["grade"], 0) + 1
    return c


def _public(p: dict) -> dict:
    return {
        "title": p.get("title", ""), "url": p["url"], "site": p.get("site") or p.get("domain"),
        "date": (p.get("date") or "")[:19], "grade": p["grade"], "grade_score": p["grade_score"],
        "passage": (p.get("passage") or "")[:220], "query": p.get("_query", ""),
    }


def _map_idx(idx, pages) -> dict | None:
    try:
        i = int(idx)
    except Exception:
        return None
    if 1 <= i <= len(pages):
        return pages[i - 1]
    return None


def _llm_card(p: dict, pages: list[dict]) -> dict:
    data = llm.verdict(p["claim"], pages, p.get("intent", "verify"))
    ev_pages, evidence, seen_urls = [], [], set()
    for e in (data.get("evidence") or [])[:4]:
        page = _map_idx(e.get("idx"), pages)
        if not page or page["url"] in seen_urls:
            continue
        seen_urls.add(page["url"])
        ev_pages.append(page)
        evidence.append({
            "point": (e.get("point") or "")[:80],
            "quote": (e.get("quote") or "")[:80],
            **_public(page),
        })
    if not evidence:  # 模型没给有效编号 → 取权威度最高的三条
        for page in pages[:3]:
            ev_pages.append(page)
            evidence.append({"point": "按权威度与时效自动选取", "quote": (page.get("passage") or "")[:60],
                             **_public(page)})

    conflicts = []
    for c in (data.get("conflicts") or [])[:3]:
        a, b = _map_idx(c.get("a"), pages), _map_idx(c.get("b"), pages)
        if not a or not b:
            continue
        conflicts.append({
            "a": {"title": a.get("title", ""), "url": a["url"], "site": a.get("site") or a["domain"],
                  "date": (a.get("date") or "")[:10], "grade": a["grade"]},
            "b": {"title": b.get("title", ""), "url": b["url"], "site": b.get("site") or b["domain"],
                  "date": (b.get("date") or "")[:10], "grade": b["grade"]},
            "judgement": (c.get("judgement") or "")[:200],
        })

    v = str(data.get("verdict") or "uncertain").lower()
    if v not in LABEL:
        v = "uncertain"

    candidates = []
    for cand in (data.get("candidates") or [])[:4]:
        page = _map_idx(cand.get("idx"), pages)
        if not page:
            continue
        candidates.append({
            "answer": (cand.get("answer") or "")[:40],
            "why": (cand.get("why") or "")[:80],
            "title": page.get("title", ""), "url": page["url"],
            "site": page.get("site") or page["domain"], "date": (page.get("date") or "")[:10],
            "grade": page["grade"],
        })

    return {
        "claim": p["claim"], "rewritten": p.get("claim"),
        "intent": p.get("intent", "verify"), "verdict": v,
        "one_line": (data.get("best") or data.get("one_line") or "").strip()[:80] or "暂无法判断",
        "reason": (data.get("reason") or "").strip()[:300],
        "confidence": round(float(data.get("confidence") or 0.5), 2),
        "evidence": evidence, "conflicts": conflicts, "candidates": candidates,
        "gaps": [str(g)[:80] for g in (data.get("gaps") or [])[:3]],
        "followups": [str(f)[:40] for f in (data.get("followups") or [])[:3]],
        "_evidence_pages": ev_pages,
    }


def _heuristic_card(p: dict, pages: list[dict]) -> dict:
    top = [x for x in pages if x["grade_score"] >= 4][:4] or pages[:3]
    blob = " ".join((x.get("title", "") + x.get("passage", "")) for x in top)
    verdict = "uncertain"
    if any(h in blob for h in FALSE_HINTS):
        verdict = "false"
    elif any(h in blob for h in NEG_HINTS) and re.search(r"(致癌|有毒|骗局|不能吃|会死|有毒害)", p["claim"]):
        verdict = "false"
    elif any(h in blob for h in TRUE_HINTS):
        verdict = "true"
    evidence = [{
        "point": f"{x['grade']} 级来源 · 相关度 {round(float(x.get('score') or 0), 2)}",
        "quote": (x.get("passage") or "")[:60], **_public(x),
    } for x in top]
    return {
        "claim": p["claim"], "rewritten": p.get("claim"),
        "intent": p.get("intent", "verify"), "verdict": verdict,
        "one_line": ("权威来源显示该说法不成立" if verdict == "false" else
                     "检索到官方确认类来源" if verdict == "true" else
                     f"找到 {len(top)} 条线索，需人工确认" if p.get("intent") == "find" else
                     "来源不足以判断"),
        "reason": "规则模式：依据来源等级与关键词匹配给出初步判断，建议配置大模型获得更细的推理。",
        "confidence": 0.4, "evidence": evidence, "conflicts": [], "candidates": [],
        "gaps": ["未做语义级交叉验证"], "followups": [],
        "_evidence_pages": top,
    }
