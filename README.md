# 一键查真伪 · 查得到，信得过

用**元宝搜索 SearchPro** 做的查证工具：丢进来一句话（或一张群聊截图），它去查、摊开证据、给出「真 / 假 / 说不准」，**查不到就直说没查到**。

> 定位：一个会看截图、会"吵架"（来源冲突裁决）、会说不知道的一键查真伪。

---

| 功能点 | 实现 |
|---|---|
| 查得准 | 5 步流水线：拆解 → 首轮检索 → 补缺检索（官方口径 / 辟谣库 / 时效）→ 交叉验证 → 门槛校验 |
| 来源点得开 | 模型只能返回**证据编号**，URL/站点/日期由后端回填，机制上无法编造链接 |
| 好不好玩 | 结论印章、证据分级徽章、可展开的调查过程、冲突对照卡 |
| 难度（多步 / 交叉验证 / 冲突裁决） | 见 `core/pipeline.py`；冲突单独成块并写采信理由 |
| 有没有人真在用 | SQLite 记录每次查询 + 参与者数 + 现场查询流水，页脚「现场使用数据」实时刷新 |
| 敢说不知道 | 权威度门槛校验：不达标自动把「真/假」降级为「说不准」；无来源直接输出「没查到可靠来源」 |
| 防滥用 | 每设备（Cookie）免验证查证 10 次，超过后弹图形验证码，通过即重置；换设备重新计数 |
| 进阶项 | 深度调查（trace 全流程）、持续盯梢（`run_watch.py` + 页面打开即查）、截图查证（多模态） |

---

## 3 分钟跑起来

```bash
cd D:/Qwork/family-detective
python -m venv D:/Qwork/.venv
D:/Qwork/.venv/Scripts/pip install -r requirements.txt
cp .env.example .env      # 填入密钥
D:/Qwork/.venv/Scripts/python main.py
```

打开 http://127.0.0.1:8000

**没密钥也能先看界面**：`.env` 里设 `MOCK_SEARCH=1`，用内置样例数据跑通全流程（顶栏会显示「演示数据模式」，正式演示必须改回 0）。

### 只验搜索接口通不通

```bash
python -m core.yuanbao "隔夜水致癌吗"
# 或起服务后：http://127.0.0.1:8000/api/probe?q=隔夜水致癌吗
```

---

## 配置项（.env）

| 变量 | 说明 |
|---|---|
| `TENCENTCLOUD_SECRET_ID/KEY` | 腾讯云密钥，开通元宝搜索后获取 |
| `SEARCH_MODE` | 0 网页 / 1 权威垂直 / 2 混合（默认 2） |
| `SEARCH_CNT` | 每次返回条数 10/20/30/40/50 |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | 任意 OpenAI 兼容模型（混元、DeepSeek、豆包） |
| `LLM_VISION` | 换视觉模型后设 1，截图查证才可用 |
| `MOCK_SEARCH` | 1 = 样例数据，仅用于无密钥调试 |
| `MIN_GRADE_FOR_VERDICT` | 允许下结论的最低来源等级，默认 4（A 级） |
| `MIN_DISTINCT_DOMAINS` | 需要几个独立权威域名互证，默认 2 |
| `WECOM_WEBHOOK` | 盯梢命中后推企业微信群机器人（可选） |
| `CAPTCHA_THRESHOLD` | 每设备免验证查证次数，默认 10 |
| `CAPTCHA_DEBUG` | 调试时把验证码答案一起返回，线上必须 0 |

---

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 密钥/模型/模式状态，页面顶栏用 |
| GET | `/api/captcha` | 获取图形验证码（dataURL） |
| POST | `/api/verify` | `{text, intent, session}` → 查证卡 + 调查过程 + 来源 |
| POST | `/api/screenshot` | multipart 图片 → 识别主张并查证 |
| GET/POST | `/api/watches` | 盯梢列表 / 新增 |
| POST | `/api/watches/{id}/check` | 检查一次，返回 `changed` 与新证据 |
| POST | `/api/watches/{id}/toggle` | 暂停 / 恢复 |
| DELETE | `/api/watches/{id}` | 删除 |
| GET | `/api/stats` | 使用统计（"有没有人真在用"的证据） |
| GET | `/api/probe?q=` | 裸检索，赛前自检 |

---

## 目录

```
family-detective/
├── main.py              FastAPI：页面 + API 同端口
├── core/
│   ├── config.py        读 .env，零依赖
│   ├── yuanbao.py       SearchPro（TC3 签名直连，装了 SDK 则优先用 SDK）
│   ├── llm.py           OpenAI 兼容调用；证据只认编号
│   ├── grade.py         来源分级 S/A/B/C + 门槛判定
│   ├── pipeline.py      五步调查流水线
│   └── store.py         SQLite：查询日志 / 盯梢 / 统计
├── static/              前端（原生 HTML/CSS/JS，无需构建）
├── run_watch.py          本地定时盯梢（录"真实提醒"用）
└── .env.example
```

---

## 演示demo

| # | 输入 | 看什么 |
|---|---|---|
| 1 | 那个讲法医的女主剧，女主是法医、男主是刑警 | 30 秒抓人：模糊线索 → 候选 + 出处 |
| 2 | 番禺珠江未来城门口装了一排斜石墩，坐都坐不了 | 冲突裁决：网传 vs 官方实地核查 |
| 3 | 隔夜水、千滚水会致癌吗？ | 三档结论 + 多源互证 + 数据 |
| 备 | 广州地铁 18 号线要改名叫番禺快线 | 兜底：明确「没查到可靠来源」，不编 |

---

## 已知限制（扩展中）

- 元宝搜索只返回检索结果，结论由大模型生成；未配置 `LLM_API_KEY` 时自动降级为规则模式（结论一律偏保守）。
- 截图查证依赖视觉模型（`LLM_VISION=1`），否则请手动粘贴文字。
- 云上沙箱没有常驻定时任务，盯梢请同时开 `run_watch.py` 做本地兜底。
- 不处理时政话题与个人私事。
