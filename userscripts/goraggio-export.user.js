// ==UserScript==
// @name         GORAGGIO iPhone HTML Export
// @namespace    https://github.com/keiyu-per/data-fetcher
// @version      0.1.0
// @description  Export rendered GORAGGIO HTML when launched from the data-fetcher dashboard
// @match        https://daidata.goraggio.com/*
// @run-at       document-idle
// @inject-into   content
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  // Only activate for an explicit export launch on an approved shop's slot list.
  var match = /^\/(100831|100883|100983)\/all_list\/?$/.exec(location.pathname);
  if (!match || location.hash !== "#df-export" ||
      new URLSearchParams(location.search).get("ps") !== "S") {
    return;
  }

  var shopId = match[1];
  var shopNames = {
    "100831": "ピーアーク北千住SSS",
    "100883": "ピーアーク竹ノ塚スタジオ",
    "100983": "コンサートホール北千住"
  };
  var filePrefix = "goraggio_" + shopId + "_";
  var attempts = 0;
  var lastCount = -1;
  var stableChecks = 0;
  var autoStarted = false;
  var maxChecks = 24; // Twelve seconds of checks; no repeated network requests.

  var panel = document.createElement("section");
  panel.id = "data-fetcher-panel";
  panel.setAttribute("role", "status");
  panel.style.cssText = "position:fixed;z-index:2147483647;left:12px;right:12px;bottom:16px;max-width:560px;margin:auto;padding:16px;border-radius:14px;background:#101827;color:#f7faff;font:14px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;box-shadow:0 5px 24px #0007;border:1px solid #3b536b";
  panel.innerHTML = '<div style="font-weight:700;font-size:16px">HTML取得ツール</div>' +
    '<div id="df-progress" style="margin:8px 0 12px">表示データを確認しています…</div>' +
    '<button id="df-save" type="button" style="width:100%;padding:12px;border:0;border-radius:9px;background:#4ce0ad;color:#102322;font-weight:700">現在のHTMLを保存</button>' +
    '<button id="df-close" type="button" style="margin-top:10px;padding:6px 12px;background:none;border:0;color:#cfdae8">閉じる</button>';
  (document.body || document.documentElement).appendChild(panel);

  var progress = panel.querySelector("#df-progress");
  var save = panel.querySelector("#df-save");
  var close = panel.querySelector("#df-close");
  close.addEventListener("click", function () { panel.remove(); });

  function rowCount() {
    var anchors = document.querySelectorAll('a[href*="detail?unit="]');
    var units = new Set();
    for (var i = 0; i < anchors.length; i += 1) {
      try {
        var url = new URL(anchors[i].getAttribute("href"), location.href);
        var unit = url.searchParams.get("unit");
        if (unit && /^\d+$/.test(unit)) units.add(unit);
      } catch (_) { /* Ignore malformed links. */ }
    }
    return units.size;
  }

  function expectedCount() {
    var source = document.body ? document.body.innerText : "";
    var matchCount = source.match(/(?:Slot\s*)?スロット\s*[|｜]?\s*(\d[\d,]*)\s*台/);
    return matchCount ? Number(matchCount[1].replace(/,/g, "")) : null;
  }

  function saveHtml(isAutomatic) {
    // Snapshot the current DOM rather than re-fetching the site from another host.
    var clone = document.documentElement.cloneNode(true);
    var overlay = clone.querySelector("#data-fetcher-panel");
    if (overlay) overlay.remove();
    var html = "<!DOCTYPE html>\n" + clone.outerHTML;
    var timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    var filename = filePrefix + timestamp + ".html";
    var blob = new Blob([html], { type: "text/html;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.style.display = "none";
    document.body.appendChild(link);
    try {
      link.click();
      progress.textContent = (isAutomatic ? "自動保存を試行しました。" : "保存を開始しました。") +
        " Safariのダウンロード一覧で「" + filename + "」を確認してください。表示されない場合は下のボタンから再試行してください。";
    } finally {
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 20000);
    }
  }

  save.addEventListener("click", function () { saveHtml(false); });
  function check() {
    if (!document.body || !document.contains(panel)) return;
    var rows = rowCount();
    var expected = expectedCount();
    attempts += 1;
    stableChecks = rows > 0 && rows === lastCount ? stableChecks + 1 : 0;
    lastCount = rows;
    progress.textContent = shopNames[shopId] + "：確認できた台番号 " + rows + "件" +
      (expected ? " / 表示台数 " + expected + "台" : "（総台数は未判定）") + "。";
    var complete = expected !== null && expected > 0 && rows === expected;
    if (complete && stableChecks >= 2 && !autoStarted) {
      autoStarted = true;
      saveHtml(true);
      return;
    }
    if (attempts < maxChecks && !autoStarted) {
      setTimeout(check, 500);
      return;
    }
    if (!autoStarted) {
      progress.textContent += " 全台分の一致を確認できなかったため、自動保存は行っていません。ページの表示と件数を確認し、必要なら手動保存してください。";
    }
  }
  setTimeout(check, 500);
})();
