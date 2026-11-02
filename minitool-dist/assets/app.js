/* 一键查真伪 · 小工具离线演示版
 * 容器合规改写：
 * - 无 fetch / XMLHttpRequest（容器禁联网）→ 内置演示数据匹配
 * - 无 navigator.clipboard → 弹出可选中文本框引导手动复制
 * - 无 <a target="_blank"> 外链 → 来源 URL 以可选中文本展示
 * - 存储：优先 window.xhs.miniTool.setStorage（9.46+），降级 localStorage 且全程 try/catch
 * - 语法基线 ES2017（Chrome 61）：无 ?./??/spread 等更新语法
 */
var $ = function (s) { return document.querySelector(s); };

var DEMO = window.DEMO || { cases: [], shot: null };

/* ---------------- 存储（异步安全封装） ---------------- */
var STORAGE_MIN = 9460;

function miniTool() {
  return window.xhs && window.xhs.miniTool;
}

function readBuildVersion(lo) {
  var env = lo && lo.miniToolEnv;
  return Number(env && env.buildVersion) || 0;
}

function getBuildVersion() {
  var x = window.xhs;
  var sync = readBuildVersion(x && x.launchOptions);
  if (sync) return Promise.resolve(sync);
  var mt = miniTool();
  if (!mt || typeof mt.getLaunchOptions !== "function") return Promise.resolve(0);
  return mt.getLaunchOptions().then(readBuildVersion).catch(function () { return 0; });
}

function storeGet(key) {
  var mt = miniTool();
  return getBuildVersion().then(function (v) {
    if (v >= STORAGE_MIN && mt && typeof mt.getStorage === "function") {
      return mt.getStorage({ key: key }).then(function (r) {
        try { return JSON.parse(r.data); } catch (e) { return null; }
      }).catch(function () { return localGet(key); });
    }
    return localGet(key);
  });
}

function storeSet(key, val) {
  var mt = miniTool();
  var data;
  try { data = JSON.stringify(val); } catch (e) { return Promise.resolve(false); }
  return getBuildVersion().then(function (v) {
    if (v >= STORAGE_MIN && mt && typeof mt.setStorage === "function") {
      return mt.setStorage({ key: key, data: data }).then(function () { return true; })
        .catch(function () { return localSet(key, val); });
    }
    return localSet(key, val);
  });
}

function localGet(key) {
  try {
    var raw = localStorage.getItem(key);
    return Promise.resolve(raw ? JSON.parse(raw) : null);
  } catch (e) { return Promise.resolve(null); }
}

function localSet(key, val) {
  try {
    localStorage.setItem(key, JSON.stringify(val));
    return Promise.resolve(true);
  } catch (e) { return Promise.resolve(false); }
}

/* ---------------- 工具 ---------------- */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function toast(msg) {
  var el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(function () { el.classList.remove("show"); }, 2200);
}

function stampClass(v) {
  var m = {
    true: "v-true", false: "v-false", uncertain: "v-uncertain",
    partially_true: "v-partially_true", not_found: "v-not_found",
    confirmed: "v-false", denied: "v-true"
  };
  return m[v] || "v-uncertain";
}

/* ---------------- 本地统计与盯梢 ---------------- */
var STATS = { total: 0, today: 0, sessions: 1, watches: 0, feed: [] };
var WATCHES = [];

function todayStr() {
  var d = new Date();
  return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
}

function renderStats() {
  $("#stTotal").textContent = STATS.total;
  $("#stToday").textContent = STATS.today;
  $("#stSessions").textContent = STATS.sessions;
  $("#stWatches").textContent = WATCHES.filter(function (w) { return w.active; }).length;
  var feed = $("#feed");
  feed.innerHTML = (STATS.feed || []).map(function (x) {
    return '<div class="f"><span>' + esc(x.time) + "</span><span>" + esc((x.claim || "").slice(0, 42)) +
      '</span><span class="f-v">' + esc(x.verdict || "") + "</span></div>";
  }).join("") || '<div class="hintline">还没有查证记录，输入一句话试试。</div>';
}

function saveStats() { storeSet("demo_stats", STATS); }

function recordStat(claim, verdict) {
  STATS.total += 1;
  var d = new Date();
  var hh = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  STATS.feed.unshift({ time: todayStr().slice(5) + " " + hh, claim: claim, verdict: verdict });
  STATS.feed = STATS.feed.slice(0, 20);
  saveStats();
  renderStats();
}

function renderWatches() {
  var box = $("#watchList");
  if (!WATCHES.length) {
    box.innerHTML = '<div class="hintline">还没有盯梢。挑一条会变的（天气预警、停课通知）加进来，第二次检查就能看到「有变化」的演示效果。</div>';
    return;
  }
  box.innerHTML = WATCHES.map(function (w) {
    var changed = w._changed;
    return '<div class="watch-item ' + (changed ? "changed" : "") + '" data-id="' + w.id + '">' +
      '<div class="watch-top"><div class="watch-claim">' + esc(w.claim) +
      (changed ? '<span class="badge-new">有变化</span>' : "") + "</div>" +
      '<div class="watch-btns">' +
      '<button class="mini ghost" data-act="check">检查</button>' +
      '<button class="mini ghost" data-act="toggle">' + (w.active ? "暂停" : "恢复") + "</button>" +
      '<button class="mini danger" data-act="del">删</button></div></div>' +
      '<div class="watch-meta"><span>上次：' + fmtTime(w.last_check) + "</span>" +
      "<span>当前判断：" + esc(w.last_verdict || "未建立基线") + "</span>" +
      "<span>历史快照 " + w.history + " 次</span></div>" +
      "</div>";
  }).join("");
}

function fmtTime(ts) {
  if (!ts) return "未检查";
  var d = new Date(ts * 1000);
  return d.toLocaleString("zh-CN", { hour12: false }).slice(5);
}

function saveWatches() {
  var plain = WATCHES.map(function (w) {
    return { id: w.id, claim: w.claim, active: w.active, last_check: w.last_check, last_verdict: w.last_verdict, history: w.history };
  });
  storeSet("demo_watches", plain).then(function () {
    STATS.watches = WATCHES.length;
    renderStats();
  });
}

function addWatch() {
  var claim = $("#watchInput").value.trim();
  if (!claim) { toast("写一句要盯的话"); return; }
  WATCHES.push({ id: Date.now(), claim: claim, active: true, last_check: 0, last_verdict: "", history: 0, _changed: false });
  $("#watchInput").value = "";
  toast("已加入盯梢，点「检查」建立基线…");
  saveWatches();
  renderWatches();
}

function checkWatch(id, silent) {
  var item = null;
  for (var i = 0; i < WATCHES.length; i++) { if (WATCHES[i].id === id) { item = WATCHES[i]; break; } }
  if (!item) return;
  item.history += 1;
  item.last_check = Math.floor(Date.now() / 1000);
  var demo = ["说不准", "假", "没查到", "有记录"];
  if (item.history === 1) {
    item.last_verdict = demo[(item.id || 0) % demo.length];
    if (!silent) toast("已建立基线：" + item.last_verdict);
  } else {
    item._changed = true;
    var idx = demo.indexOf(item.last_verdict);
    item.last_verdict = demo[(idx + 1 + item.history) % demo.length];
    if (!silent) toast("盯梢命中变化：" + item.last_verdict);
  }
  saveWatches();
  renderWatches();
}

/* ---------------- 查证（本地演示匹配） ---------------- */
var busy = false;

function pickCase(text) {
  var t = (text || "").toLowerCase();
  for (var i = 0; i < DEMO.cases.length; i++) {
    var kws = DEMO.cases[i].match;
    for (var j = 0; j < kws.length; j++) {
      if (t.indexOf(kws[j].toLowerCase()) >= 0) return DEMO.cases[i];
    }
  }
  return null;
}

function verify(text) {
  text = (text || "").trim();
  if (!text) { toast("先说一句要查的话"); return; }
  if (busy) return;
  busy = true;
  setBusy(true);
  pendingShot = null;

  var result = $("#result");
  result.innerHTML = '<section class="panel"><div class="loading"><div class="dots"><span></span><span></span><span></span></div><span id="loadingText">拆解主张…</span></div></section>';
  var phrases = ["拆解主张…", "首轮检索中…", "补查官方口径…", "交叉验证来源…", "生成查证卡…"];
  var i = 0;
  var timer = setInterval(function () {
    var el = $("#loadingText");
    if (el) el.textContent = phrases[Math.min(i++, phrases.length - 1)];
  }, 700);

  setTimeout(function () {
    clearInterval(timer);
    var hit = pickCase(text);
    var payload = hit || {
      card: {
        verdict: "uncertain", verdict_label: "说不准", claim: text,
        from_screenshot: false, speaker: "",
        one_line: "离线演示包未收录与「" + text.slice(0, 24) + "」对应的查证样例。",
        reason: "完整联网版会对这句话做多轮元宝检索与来源交叉验证；演示包仅内置地震核实、饮水谣言、转账传言、停课通知等真实样例，可任选一句体验。",
        confidence: 0.3, elapsed_ms: 3200, search_calls: 2,
        counts: { S: 0, A: 0, B: 0, C: 0 }, checked_at: "2026-10-24",
        gate_note: "演示数据未命中", candidates: [], event: null, conflicts: [], gaps: [], warnings: []
      },
      evidence: [], trace: [
        { step: 1, title: "拆解主张", detail: "演示包：未命中内置样例关键词。", note: "offline-demo" },
        { step: 2, title: "门槛校验", detail: "无内置证据，给出「说不准」占位结论。", note: "gate=downgrade" }
      ], sources: []
    };
    var c = payload.card;
    result.innerHTML = renderResult(payload);
    bindResultEvents();
    recordStat(c.claim, c.verdict_label);
    setBusy(false);
    busy = false;
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 2600);
}

function setBusy(v) {
  var ids = ["#btnVerify", "#btnShot"];
  for (var i = 0; i < ids.length; i++) {
    var el = $(ids[i]);
    if (el) el.disabled = v;
  }
}

/* ---------------- 渲染 ---------------- */
function renderResult(data) {
  var c = data.card;
  var evs = data.evidence || c.evidence || [];
  var label = c.verdict_label || "说不准";
  var small = label.length >= 5 ? "font-size:17px;letter-spacing:1px"
            : label.length === 4 ? "font-size:21px;letter-spacing:2px"
            : label.length === 3 ? "font-size:30px;letter-spacing:3px" : "";

  var html = '<section class="panel">';

  html += '<div class="card-head">' +
    '<div class="stamp ' + stampClass(c.verdict) + '" style="' + small + '">' + esc(label) + "</div>" +
    "<div>" +
    '<div class="claim">主张：' + esc(c.claim) + (c.from_screenshot ? "（来自截图 · " + esc(c.speaker || "未知") + "）" : "") + "</div>" +
    '<div class="one-line serif">' + esc(c.one_line) + "</div>" +
    (c.reason ? '<div class="reason">' + esc(c.reason) + "</div>" : "") +
    "</div></div>";

  var counts = c.counts || {};
  html += '<div class="meta">' +
    "<span>结论可信度 <b>" + Math.round((c.confidence || 0) * 100) + "%</b></span>" +
    "<span>用时 <b>" + ((c.elapsed_ms || 0) / 1000).toFixed(1) + "s</b></span>" +
    "<span>检索 <b>" + (c.search_calls || 0) + "</b> 次</span>" +
    "<span>来源构成 <b>S" + (counts.S || 0) + " / A" + (counts.A || 0) + " / B" + (counts.B || 0) + " / C" + (counts.C || 0) + "</b></span>" +
    "<span>核查时间 <b>" + esc(c.checked_at) + "</b></span>" +
    "</div>";

  if (c.gate_note) {
    html += '<div class="conflict"><div class="judge" style="border:0;margin:0;padding:0">⚠️ ' + esc(c.gate_note) + "，因此结论降级为「说不准」。</div></div>";
  }

  var cands = c.candidates || [];
  if (cands.length) {
    html += '<div class="section-label">候选线索 · 顺着线索找到的</div>';
    for (var i = 0; i < cands.length; i++) {
      var x = cands[i];
      html += '<div class="cand">' +
        '<div class="cand-no">' + (i + 1) + "</div>" +
        '<div class="cand-body"><div class="cand-answer">' + esc(x.answer || "") + "</div>" +
        (x.why ? '<div class="cand-why">' + esc(x.why) + "</div>" : "") +
        '<div class="ev-src"><span class="src-name">' + esc(x.site || "来源") + " · " + esc((x.title || "").slice(0, 30)) + "</span>" +
        '<span class="src-url">' + esc(x.url || "") + "</span></div>" +
        "</div></div>";
    }
  }

  if (c.event && c.event.fields) {
    var FL = [["time", "时间"], ["location", "位置"], ["lat", "纬度"], ["lon", "经度"], ["magnitude", "强度"], ["depth", "深度"]];
    html += '<div class="section-label">官方通报数据</div><div class="ev-grid">';
    for (var f = 0; f < FL.length; f++) {
      var v = c.event.fields[FL[f][0]];
      if (v) {
        html += '<div class="ev-cell"><div class="ev-k">' + FL[f][1] + '</div><div class="ev-v">' + esc(v) + "</div></div>";
      }
    }
    html += "</div>";
    if (c.event.agreement) {
      html += '<div class="hintline">多源核对：' + esc(c.event.agreement) + "</div>";
    }
  }

  if (evs.length) {
    html += '<div class="section-label">' +
      (c.verdict === "not_found" ? "查到的相关内容 · 但不足以定论" : "证据 · " + evs.length + " 条（来源 URL 可长按复制核对）") +
      "</div>";
    for (var e = 0; e < evs.length; e++) {
      var ev = evs[e];
      html += '<div class="ev">' +
        '<div class="badge ' + esc(ev.grade) + '">' + esc(ev.grade) + "</div>" +
        '<div class="ev-body">' +
        '<div class="ev-point">' + esc(ev.point) + "</div>" +
        (ev.quote ? '<div class="ev-quote">' + esc(ev.quote) + "</div>" : "") +
        '<div class="ev-src"><span class="src-name">' + esc(ev.site || "来源") + " · " + esc((ev.title || "").slice(0, 34)) + "</span>" +
        '<span class="src-date">' + esc((ev.date || "").slice(0, 10)) + "</span></div>" +
        (ev.url ? '<div class="src-url">' + esc(ev.url) + "</div>" : "") +
        "</div></div>";
    }
  } else {
    html += '<div class="section-label">证据</div><div class="gap-item">没有可引用的来源，所以不下结论。</div>';
  }

  var conflicts = c.conflicts || [];
  if (conflicts.length) {
    html += '<div class="section-label">来源打架 · 它怎么判</div>';
    for (var k = 0; k < conflicts.length; k++) {
      var cf = conflicts[k];
      html += '<div class="conflict"><div class="two">' +
        '<div class="side"><b>说法 A · ' + esc(cf.a.grade) + " 级</b>" + esc(cf.a.site) + "<br>" + esc((cf.a.title || "").slice(0, 40)) + "<br><span class=\"dim\">" + esc(cf.a.date) + "</span></div>" +
        '<div class="side"><b>说法 B · ' + esc(cf.b.grade) + " 级</b>" + esc(cf.b.site) + "<br>" + esc((cf.b.title || "").slice(0, 40)) + "<br><span class=\"dim\">" + esc(cf.b.date) + "</span></div>" +
        '</div><div class="judge">采信理由：' + esc(cf.judgement || "未说明") + "</div></div>";
    }
  }

  var gaps = c.gaps || [];
  if (gaps.length) {
    html += '<div class="section-label">还缺什么</div>';
    for (var g = 0; g < gaps.length; g++) { html += '<div class="gap-item">' + esc(gaps[g]) + "</div>"; }
  }

  var trace = data.trace || [];
  html += '<div class="section-label">调查过程 · ' + trace.length + " 步</div>";
  html += '<details class="trace" open><summary>展开 / 收起每一步（评委看这里）<span class="chev">▾</span></summary><div class="steps">';
  for (var s = 0; s < trace.length; s++) {
    html += '<div class="step s' + trace[s].step + '">' +
      '<div class="st-title">' + trace[s].step + ". " + esc(trace[s].title) + "</div>" +
      '<div class="st-detail">' + esc(trace[s].detail) + "</div>" +
      (trace[s].note ? '<div class="st-note">' + esc(trace[s].note) + "</div>" : "") +
      "</div>";
  }
  html += "</div></details>";

  var sources = data.sources || [];
  if (sources.length) {
    html += '<div class="section-label">全部来源 · ' + sources.length + " 条</div>" + '<div class="sources">';
    for (var u = 0; u < sources.length; u++) {
      html += '<div class="src-item"><span class="badge ' + esc(sources[u].grade) + ' badge-mini">' + esc(sources[u].grade) + "</span>" +
        '<span class="src-tt">' + esc(sources[u].title || sources[u].url) + "</span>" +
        '<span class="dim">' + esc(sources[u].site || "") + " · " + esc((sources[u].date || "").slice(0, 10)) + "</span></div>";
    }
    html += "</div>";
  }

  if ((c.warnings || []).length) {
    html += '<div class="hintline">运行提示：' + esc(c.warnings.join("；")) + "</div>";
  }

  html += '<div class="row row-foot"><button class="ghost" id="btnCopy">复制结论</button></div>';
  html += "</section>";
  return html;
}

function bindResultEvents() {
  var copy = $("#btnCopy");
  if (copy) {
    copy.addEventListener("click", function () {
      var one = document.querySelector(".one-line");
      var t = one ? one.textContent : "";
      var urls = [];
      var nodes = document.querySelectorAll(".src-url");
      for (var i = 0; i < nodes.length && i < 3; i++) urls.push(nodes[i].textContent);
      $("#copyText").value = t + "\n来源：\n" + urls.join("\n");
      $("#copyModal").classList.add("show");
      var ta = $("#copyText");
      ta.focus();
      ta.select();
    });
  }
}

/* ---------------- 截图（本地选图预览 + 演示结论） ---------------- */
var pendingShot = null;

function handleShot(file) {
  if (!file) return;
  pendingShot = file;
  var result = $("#result");
  result.innerHTML = '<section class="panel"><div class="loading"><div class="dots"><span></span><span></span><span></span></div><span>读图、找那句话、再去查…</span></div></section>';
  setBusy(true);

  var finish = function () {
    var d = DEMO.shot;
    result.innerHTML = renderResult(d);
    bindResultEvents();
    recordStat(d.card.claim, d.card.verdict_label);
    setBusy(false);
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (window.FileReader && file.type && file.type.indexOf("image") === 0) {
    var reader = new FileReader();
    reader.onload = function () {
      finish();
      var sec = document.querySelector("#result .panel");
      if (sec) {
        var img = document.createElement("img");
        img.className = "shot-preview";
        img.alt = "截图预览";
        img.src = reader.result;
        sec.insertBefore(img, sec.querySelector(".meta"));
      }
    };
    reader.onerror = function () { finish(); };
    reader.readAsDataURL(file);
  } else {
    setTimeout(finish, 1200);
  }
}

/* ---------------- 初始化 ---------------- */
function init() {
  $("#btnVerify").addEventListener("click", function () { verify($("#claim").value); });
  $("#btnShot").addEventListener("click", function () { $("#fileInput").click(); });
  $("#fileInput").addEventListener("change", function (e) {
    handleShot(e.target.files && e.target.files[0]);
    e.target.value = "";
  });
  $("#claim").addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") verify($("#claim").value);
  });

  $("#btnWatch").addEventListener("click", addWatch);
  $("#watchInput").addEventListener("keydown", function (e) { if (e.key === "Enter") addWatch(); });
  $("#btnCheckAll").addEventListener("click", function () {
    var list = WATCHES.filter(function (w) { return w.active; });
    if (!list.length) { toast("还没有盯梢"); return; }
    for (var i = 0; i < list.length; i++) checkWatch(list[i].id, true);
    toast("全部检查完成");
  });

  $("#watchList").addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest("button[data-act]") : null;
    if (!btn) return;
    var wrap = btn.closest(".watch-item");
    var id = Number(wrap && wrap.getAttribute("data-id"));
    var act = btn.getAttribute("data-act");
    if (act === "check") checkWatch(id, false);
    if (act === "toggle") {
      for (var i = 0; i < WATCHES.length; i++) {
        if (WATCHES[i].id === id) { WATCHES[i].active = !WATCHES[i].active; break; }
      }
      saveWatches();
      renderWatches();
    }
    if (act === "del") {
      WATCHES = WATCHES.filter(function (w) { return w.id !== id; });
      saveWatches();
      renderWatches();
    }
  });

  $("#btnCopyClose").addEventListener("click", function () {
    $("#copyModal").classList.remove("show");
  });
  $("#copyModal").addEventListener("click", function (e) {
    if (e.target === $("#copyModal")) $("#copyModal").classList.remove("show");
  });

  Promise.all([storeGet("demo_stats"), storeGet("demo_watches")]).then(function (r) {
    if (r[0] && typeof r[0].total === "number") STATS = r[0];
    if (r[1] && r[1].length) {
      WATCHES = r[1].map(function (w) {
        w._changed = false;
        return w;
      });
    }
    renderStats();
    renderWatches();
  });
}

document.addEventListener("DOMContentLoaded", init);
