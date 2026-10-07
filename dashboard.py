# -*- coding: utf-8 -*-
# Copyright (c) 2026 abdurrehmandaudi
# Copyright (c) 2026 RavenHogwarts (modifications)
# Required Notice: Copyright (c) 2026 abdurrehmandaudi -- justdowork-proxy
# Licensed under the PolyForm Noncommercial License 1.0.0 -- commercial
# use is not permitted without a separate written commercial license.
# See LICENSE or https://polyformproject.org/licenses/noncommercial/1.0.0
r"""dashboard.py -- the live dashboard served by ccproxy at `/`.

ccproxy.py imports this. It lives in its own file so ccproxy.py stays readable,
and so that a broken dashboard cannot take the proxy down (ccproxy falls back to
a plain page if this module fails to import).

The page polls `/stats.json` every 2 seconds. No CDN, no internet access --
everything is inside this one file.

The UI is bilingual (English / 简体中文): the button in the header switches
language, the choice is remembered per browser, and the initial language
follows the `ui_lang` field of config.json (exposed via /stats.json).
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ccproxy dashboard</title>
<style>
  :root{
    --bg:#0e1116; --panel:#161a22; --panel2:#1c212b; --line:#252c38;
    --fg:#e6e9ef; --muted:#a3abc0; --accent:#5b9dff;
    --good:#3ecf8e; --warn:#ffb454; --bad:#ff6b6b; --violet:#a78bfa;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
  a{color:var(--accent);text-decoration:none}
  .wrap{max-width:1180px;margin:0 auto;padding:18px 16px 60px}
  header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;
         justify-content:space-between;padding:14px 16px;background:var(--panel);
         border:1px solid var(--line);border-radius:14px;margin-bottom:14px}
  .brand{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:650}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--good);
       box-shadow:0 0 0 4px rgba(62,207,142,.15)}
  .dot.off{background:var(--bad);box-shadow:0 0 0 4px rgba(255,107,107,.15)}
  .meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--muted)}
  .meta b{color:var(--fg);font-weight:600}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
     margin:22px 0 10px;font-weight:650}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:10px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 13px}
  .card .k{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .card .v{font-size:23px;font-weight:680;margin-top:3px;font-variant-numeric:tabular-nums}
  .card .s{font-size:11.5px;color:var(--muted);margin-top:2px}
  .v.good{color:var(--good)} .v.bad{color:var(--bad)} .v.warn{color:var(--warn)}
  .v.accent{color:var(--accent)} .v.violet{color:var(--violet)}
  .grid2{display:grid;grid-template-columns:1.35fr 1fr;gap:14px}
  @media(max-width:820px){.grid2{grid-template-columns:1fr}}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
  .bar{display:flex;height:26px;border-radius:8px;overflow:hidden;background:var(--panel2);
       border:1px solid var(--line)}
  .bar span{display:block;height:100%;min-width:2px}
  .legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:12.5px}
  .legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px}
  .legend b{font-variant-numeric:tabular-nums;font-weight:600}
  .legend .m{color:var(--muted)}
  .strip{display:flex;align-items:flex-end;gap:2px;height:56px;margin-top:6px}
  .strip div{flex:1;min-width:2px;border-radius:2px 2px 0 0;background:var(--accent);opacity:.75}
  .strip div.bad{background:var(--bad);opacity:.9}
  .strip div.srv{background:var(--violet)}
  .chips{display:flex;flex-wrap:wrap;gap:7px}
  .chip{background:var(--panel2);border:1px solid var(--line);border-radius:999px;
        padding:4px 11px;font-size:12.5px}
  .chip b{font-variant-numeric:tabular-nums}
  .tblwrap{overflow:auto;max-height:360px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
  .errlist{max-height:220px;overflow-y:auto}
  table{border-collapse:collapse;width:100%;font-size:12.5px;white-space:nowrap}
  th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:600;font-size:11.5px;text-transform:uppercase;
     letter-spacing:.05em;position:sticky;top:0;background:var(--panel)}
  tbody tr:last-child td{border-bottom:none}
  tbody tr:hover{background:var(--panel2)}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  .pill{border-radius:999px;padding:1px 8px;font-size:11px;border:1px solid var(--line)}
  .pill.ok{color:var(--good);border-color:rgba(62,207,142,.4)}
  .pill.no{color:var(--bad);border-color:rgba(255,107,107,.4)}
  .pill.st{color:var(--accent);border-color:rgba(91,157,255,.4)}
  .pill.dr{color:var(--warn);border-color:rgba(255,180,84,.4)}
  td.note{white-space:normal;max-width:360px}
  .notewrap{display:flex;align-items:flex-start;gap:6px}
  .notetxt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px}
  .notetxt.open{white-space:normal;word-break:break-word;max-width:none}
  .notebtn{flex:0 0 auto;background:var(--panel2);border:1px solid var(--line);
           border-radius:6px;padding:0 6px;font-size:11px;line-height:18px;
           color:var(--muted);cursor:pointer}
  .notebtn:hover{border-color:var(--accent);color:var(--accent)}
  .errrow{padding:3px 0;cursor:pointer}
  .errrow .d{display:none;white-space:pre-wrap;word-break:break-word;
             margin:2px 0 6px;color:var(--fg)}
  .errrow.open .d{display:block}
  .statrow{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:10px}
  .muted{color:var(--muted)}
  .err{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
  .empty{color:var(--muted);padding:16px;text-align:center}
  .hint{font-size:12px;color:var(--muted);margin-top:9px}
  button{background:var(--panel2);color:var(--fg);border:1px solid var(--line);
         border-radius:8px;padding:5px 12px;font-size:12.5px;cursor:pointer}
  button:hover{border-color:var(--accent);color:var(--accent)}
  button:disabled{opacity:.5;cursor:default}
  input{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
        padding:5px 10px;font-size:12.5px;color:var(--fg);font-family:inherit}
  input:focus{outline:none;border-color:var(--accent)}
  input::placeholder{color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="brand">
      <span class="dot" id="dot"></span> ccproxy
      <span class="muted" id="uptime" style="font-weight:400;font-size:13px"></span>
    </div>
    <div class="meta" id="meta"></div>
    <div style="display:flex;gap:8px">
      <button id="lang" title="Language / 语言">中</button>
      <button id="pause"></button>
      <button id="reset"></button>
    </div>
  </header>

  <h2 data-i18n="secTokens"></h2>
  <div class="cards" id="cards"></div>

  <h2 data-i18n="secData"></h2>
  <div class="grid2">
    <div class="panel">
      <div class="bar" id="bar"></div>
      <div class="legend" id="legend"></div>
      <div class="hint" id="barhint"></div>
      <div class="hint" id="budget"></div>
      <div class="strip" id="strip"></div>
      <div class="hint" id="striphint"></div>
    </div>
    <div class="panel">
      <div class="muted" style="font-size:11.5px;text-transform:uppercase;letter-spacing:.05em"
           data-i18n="toolUsage"></div>
      <div class="chips" id="tools" style="margin-top:10px"></div>
      <div class="muted" style="font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;margin-top:16px"
           data-i18n="disk"></div>
      <div class="chips" id="disk" style="margin-top:10px"></div>
    </div>
  </div>

  <h2 data-i18n="secRecent"></h2>
  <div class="statrow" id="statrow"></div>
  <div class="tblwrap">
    <table>
      <thead><tr>
        <th>#</th><th data-i18n="thTime"></th><th data-i18n="thKind"></th>
        <th class="num" data-i18n="thMsgs"></th>
        <th class="num" data-i18n="thInput"></th><th class="num" data-i18n="thOutput"></th>
        <th class="num" data-i18n="thSec"></th>
        <th data-i18n="thTools"></th><th data-i18n="thKeySrc"></th>
        <th class="num" data-i18n="thDrops"></th>
        <th data-i18n="thNote"></th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="hint" id="rowsmore"></div>

  <div id="errbox"></div>

  <h2 data-i18n="secKey"></h2>
  <div class="panel">
    <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">
      <span class="muted" data-i18n="keyCurrent"></span>
      <b class="err" id="keycur">loading ...</b>
      <span id="keypill"></span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
      <input id="keyin" type="password" autocomplete="off" spellcheck="false"
             style="flex:1;min-width:220px">
      <button id="keysave"></button>
    </div>
    <div class="hint" id="keyhint"></div>
  </div>

</div>

<script>
"use strict";
var paused = false, last = null, tick = 0;
var ROW_STEP = 50, rowLimit = ROW_STEP;   // render in chunks, "load more" on demand
var openNotes = {};                        // request n -> note expanded?

/* ---- i18n ------------------------------------------------------------- */
var I18N = {
  en: {
    pause: "Pause", resume: "Resume", reset: "Reset",
    up: "up {t}", upstream: "upstream", model: "model", key: "key", avg: "avg {v}s",
    keySet: "set", keyMissing: "MISSING", keyClient: "client-supplied",
    secTokens: "Token spend", secData: "Where the data goes",
    secRecent: "Recent requests", secErrors: "Recent errors", secKey: "API key",
    cardRequests: "Requests", cardRequestsSub: "{ok} ok \u00b7 {fail} failed",
    cardTotal: "Total tokens", cardTotalSub: "input + output, what the relay bills",
    cardInput: "Input tokens", cardInputSub: "avg {n} / request",
    cardOutput: "Output tokens", cardOutputSub: "written by the model",
    cardSaved: "Avoided by trimming", cardSavedSub: "never sent, so never billed",
    cardPhantom: "Phantom (relay)", cardPhantomSub: "baseline {n} subtracted",
    cardOverhead: "Relay overhead", cardOverheadSub: "every request, inside input",
    cardTools: "Tool calls", cardToolsSub: "web {w} \u00b7 client {c}",
    cardDrops: "Dropped calls", dropsCheck: "check the log", dropsNone: "none",
    cardUpstream: "Upstream calls", retry: "{n} retry", retries: "{n} retries",
    legSystem: "System prompt", legTools: "Tool definitions",
    legHistory: "History", legOutput: "Model output",
    barTotal: "Total {n} tokens. This is what the proxy itself sent upstream.",
    barPhantom: " The relay's phantom {n} tokens are shown separately.",
    barNone: "No requests yet.",
    budgetLine: "Average request: <b>{s}</b> tokens sent (history window limit ~{l}). " +
                "History averaged <b>{h}</b> tokens kept out of <b>{r}</b> offered &mdash; {tail}",
    budgetTrim: "<b>{n}</b> tokens per request were trimmed away.",
    budgetNone: "nothing needed trimming yet.",
    stripIntro: "Each bar is one request's input (height = tokens). ",
    stripViolet: "Violet", stripMid: " = the request used a web tool, ",
    stripRed: "red", stripEnd: " = failed.",
    toolUsage: "Tool usage", toolsEmpty: "nothing yet", disk: "Disk",
    logChip: "log", dumpChip: "debug_dump", dumpsChip: "dumps",
    dumpsOn: "ON", dumpsOff: "off",
    thTime: "Time", thKind: "Kind", thMsgs: "Msgs", thInput: "Input",
    thOutput: "Output", thSec: "Sec", thTools: "Tools", thDrops: "Drops",
    thNote: "Note", pillStream: "stream", pillWeb: "web", pillFail: "fail",
    emptyTable: "No requests yet. Point Claude Code at this proxy " +
                "(set ANTHROPIC_BASE_URL to its address) and ask it something.",
    okWord: "ok", dash: "-",
    noteUpstreamException: "upstream connection failed",
    noteTruncatedSalvage: "truncated body salvaged",
    noteMore: "more", noteLess: "less",
    loadMore: "Show {n} more", showingRows: "showing {n} of {total}",
    statFailRate: "failure rate", statAllOk: "all ok",
    thKeySrc: "Key", keySrcClient: "client", keySrcConfig: "config",
    tokenPrompt: "This proxy requires an access token (X-Proxy-Token):",
    keyCurrent: "current:", notSet: "not set",
    pillSet: "set", pillMissing: "missing",
    pillClientNone: "none &mdash; client-supplied keys in use",
    keyPlaceholder: "sk-...", keySave: "Save key",
    keyHint: "Applied immediately, no restart needed. Saved to .env when the file " +
             "is writable, so it survives restarts; otherwise it applies until the " +
             "next restart.",
    keyEnterFirst: "Enter a key first.",
    keySaved: "Saved and applied -- survives restarts.",
    keyTemp: "Applied for this run only (.env is not writable here).",
    keyFailedPfx: "Failed: ", keyReqFail: "Request failed.",
    confirmReset: "Reset all counters? The recent-requests list will be cleared too."
  },
  zh: {
    pause: "暂停", resume: "继续", reset: "重置",
    up: "运行 {t}", upstream: "上游", model: "模型", key: "密钥", avg: "平均 {v}s",
    keySet: "已设置", keyMissing: "未设置", keyClient: "客户端提供",
    secTokens: "Token 消耗", secData: "数据都去了哪",
    secRecent: "最近请求", secErrors: "最近错误", secKey: "API 密钥",
    cardRequests: "请求数", cardRequestsSub: "{ok} 成功 \u00b7 {fail} 失败",
    cardTotal: "总 Token", cardTotalSub: "输入 + 输出，中转站计费的部分",
    cardInput: "输入 Token", cardInputSub: "平均 {n} / 次",
    cardOutput: "输出 Token", cardOutputSub: "模型生成的部分",
    cardSaved: "裁剪省下的", cardSavedSub: "未发送，不会计费",
    cardPhantom: "幻影 Token（中转站）", cardPhantomSub: "已减去基线 {n}",
    cardOverhead: "中转站开销", cardOverheadSub: "每次请求都加在输入里",
    cardTools: "工具调用", cardToolsSub: "网络工具 {w} \u00b7 客户端 {c}",
    cardDrops: "丢弃的调用", dropsCheck: "查看日志", dropsNone: "无",
    cardUpstream: "上游调用", retry: "{n} 次重试", retries: "{n} 次重试",
    legSystem: "系统提示词", legTools: "工具定义",
    legHistory: "历史消息", legOutput: "模型输出",
    barTotal: "共 {n} Token。这是代理实际发往上游的部分。",
    barPhantom: " 中转站的幻影 {n} Token 已单独列示。",
    barNone: "还没有请求。",
    budgetLine: "平均每次请求发送 <b>{s}</b> Token（历史上限约 {l}）。" +
                "历史保留平均 <b>{h}</b> Token / 次，原始 <b>{r}</b> Token &mdash; {tail}",
    budgetTrim: "每次请求裁掉了 <b>{n}</b> Token。",
    budgetNone: "暂无需裁剪。",
    stripIntro: "每根柱条是一个请求的输入（高度 = Token 数）。",
    stripViolet: "紫色", stripMid: " = 该请求用了网络工具，",
    stripRed: "红色", stripEnd: " = 失败。",
    toolUsage: "工具使用", toolsEmpty: "暂无数据", disk: "磁盘",
    logChip: "日志", dumpChip: "调试转储", dumpsChip: "转储",
    dumpsOn: "开", dumpsOff: "关",
    thTime: "时间", thKind: "类型", thMsgs: "消息", thInput: "输入",
    thOutput: "输出", thSec: "秒", thTools: "工具", thDrops: "丢弃",
    thNote: "备注", pillStream: "流式", pillWeb: "网络", pillFail: "失败",
    emptyTable: "还没有请求。把 Claude Code 指向本代理（设置 ANTHROPIC_BASE_URL" +
                " 为其地址）后随便问点什么。",
    okWord: "正常", dash: "-",
    noteUpstreamException: "上游连接失败",
    noteTruncatedSalvage: "已从截断的响应体中恢复",
    noteMore: "展开", noteLess: "收起",
    loadMore: "再显示 {n} 条", showingRows: "显示 {n} / {total}",
    statFailRate: "失败率", statAllOk: "全部正常",
    thKeySrc: "密钥来源", keySrcClient: "客户端", keySrcConfig: "配置",
    tokenPrompt: "此代理需要访问令牌（X-Proxy-Token）：",
    keyCurrent: "当前：", notSet: "未设置",
    pillSet: "已设置", pillMissing: "缺失",
    pillClientNone: "无 &mdash; 正在使用客户端密钥",
    keyPlaceholder: "sk-...", keySave: "保存密钥",
    keyHint: "立即生效，无需重启。.env 可写时会保存到其中，重启后依然有效；" +
             "否则仅本次运行有效。",
    keyEnterFirst: "先输入密钥。",
    keySaved: "已保存并生效 —— 重启后依然有效。",
    keyTemp: "仅本次运行有效（.env 不可写）。",
    keyFailedPfx: "失败：", keyReqFail: "请求失败。",
    confirmReset: "重置所有计数器？最近请求列表也会被清空。"
  }
};

var LANG = "en", langLocked = false;
try {
  LANG = localStorage.getItem("ccproxy_lang") || "en";
  langLocked = !!LANG;
} catch (e) {}
if (!I18N[LANG]) LANG = "en";

function t(k){
  var d = I18N[LANG];
  if (d && d[k] != null) return d[k];
  if (I18N.en[k] != null) return I18N.en[k];
  return k;
}
function tf(k, vars){
  return t(k).replace(/\{(\w+)\}/g, function(_, name){ return vars[name]; });
}
function setLang(l, save){
  if (!I18N[l]) return;
  LANG = l;
  if (save){
    langLocked = true;
    try { localStorage.setItem("ccproxy_lang", l); } catch (e) {}
  }
  applyStatic();
  if (last) render(last);
}
function applyStatic(){
  var els = document.querySelectorAll("[data-i18n]"), i;
  for (i = 0; i < els.length; i++) els[i].textContent = t(els[i].getAttribute("data-i18n"));
  el("pause").textContent = t(paused ? "resume" : "pause");
  el("reset").textContent = t("reset");
  el("lang").textContent = (LANG === "en") ? "中" : "EN";
  el("keyin").placeholder = t("keyPlaceholder");
  el("keysave").textContent = t("keySave");
  el("keyhint").textContent = t("keyHint");
}

function el(id){ return document.getElementById(id); }

function fmt(n){
  n = Number(n) || 0;
  if (n >= 1e9) return (n/1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n/1e6).toFixed(2) + "M";
  if (n >= 1e4) return (n/1e3).toFixed(1) + "k";
  return String(n);
}
function bytes(n){
  n = Number(n) || 0;
  if (n >= 1073741824) return (n/1073741824).toFixed(2) + " GB";
  if (n >= 1048576) return (n/1048576).toFixed(1) + " MB";
  if (n >= 1024) return (n/1024).toFixed(1) + " KB";
  return n + " B";
}
function uptime(s){
  s = Number(s) || 0;
  var d = Math.floor(s/86400), h = Math.floor(s%86400/3600),
      m = Math.floor(s%3600/60), x = Math.floor(s%60);
  if (d) return d + "d " + h + "h";
  if (h) return h + "h " + m + "m";
  if (m) return m + "m " + x + "s";
  return x + "s";
}
function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function sum(o){ var t2 = 0, k; for (k in o) if (o.hasOwnProperty(k)) t2 += Number(o[k]) || 0; return t2; }

/* A request/error note: proxy-generated notes carry a stable `note_code`
   we translate into the active language; the raw upstream error text (no
   code) is shown verbatim. For an upstream exception we append its detail.
   `full` picks the untruncated `note_full` over the short row `note`. */
function noteText(r, full){
  var code = r && r.note_code;
  var raw = (full && r && r.note_full) ? r.note_full : ((r && r.note) || "");
  if (code){
    var key = "note" + code.charAt(0).toUpperCase() + code.slice(1);
    var label = t(key);
    if (label !== key){
      if (code === "upstreamException"){
        var i = raw.indexOf("exception:");
        var detail = i >= 0 ? raw.slice(i + 10).trim() : raw;
        return detail ? label + ": " + detail : label;
      }
      return label;
    }
  }
  return raw;
}

/* The Note table cell. When the full text is longer than the short note
   (i.e. it was truncated for the row), add a toggle that reveals it. */
function noteCell(r){
  if (!r.note) return '<span class="muted">' + t("okWord") + "</span>";
  var open = !!openNotes[r.n];
  var shortTxt = noteText(r, false), fullTxt = noteText(r, true);
  var txt = open ? fullTxt : shortTxt;
  var hasMore = fullTxt.length > shortTxt.length;
  var html = '<div class="notewrap"><span class="notetxt' + (open ? " open" : "") +
             '">' + esc(txt) + "</span>";
  if (hasMore)
    html += '<button class="notebtn" data-note="' + r.n + '">' +
            t(open ? "noteLess" : "noteMore") + "</button>";
  return html + "</div>";
}

function card(k, v, sub, cls){
  return '<div class="card"><div class="k">' + esc(k) + '</div>' +
         '<div class="v ' + (cls || "") + '">' + v + '</div>' +
         (sub ? '<div class="s">' + sub + '</div>' : "") + '</div>';
}

function render(s){
  last = s;
  var reqs = s.total_reqs || 0, ok = s.ok || 0, fail = s.fail || 0;

  // first paint: follow config.json's ui_lang unless the user chose here
  if (!langLocked && s.ui_lang && String(s.ui_lang).toLowerCase().indexOf("zh") === 0
      && LANG !== "zh") setLang("zh", false);

  el("dot").className = "dot" + ((s.key_set || s.client_key_passthrough) ? "" : " off");
  el("uptime").textContent = "| " + tf("up", {t: uptime(s.uptime_s + tick)});
  el("meta").innerHTML =
    "<span>" + t("upstream") + " <b>" + esc(s.upstream) + "</b></span>" +
    "<span>" + t("model") + " <b>" + esc(s.model) + "</b></span>" +
    "<span>" + t("key") + " <b>" + (s.key_set ? t("keySet")
        : (s.client_key_passthrough ? t("keyClient") : t("keyMissing"))) + "</b></span>" +
    "<span>" + tf("avg", {v: reqs ? (Number(s.duration||0)/reqs).toFixed(1) : "0"}) + "</span>";

  var avgIn = reqs ? Math.round((s.in_tok||0)/reqs) : 0;
  var totalTok = (s.in_tok||0) + (s.out_tok||0);
  el("cards").innerHTML =
    card(t("cardRequests"), fmt(reqs), tf("cardRequestsSub", {ok: ok, fail: fail}),
         fail ? "" : "good") +
    card(t("cardTotal"), fmt(totalTok), t("cardTotalSub"), "accent") +
    card(t("cardInput"), fmt(s.in_tok), tf("cardInputSub", {n: fmt(avgIn)}), "accent") +
    card(t("cardOutput"), fmt(s.out_tok), t("cardOutputSub"), "violet") +
    card(t("cardSaved"), fmt(s.saved_tok), t("cardSavedSub"), "good") +
    (s.phantom_tok > 0
      ? card(t("cardPhantom"), fmt(s.phantom_tok),
             tf("cardPhantomSub", {n: fmt(s.usage_baseline_tokens)}), "warn")
      : card(t("cardOverhead"), "~10.4k", t("cardOverheadSub"), "warn")) +
    card(t("cardTools"), fmt(sum(s.tool_uses) + sum(s.server_tools)),
         tf("cardToolsSub", {w: sum(s.server_tools), c: sum(s.tool_uses)})) +
    card(t("cardDrops"), fmt(s.drops_total),
         s.drops_total ? t("dropsCheck") : t("dropsNone"),
         s.drops_total ? "bad" : "good") +
    card(t("cardUpstream"), fmt(s.upstream_calls),
         (s.retries_total||0) === 1 ? tf("retry", {n: s.retries_total})
                                    : tf("retries", {n: s.retries_total||0}),
         (s.retries_total ? "warn" : ""));

  // ---- where the data goes ----
  var parts = [
    [t("legSystem"), s.sys_tok, "#5b9dff"],
    [t("legTools"), s.tools_tok, "#a78bfa"],
    [t("legHistory"), s.hist_tok, "#3ecf8e"],
    [t("legOutput"), s.out_tok, "#ffb454"]
  ];
  var tot = 0, i;
  for (i = 0; i < parts.length; i++) tot += Number(parts[i][1]) || 0;
  var bar = "", leg = "";
  for (i = 0; i < parts.length; i++){
    var pct = tot ? (Number(parts[i][1])||0) * 100 / tot : 0;
    if (pct > 0.4) bar += '<span style="width:' + pct.toFixed(2) + '%;background:' + parts[i][2] + '" ' +
                         'title="' + esc(parts[i][0]) + ': ' + fmt(parts[i][1]) + '"></span>';
    leg += '<div><i style="background:' + parts[i][2] + '"></i>' + esc(parts[i][0]) +
           ' <b>' + fmt(parts[i][1]) + '</b> <span class="m">(' + pct.toFixed(1) + '%)</span></div>';
  }
  if (!tot) bar = '<span style="width:100%;background:var(--panel2)"></span>';
  el("bar").innerHTML = bar;
  el("legend").innerHTML = leg;
  el("barhint").textContent = tot
    ? tf("barTotal", {n: fmt(tot)})
    : t("barNone");
  if (tot && s.usage_baseline_tokens > 0)
    el("barhint").textContent += tf("barPhantom", {n: fmt(s.usage_baseline_tokens)});

  // ---- how much of the budget each request actually used ----
  var budgetEl = el("budget");
  if (reqs && s.max_history_chars > 0){
    var sentAvg = Math.round(((s.sys_tok||0)+(s.tools_tok||0)+(s.hist_tok||0))/reqs);
    var histAvg = Math.round((s.hist_tok||0)/reqs);
    var rawAvg  = Math.round((s.raw_hist_tok||0)/reqs);
    var limitTok = Math.round(s.max_history_chars/4);
    var tail = rawAvg > histAvg ? tf("budgetTrim", {n: fmt(rawAvg - histAvg)})
                                : t("budgetNone");
    budgetEl.innerHTML = tf("budgetLine", {s: fmt(sentAvg), l: fmt(limitTok),
                                           h: fmt(histAvg), r: fmt(rawAvg), tail: tail});
  } else if (budgetEl) {
    budgetEl.innerHTML = "";
  }

  el("striphint").innerHTML = t("stripIntro") +
      '<span style="color:var(--violet)">' + t("stripViolet") + '</span>' + t("stripMid") +
      '<span style="color:var(--bad)">' + t("stripRed") + '</span>' + t("stripEnd");

  var rec = (s.recent || []).slice(0, 60).reverse();
  var mx = 1;
  for (i = 0; i < rec.length; i++) mx = Math.max(mx, Number(rec[i].in_tok)||0);
  var st = "";
  for (i = 0; i < rec.length; i++){
    var r = rec[i], h = Math.max(2, Math.round((Number(r.in_tok)||0) * 100 / mx));
    var cls = !r.ok ? "bad" : (Number(r.server_tools) ? "srv" : "");
    st += '<div class="' + cls + '" style="height:' + h + '%;" title="#' + r.n + " " +
          esc(r.ts) + " - " + fmt(r.in_tok) + " in / " + fmt(r.out_tok) + ' out"></div>';
  }
  el("strip").innerHTML = st || '<div class="muted" style="height:auto">' + t("barNone") + '</div>';

  // ---- tools ----
  var tc = "", name;
  var all = {};
  for (name in s.tool_uses) if (s.tool_uses.hasOwnProperty(name)) all[name] = s.tool_uses[name];
  for (name in s.server_tools) if (s.server_tools.hasOwnProperty(name))
    all[name] = (all[name]||0) + s.server_tools[name];
  var keys = Object.keys(all).sort(function(a,b){ return all[b]-all[a]; });
  for (i = 0; i < keys.length; i++)
    tc += '<span class="chip">' + esc(keys[i]) + ' <b>' + fmt(all[keys[i]]) + '</b></span>';
  el("tools").innerHTML = tc || '<span class="muted">' + t("toolsEmpty") + '</span>';

  el("disk").innerHTML =
    '<span class="chip">' + t("logChip") + ' <b>' + bytes(s.disk.log_bytes) + '</b></span>' +
    '<span class="chip">' + t("dumpChip") + ' <b>' + bytes(s.disk.dump_bytes) + '</b> ' +
    '<span class="muted">(' + s.disk.dump_files + ')</span></span>' +
    '<span class="chip">' + t("dumpsChip") + ' ' +
    (s.dump_requests ? '<b style="color:var(--warn)">' + t("dumpsOn") + '</b>'
                     : '<b>' + t("dumpsOff") + '</b>') + '</span>';

  // ---- status summary ----
  var reqTotal = reqs, failTotal = fail;
  var sr = "";
  if (reqTotal){
    var rate = (failTotal * 100 / reqTotal);
    sr += '<span class="chip">' + t("statFailRate") + ' <b style="color:var(--' +
          (failTotal ? "bad" : "good") + ')">' + rate.toFixed(1) + '%</b></span>';
    var sc = s.status_counts || {}, scKeys = Object.keys(sc).sort();
    if (scKeys.length)
      for (i = 0; i < scKeys.length; i++)
        sr += '<span class="chip">' + esc(scKeys[i]) +
              ' <b style="color:var(--bad)">' + fmt(sc[scKeys[i]]) + '</b></span>';
    else
      sr += '<span class="chip muted">' + t("statAllOk") + '</span>';
  }
  el("statrow").innerHTML = sr;

  // ---- table (rendered in chunks; "load more" extends rowLimit) ----
  var rows = "";
  var list = (s.recent || []);
  if (rowLimit > list.length) rowLimit = Math.max(ROW_STEP, list.length);
  var shown = Math.min(rowLimit, list.length);
  for (i = 0; i < shown; i++){
    var r = list[i];
    var pills = "";
    if (!r.ok) pills += '<span class="pill no">' + t("pillFail") + " " + r.status + "</span> ";
    if (r.stream) pills += '<span class="pill st">' + t("pillStream") + "</span> ";
    if (Number(r.server_tools)) pills += '<span class="pill dr">' + t("pillWeb") + "</span> ";
    var nm = (r.names || []).join(", ");
    rows += "<tr>" +
      "<td>" + r.n + "</td>" +
      '<td title="' + esc(r.ts_full || r.ts) + '">' + esc(r.ts) + "</td>" +
      "<td>" + (pills || '<span class="muted">' + t("dash") + "</span>") + "</td>" +
      '<td class="num">' + r.client_msgs + "&rarr;" + r.sent_msgs + "</td>" +
      '<td class="num">' + fmt(r.in_tok) + "</td>" +
      '<td class="num">' + fmt(r.out_tok) + "</td>" +
      '<td class="num">' + r.dur + "</td>" +
      "<td>" + (nm ? esc(nm) : '<span class="muted">' + t("dash") + "</span>") + "</td>" +
      "<td>" + (r.key_src ? (r.key_src === "client" ? t("keySrcClient") : t("keySrcConfig"))
                         : '<span class="muted">' + t("dash") + "</span>") + "</td>" +
      '<td class="num">' + (r.drops ? '<span class="pill dr">' + r.drops + "</span>" : t("dash")) + "</td>" +
      '<td class="note">' + noteCell(r) + "</td>" +
      "</tr>";
  }
  el("rows").innerHTML = rows ||
    '<tr><td colspan="11" class="empty">' + t("emptyTable") + "</td></tr>";

  // "load more" footer
  var moreEl = el("rowsmore");
  if (list.length > shown){
    var remain = list.length - shown, step = Math.min(ROW_STEP, remain);
    moreEl.innerHTML = '<button id="loadmore">' + tf("loadMore", {n: step}) + "</button> " +
                       '<span class="muted">' + tf("showingRows", {n: shown, total: list.length}) + "</span>";
    el("loadmore").onclick = function(){ rowLimit += ROW_STEP; if (last) render(last); };
  } else if (list.length){
    moreEl.innerHTML = '<span class="muted">' + tf("showingRows", {n: shown, total: list.length}) + "</span>";
  } else {
    moreEl.innerHTML = "";
  }

  // ---- errors ----
  var errs = s.errors || [];
  var eb = el("errbox");
  if (errs.length){
    var eh = '<h2>' + t("secErrors") + '</h2><div class="panel err errlist">';
    for (i = 0; i < errs.length; i++){
      var e = errs[i], shortE = esc(noteText(e, false)), fullE = esc(noteText(e, true));
      var expandable = fullE.length > shortE.length;
      eh += '<div class="errrow' + (expandable ? " can" : "") + '" data-err="' + i + '">#' +
            e.n + " " + '<span title="' + esc(e.ts_full || e.ts) + '">' + esc(e.ts) + "</span>" +
            ' <span class="pill no">' + e.status + "</span> " + shortE +
            (expandable ? '<div class="d">' + fullE + "</div>" : "") + "</div>";
    }
    eb.innerHTML = eh + "</div>";
  } else {
    eb.innerHTML = "";
  }
}

/* fetch wrapper: attaches the proxy access token (CCPROXY_TOKEN) when one
   is stored; on 401 asks for it once per page load, then leaves the caller
   to see the error */
var tokenPrompted = false;
function ffetch(url, opts){
  opts = opts || {};
  var tok = null;
  try { tok = localStorage.getItem("ccproxy_token"); } catch (e) {}
  if (tok){
    opts.headers = Object.assign({}, opts.headers, {"X-Proxy-Token": tok});
  }
  return fetch(url, opts).then(function(r){
    if (r.status === 401 && !tokenPrompted){
      tokenPrompted = true;
      var v = prompt(t("tokenPrompt"));
      if (v){
        try { localStorage.setItem("ccproxy_token", v); } catch (e) {}
        opts.headers = Object.assign({}, opts.headers, {"X-Proxy-Token": v});
        return fetch(url, opts);
      }
      try { localStorage.removeItem("ccproxy_token"); } catch (e) {}
    }
    return r;
  });
}

function poll(){
  ffetch("/stats.json", {cache: "no-store"})
    .then(function(r){ return r.json(); })
    .then(function(s){ render(s); tick = 0; })
    .catch(function(){ el("dot").className = "dot off"; });
}

el("lang").onclick = function(){ setLang(LANG === "en" ? "zh" : "en", true); };
el("pause").onclick = function(){
  paused = !paused;
  this.textContent = t(paused ? "resume" : "pause");
};
el("reset").onclick = function(){
  if (!confirm(t("confirmReset"))) return;
  ffetch("/stats/reset", {method: "POST"}).then(poll);
};

/* delegated clicks: expand/collapse a request note (survives re-render
   because openNotes is keyed by request #) ... */
el("rows").addEventListener("click", function(ev){
  var b = ev.target.closest ? ev.target.closest(".notebtn") : null;
  if (!b) return;
  var n = b.getAttribute("data-note");
  openNotes[n] = !openNotes[n];
  if (last) render(last);
});
/* ... and expand an error line in place */
el("errbox").addEventListener("click", function(ev){
  var row = ev.target.closest ? ev.target.closest(".errrow.can") : null;
  if (row) row.classList.toggle("open");
});

function loadKey(){
  ffetch("/api/key", {cache: "no-store"})
    .then(function(r){ return r.json(); })
    .then(function(s){
      el("keycur").textContent = s.key_set ? s.masked : t("notSet");
      el("keypill").innerHTML = s.key_set
        ? '<span class="pill ok">' + t("pillSet") + "</span>"
        : (s.passthrough
            ? '<span class="pill dr">' + t("pillClientNone") + "</span>"
            : '<span class="pill no">' + t("pillMissing") + "</span>");
    });
}
el("keysave").onclick = function(){
  var v = el("keyin").value.trim();
  if (!v){ el("keyhint").textContent = t("keyEnterFirst"); return; }
  this.disabled = true;
  ffetch("/api/key", {method: "POST", headers: {"Content-Type": "application/json"},
                      body: JSON.stringify({api_key: v})})
    .then(function(r){ return r.json().then(function(j){ return {ok: r.ok, j: j}; }); })
    .then(function(res){
      el("keyin").value = "";
      el("keyhint").textContent = res.ok
        ? (res.j.persisted ? t("keySaved") : t("keyTemp"))
        : t("keyFailedPfx") + (res.j.error || res.j.status);
      loadKey(); poll();
    })
    .catch(function(){ el("keyhint").textContent = t("keyReqFail"); })
    .finally(function(){ el("keysave").disabled = false; });
};

applyStatic();
loadKey();
poll();

/* polling backs off when the tab is hidden: no network while in the
   background, and an immediate refresh the moment it becomes visible */
function hidden(){
  try { return document.hidden; } catch (e) { return false; }
}
document.addEventListener("visibilitychange", function(){
  if (!hidden() && !paused){ tick = 0; poll(); }
});
setInterval(function(){
  if (hidden()) return;            // asleep in the background
  tick++;
  if (!paused) poll();
  else if (last) render(last);     // keep the uptime ticking
}, 2000);
</script>
</body>
</html>
"""
