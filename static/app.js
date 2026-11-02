const $ = (s) => document.querySelector(s);

const SESSION = (() => {
  let s = localStorage.getItem("detective_sid");
  if (!s) {
    s = "u_" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("detective_sid", s);
  }
  return s;
})();

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2200);
}

async function api(path, opt, retried) {
  const r = await fetch(path, opt);
  let data = {};
  let isJson = true;
  try { data = await r.json(); } catch (e) { isJson = false; }
  if (!r.ok) {
    // 网关超时/后端打盹：等 3 秒自动重试一次
    if ([524, 502, 503, 504].includes(r.status) && !retried) {
      await new Promise((res) => setTimeout(res, 3000));
      return api(path, opt, true);
    }
    // 403 且不是业务错误：多半是分享链接参数丢了或会话过期
    if (r.status === 403 && (!isJson || !data.error)) {
      const err = new Error("链接校验失败：请用完整分享链接重新打开本页（结尾要带 ?sharecode=…），再试一次");
      err.data = data;
      err.status = r.status;
      throw err;
    }
    const err = new Error(data.error || ("请求失败 " + r.status));
    err.data = data;
    err.status = r.status;
    throw err;
  }
  return data;
}

/* ------------------------------------------------ 状态 */
async function loadHealth() {
  const pill = $("#statusPill");
  try {
    const h = await api("/api/health");
    if (h.mock_search) {
      pill.className = "pill warn";
      pill.textContent = "演示数据模式";
      pill.title = "MOCK_SEARCH=1，检索结果为样例数据";
    } else if (!h.search_ready) {
      pill.className = "pill bad";
      pill.textContent = "未配置搜索密钥";
    } else if (!h.llm_ready) {
      pill.className = "pill warn";
      pill.textContent = "规则模式（未配大模型）";
    } else {
      pill.className = "pill ok";
      pill.textContent = "元宝搜索 · 已就绪";
    }
    pill.title = [
      "模型：" + h.model,
      "视觉：" + (h.vision_ready ? "开" : "关"),
      h.missing && h.missing.length ? "缺少：" + h.missing.join("、") : "",
      "服务器时间：" + h.server_time,
    ].filter(Boolean).join("\n");
  } catch (e) {
    pill.className = "pill bad";
    pill.textContent = "服务未连接";
  }
}

/* ------------------------------------------------ 查证 */
let busy = false;
let pending = null;   // 被验证码拦下时暂存的请求，验证通过后自动续跑

async function verify(text, intent, cap) {
  text = (text || "").trim();
  if (!text) { toast("先说一句要查的话"); return; }
  if (busy) return;
  busy = true;
  setBusy(true);
  pending = { type: "text", text, intent };

  const result = $("#result");
  result.innerHTML = '<section class="panel"><div class="loading"><div class="dots"><span></span><span></span><span></span></div><span id="loadingText">拆解主张…</span></div></section>';
  const phrases = ["拆解主张…", "首轮检索中…", "补查官方口径…", "交叉验证来源…", "生成查证卡…"];
  let i = 0;
  const timer = setInterval(() => {
    const el = $("#loadingText");
    if (el) el.textContent = phrases[Math.min(i++, phrases.length - 1)];
  }, 1600);

  try {
    const data = await api("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ text, intent, session: SESSION }, cap || {})),
    });
    clearInterval(timer);
    pending = null;
    result.innerHTML = renderResult(data);
    bindResultEvents();
    if (data.stats) renderStats(data.stats, null);
    loadStats();
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    clearInterval(timer);
    if (e.data && e.data.need_captcha) {
      renderCaptcha(e.data);
      result.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      result.innerHTML = '<section class="panel"><div class="err">' + esc(e.message) + "</div></section>";
    }
  } finally {
    busy = false;
    setBusy(false);
  }
}

function setBusy(v) {
  ["#btnVerify", "#btnFind", "#btnLatest", "#btnShot"].forEach((s) => {
    const el = $(s);
    if (el) el.disabled = v;
  });
}

/* ------------------------------------------------ 渲染 */
function stampClass(v) {
  return {
    true: "v-true", false: "v-false", uncertain: "v-uncertain",
    partially_true: "v-partially_true", not_found: "v-not_found",
    confirmed: "v-false", denied: "v-true",
  }[v] || "v-uncertain";
}

function renderResult(data) {
  const c = data.card;
  const evs = c.evidence || [];
  const label = c.verdict_label || "说不准";
  const small = label.length >= 5 ? "font-size:17px;letter-spacing:1px"
              : label.length === 4 ? "font-size:21px;letter-spacing:2px"
              : label.length === 3 ? "font-size:30px;letter-spacing:3px" : "";

  let html = '<section class="panel">';

  html += '<div class="card-head">' +
    '<div class="stamp ' + stampClass(c.verdict) + '" style="' + small + '">' + esc(label) + "</div>" +
    "<div>" +
    '<div class="claim">主张：' + esc(c.claim) + (c.from_screenshot ? "（来自截图 · " + esc(c.speaker || "未知") + "）" : "") + "</div>" +
    (c.time_note ? '<div class="time-note">⏱ 时间归一化：' + esc(c.time_note) + "</div>" : "") +
    '<div class="one-line serif">' + esc(c.one_line) + "</div>" +
    (c.reason ? '<div class="reason">' + esc(c.reason) + "</div>" : "") +
    "</div></div>";

  html += '<div class="meta">' +
    "<span>结论可信度 <b>" + Math.round((c.confidence || 0) * 100) + "%</b></span>" +
    "<span>用时 <b>" + ((c.elapsed_ms || 0) / 1000).toFixed(1) + "s</b></span>" +
    "<span>检索 <b>" + (c.search_calls || 0) + "</b> 次</span>" +
    "<span>来源构成 <b>S" + (c.counts?.S || 0) + " / A" + (c.counts?.A || 0) + " / B" + (c.counts?.B || 0) + " / C" + (c.counts?.C || 0) + "</b></span>" +
    "<span>核查时间 <b>" + esc(c.checked_at) + "</b></span>" +
    (data.quota ? "<span>本设备额度 <b>" + data.quota.used + "/" + data.quota.limit + "</b></span>" : "") +
    "</div>";

  if (c.gate_note) {
    html += '<div class="conflict" style="background:#fdf6e6"><div class="judge" style="border:0;margin:0;padding:0">⚠️ ' + esc(c.gate_note) + "，因此结论降级为「说不准」。</div></div>";
  }

  if ((c.candidates || []).length) {
    html += '<div class="section-label">候选线索 · 顺着线索找到的</div>';
    c.candidates.forEach((x, i) => {
      html += '<div class="cand">' +
        '<div class="cand-no">' + (i + 1) + "</div>" +
        '<div class="cand-body"><div class="cand-answer">' + esc(x.answer || "") + "</div>" +
        (x.why ? '<div class="cand-why">' + esc(x.why) + "</div>" : "") +
        '<div class="ev-src"><a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.site || "来源") + " · " + esc((x.title || "").slice(0, 30)) + "</a><span>" + esc(x.date || "") + "</span></div>" +
        "</div></div>";
    });
  }

  if (c.event && c.event.fields && Object.keys(c.event.fields).length) {
    const FL = [["time", "时间"], ["location", "位置"], ["lat", "纬度"], ["lon", "经度"], ["magnitude", "强度"], ["depth", "深度"]];
    html += '<div class="section-label">官方通报数据</div><div class="ev-grid">';
    FL.forEach((f) => {
      if (c.event.fields[f[0]]) {
        html += '<div class="ev-cell"><div class="ev-k">' + f[1] + '</div><div class="ev-v">' + esc(c.event.fields[f[0]]) + "</div></div>";
      }
    });
    html += "</div>";
    if (c.event.agreement) {
      html += '<div class="hintline">多源核对：' + esc(c.event.agreement) + "</div>";
    }
  }

  if (evs.length) {
    html += '<div class="section-label">' +
      (c.verdict === "not_found" ? "查到的相关内容 · 但不足以定论" : "证据 · " + evs.length + " 条（点来源可核对原文）") +
      "</div>";
    evs.forEach((e) => {
      html += '<div class="ev">' +
        '<div class="badge ' + esc(e.grade) + '">' + esc(e.grade) + "</div>" +
        '<div class="ev-body">' +
        '<div class="ev-point">' + esc(e.point) + "</div>" +
        (e.quote ? '<div class="ev-quote">' + esc(e.quote) + "</div>" : "") +
        '<div class="ev-src"><a href="' + esc(e.url) + '" target="_blank" rel="noopener">' + esc(e.site || "来源") + " · " + esc((e.title || "").slice(0, 34)) + "</a>" +
        "<span>" + esc((e.date || "").slice(0, 10)) + "</span></div>" +
        "</div></div>";
    });
  } else {
    html += '<div class="section-label">证据</div><div class="gap-item">没有可引用的来源，所以不下结论。</div>';
  }

  if ((c.conflicts || []).length) {
    html += '<div class="section-label">来源打架 · 它怎么判</div>';
    c.conflicts.forEach((x) => {
      html += '<div class="conflict"><div class="two">' +
        '<div class="side"><b>说法 A · ' + esc(x.a.grade) + " 级</b>" + esc(x.a.site) + "<br>" + esc((x.a.title || "").slice(0, 40)) + "<br><span style=\"color:#8b8471\">" + esc(x.a.date) + "</span></div>" +
        '<div class="side"><b>说法 B · ' + esc(x.b.grade) + " 级</b>" + esc(x.b.site) + "<br>" + esc((x.b.title || "").slice(0, 40)) + "<br><span style=\"color:#8b8471\">" + esc(x.b.date) + "</span></div>" +
        '</div><div class="judge">采信理由：' + esc(x.judgement || "未说明") + "</div></div>";
    });
  }

  if ((c.gaps || []).length) {
    html += '<div class="section-label">还缺什么</div>';
    c.gaps.forEach((g) => { html += '<div class="gap-item">' + esc(g) + "</div>"; });
  }

  // 调查过程
  html += '<div class="section-label">调查过程 · ' + (data.trace || []).length + " 步</div>";
  html += '<details class="trace" open><summary>展开 / 收起每一步（评委看这里）<span class="chev">▾</span></summary><div class="steps">';
  (data.trace || []).forEach((s) => {
    html += '<div class="step s' + s.step + '">' +
      '<div class="st-title">' + s.step + ". " + esc(s.title) + "</div>" +
      '<div class="st-detail">' + esc(s.detail) + "</div>" +
      (s.note ? '<div class="st-note">' + esc(s.note) + "</div>" : "") +
      "</div>";
  });
  html += "</div></details>";

  // 来源墙
  if ((data.sources || []).length) {
    html += '<div class="section-label">全部来源 · ' + data.sources.length + " 条</div><div class=\"sources\">";
    data.sources.forEach((s) => {
      html += '<div class="src-item"><span class="badge ' + esc(s.grade) + '" style="width:18px;height:18px;font-size:10px">' + esc(s.grade) + "</span>" +
        '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.title || s.url) + "</a>" +
        '<span style="color:#a9a396">' + esc(s.site || "") + " · " + esc((s.date || "").slice(0, 10)) + "</span></div>";
    });
    html += "</div>";
  }

  if ((c.warnings || []).length) {
    html += '<div class="hintline">运行提示：' + esc(c.warnings.join("；")) + "</div>";
  }

  html += '<div class="row" style="margin-top:16px"><button class="ghost" id="btnCopy">复制结论</button>' +
    '<button class="ghost" id="btnWatchThis">盯住这条</button></div>';

  html += "</section>";
  return html;
}

function bindResultEvents() {
  const copy = $("#btnCopy");
  if (copy) {
    copy.onclick = () => {
      const t = $(".one-line")?.textContent || "";
      const ev = Array.from(document.querySelectorAll(".ev-src a")).slice(0, 3).map((a) => a.href).join("\n");
      navigator.clipboard?.writeText(t + "\n来源：\n" + ev).then(() => toast("已复制"), () => toast("复制失败"));
    };
  }
  const w = $("#btnWatchThis");
  if (w) {
    w.onclick = () => {
      const claim = $(".card-head .claim")?.textContent?.replace(/^主张：/, "").replace(/（来自截图.*$/, "") || "";
      $("#watchInput").value = claim;
      $("#watchInput").scrollIntoView({ behavior: "smooth", block: "center" });
      $("#watchInput").focus();
    };
  }
}

/* ------------------------------------------------ 验证码 */
function renderCaptcha(info) {
  const result = $("#result");
  result.innerHTML = '<section class="panel">' +
    "<h2>需要验证一下是你本人</h2>" +
    '<div class="hintline">同一台设备免验证可查 <b>' + info.quota.limit + '</b> 次，本设备已用 ' + info.quota.used +
    " 次。输入图中文字验证后即可继续，验证不消耗查证次数。</div>" +
    '<div class="row"><img id="captchaImg" alt="验证码" src="' + info.image + '" style="height:56px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:2px" />' +
    '<input id="captchaInput" placeholder="输入图中文字（不区分大小写）" style="flex:1;min-width:160px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font-size:15px;font-family:inherit;" />' +
    '<button class="primary" id="btnCaptchaGo">验证并继续</button>' +
    '<button class="ghost" id="btnCaptchaNew">换一张</button></div>' +
    "</section>";
  $("#captchaInput").focus();

  const submit = () => {
    const code = $("#captchaInput").value.trim();
    if (!code) { toast("先输入图中文字"); return; }
    const cap = { captcha_id: info.captcha_id, captcha_code: code };
    if (pending && pending.type === "shot") {
      uploadScreenshot(pending.file, cap);
    } else {
      const p = pending || { text: $("#claim").value, intent: "auto" };
      verify(p.text, p.intent, cap);
    }
  };
  $("#btnCaptchaGo").onclick = submit;
  $("#captchaInput").addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
  $("#btnCaptchaNew").onclick = async () => {
    try {
      const d = await api("/api/captcha");
      info.captcha_id = d.captcha_id;
      $("#captchaImg").src = d.image;
      $("#captchaInput").value = "";
    } catch (e) { toast(e.message); }
  };
}

/* ------------------------------------------------ 截图 */
async function uploadScreenshot(file, cap) {
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  fd.append("hint", $("#claim").value.trim());
  if (cap) {
    fd.append("captcha_id", cap.captcha_id);
    fd.append("captcha_code", cap.captcha_code);
  }
  pending = { type: "shot", file };

  const result = $("#result");
  result.innerHTML = '<section class="panel"><div class="loading"><div class="dots"><span></span><span></span><span></span></div><span>读图、找那句话、再去查…</span></div></section>';
  setBusy(true);
  try {
    const data = await api("/api/screenshot", { method: "POST", body: fd });
    pending = null;
    result.innerHTML = renderResult(data);
    bindResultEvents();
    loadStats();
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    if (e.data && e.data.need_captcha) {
      renderCaptcha(e.data);
    } else {
      result.innerHTML = '<section class="panel"><div class="err">' + esc(e.message) + "<br><br>提示：把截图里那句话直接粘贴到输入框，同样能查。</div></section>";
    }
  } finally {
    setBusy(false);
  }
}

/* ------------------------------------------------ 盯梢 */
let WATCHES = [];

async function loadWatches(autoCheck) {
  try {
    const data = await api("/api/watches");
    WATCHES = data.items || [];
    renderWatches();
    if (autoCheck) {
      const todo = WATCHES.filter((w) => w.active).slice(0, 5);
      for (const w of todo) {
        try { await checkWatch(w.id, true); } catch (e) { /* ignore */ }
      }
    }
  } catch (e) {
    $("#watchList").innerHTML = '<div class="hintline">' + esc(e.message) + "</div>";
  }
}

function fmtTime(ts) {
  if (!ts) return "未检查";
  const d = new Date(ts * 1000);
  return d.toLocaleString("zh-CN", { hour12: false }).slice(5);
}

function renderWatches() {
  const box = $("#watchList");
  if (!WATCHES.length) {
    box.innerHTML = '<div class="hintline">还没有盯梢。挑一条会变的（天气预警、余票、官方通报），明天就能录到「真实触发的提醒」。</div>';
    return;
  }
  box.innerHTML = WATCHES.map((w) => {
    const changed = w._changed;
    return '<div class="watch-item ' + (changed ? "changed" : "") + '" data-id="' + w.id + '">' +
      '<div class="watch-top"><div class="watch-claim">' + esc(w.claim) +
      (changed ? '<span class="badge-new">有变化</span>' : "") + "</div>" +
      '<div style="display:flex;gap:6px;flex:0 0 auto">' +
      '<button class="mini ghost" data-act="check">检查</button>' +
      '<button class="mini ghost" data-act="toggle">' + (w.active ? "暂停" : "恢复") + "</button>" +
      '<button class="mini danger" data-act="del">删</button></div></div>' +
      '<div class="watch-meta"><span>上次：' + fmtTime(w.last_check) + "</span>" +
      "<span>当前判断：" + esc(w.last_verdict || "未建立基线") + "</span>" +
      "<span>历史快照 " + (w.history ? w.history.length : 0) + " 次</span></div>" +
      "</div>";
  }).join("");
}

async function checkWatch(id, silent) {
  const item = WATCHES.find((w) => w.id === id) || {};
  const data = await api("/api/watches/" + id + "/check", { method: "POST" });
  if (data.changed) {
    item._changed = true;
    toast("盯梢命中变化：" + data.verdict_label + " · " + (data.one_line || ""));
  } else if (!silent) {
    toast("已检查：" + data.verdict_label + (item.last_check ? "（暂无变化）" : "（已建立基线）"));
  }
  await loadWatches(false);
  loadStats();
  return data;
}

async function addWatch() {
  const claim = $("#watchInput").value.trim();
  if (!claim) { toast("写一句要盯的话"); return; }
  try {
    await api("/api/watches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim }),
    });
    $("#watchInput").value = "";
    toast("已加入盯梢，正在建立基线…");
    const data = await api("/api/watches");
    WATCHES = data.items || [];
    renderWatches();
    const last = WATCHES[0];
    if (last) await checkWatch(last.id, true);
  } catch (e) {
    toast(e.message);
  }
}

/* ------------------------------------------------ 统计 */
function renderStats(s, recent) {
  if (s) {
    $("#stTotal").textContent = s.total ?? "–";
    $("#stToday").textContent = s.today ?? "–";
    $("#stSessions").textContent = s.sessions ?? "–";
    $("#stWatches").textContent = s.watches ?? "–";
  }
  if (recent) {
    $("#feed").innerHTML = recent.length
      ? recent.map((x) => '<div class="f"><span>' + esc(x.time) + "</span><span>" + esc((x.claim || "").slice(0, 42)) + "</span><span style=\"margin-left:auto;color:#8b8471\">" + esc(x.verdict || "") + "</span></div>").join("")
      : '<div class="hintline">还没有人查过。让旁边的人扫个码试试。</div>';
  }
}

async function loadStats() {
  try {
    const d = await api("/api/stats");
    renderStats(d.stats, d.recent || []);
  } catch (e) { /* ignore */ }
}

/* ------------------------------------------------ 绑定 */
function init() {
  $("#btnVerify").onclick = () => verify($("#claim").value, "auto");
  $("#btnFind").onclick = () => verify($("#claim").value, "find");
  $("#btnLatest").onclick = () => verify($("#claim").value, "latest");
  $("#btnShot").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = (e) => uploadScreenshot(e.target.files[0]);
  $("#claim").addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") verify($("#claim").value, "auto");
  });

  $("#btnWatch").onclick = addWatch;
  $("#watchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") addWatch(); });
  $("#btnCheckAll").onclick = async () => {
    const list = WATCHES.filter((w) => w.active);
    if (!list.length) { toast("还没有盯梢"); return; }
    for (const w of list) { try { await checkWatch(w.id, true); } catch (e) { toast(e.message); } }
    toast("全部检查完成");
  };

  $("#watchList").onclick = async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = +btn.closest(".watch-item").dataset.id;
    const act = btn.dataset.act;
    try {
      if (act === "check") await checkWatch(id, false);
      if (act === "toggle") {
        const w = WATCHES.find((x) => x.id === id);
        const d = await api("/api/watches/" + id + "/toggle", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: !(w && w.active) }),
        });
        WATCHES = d.items || [];
        renderWatches();
      }
      if (act === "del") {
        const d = await api("/api/watches/" + id, { method: "DELETE" });
        WATCHES = d.items || [];
        renderWatches();
        loadStats();
      }
    } catch (err) { toast(err.message); }
  };

  loadHealth();
  loadStats();
  loadWatches(true);

  // 支持 ?q=直接开查（现场扫码演示 / 生成演示链接用）
  const params = new URLSearchParams(location.search);
  const q = params.get("q");
  if (q) {
    $("#claim").value = q;
    verify(q, params.get("intent") || "auto");
  }
  if (params.has("debugw")) {
    setTimeout(() => {
      const wide = [];
      document.querySelectorAll("body *").forEach((el) => {
        const cs = getComputedStyle(el);
        if (cs.display === "none") return;
        const r = el.getBoundingClientRect();
        const overflowX = el.scrollWidth > el.clientWidth + 2;
        if (overflowX && r.width < 460) {
          const cls = typeof el.className === "string" ? el.className.split(" ")[0] : "";
          wide.push(el.tagName + "." + cls + " w=" + Math.round(r.width) + " sw=" + el.scrollWidth);
        }
      });
      document.title = "W=" + document.documentElement.scrollWidth +
        " | " + (wide.slice(0, 10).join(" ; ") || "no-x-overflow");
    }, 1500);
  }
}

document.addEventListener("DOMContentLoaded", init);
