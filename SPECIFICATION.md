# 仕様書 — 台データ取得ツール（半自動）

- 文書ID：SPEC-001
- 版：1.0
- 作成日：2026-10-13
- 対象リポジトリ：`keiyu-per/data-fetcher`
- 実装基準：Safari Userscripts v0.2.2（2026-10-13時点）
- 文書の更新ルール：[CHANGE_MANAGEMENT.md](CHANGE_MANAGEMENT.md)

## 1. 目的とシステム境界

iPhoneのSafariからGORAGGIOの公式画面を**利用者が操作して表示**し、表示内容のHTMLをローカル保存する。利用者が保存したファイルをオフラインで解析し、対象店舗・対象日・台番号・取得件数・欠損状況を把握する。設定判別は、機種別の十分な指標が取得・検証できた場合に限って別仕様で実装する。

従来の「台データ取得ツール」（ブラウザ直接操作・取得・解析を中心とするChatGPTプロジェクト）とは別の、**半自動取得専用**の運用を対象とする。ChatGPT Projectsの新規作成自体は本GitHubリポジトリの機能ではない。

## 2. 構成

```text
iPhone Safari
  └─ GitHub Pages（index.html：店舗・モード選択）
      └─ GORAGGIO公式サイト（利用者が画面を操作）
          └─ Userscripts（goraggio-export.user.js：表示ページのHTML保存）
              └─ ローカルHTML / 詳細JSON（利用者がアップロード）
                  └─ Python（goraggio.py / merge_captures.py：オフライン解析）
                      └─ CSV / JSON / 欠損レポート
```

| コンポーネント | 責務 |
| --- | --- |
| `index.html` | 対象店舗、店舗全体・機種別・台番号指定の3モード、遷移先URL生成 |
| `userscripts/goraggio-export.user.js` | 画面への操作パネル表示、現在ページのHTML保存、選択台の詳細JSON取得（制約あり） |
| `goraggio.py` | 保存HTMLのオフライン解析、店舗・日付・台番号チェック |
| `merge_captures.py` | `all_list` と詳細バンドル・個別詳細HTMLの結合、取得率集計 |
| `tests/` と GitHub Actions | JavaScript構文・トリガー回帰テスト、Python単体テスト |

## 3. 機能要件

| ID | 要件 | 現状と備考 |
| --- | --- | --- |
| FR-01 | 店舗の選択（100831 / 100983 / 100883） | 実装済み |
| FR-02 | 「店舗全体」→ `/{id}/all_list?ps=S#df-export` に遷移 | 実装済み |
| FR-03 | 「機種別」→ `/{id}/list?mode=psModelNameSearch&ps=S#df-export` に遷移 | 実装済み |
| FR-04 | 「台番号指定」→ `/{id}/detail?unit={unit}#df-export` に遷移 | 実装済み。台番号入力は半角数字1〜6桁 |
| FR-05 | Userscriptsパネルを該当ページに表示 | v0.2.2で `all_list` / `list` / `unit_list` / `detail` に対応。iPhone全経路の実機検証は要継続 |
| FR-06 | `all_list` の表示HTMLを保存 | 実装済み、実機保存の報告あり |
| FR-07 | `list`・`unit_list` の表示HTMLを保存 | 実装済み。2026-10-13のマイジャグラーV・28台の `unit_list` HTML保存を確認 |
| FR-08 | `detail` の表示HTMLを台番号つき名称で保存 | 実装済み、個別実機検証は未完了 |
| FR-09 | `all_list` から機種を選び、25台以内ずつ詳細をJSON保存 | 試験実装済み。HTTP 403/429、同意画面、非HTML等で停止。実機連続取得は未検証 |
| FR-10 | 一覧と詳細データの結合・欠損件数の集計 | `all_list` + 詳細JSON/HTMLについて実装済み・オフライン試験あり |
| FR-11 | 機種別 `unit_list` の累計G・確率等をPythonで構造化 | **未実装**。HTML保存と解析成功を混同しない |
| FR-12 | 過去日の推移やグラフ、CZ・AT履歴の抽出 | **未実装／実データ検証待ち** |
| FR-13 | 設定推定・イベント日の有望台評価 | **未実装**。抽出データが揃った場合に別途設計・検証する |

## 4. Userscripts起動条件

- `@match https://daidata.goraggio.com/*` だけで自動表示せず、店舗IDとパスを検査する。
- Data Fetcherからの明示的な `#df-export` を起点とし、同一タブの `sessionStorage` で同一店舗への意思を15分間保持する。
- 別タブや有効期限切れ、対象外URLでのパネル表示は保証しない。Safariのストレージ制限時はハッシュ起点にフォールバックする。
- `list`・`unit_list` は現時点で**表示HTML保存のみ**。`all_list` 向けの複数台詳細取得UIとは異なる。

## 5. 入力・出力および検証項目

**入力**：利用者がGORAGGIOで保存した `all_list` HTML、`unit_list` HTML、個別 `detail` HTML、`goraggio-detail-bundle/v1` JSON。

**出力（現行Python）**：
- `goraggio.py`：`all_list` 等の対応入力から一覧CSV・JSON
- `merge_captures.py`：`coverage.json`、`machines.csv`、`machines.json`
- `unit_list` 保存HTMLは、**現行の `merge_captures.py` ではそのまま結合できない**。解析は別実装待ち。

**検査ルール**：店舗ID・対象日・取得時刻、観測した台数、重複・欠損、詳細取得率、必要な統計項目が存在するかを区別する。公式総台数が不明な場合、観測件数を「全台取得」と断言しない。欠損値を0や推測値で補わない。

## 6. 非機能要件・禁止事項

- NFR-01：原則iPhone/Safariで画面操作・ファイル保存できる。
- NFR-02：機種・台番号・日付・取得ページ種別を結果に付与する。
- NFR-03：HTTP 403/429、利用規約同意・認証/CAPTCHA等を迂回しない。サイトの利用規約を確認し、自動収集について必要な許諾なしに運用しない。
- NFR-04：取得済み生HTML・JSONの公開GitHubへのコミット禁止。テストは合成・匿名化データで実施する。
- NFR-05：連続通信の上限は1回25台、リクエスト間隔2秒以上。端末が非アクティブになったら中断する。
- NFR-06：コード変更はオフラインの自動テストと実機確認項目を記録する。
- NFR-07：有望台・設定推定は不確実性と根拠を明記し、設定確定や収支保証と表現しない。

## 7. 受け入れ基準

1. 3モードのURL遷移と、対象ページでのUserscripts起動条件を回帰テストする。
2. `all_list` と `unit_list` のページタイプを識別し、保存確認を実施する。
3. 解析可能な項目と未取得の項目を明示し、0件・不整合・未対応形式はエラーにする。
4. Python/JavaScript変更後はオフラインCIが成功していることを確認する。Safari実機でしか検証できない項目は「未検証」と記す。
5. 仕様変更時は[変更管理台帳](CHANGE_MANAGEMENT.md)と[変更履歴](CHANGELOG.md)を更新する。

## 8. 今後の候補（未実装）

- BL-01：`unit_list` 専用パーサーとCSV/JSON出力
- BL-02：日付別・同一台番号別の履歴比較
- BL-03：個別 `detail` の履歴・グラフ数値の取得可能性を実データで検証
- BL-04：入力根拠、設定別指標、サンプル規模、欠損率を説明できる評価ロジックの別仕様化
- BL-05：iPhoneでの同意後の再開・保存導線を改良。ただし同意自動化や制限回避は行わない

**注意**：本書は現行ソースの観察に基づく後追い仕様化（as-built）です。未実装の候補は実装完了を意味しません。
