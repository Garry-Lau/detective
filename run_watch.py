"""本地定时盯梢：每 N 秒让服务检查一遍所有订阅，有变化就打印（可推企业微信）。

用途：云上沙箱没人访问时会休眠，cron 不一定跑；比赛时用笔记本跑这个脚本，
就能录到"一次真实触发的提醒"。

用法：
    python run_watch.py                # 默认 300 秒一轮，指向 http://127.0.0.1:8000
    python run_watch.py --interval 60 --base https://xxx.share.link
"""
from __future__ import annotations

import argparse
import time

import requests

from core.config import WECOM_WEBHOOK


def push(text: str) -> None:
    if not WECOM_WEBHOOK:
        return
    try:
        requests.post(WECOM_WEBHOOK, json={"msgtype": "text", "text": {"content": text}}, timeout=10)
    except Exception as e:
        print(f"[warn] 推送失败：{e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--interval", type=int, default=300)
    args = ap.parse_args()

    print(f"盯梢守护启动：{args.base}，每 {args.interval}s 检查一次，Ctrl+C 结束")
    while True:
        try:
            items = requests.get(f"{args.base}/api/watches", timeout=20).json().get("items", [])
            active = [w for w in items if w.get("active")]
            print(f"[{time.strftime('%H:%M:%S')}] 待检查 {len(active)} 条")
            for w in active:
                try:
                    r = requests.post(f"{args.base}/api/watches/{w['id']}/check", timeout=120).json()
                    tag = "变化!" if r.get("changed") else "无变化"
                    line = f"[{tag}] {w['claim'][:30]} → {r.get('verdict_label')} {r.get('one_line', '')}"
                    print("  " + line)
                    if r.get("changed"):
                        push("【盯梢提醒】\n" + line + "\n新增来源：" + "；".join(r.get("added", [])[:2]))
                except Exception as e:
                    print(f"  [err] {w['id']}: {e}")
        except Exception as e:
            print(f"[err] 拉取订阅失败：{e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
