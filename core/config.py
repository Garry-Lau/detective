"""环境配置：读取项目根目录 .env（无第三方依赖）。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_env()

# ---- 元宝搜索（腾讯云 wsa / SearchPro）----
SECRET_ID = os.getenv("TENCENTCLOUD_SECRET_ID", "")
SECRET_KEY = os.getenv("TENCENTCLOUD_SECRET_KEY", "")
SEARCH_MODE = int(os.getenv("SEARCH_MODE", "2"))       # 0 网页 / 1 权威垂直 / 2 混合
SEARCH_CNT = int(os.getenv("SEARCH_CNT", "30"))
SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "20"))

# ---- 大模型（OpenAI 兼容协议）----
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
# openai / anthropic；留空则按 BASE_URL 自动判断（含 anthropic 走 anthropic 协议）
LLM_PROTOCOL = os.getenv("LLM_PROTOCOL", "").lower()
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
LLM_VISION = os.getenv("LLM_VISION", "0") == "1"        # 截图查证需要视觉模型
# 1=保留思考过程（更稳但慢，可能触发网关超时）；0=关闭（默认，快约 5-10 倍）
LLM_THINKING = os.getenv("LLM_THINKING", "0") == "1"

# ---- 运行 ----
MOCK_SEARCH = os.getenv("MOCK_SEARCH", "0") == "1"
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "detective.db"))
PORT = int(os.getenv("PORT", "8000"))
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "")

# 可信度门槛：达到才允许下「真/假」结论
MIN_GRADE_FOR_VERDICT = int(os.getenv("MIN_GRADE_FOR_VERDICT", "4"))   # 4=A, 5=S
MIN_DISTINCT_DOMAINS = int(os.getenv("MIN_DISTINCT_DOMAINS", "2"))

# 防滥用：每设备免验证查证次数，超过后需图形验证码（验证通过重置计数）
CAPTCHA_THRESHOLD = int(os.getenv("CAPTCHA_THRESHOLD", "10"))
CAPTCHA_DEBUG = os.getenv("CAPTCHA_DEBUG", "0") == "1"   # 调试时把答案一起返回，线上必须 0


def missing_keys() -> list[str]:
    miss = []
    if not MOCK_SEARCH:
        if not SECRET_ID or not SECRET_KEY:
            miss.append("TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY")
    if not LLM_API_KEY:
        miss.append("LLM_API_KEY")
    return miss
