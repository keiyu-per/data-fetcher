// ==UserScript==
// @name         GORAGGIO iPhone HTML Export
// @namespace    https://github.com/keiyu-per/data-fetcher
// @version      0.2.1
// @description  Save displayed lists and retrieve selected machine detail HTML in Safari
// @match        https://daidata.goraggio.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var shopNames = {
    "100831": "ピーアーク北千住SSS",
    "100883": "ピーアーク竹ノ塚スタジオ",
    "100983": "コンサートホール北千住"
  };
  var matched = /^\/(100831|100883|100983)\/(all_list|detail)\/?$/.exec(location.pathname);
  if (!matched || !location.hash.startsWith("#df-export")) return;
  var shopId = matched[1];
  var mode = matched[2];
  var BATCH_SIZE = 25;
  var INTERVAL_MS = 2000;
  var stopped = false;
  var working = false;
  var nextIndex = 0;
  var selectionKey = "";
  var lastBundle = null;
  var controller = null;

  var panel = document.createElement("section");
  panel.id = "data-fetcher-panel";
  panel.style.cssText = "position:fixed;z-index:2147483646;left:10px;right:10px;bottom:10px;max-width:560px;margin:auto;padding:16px;max-height:72vh;overflow:auto;border-radius:14px;background:#101827;color:#f7faff;font:14px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;box-shadow:0 6px 28px #0009;border:1px solid #3b536b";
  panel.innerHTML =
    '<div style="font-weight:800;font-size:17px">GORAGGIO HTML取得 v0.2</div>' +
    '<div id="df-status" style="margin:8px 0 12px" aria-live="polite">読み込み中…</div>' +
    '<div id="df-controls"></div>' +
    '<button id="df-close" type="button" style="margin-top:10px;background:none;border:0;color:#cfdae8;padding:8px">閉じる</button>';
  (document.body || document.documentElement).appendChild(panel);
  var status = panel.querySelector("#df-status");
  var controls = panel.querySelector("#df-controls");
  var close = panel.querySelector("#df-close");
  close.addEventListener("click", function () {
    if (working) {
      status.textContent = "取得中は閉じられません。「中止」を押してください。";
      return;
    }
    panel.remove();
  });

  function button(label, handler, secondary) {
    var el = document.createElement("button");
    el.type = "button";
    el.textContent = label;
    el.style.cssText = "display:block;width:100%;padding:12px;margin:8px 0;border:1px solid " +
      (secondary ? "#5d7893" : "#4ce0ad") + ";border-radius:9px;background:" +
      (secondary ? "#1b2b41;color:#fff" : "#4ce0ad;color:#102322") + ";font-weight:750";
    el.addEventListener("click", handler);
    controls.appendChild(el);
    return el;
  }

  function snapshot() {
    var clone = document.documentElement.cloneNode(true);
    var overlay = clone.querySelector("#data-fetcher-panel");
    if (overlay) overlay.remove();
    // Remove session/CSRF elements, but retain inline scripts that might contain chart data.
    clone.querySelectorAll('meta[name="csrf-token"],input[name="_token"],input[name="csrf_token"]').forEach(function (el) { el.remove(); });
    return "<!DOCTYPE html>\n" + clone.outerHTML;
  }

  function cleanFetchedHtml(html) {
    return html
      .replace(/<meta\b[^>]*name=["']csrf-token["'][^>]*>/gi, "")
      .replace(/<input\b[^>]*name=["'](?:_token|csrf_token)["'][^>]*>/gi, "");
  }

  function download(text, filename, type) {
    var blob = new Blob([text], { type: type || "application/json;charset=utf-8" });
    var href = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = href;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(href); }, 30000);
  }

  function dateString() {
    return new Date().toISOString().replace(/[:.]/g, "-");
  }

  function getUnit(a) {
    try {
      var u = new URL(a.href, location.href);
      if (u.origin !== location.origin ||
          !new RegExp("^/" + shopId + "/detail/?$").test(u.pathname)) return null;
      var unit = u.searchParams.get("unit");
      return unit && /^\d+$/.test(unit) ? { unit: unit, url: u } : null;
    } catch (_) { return null; }
  }

  function listRows() {
    var out = [];
    var seen = new Set();
    document.querySelectorAll("table tbody tr").forEach(function (tr) {
      var a = tr.querySelector('a[href*="detail?unit="]');
      if (!a) return;
      var detail = getUnit(a);
      if (!detail || seen.has(detail.unit)) return;
      var cells = Array.from(tr.querySelectorAll("td")).map(function (td) { return td.textContent.trim(); });
      if (cells.length < 4) return;
      var selectedDay = new URLSearchParams(location.search).get("hist_num");
      if (!selectedDay) {
        var dropdown = document.querySelector('select[name="hist_num"]');
        if (dropdown) selectedDay = dropdown.value;
      }
      if (selectedDay && /^\d+$/.test(selectedDay) && selectedDay !== "0") {
        detail.url.searchParams.set("hist_num", selectedDay);
      }
      out.push({
        unit: detail.unit, detail_url: detail.url.href,
        model: cells[3] || "", row_cells: cells
      });
      seen.add(detail.unit);
    });
    return out;
  }

  // Detail pages are obtained by a normal, same-origin, credentialed browser request.
  // Stop at the first HTTP denial or consent page. Never solve/skip consent or CAPTCHA.
  async function fetchDetail(item) {
    var u = new URL(item.detail_url);
    if (u.origin !== location.origin ||
        u.pathname !== "/" + shopId + "/detail" ||
        u.searchParams.get("unit") !== item.unit) throw Error("取得先URLが想定外です");
    controller = new AbortController();
    var response = await fetch(u.href, {
      method: "GET", credentials: "same-origin", redirect: "follow",
      headers: { "Accept": "text/html,application/xhtml+xml" },
      signal: controller.signal
    });
    if (!response.ok) throw Error("HTTP " + response.status + "。自動取得を停止しました");
    var finalUrl = new URL(response.url);
    if (finalUrl.origin !== location.origin ||
        finalUrl.pathname !== u.pathname) throw Error("別ページに移動したため停止しました");
    if (!(response.headers.get("content-type") || "").includes("text/html")) {
      throw Error("HTML以外の応答を受信したため停止しました");
    }
    var html = await response.text();
    if (html.length > 2000000) throw Error("ページサイズが大きすぎるため停止しました");
    var dom = new DOMParser().parseFromString(html, "text/html");
    var content = dom.body ? dom.body.textContent || "" : "";
    if (/規約に同意する|利用規約に同意する|captcha|access denied|403 forbidden/i.test(content)) {
      throw Error("同意・認証・制限ページを検出したため停止しました");
    }
    if (!/スタート|ゲーム数|BB|RB|ART|AT|大当|当たり|回数/.test(content)) {
      throw Error("詳細データを確認できません。HTML形式が変わった可能性があります");
    }
    return {
      unit: item.unit, model: item.model, url: u.href,
      captured_at: new Date().toISOString(), html: cleanFetchedHtml(html)
    };
  }

  function makeBundle(items, attemptedFrom, attemptedTo) {
    return {
      format: "goraggio-detail-bundle/v1", shop_id: shopId, shop_name: shopNames[shopId],
      source_url: location.href, captured_at: new Date().toISOString(),
      target_date_label: (document.querySelector('select[name="hist_num"] option:checked') || {}).textContent || null,
      list_html: cleanFetchedHtml(snapshot()),
      requested_units: items.map(function (x) { return x.unit; }),
      batch_start: attemptedFrom, batch_end: attemptedTo,
      details: [], errors: []
    };
  }

  if (mode === "detail") {
    var oneUnit = new URLSearchParams(location.search).get("unit");
    status.textContent = shopNames[shopId] + " / 台番号 " + (oneUnit || "?") +
      "。詳細HTMLを単体で保存できます。";
    button("この台の詳細HTMLを保存", function () {
      download(snapshot(), "goraggio_" + shopId + "_unit_" + (oneUnit || "unknown") +
        "_" + dateString() + ".html", "text/html;charset=utf-8");
      status.textContent = "保存を試行しました。Safariのダウンロード一覧を確認してください。";
    });
    return;
  }

  var rows = listRows();
  var modelSelector = document.createElement("select");
  modelSelector.style.cssText = "width:100%;padding:12px;background:#1b2b41;color:#fff;border:1px solid #5d7893;border-radius:9px;font-size:15px;margin-bottom:6px";
  var allOption = document.createElement("option");
  allOption.value = "__all__";
  allOption.textContent = "全機種（25台ごとに保存）";
  modelSelector.appendChild(allOption);
  var modelCounts = {};
  rows.forEach(function (r) {
    modelCounts[r.model] = (modelCounts[r.model] || 0) + 1;
  });
  Object.keys(modelCounts).sort(function (a, b) { return a.localeCompare(b, "ja"); }).forEach(function (name) {
    if (!name) return;
    var option = document.createElement("option");
    option.value = name;
    option.textContent = name + "（" + modelCounts[name] + "台）";
    modelSelector.appendChild(option);
  });
  controls.appendChild(modelSelector);
  if (modelCounts["L東京喰種"]) modelSelector.value = "L東京喰種";

  function selectedRows() {
    return modelSelector.value === "__all__" ? rows :
      rows.filter(function (r) { return r.model === modelSelector.value; });
  }

  status.textContent = shopNames[shopId] + "：一覧 " + rows.length +
    "台。詳細は未取得です。対象機種を選択してください。";
  button("一覧HTMLを保存", function () {
    download(snapshot(), "goraggio_" + shopId + "_all_list_" + dateString() + ".html", "text/html;charset=utf-8");
    status.textContent = "一覧HTMLの保存を試行しました。";
  }, true);

  var unitSelector = document.createElement("select");
  unitSelector.style.cssText = modelSelector.style.cssText;
  controls.appendChild(unitSelector);
  function updateUnitSelector() {
    var previous = unitSelector.value;
    unitSelector.replaceChildren();
    selectedRows().forEach(function (r) {
      var option = document.createElement("option");
      option.value = r.unit;
      option.textContent = "台番号 " + r.unit + " / " + r.model;
      unitSelector.appendChild(option);
    });
    if (selectedRows().some(function (r) { return r.unit === previous; })) unitSelector.value = previous;
  }
  updateUnitSelector();
  button("選択した1台をSafariで開く（手動取得用）", function () {
    var row = rows.find(function (r) { return r.unit === unitSelector.value; });
    if (!row) return;
    location.assign(row.detail_url + "#df-export");
  }, true);

  var runButton = button("選択機種の詳細を取得（最大25台）", function () {
    runBatch().catch(function (e) {
      status.textContent = "予期しないエラー：" + e.message;
      working = false;
      modelSelector.disabled = false;
      runButton.disabled = false;
      if (lastBundle) downloadButton.disabled = false;
    });
  });
  var stopButton = button("取得を中止", function () {
    stopped = true;
    if (controller) controller.abort();
    status.textContent = "中止処理中です…";
  }, true);
  stopButton.disabled = true;
  var downloadButton = button("取得済みの詳細データを保存", function () {
    if (!lastBundle) return;
    download(JSON.stringify(lastBundle), "goraggio_" + shopId + "_details_" +
      dateString() + ".json");
    status.textContent = "詳細データの保存を試行しました。Safariのダウンロード一覧を確認してください。";
  }, true);
  downloadButton.disabled = true;

  modelSelector.addEventListener("change", function () {
    nextIndex = 0;
    selectionKey = "";
    updateUnitSelector();
    status.textContent = "対象：" + selectedRows().length + "台。25台ずつ取得します。";
  });

  async function runBatch() {
    if (working) return;
    var selected = selectedRows();
    if (!selected.length) {
      status.textContent = "対象台が見つかりません。";
      return;
    }
    var key = modelSelector.value + "|" + (document.querySelector('select[name="hist_num"]') || {}).value;
    if (selectionKey !== key) {
      selectionKey = key;
      nextIndex = 0;
    }
    if (nextIndex >= selected.length) nextIndex = 0;
    var start = nextIndex;
    var end = Math.min(selected.length, start + BATCH_SIZE);
    var chunk = selected.slice(start, end);
    var bundle = makeBundle(chunk, start, end);
    lastBundle = bundle;
    working = true;
    stopped = false;
    runButton.disabled = true;
    stopButton.disabled = false;
    downloadButton.disabled = true;
    modelSelector.disabled = true;
    try {
      for (var i = 0; i < chunk.length; i++) {
        if (stopped) break;
        if (i > 0) await new Promise(function (resolve) { setTimeout(resolve, INTERVAL_MS); });
        if (stopped) break;
        if (document.visibilityState === "hidden") {
          throw Error("Safariが非表示になりました。画面を開いたまま再実行してください");
        }
        status.textContent = "詳細取得中：" + (start + i + 1) + "/" + selected.length +
          "台（保存可能：" + bundle.details.length + "台）";
        try {
          var data = await fetchDetail(chunk[i]);
          bundle.details.push(data);
          nextIndex = start + i + 1;
        } catch (e) {
          bundle.errors.push({ unit: chunk[i].unit, error: e.message || String(e) });
          status.textContent = "停止：" + (e.message || String(e)) +
            "。取得済みデータは下のボタンで保存できます。";
          stopped = true;
          break;
        }
      }
    } finally {
      working = false;
      controller = null;
      modelSelector.disabled = false;
      runButton.disabled = false;
      stopButton.disabled = true;
      downloadButton.disabled = bundle.details.length === 0 && bundle.errors.length === 0;
      if (!stopped) {
        status.textContent = "詳細 " + bundle.details.length + "台取得。" +
          (nextIndex < selected.length ? " 次の25台に進むにはもう一度取得ボタンを押してください。" :
            " 選択した台の取得が完了しました。") +
          " 下の保存ボタンを押してください。";
      }
      if (bundle.details.length || bundle.errors.length) {
        // Automatic downloads may be blocked by Safari after an awaited request.
        // Always leave the explicit download button enabled.
        try {
          download(JSON.stringify(bundle), "goraggio_" + shopId + "_details_" +
            dateString() + ".json");
        } catch (_) {
          status.textContent += " 自動ダウンロードに失敗したため保存ボタンを押してください。";
        }
      }
    }
  }
})();
