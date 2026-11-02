"""元宝搜索 SearchPro 客户端。

优先走腾讯云官方 SDK（若已安装 tencentcloud-sdk-python），
否则用内置的 TC3-HMAC-SHA256 签名直连，零重依赖。
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import time
from typing import Any

import requests

from . import config

HOST = "wsa.tencentcloudapi.com"
SERVICE = "wsa"
ACTION = "SearchPro"
VERSION = "2025-05-08"


# ---------------- TC3 签名 ----------------
def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sign(payload: str, ts: int) -> str:
    date = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{HOST}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        "POST\n/\n\n" + canonical_headers + "\n" + signed_headers + "\n" + hashed_payload
    )
    scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n" + str(ts) + "\n" + scope + "\n"
        + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )
    k_date = _hmac(("TC3" + config.SECRET_KEY).encode("utf-8"), date)
    k_service = _hmac(k_date, SERVICE)
    k_signing = _hmac(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"TC3-HMAC-SHA256 Credential={config.SECRET_ID}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def _call_raw(params: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(params, ensure_ascii=False)
    ts = int(time.time())
    headers = {
        "Authorization": _sign(payload, ts),
        "Content-Type": "application/json; charset=utf-8",
        "Host": HOST,
        "X-TC-Action": ACTION,
        "X-TC-Timestamp": str(ts),
        "X-TC-Version": VERSION,
    }
    r = requests.post(
        f"https://{HOST}", headers=headers, data=payload.encode("utf-8"),
        timeout=config.SEARCH_TIMEOUT,
    )
    data = r.json()
    resp = data.get("Response", data)
    if "Error" in resp:
        raise RuntimeError(f"{resp['Error'].get('Code')}: {resp['Error'].get('Message')}")
    return resp


def _call_sdk(params: dict[str, Any]) -> dict[str, Any]:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.wsa.v20250508 import models, wsa_client

    cred = credential.Credential(config.SECRET_ID, config.SECRET_KEY)
    hp = HttpProfile()
    hp.endpoint = HOST
    client = wsa_client.WsaClient(cred, "", ClientProfile(httpProfile=hp))
    req = models.SearchProRequest()
    req.from_json_string(json.dumps(params, ensure_ascii=False))
    return json.loads(client.SearchPro(req).to_json_string())


MOCK_PAGES = [
    {"title": "隔夜水、千滚水会致癌吗？", "url": "https://www.piyao.org.cn/2025-03/12/c_1.htm",
     "site": "中国互联网联合辟谣平台", "date": "2025-03-12 10:00:00",
     "passage": "反复烧开的水中亚硝酸盐含量仍远低于生活饮用水卫生标准限值，目前没有证据表明隔夜水、千滚水会致癌。",
     "authority_level": 5, "score": 0.93},
    {"title": "千滚水到底能不能喝？", "url": "https://www.kepuchina.cn/article/2024/0920.htm",
     "site": "科学辟谣", "date": "2024-09-20 09:00:00",
     "passage": "实验显示水反复加热 20 次后亚硝酸盐含量约为 0.002mg/L，远低于 1mg/L 的国家标准。",
     "authority_level": 4, "score": 0.9},
    {"title": "网传广州珠江未来城设“缺德墩”，官方实地排查后辟谣", "url": "https://www.toutiao.com/article/7694471308284822062",
     "site": "广州番禺发布", "date": "2026-10-09 09:20:00",
     "passage": "番禺有关部门前往项目外围及公共区域巡查，未见网传斜面石墩，附近商户称从未见过该设施。",
     "authority_level": 5, "score": 0.95},
    {"title": "“缺德墩”是这儿的？开发商回应：不在我们地块", "url": "https://mp.weixin.qq.com/s/mock-qiude",
     "site": "广州辟谣", "date": "2026-10-09 18:00:00",
     "passage": "项目开发方发布澄清声明：网传争议石墩所处区域并非本项目地块范围，相关设施亦非项目配套。",
     "authority_level": 5, "score": 0.92},
    {"title": "那个讲法医的女主剧是哪部？盘点 5 部法医题材剧集", "url": "https://movie.douban.com/review/mock-fayi",
     "site": "豆瓣", "date": "2025-11-02 12:00:00",
     "passage": "《法医秦明》主角为法医，搭档刑警；《骨语》以女法医为主角；《心灵法医》为法医与刑警组合。",
     "authority_level": 3, "score": 0.88},
    {"title": "法医题材剧集推荐（腾讯视频片单）", "url": "https://v.qq.com/x/cover/mock-list.html",
     "site": "腾讯视频", "date": "2026-01-15 08:00:00",
     "passage": "片单收录《法医秦明》《骨语》《心灵法医》等多部以法医为主角的剧集。",
     "authority_level": 3, "score": 0.86},
    {"title": "转发！这种“免费领鸡蛋”活动专坑老人", "url": "https://mp.weixin.qq.com/s/mock-fanzha",
     "site": "某营销号", "date": "2024-05-01 08:00:00",
     "passage": "多地出现以免费领鸡蛋为名诱导老年人购买高价保健品的骗局，请注意甄别。",
     "authority_level": 1, "score": 0.5},
]


def _mock(query: str, cnt: int) -> dict[str, Any]:
    q = query.lower()
    if "缺德" in q or "石墩" in q:
        pages = MOCK_PAGES[2:4]
    elif "法医" in q:
        pages = MOCK_PAGES[4:6]
    elif "鸡蛋" in q or "讲座" in q or "保健品" in q:
        pages = MOCK_PAGES[6:7]
    elif "水" in q or "致癌" in q:
        pages = MOCK_PAGES[0:2]
    else:
        pages = []
    return {"Pages": [json.dumps(p, ensure_ascii=False) for p in pages[:cnt]], "Version": "mock"}


def _invoke(params: dict[str, Any]) -> dict[str, Any]:
    try:
        return _call_sdk(params)
    except ImportError:
        return _call_raw(params)


def search(
    query: str,
    *,
    cnt: int | None = None,
    mode: int | None = None,
    freshness: str | None = None,
    industry: str | None = None,
    site: str | None = None,
) -> dict[str, Any]:
    """执行一次检索，返回标准化后的 {query, version, pages[]}。"""
    params: dict[str, Any] = {
        "Query": query,
        "Mode": mode if mode is not None else config.SEARCH_MODE,
        "Cnt": cnt or config.SEARCH_CNT,
    }
    if freshness:
        params["Freshness"] = freshness
    if industry:
        params["Industry"] = industry
    if site:
        params["Site"] = site

    if config.MOCK_SEARCH:
        resp = _mock(query, params["Cnt"])
    else:
        try:
            resp = _invoke(params)
        except Exception as e:
            # 极速版不支持 Mode / Cnt / Industry / Freshness（Site 也不保证），
            # 命中参数类错误时退化为最简调用，保证"能用"优先。
            msg = str(e)
            if any(k in msg for k in ("InvalidParameter", "Unsupported", "参数")):
                resp = _invoke({"Query": query})
                resp["_lite"] = True
            else:
                raise

    pages = []
    for raw in resp.get("Pages", []) or []:
        try:
            p = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            continue
        if not p.get("url"):
            continue
        p["passage"] = (p.get("passage") or p.get("content") or "").strip()
        p["title"] = (p.get("title") or "").strip()
        pages.append(p)

    return {"query": query, "version": resp.get("Version", ""), "pages": pages}


if __name__ == "__main__":  # 快速自检：python -m core.yuanbao "隔夜水致癌吗"
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "广州天气"
    out = search(q)
    print(f"version={out['version']} pages={len(out['pages'])}")
    for i, p in enumerate(out["pages"][:5], 1):
        print(i, p.get("grade", "-"), p.get("site"), p.get("title")[:40], p.get("url"))
