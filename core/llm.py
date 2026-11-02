"""大模型调用（OpenAI 兼容协议，零 SDK 依赖）。

关键设计：模型只允许返回「证据编号 idx」，URL / 站点 / 日期 / 权威度全部由后端回填，
从机制上杜绝模型编造来源链接。
"""
from __future__ import annotations

import json
import re

import requests

from . import config


def available() -> bool:
    return bool(config.LLM_API_KEY)


def protocol() -> str:
    if config.LLM_PROTOCOL in ("openai", "anthropic"):
        return config.LLM_PROTOCOL
    return "anthropic" if "anthropic" in config.LLM_BASE_URL.lower() else "openai"


def _to_anthropic_content(content):
    if isinstance(content, str):
        return content
    out = []
    for part in content:
        if part.get("type") == "text":
            out.append({"type": "text", "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if url.startswith("data:") and ";base64," in url:
                head, data = url.split(";base64,", 1)
                mime = head.replace("data:", "") or "image/jpeg"
                out.append({"type": "image", "source": {
                    "type": "base64", "media_type": mime, "data": data}})
    return out


def _chat_anthropic(messages: list[dict], max_tokens: int, temperature: float) -> str:
    system = "\n".join(m["content"] for m in messages
                       if m["role"] == "system" and isinstance(m["content"], str))
    msgs = [{"role": m["role"], "content": _to_anthropic_content(m["content"])}
            for m in messages if m["role"] != "system"]
    body = {
        "model": config.LLM_MODEL,
        "messages": msgs,
    }
    if config.LLM_THINKING:
        # 思考模式：token 预算要给足，否则思考耗尽 max_tokens 只剩空文本
        body["max_tokens"] = max(max_tokens, 4096)
    else:
        # 默认关闭 thinking：JSON 任务不需要，且能把延迟从几十秒压到 1-2 秒（避免网关 524）
        body["thinking"] = {"type": "disabled"}
        body["max_tokens"] = max(max_tokens, 800)
    body["temperature"] = temperature
    if system:
        body["system"] = system
    r = requests.post(
        f"{config.LLM_BASE_URL}/v1/messages",
        headers={
            "x-api-key": config.LLM_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=config.LLM_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"LLM {r.status_code}: {r.text[:300]}")
    data = r.json()
    blocks = data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not text:
        raise RuntimeError(
            f"模型返回空文本（stop_reason={data.get('stop_reason')}，"
            f"可能是思考过程耗尽了 max_tokens）"
        )
    return text


def chat(messages: list[dict], *, json_mode: bool = True, max_tokens: int = 1600,
         temperature: float = 0.2) -> str:
    if not available():
        raise RuntimeError("未配置 LLM_API_KEY")
    if protocol() == "anthropic":
        return _chat_anthropic(messages, max_tokens, temperature)

    body = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        f"{config.LLM_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=config.LLM_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"LLM {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except Exception:
        pass
    start, depth = -1, 0
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    start = -1
    return {}


PLAN_SYS = """你是"查证流程规划器"。用户会丢来一句话（可能是传言、群聊截图里的一句话、或一个模糊的找东西需求）。
请判断意图并生成检索计划，只输出 JSON：
{
 "intent": "verify | find | latest | event",
 "claim": "把用户的话改写成一句客观、可核查的主张（找东西则写清要找什么）",
 "queries": ["检索式1", "检索式2", "检索式3"],
 "freshness": "none | d3 | d7 | m3 | y1",
 "why": "一句话说明你的检索思路"
}
规则：verify=判断真假；find=凭模糊线索找具体事物；latest=查最新动态；
event=用户在问"某地是否发生了地震/台风/洪水/火灾等灾害事件"，只提取地点与事件词。
检索式要短、含关键词，不要带问号，三条分别覆盖：直接主张、加上"辟谣/官方"、加上关键实体或反方说法。"""


def plan(claim: str) -> dict:
    text = chat([
        {"role": "system", "content": PLAN_SYS},
        {"role": "user", "content": claim},
    ], max_tokens=500)
    data = _extract_json(text)
    if not data.get("queries"):
        raise RuntimeError("规划失败：模型未返回 queries")
    data["queries"] = [q for q in data["queries"] if isinstance(q, str) and q.strip()][:3]
    data.setdefault("intent", "verify")
    data.setdefault("claim", claim)
    data.setdefault("freshness", "none")
    return data


VERDICT_SYS = """你是严谨的查证员。你只能依据给定的检索结果作答，禁止使用自身记忆补充事实。
只输出 JSON：
{
 "verdict": "true | false | uncertain | partially_true | not_found",
 "one_line": "一句话结论，30 字内，不含链接",
 "reason": "两句话内说明依据逻辑",
 "evidence": [{"idx": 1, "point": "这条证据支持什么", "quote": "原文关键句（不超过40字）"}],
 "conflicts": [{"a": 1, "b": 3, "judgement": "两源冲突时你采信哪一方，为什么"}],
 "gaps": ["还缺什么证据"],
 "confidence": 0.0,
 "followups": ["建议继续查的检索式"],
 "candidates": [{"idx": 1, "answer": "候选答案（找剧/找店/找歌时填）", "why": "为什么是它"}],
 "best": "最可能的答案（仅 find 意图填）"
}
硬规则：
1. 所有 idx 必须是给定结果的编号；不得编造链接、站点或日期。
2. 结果中没有可靠依据时，verdict 用 not_found，one_line 写"没查到可靠来源"，不要猜。
3. 只有官方/权威来源明确支持时才用 true / false；来源矛盾或权威度不足时用 uncertain。
4. evidence 最多 4 条，优先选权威度高、时间新的。"""


def verdict(claim: str, sources: list[dict], intent: str = "verify") -> dict:
    lines = []
    for i, p in enumerate(sources, 1):
        lines.append(
            f"[{i}] {p['title']}\n站点:{p.get('site') or p.get('domain')}｜日期:{p.get('date') or '未知'}"
            f"｜等级:{p.get('grade')}({p.get('grade_score')})｜链接:{p['url']}\n摘要:{(p.get('passage') or '')[:400]}"
        )
    prompt = (
        f"待查主张：{claim}\n意图：{intent}\n\n检索结果共 {len(sources)} 条：\n\n"
        + "\n\n".join(lines)
    )
    text = chat([
        {"role": "system", "content": VERDICT_SYS},
        {"role": "user", "content": prompt},
    ], max_tokens=3000)
    data = _extract_json(text)
    if not data:
        # 思考型模型偶发把 JSON 截断，给一次更"硬"的重试
        text = chat([
            {"role": "system", "content": VERDICT_SYS},
            {"role": "user", "content": prompt + "\n\n注意：直接输出完整 JSON，不要任何解释或 markdown 代码块。"},
        ], max_tokens=3000, temperature=0)
        data = _extract_json(text)
    if not data:
        raise RuntimeError("模型未返回合法 JSON")
    return data


EXTRACT_SYS = """从这张聊天截图中，找出最需要核查的那句话（传言、通知、广告宣称）。只输出 JSON：{"claim":"那句话（尽量原文，20~120字）","speaker":"谁说的（如"二姨"/"某公众号"，不确定就写未知）","why":"为什么值得查，20字内"}
如果截图里没有可核查的内容，claim 返回空字符串。"""


def extract_claim_from_image(image_b64: str, mime: str, hint: str = "") -> dict:
    if not config.LLM_VISION:
        raise RuntimeError("当前模型未开启视觉能力（LLM_VISION=0）")
    text = chat([
        {"role": "system", "content": EXTRACT_SYS},
        {"role": "user", "content": [
            {"type": "text", "text": f"截图如下。用户补充说明：{hint or '无'}"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
        ]},
    ], max_tokens=400)
    return _extract_json(text)


EVENT_SYS = """你是灾害事件核查员，回答"某地是否真的发生了某事件"，并给出官方通报的关键数据。
只依据给定的检索结果，禁止使用自身记忆补充。只输出 JSON：
{
 "status": "confirmed | denied | no_record",
 "one_line": "≤22字事实句，如「10月23日08时 那曲双湖 5.1级地震」；无记录时写「未找到官方测定/通报记录」",
 "time": "官方通报的发生时间（照抄原文格式），无则空字符串",
 "location": "官方通报的地点（照抄原文），无则空",
 "lat": "纬度数值（照抄原文），无则空",
 "lon": "经度数值（照抄原文），无则空",
 "magnitude": "震级/风力等级等强度（照抄原文），无则空",
 "depth": "震源深度等补充参数，无则空",
 "confidence": 0.0,
 "evidence": [{"idx": 1, "field": "发生与否|时间|位置|强度", "point": "这条来源证实了什么"}],
 "agreement": "多个官方平台数据是否一致；不一致时指出差异",
 "gaps": ["缺什么关键数据"]
}
硬规则：
1. confirmed 必须有官方测定/通报（地震台网、政府、应急管理部门）或引用官方数据的央媒报道；只有自媒体转述、转发时一律 no_record。
2. 时间、经纬度、震级必须逐字照抄来源原文，禁止推算或四舍五入。
3. denied 仅当有官方明确辟谣"未发生"。
4. evidence 最多 4 条，优先官方与央媒。"""


def event_verdict(claim: str, sources: list[dict]) -> dict:
    lines = []
    for i, p in enumerate(sources, 1):
        lines.append(
            f"[{i}] {p['title']}\n站点:{p.get('site') or p.get('domain')}｜日期:{p.get('date') or '未知'}"
            f"｜等级:{p.get('grade')}({p.get('grade_score')})｜链接:{p['url']}\n摘要:{(p.get('passage') or '')[:300]}"
        )
    prompt = f"待核实事件：{claim}\n\n检索结果共 {len(sources)} 条：\n\n" + "\n\n".join(lines)
    for attempt in range(2):
        text = chat([
            {"role": "system", "content": EVENT_SYS},
            {"role": "user", "content": prompt + ("\n\n注意：直接输出完整 JSON，不要解释。" if attempt else "")},
        ], max_tokens=3000, temperature=0 if attempt else 0.2)
        data = _extract_json(text)
        if data:
            return data
    raise RuntimeError("模型未返回合法 JSON")
