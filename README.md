# Data Fetcher — iPhone Safari向けGORAGGIO HTML取得

**目的**：iPhoneだけで店舗と機種を選択し、GORAGGIOの台番号一覧および選択機種の各台詳細HTMLをローカルに保存・解析する。

[Webアプリ](https://keiyu-per.github.io/data-fetcher/) | [仕様書](SPECIFICATION.md) | [変更管理台帳](CHANGE_MANAGEMENT.md) | [変更履歴](CHANGELOG.md) | [ChatGPT半自動プロジェクト設定](CHATGPT_PROJECT_SETUP.md) | [iPhoneでの詳細取得手順](DETAIL_CAPTURE.md) | [セットアップ](IPHONE_SETUP.md)

## 現在の実装（Userscripts v0.2.2）

| 機能 | 状態 |
| --- | --- |
| GitHub Pagesの店舗選択UI（3店舗） | 実装済み・Safari表示確認済み |
| Safari Userscriptsによる一覧HTML保存 | 実装済み・実機保存確認済み |
| 全台一覧の451行解析 | 2026-10-13の実ファイルで検証済み（公式総台数との照合は未了） |
| マイジャグラーV機種別 `unit_list` HTML保存（28台） | 2026-10-13の実ファイルで保存確認済み |
| `unit_list` のPython構造化解析 | 未実装 |
| 選択機種の詳細ページ取得（同一サイトの通常リクエスト） | 実装済み・実機未検証 |
| 25台単位の詳細JSON保存・取得中断 | 実装済み・実機未検証 |
| 選択1台の詳細ページ移動・手動HTML保存 | 実装済み・実機未検証 |
| 一覧と詳細の結合CSV/JSON・欠損率集計 | 実装済み・オフライン自動テスト成功 |
| 詳細のCZ/AT履歴・グラフ検証、設定推定 | 未実装 |

GitHub Actionsからの直接HTTP取得は **HTTP 403** のため、通常運用には使用しません。従来の `fetch_goraggio.py` と `GORAGGIO HTML retrieval test` は診断目的で保持し、手動起動のみです。通常の品質確認は `Offline data-fetcher validation` が行います。

## 画面遷移（2026-10-13更新）

店舗を選択してから「店舗全体」「機種別」「台番号指定」を選択する。

| モード | 遷移先 | 備考 |
| --- | --- | --- |
| 店舗全体 | `/{shop_id}/all_list?ps=S` | 従来の全台一覧画面。既存Userscriptsとの連携を維持 |
| 機種別 | `/{shop_id}/list?mode=psModelNameSearch&ps=S` | 公式の「機種別で探す」画面。選択した機種の台一覧は `unit_list` に進む。**表示HTMLの手動保存は対応**。構造化解析は未対応 |
| 台番号指定 | `/{shop_id}/detail?unit={unit}` | 半角数字1〜6桁を入力。実在する台番号かはサイト表示で確認 |

画面モードの切替はGitHub Pages側のナビゲーションのみで、**モデル一覧からの一括詳細取得が成功したことを意味しない**。

GORAGGIOの規約ページには、スクレイピングに関する禁止事項が記載されている。公式ページへの通常の移動と、自動収集の許可は別問題であるため、後者は必要な利用許諾を確認してから使用すること。

## 仕様書と変更管理

実装と文書の差をなくすため、[現行仕様書](SPECIFICATION.md)を基準に、[変更管理台帳](CHANGE_MANAGEMENT.md)に変更ID・状態・検証を記録します。ユーザー向け更新は[CHANGELOG](CHANGELOG.md)へ記載し、PR作成時はテンプレートのチェックを利用します。ChatGPTの既存「台データ取得ツール」と分離して使うための[新プロジェクト設定文](CHATGPT_PROJECT_SETUP.md)も用意しています（ChatGPT上でのプロジェクト作成は別操作）。

## 構成

- `index.html` — iPhone用3店舗選択ページ
- `userscripts/goraggio-export.user.js` — Safari上で一覧・詳細を保存するユーザースクリプト
- `goraggio.py` — 取得済みHTMLの既存オフラインパーサー
- `merge_captures.py` — 詳細JSON・手動保存HTMLと台番号一覧の結合、欠損レポート
- `tests/` — 403・HTML不足・データ照合・日付抽出の自動テスト
- `DETAIL_CAPTURE.md` — 詳細取得、Python解析、実機検証の手順

## 対応店舗（GORAGGIO ID）

- ピーアーク北千住SSS：`100831`
- コンサートホール北千住：`100983`
- ピーアーク竹ノ塚スタジオ：`100883`

## 設計上の安全性と制約

利用規約確認や認証を自動化せず、403/429・同意ページ・予期しないレスポンスでは取得を停止します。25台ずつ、最低約2秒の間隔で取得を試みます。iOSでは非アクティブ中の処理や自動ダウンロードが制限されることがあります。

HTML内の機種・回数・台番号が取得できることと、設定判別に必要な履歴・グラフ・CZ等が得られることは**別問題**です。詳細の生HTMLが取れた後に、抽出可能な項目を個別検証します。抽出されていない数値は推測で補いません。

ダウンロードJSONや生HTMLは公開GitHubリポジトリにコミットしないでください。
