"""一键查真伪 · FastAPI 单进程服务（页面 + API 同端口，发布友好）。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core import captcha, config, llm, pipeline, store, yuanbao

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(title="一键查真伪", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup() -> None:
    store.init()


def _device_of(req: Request) -> tuple[str, bool]:
    """取（或签发）设备 Cookie。返回 (device_id, 是否新签发)。"""
    device = req.cookies.get("wb_device")
    if device and 8 <= len(device) <= 64:
        return device, False
    return uuid.uuid4().hex, True


def _gate(req: Request, body_hint: dict | None = None):
    """限流闸门：返回 (device, new_cookie, 被拦截时的响应)。响应为 None 表示放行。"""
    device, new_cookie = _device_of(req)
    if captcha.needs_captcha(device):
        ok = captcha.check((body_hint or {}).get("captcha_id"), (body_hint or {}).get("captcha_code"))
        if not ok:
            cid, code, image = captcha.new_challenge()
            payload = {
                "need_captcha": True,
                "captcha_id": cid,
                "image": image,
                "quota": {"used": captcha.used(device), "limit": config.CAPTCHA_THRESHOLD},
            }
            if config.CAPTCHA_DEBUG:
                payload["debug_code"] = code
            resp = JSONResponse(payload, status_code=429)
            if new_cookie:
                resp.set_cookie("wb_device", device, max_age=365 * 86400, httponly=True, samesite="lax")
            return device, new_cookie, resp
        captcha.reset(device)   # 验证通过，重置本设备计数
    return device, new_cookie, None


def _finish(resp: JSONResponse, device: str, new_cookie: bool) -> JSONResponse:
    if new_cookie:
        resp.set_cookie("wb_device", device, max_age=365 * 86400, httponly=True, samesite="lax")
    return resp


@app.get("/api/captcha")
def get_captcha():
    cid, code, image = captcha.new_challenge()
    payload = {"captcha_id": cid, "image": image}
    if config.CAPTCHA_DEBUG:
        payload["debug_code"] = code
    return payload


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    miss = config.missing_keys()
    return {
        "ok": True,
        "mock_search": config.MOCK_SEARCH,
        "search_ready": config.MOCK_SEARCH or bool(config.SECRET_ID and config.SECRET_KEY),
        "llm_ready": llm.available(),
        "vision_ready": llm.available() and config.LLM_VISION,
        "model": config.LLM_MODEL if llm.available() else "rule-based",
        "missing": miss,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.post("/api/verify")
async def verify(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "请输入要查证的内容"}, status_code=400)
    device, new_cookie, blocked = _gate(req, body)
    if blocked is not None:
        return blocked

    session = body.get("session") or device
    try:
        result = pipeline.investigate(
            text,
            intent=body.get("intent") or "auto",
            freshness=body.get("freshness") or None,
        )
    except Exception as e:
        return _finish(JSONResponse({"error": f"查证失败：{e}"}, status_code=500), device, new_cookie)

    captcha.bump(device)
    card = result["card"]
    store.log_query(card["claim"], card.get("intent", ""), card.get("verdict", ""),
                    str(session), card.get("elapsed_ms", 0))
    result["source_image"] = body.get("source_image") or ""
    result["stats"] = store.stats()
    result["quota"] = {"used": captcha.used(device), "limit": config.CAPTCHA_THRESHOLD}
    return _finish(JSONResponse(result), device, new_cookie)


@app.post("/api/screenshot")
async def screenshot(
    req: Request,
    file: UploadFile = File(...),
    hint: str = Form(""),
    captcha_id: str = Form(""),
    captcha_code: str = Form(""),
):
    device, new_cookie, blocked = _gate(req, {"captcha_id": captcha_id, "captcha_code": captcha_code})
    if blocked is not None:
        return blocked

    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        return _finish(JSONResponse({"error": "图片过大（限 8MB）"}, status_code=400), device, new_cookie)
    mime = file.content_type or "image/jpeg"
    b64 = base64.b64encode(raw).decode()
    try:
        got = llm.extract_claim_from_image(b64, mime, hint)
    except Exception as e:
        return _finish(JSONResponse({
            "error": f"截图识别失败：{e}",
            "hint": "当前模型未开启视觉能力时，请把截图里那句话直接粘贴到输入框。",
        }, status_code=400), device, new_cookie)

    claim = (got.get("claim") or hint or "").strip()
    if not claim:
        return _finish(JSONResponse({"error": "截图里没找到可核查的内容，请手动输入"}, status_code=400),
                       device, new_cookie)

    captcha.bump(device)
    result = pipeline.investigate(claim, intent="verify")
    card = result["card"]
    card["from_screenshot"] = True
    card["speaker"] = got.get("speaker") or "未知"
    card["screenshot_note"] = got.get("why") or ""
    card["image"] = f"data:{mime};base64,{b64}" if len(b64) < 1_200_000 else ""
    store.log_query(card["claim"], "screenshot", card.get("verdict", ""), device,
                    card.get("elapsed_ms", 0))
    result["stats"] = store.stats()
    result["quota"] = {"used": captcha.used(device), "limit": config.CAPTCHA_THRESHOLD}
    return _finish(JSONResponse(result), device, new_cookie)


# ------------------------------------------------------------ 盯梢
@app.get("/api/watches")
def watches():
    return {"items": store.list_watches()}


@app.post("/api/watches")
async def add_watch(req: Request):
    body = await req.json()
    claim = (body.get("claim") or "").strip()
    if not claim:
        return JSONResponse({"error": "订阅内容不能为空"}, status_code=400)
    wid = store.add_watch(claim)
    return {"id": wid, "items": store.list_watches()}


@app.post("/api/watches/{wid}/check")
def check_watch(wid: int):
    w = store.get_watch(wid)
    if not w:
        return JSONResponse({"error": "订阅不存在"}, status_code=404)
    try:
        result = pipeline.investigate(w["claim"])
    except Exception as e:
        return JSONResponse({"error": f"检查失败：{e}"}, status_code=500)

    card = result["card"]
    top = [e["url"] for e in card.get("evidence", [])[:3]]
    fp = hashlib.md5(
        json.dumps([card["verdict"], top], ensure_ascii=False).encode()
    ).hexdigest()[:16]
    prev_fp = w.get("fingerprint") or ""
    changed = bool(prev_fp) and prev_fp != fp

    old_top = set()
    if w.get("history"):
        old_top = set(w["history"][-1].get("top") or [])

    store.update_watch(wid, card["verdict"], fp,
                       {"top": top, "one_line": card.get("one_line", "")})
    return {
        "changed": changed,
        "verdict": card["verdict"],
        "verdict_label": card["verdict_label"],
        "one_line": card.get("one_line", ""),
        "added": [u for u in top if u not in old_top],
        "removed": [u for u in old_top if u not in top],
        "card": card,
        "checked_at": card["checked_at"],
    }


@app.post("/api/watches/{wid}/toggle")
async def toggle_watch(wid: int, req: Request):
    body = await req.json()
    store.set_active(wid, bool(body.get("active", True)))
    return {"items": store.list_watches()}


@app.delete("/api/watches/{wid}")
def remove_watch(wid: int):
    store.delete_watch(wid)
    return {"items": store.list_watches()}


# ------------------------------------------------------------ 统计
@app.get("/api/stats")
def stats():
    return {"stats": store.stats(), "recent": store.recent()}


@app.get("/api/probe")
def probe(q: str):
    """裸检索，用于调试与赛前自检：看清楚接口到底返回了什么。"""
    try:
        res = yuanbao.search(q)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    from core import grade as g
    return {"query": q, "version": res["version"],
            "pages": [pipeline._public(g.grade(p)) for p in res["pages"]]}


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
