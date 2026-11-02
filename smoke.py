"""赛前回归：直接跑流水线，检查 4 条演示查询的真实表现。

用法：D:/Qwork/.venv/Scripts/python check.py 之后
      D:/Qwork/.venv/Scripts/python smoke.py
"""
from __future__ import annotations

import sys
import time

from core import pipeline

CASES = [
    ("事件核实·地震", "西藏今天发生地震了吗", "event"),
    ("查模糊", "那个讲法医的女主剧，女主是法医、男主是刑警", "find"),
    ("查真假·冲突", "番禺珠江未来城门口装了一排斜石墩，坐都坐不了", "auto"),
    ("查真假·经典辟谣", "隔夜水、千滚水会致癌吗？", "auto"),
    ("兜底", "广州地铁18号线要改名叫番禺快线", "auto"),
]


def main() -> int:
    bad = 0
    for tag, text, intent in CASES:
        print("\n" + "=" * 70)
        print(f"【{tag}】{text}")
        t0 = time.time()
        try:
            r = pipeline.investigate(text, intent=intent)
        except Exception as e:
            print(f"  ❌ 失败：{e}")
            bad += 1
            continue
        c = r["card"]
        print(f"  结论：{c['verdict_label']} ｜ {c['one_line']}")
        ev = c.get("event") or {}
        if ev.get("fields"):
            print("  事件数据：", {k: v for k, v in ev["fields"].items()})
            if ev.get("agreement"):
                print("  多源核对：", ev["agreement"][:100])
        print(f"  用时 {time.time() - t0:.1f}s ｜ 检索 {c['search_calls']} 次 ｜ "
              f"来源 S{c['counts']['S']}/A{c['counts']['A']}/B{c['counts']['B']}/C{c['counts']['C']}")
        print(f"  门槛：{'通过' if c['gate']['passed'] else '未通过 ' + c['gate']['reason']}")
        for e in c["evidence"][:4]:
            print(f"    [{e['grade']}] {e.get('site')} · {(e.get('date') or '')[:10]} · {e['title'][:38]}")
            print(f"        {e['url'][:110]}")
        for x in c.get("candidates", [])[:3]:
            print(f"    候选：{x['answer']} ← {x['site']} {x['url'][:70]}")
        for cf in c.get("conflicts", [])[:2]:
            print(f"    冲突：{cf['a']['site']} vs {cf['b']['site']} → {(cf['judgement'] or '')[:60]}")
        for w in c.get("warnings", []):
            print(f"    ⚠️ {w}")
        if not c["evidence"] and c["verdict"] != "not_found":
            bad += 1
    print("\n" + "=" * 70)
    print(f"跑完 {len(CASES)} 条，异常 {bad} 条")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
