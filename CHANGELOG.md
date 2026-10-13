# 変更履歴（CHANGELOG）

このファイルは `data-fetcher` のユーザーに影響する変更・仕様変更を記録する。詳細なトレーサビリティは[変更管理台帳](CHANGE_MANAGEMENT.md)を参照。

## [Unreleased] — 2026-10-13

### Added
- 現行実装に基づく仕様書 `SPECIFICATION.md`（as-built）を追加。
- 変更ID／状態／受け入れ基準を記録する `CHANGE_MANAGEMENT.md` とPRテンプレートを追加。
- ChatGPTの新規プロジェクト「台データ取得ツール（半自動）」向けに、設定ガイド `CHATGPT_PROJECT_SETUP.md` を追加。

### Changed
- README・iPhoneセットアップ手順・詳細取得手順の表記をUserscripts v0.2.2に統一。
- 機種別 `unit_list` HTML保存と、未実装の `unit_list` 構造化パーサーを明確に区別。

## [0.2.2] — 2026-10-13

### Changed
- Userscriptsの対象ページを `all_list`／`detail` に加え `list`／`unit_list` に拡張。
- Data Fetcherからの `#df-export` 起点と同一タブ `sessionStorage`（15分）での起動意図引き継ぎを導入。
- GitHub ActionsでUserscripts起動条件の回帰テストを追加し、連続コミット時の旧検証ジョブをキャンセルする設定を追加。

### Notes
- 機種別ページは現時点で「表示中HTMLの保存」に対応。取得済み `unit_list` をPythonで解析・結合する機能は未実装。
- 詳細ページの連続取得とCZ/AT・グラフ解析のSafari実機検証は未完了。

## [0.2.1] — 2026-10-13以前の実装を遡及整理

### Added
- iPhone向けの一覧HTML保存、試験的な詳細取得JSON、個別詳細手動保存。
- `all_list` 一覧と取得できた詳細を結合するオフライン処理および単体テスト。
- 3店舗・3モードのGitHub Pagesナビゲーション（後続更新を含む）。

### Notes
- 本節は過去の正確なリリース日ごとの記録ではなく、仕様書導入時点の履歴を整理したもの。
