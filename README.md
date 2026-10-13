# Data Fetcher — iPhone Safari向けGORAGGIO HTML取得

**目的**：iPhoneだけで店舗と機種を選択し、GORAGGIOの台番号一覧および選択機種の各台詳細HTMLをローカルに保存・解析する。

[Webアプリ](https://keiyu-per.github.io/data-fetcher/) | [iPhoneでの詳細取得手順](DETAIL_CAPTURE.md) | [セットアップ](IPHONE_SETUP.md)

## 現在の実装（v0.2.1）

| 機能 | 状態 |
| --- | --- |
| GitHub Pagesの店舗選択UI（3店舗） | 実装済み・Safari表示確認済み |
| Safari Userscriptsによる一覧HTML保存 | 実装済み・実機保存確認済み |
| 全台一覧の451行解析 | 2026-10-13の実ファイルで検証済み |
| 選択機種の詳細ページ取得（同一サイトの通常リクエスト） | 実装済み・実機未検証 |
| 25台単位の詳細JSON保存・取得中断 | 実装済み・実機未検証 |
| 選択1台の詳細ページ移動・手動HTML保存 | 実装済み・実機未検証 |
| 一覧と詳細の結合CSV/JSON・欠損率集計 | 実装済み・オフライン自動テスト成功 |
| 詳細のCZ/AT履歴・グラフ検証、設定推定 | 未実装 |

GitHub Actionsからの直接HTTP取得は **HTTP 403** のため、通常運用には使用しません。従来の `fetch_goraggio.py` と `GORAGGIO HTML retrieval test` は診断目的で保持し、手動起動のみです。通常の品質確認は `Offline data-fetcher validation` が行います。

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
