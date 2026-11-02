"""一键自检：确认搜索密钥、大模型密钥、数据库都能用。

用法（在项目目录下）：
    D:/Qwork/.venv/Scripts/python check.py
"""
from __future__ import annotations

import sys

from core import config, grade, llm, store, yuanbao


def mask(s: str) -> str:
    if not s:
        return "（空）"
    return s[:6] + "…" + s[-4:] if len(s) > 12 else "（已填，长度偏短）"


def line(ok: bool, msg: str) -> None:
    print(("  ✅ " if ok else "  ❌ ") + msg)


def main() -> int:
    print("\n=== 1. 配置读取 ===")
    print(f"  .env 路径：{config.ROOT / '.env'}（存在：{(config.ROOT / '.env').exists()}）")
    print(f"  MOCK_SEARCH = {config.MOCK_SEARCH}  （必须是 0 才是真实检索）")
    print(f"  SecretId  = {mask(config.SECRET_ID)}")
    print(f"  SecretKey = {mask(config.SECRET_KEY)}")
    print(f"  模型      = {config.LLM_MODEL} @ {config.LLM_BASE_URL}")
    print(f"  LLM Key   = {mask(config.LLM_API_KEY)}")

    fail = 0

    print("\n=== 2. 元宝搜索 SearchPro ===")
    if config.MOCK_SEARCH:
        print("  ⚠️ 当前是演示数据模式（MOCK_SEARCH=1），跳过真实调用")
    elif not config.SECRET_ID or not config.SECRET_KEY:
        line(False, "SecretId / SecretKey 未填写")
        fail += 1
    else:
        try:
            res = yuanbao.search("广州天气", cnt=10)
            pages = [grade.grade(p) for p in res["pages"]]
            line(True, f"调用成功，返回 {len(pages)} 条，版本 {res['version']}")
            for p in pages[:3]:
                print(f"     [{p['grade']}] {p.get('site') or p['domain']} | {p['title'][:32]} | "
                      f"auth={p.get('authority_level')} | {p['url'][:60]}")
            if not pages:
                print("     ⚠️ 有响应但没结果，检查额度是否核销")
        except Exception as e:
            line(False, f"调用失败：{e}")
            msg = str(e)
            if "ResourceNotFound" in msg or "未开通" in msg:
                print("     → 这不是密钥错，是「服务没开通」。去这里点『开通服务』：")
                print("       https://console.cloud.tencent.com/wsapi/index")
                print("       子账号的话，让主账号开通并授权 QcloudWSAFullAccess")
                print("       开通后别忘了用活动邀请码核销，才有每月 6000 次免费额度")
            else:
                print("     常见原因：密钥错误 / 额度未核销 / 本机网络 / 子账号权限")
            fail += 1

    print("\n=== 3. 大模型 ===")
    if not llm.available():
        line(False, "LLM_API_KEY 未填写（不填也能跑，但结论会退化成规则模式）")
        fail += 1
    else:
        try:
            out = llm.chat([{"role": "user", "content": "只回复两个字：可用"}], max_tokens=20)
            line(True, f"连通，模型回复：{out.strip()[:30]}")
        except Exception as e:
            line(False, f"调用失败：{e}")
            print("     检查 LLM_BASE_URL 是否以 /v1 结尾、模型名是否正确、余额是否充足")
            fail += 1

    print("\n=== 4. 数据库 ===")
    try:
        store.init()
        s = store.stats()
        line(True, f"SQLite 正常：{config.DB_PATH}（已有 {s['total']} 条查询记录）")
    except Exception as e:
        line(False, f"数据库异常：{e}")
        fail += 1

    print("\n=== 结论 ===")
    if fail == 0:
        print("  🎉 全部就绪。运行 python main.py，浏览器打开 http://127.0.0.1:8000")
        return 0
    print(f"  还有 {fail} 项待修（见上面的 ❌）。密钥只需要改 .env，改完重跑本脚本即可。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
