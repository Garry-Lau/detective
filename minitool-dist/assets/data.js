/* 一键查真伪 · 离线演示数据（源自真实查证结果的脱敏样例） */
window.DEMO = {
  cases: [
    {
      match: ["隔夜水", "千滚水", "反复烧", "开水致癌", "水致癌", "亚硝酸盐"],
      card: {
        verdict: "false",
        verdict_label: "假",
        claim: "隔夜水、千滚水会致癌",
        from_screenshot: false,
        speaker: "",
        one_line: "反复烧开或隔夜的白开水不会致癌：亚硝酸盐含量远低于国家生活饮用水 1 mg/L 的安全限值，「亚硝胺致癌」缺乏剂量支撑。",
        reason: "多家权威科普与监管口径一致：实验室测定自来水反复烧开 20 次后亚硝酸盐约 0.038 mg/L，不到限值的 1/20。该说法属于典型的「剂量不谈、只谈物质」式健康谣言。",
        confidence: 0.88,
        elapsed_ms: 6200,
        search_calls: 4,
        counts: { S: 1, A: 2, B: 1, C: 1 },
        checked_at: "2026-10-24 10:20",
        gate_note: "",
        candidates: [],
        event: null,
        conflicts: [
          {
            a: { grade: "C", site: "某养生号", title: "千滚水亚硝酸盐超标 10 倍，喝了致癌", date: "2025-11-02" },
            b: { grade: "S", site: "中国互联网联合辟谣平台", title: "「隔夜水致癌」缺乏剂量支撑，实验数据驳斥", date: "2025-12-18" },
            judgement: "C 级自媒体未给出检测方法与数值来源；S 级辟谣平台给出实测数据与国标限值，予以采信。"
          }
        ],
        gaps: ["不同材质容器的析出物（如劣质保温杯）不在本结论覆盖范围内"],
        warnings: []
      },
      evidence: [
        { grade: "S", point: "实测：自来水反复烧开 20 次后，亚硝酸盐含量约 0.038 mg/L，远低于 1 mg/L 国标限值。", quote: "「千滚水」中亚硝酸盐含量不足以对健康构成威胁，相关致癌说法缺乏科学依据。", site: "中国互联网联合辟谣平台", title: "「隔夜水致癌」缺乏剂量支撑，实验数据驳斥", url: "https://www.piyao.org.cn/2025-12/18/c_111000_example.htm", date: "2025-12-18" },
        { grade: "A", point: "地方市场监管局科普栏目亦辟谣：隔夜白开水可正常饮用，建议加盖防尘。", quote: "亚硝酸盐超标的担忧被反复检测数据否定，市民无需恐慌。", site: "广州日报", title: "隔夜水到底能不能喝？检测数据说话", url: "https://www.gzdaily.example.cn/2026-01/06/content_example.htm", date: "2026-01-06" },
        { grade: "A", point: "科普机构核查多起同源谣言，确认该说法 2015 年起反复流传、口径一致。", quote: "每隔一段时间就会以「再不看就删」的形式重新传播。", site: "科普中国", title: "隔夜水、千滚水致癌？这次一次说清", url: "https://www.kepuchina.example.cn/article/2026-01.htm", date: "2026-01-09" },
        { grade: "B", point: "生活类自媒体转述辟谣内容，无新增数据。", quote: "转发官方检测结论。", site: "网易号·生活百科", title: "关于千滚水的真相，转给家人", url: "https://www.163.example.com/life/2026-01.htm", date: "2026-01-08" }
      ],
      trace: [
        { step: 1, title: "拆解主张", detail: "识别为健康类可验证主张：隔夜/反复烧开的水 → 亚硝酸盐/亚硝胺 → 致癌。", note: "intent=verify · 关键实体：白开水、亚硝酸盐、致癌" },
        { step: 2, title: "首轮全网检索", detail: "全网检索「隔夜水 千滚水 致癌 亚硝酸盐」，取 10 条结果。", note: "cnt=10 · mode=general" },
        { step: 3, title: "补查官方口径", detail: "定向补查辟谣平台与监管机构口径，命中 1 条 S 级来源。", note: "Industry=gov · site=piyao.org.cn" },
        { step: 4, title: "交叉验证", detail: "4 条有效证据互证，其中 1 条与主流口径冲突，已列入「来源打架」。", note: "S1 / A2 / B1" },
        { step: 5, title: "门槛校验", detail: "S≥1 且独立权威域名≥2，满足出「假」结论门槛。", note: "gate=pass" }
      ],
      sources: [
        { grade: "S", site: "中国互联网联合辟谣平台", title: "「隔夜水致癌」缺乏剂量支撑，实验数据驳斥", url: "https://www.piyao.org.cn/2025-12/18/c_111000_example.htm", date: "2025-12-18" },
        { grade: "A", site: "广州日报", title: "隔夜水到底能不能喝？检测数据说话", url: "https://www.gzdaily.example.cn/2026-01/06/content_example.htm", date: "2026-01-06" },
        { grade: "A", site: "科普中国", title: "隔夜水、千滚水致癌？这次一次说清", url: "https://www.kepuchina.example.cn/article/2026-01.htm", date: "2026-01-09" }
      ]
    },
    {
      match: ["地震", "西藏", "定日", "震级", "余震"],
      card: {
        verdict: "confirmed",
        verdict_label: "有记录",
        claim: "西藏发生 6.8 级地震",
        from_screenshot: false,
        speaker: "",
        one_line: "经中国地震台网核实：2025 年 1 月 7 日 09 时 05 分，西藏日喀则市定日县发生 6.8 级地震，震源深度 10 千米。该信息属实。",
        reason: "中国地震台网正式测定与新华社、央视新闻通报完全一致，且各官方渠道发布时间在震后 10 分钟内，不存在传言失真。",
        confidence: 0.95,
        elapsed_ms: 4800,
        search_calls: 5,
        counts: { S: 2, A: 2, B: 0, C: 0 },
        checked_at: "2026-10-24 10:22",
        gate_note: "",
        candidates: [],
        event: {
          fields: {
            time: "2025-01-07 09:05",
            location: "西藏日喀则市定日县",
            lat: "28.50",
            lon: "87.45",
            magnitude: "6.8 级",
            depth: "10 千米"
          },
          agreement: "中国地震台网、新华社、央视新闻三源数据逐字一致。"
        },
        conflicts: [],
        gaps: [],
        warnings: []
      },
      evidence: [
        { grade: "S", point: "中国地震台网正式测定：定日县 6.8 级地震，震源深度 10 千米。", quote: "正式测定：01月07日09时05分在西藏日喀则市定日县（北纬28.50度，东经87.45度）发生6.8级地震，震源深度10千米。", site: "中国地震台网", title: "西藏日喀则市定日县发生6.8级地震", url: "https://news.ceic.ac.cn/example_CC20250107090501.html", date: "2025-01-07" },
        { grade: "S", point: "应急管理部启动地震应急响应，派出工作组赶赴震中。", quote: "已启动应急响应，救援力量正在集结。", site: "新华社", title: "西藏定日6.8级地震 应急管理部启动应急响应", url: "https://www.news.example.cn/2025-01/07/c_1130001.htm", date: "2025-01-07" },
        { grade: "A", point: "央视新闻滚动直播灾情与救援进展，数据与台网一致。", quote: "震中位于定日县长所乡，周边村镇通信正在抢通。", site: "央视新闻", title: "西藏定日县发生6.8级地震 滚动报道", url: "https://news.cctv.example.com/2025/01/07/ARTI.shtml", date: "2025-01-07" }
      ],
      trace: [
        { step: 1, title: "拆解主张", detail: "识别为事件核实类（地震）：需核实发生时间、地点、震级、深度。", note: "intent=event · EVENT_RE 命中" },
        { step: 2, title: "全网快查", detail: "全网检索「西藏 地震」，过滤转发类内容（头条号/百家号等）。", note: "过滤掉 3 条转发源" },
        { step: 3, title: "官方行业检索", detail: "Industry=gov 定向检索，命中中国地震台网正式测定。", note: "S 级 · ceic.ac.cn" },
        { step: 4, title: "权威媒体互证", detail: "新华社、央视新闻通报与台网数据逐字一致。", note: "S1 / A1 追加" },
        { step: 5, title: "门槛校验与制卡", detail: "grade≥4 满足，事件卡确认：时间/位置/经纬度/震级/深度逐字摘自官方通报。", note: "gate=pass · confirmed" }
      ],
      sources: [
        { grade: "S", site: "中国地震台网", title: "西藏日喀则市定日县发生6.8级地震", url: "https://news.ceic.ac.cn/example_CC20250107090501.html", date: "2025-01-07" },
        { grade: "S", site: "新华社", title: "西藏定日6.8级地震 应急管理部启动应急响应", url: "https://www.news.example.cn/2025-01/07/c_1130001.htm", date: "2025-01-07" },
        { grade: "A", site: "央视新闻", title: "西藏定日县发生6.8级地震 滚动报道", url: "https://news.cctv.example.com/2025/01/07/ARTI.shtml", date: "2025-01-07" }
      ]
    },
    {
      match: ["微信", "转账", "手续费", "限额", "新规"],
      card: {
        verdict: "uncertain",
        verdict_label: "说不准",
        claim: "微信将全面收取转账手续费",
        from_screenshot: false,
        speaker: "",
        one_line: "未找到官方公告证实「全面收取转账手续费」，现有信息以个人账号转述为主，不足以定论。",
        reason: "相关说法集中出现在自媒体与群聊截图，缺少微信支付官方公告或权威媒体报道互证；历史上同类「收费新规」传言多次被辟谣，但不排除政策调整的可能，需持续观察。",
        confidence: 0.35,
        elapsed_ms: 5100,
        search_calls: 3,
        counts: { S: 0, A: 1, B: 2, C: 1 },
        checked_at: "2026-10-24 10:25",
        gate_note: "未达到「1 条 S 级或 2 个独立 A 级互证」门槛",
        candidates: [
          { answer: "微信支付官网「费率公告」栏目当前无新增收费公告。", why: "官方栏目为空白结果，只能证明「此刻没有公告」，不能证明「不会收」。", url: "https://pay.weixin.qq.com/index.php/public/notice", site: "微信支付", date: "" }
        ],
        event: null,
        conflicts: [],
        gaps: ["缺少微信支付官方公告或客服口径的直接引用", "若传言属实，应有银行/商户端配套通知，暂未检索到"],
        warnings: []
      },
      evidence: [
        { grade: "A", point: "财经媒体报道称「网传收费截图无法确认来源」，向腾讯方面求证未获正式回应。", quote: "截至发稿，腾讯尚未就网传截图发表官方声明。", site: "21世纪经济报道", title: "网传微信转账收费截图存疑", url: "https://www.21jingji.example.com/article/2026-02.htm", date: "2026-02-11" },
        { grade: "B", point: "自媒体解读文章，内容以推测为主。", quote: "如果按 0.1% 费率测算……", site: "搜狐号·支付圈", title: "微信转账要收费了？真相在这", url: "https://www.sohu.example.com/pay/2026-02.htm", date: "2026-02-10" }
      ],
      trace: [
        { step: 1, title: "拆解主张", detail: "识别为政策/规则类主张：微信 · 转账 · 手续费新规。", note: "intent=verify" },
        { step: 2, title: "首轮全网检索", detail: "检索「微信 转账 手续费 新规」，多为自媒体转述。", note: "10 条 · 过滤 6 条低质" },
        { step: 3, title: "补查官方口径", detail: "微信支付公告栏目与监管部门渠道均无对应公告。", note: "S=0" },
        { step: 4, title: "交叉验证", detail: "仅有 1 条 A 级独立报道，B/C 级来源无法互证。", note: "独立 A 域名=1 < 2" },
        { step: 5, title: "门槛校验", detail: "未达门槛 → 结论降级为「说不准」，并给出后续核查路径。", note: "gate=downgrade" }
      ],
      sources: [
        { grade: "A", site: "21世纪经济报道", title: "网传微信转账收费截图存疑", url: "https://www.21jingji.example.com/article/2026-02.htm", date: "2026-02-11" },
        { grade: "B", site: "搜狐号·支付圈", title: "微信转账要收费了？真相在这", url: "https://www.sohu.example.com/pay/2026-02.htm", date: "2026-02-10" }
      ]
    },
    {
      match: ["台风", "停课", "暴雨预警", "停工"],
      card: {
        verdict: "not_found",
        verdict_label: "没查到",
        claim: "广州下周因台风停课",
        from_screenshot: false,
        speaker: "",
        one_line: "未检索到教育、气象部门的停课通知或权威媒体报道，无法确认该说法。",
        reason: "广州市教育局与气象局官方渠道、本地权威媒体均无对应停课通知；群传停课消息常见于台风季，建议以「广州教育」「广州天气」官方发布为准，勿先转发。",
        confidence: 0.2,
        elapsed_ms: 4400,
        search_calls: 3,
        counts: { S: 0, A: 0, B: 1, C: 2 },
        checked_at: "2026-10-24 10:27",
        gate_note: "无 S/A 级来源，不足以出「真 / 假」结论",
        candidates: [],
        event: null,
        conflicts: [],
        gaps: ["官方渠道（广州市教育局、气象局）暂无相关发布", "建议临近日期再查一次，预警类信息通常提前 1–2 天发布"],
        warnings: []
      },
      evidence: [
        { grade: "B", point: "本地门户汇总网友讨论，无官方出处。", quote: "家长群流传的停课通知截图未能找到原始出处。", site: "大洋网", title: "网传停课通知？记者求证中", url: "https://www.dayoo.example.com/2026-10.htm", date: "2026-10-23" }
      ],
      trace: [
        { step: 1, title: "拆解主张", detail: "识别为通知类传言：广州 · 台风 · 停课。", note: "intent=verify" },
        { step: 2, title: "全网快查", detail: "检索未发现官方通知，仅有群传截图讨论。", note: "S/A=0" },
        { step: 3, title: "官方定向补查", detail: "教育局、气象局渠道无发布。", note: "site=gz.gov.cn 空结果" },
        { step: 4, title: "交叉验证", detail: "无可互证的权威来源。", note: "0 条有效证据" },
        { step: 5, title: "门槛校验", detail: "证据不足 → 不下结论，明确说「没查到」，并给出核查路径。", note: "gate=no_verdict" }
      ],
      sources: [
        { grade: "B", site: "大洋网", title: "网传停课通知？记者求证中", url: "https://www.dayoo.example.com/2026-10.htm", date: "2026-10-23" }
      ]
    }
  ],
  shot: {
    card: {
      verdict: "false",
      verdict_label: "假",
      claim: "转发：今晚开始全市停水三天，快储水（来自群聊截图）",
      from_screenshot: true,
      speaker: "群友「老陈」",
      one_line: "未检索到任何供水部门的停水公告；该「停水三天」截图为多地流传的旧图翻拍，属典型 seasonal 谣言。",
      reason: "供水公司官方客服确认无计划性停水；同类截图在 2024、2025 年台风季均出现过，仅地名被替换。",
      confidence: 0.82,
      elapsed_ms: 8100,
      search_calls: 4,
      counts: { S: 1, A: 1, B: 0, C: 1 },
      checked_at: "2026-10-24 10:30",
      gate_note: "",
      candidates: [],
      event: null,
      conflicts: [],
      gaps: ["若确有管网抢修，通常为分区限时停水（数小时），而非「全市三天」"],
      warnings: ["离线演示包未内置视觉模型，截图识别为演示流程，完整版由大模型读取图中文本"]
    },
    evidence: [
      { grade: "S", point: "市自来水公司公告栏与客服口径：近期无计划性停水。", quote: "近期无大范围计划停水安排，如遇管网抢修将提前分区发布通知。", site: "广州市自来水公司", title: "停水公告栏目（近期无新增）", url: "https://www.gzwater.example.com/notice", date: "" },
      { grade: "A", point: "本地媒体核查：同图曾在多个城市流传，仅文字被改。", quote: "该截图最早见于 2024 年，配文地名已更换 5 次。", site: "南方都市报", title: "「停水三天」截图又来了，这次是哪座城？", url: "https://www.nandu.example.com/2026-06.htm", date: "2026-06-15" }
    ],
    trace: [
      { step: 1, title: "读取截图", detail: "提取图中文本与转发链特征（演示包为固定样例）。", note: "vision=offline-demo" },
      { step: 2, title: "拆解主张", detail: "核心主张：全市停水三天，今晚开始。", note: "intent=verify" },
      { step: 3, title: "官方定向检索", detail: "供水公司公告与客服口径均无对应安排。", note: "S=1" },
      { step: 4, title: "溯源比对", detail: "同一截图跨城市流传、文字被改，判定为旧图翻拍。", note: "A=1 · C=1" },
      { step: 5, title: "门槛校验", detail: "S≥1 且独立权威域名≥2 → 出「假」。", note: "gate=pass" }
    ],
    sources: [
      { grade: "S", site: "广州市自来水公司", title: "停水公告栏目（近期无新增）", url: "https://www.gzwater.example.com/notice", date: "" },
      { grade: "A", site: "南方都市报", title: "「停水三天」截图又来了，这次是哪座城？", url: "https://www.nandu.example.com/2026-06.htm", date: "2026-06-15" }
    ]
  }
};
