# 詳細HTML取得 — iPhone Safari 試作 v0.2.2

この機能は**iPhoneのSafari内で、利用者が通常閲覧できるGORAGGIOの詳細ページ**を取得します。GitHub ActionsからのHTTP取得（403）は使用しません。相手サイトの利用条件を確認し、利用規約への同意・アクセス制限の回避はしません。

## 初回設定（v0.1を使っている場合も更新が必要）

1. iPhoneのSafariで [Userscripts](https://apps.apple.com/jp/app/userscripts/id1463298887) 拡張機能を有効化し、`daidata.goraggio.com` へのアクセスを許可する
2. [goraggio-export.user.js](https://keiyu-per.github.io/data-fetcher/userscripts/goraggio-export.user.js) をSafariで開く
3. SafariのUserscripts拡張メニューから `GORAGGIO iPhone HTML Export` を **v0.2.2** に更新する（自動更新を前提にしない）
4. [Data Fetcher](https://keiyu-per.github.io/data-fetcher/) を開き、店舗を選んで取得を開始する

## 一覧・詳細の取得

1. GORAGGIOで利用規約の画面が表示された場合は、自分で内容を確認して同意する。**同意自動化はしない**
2. 同意後にData Fetcherに戻り、再度「Safariで一覧・詳細取得を開始」を押す
3. Safariページ下部に「GORAGGIO HTML取得 v0.2.2」パネルが表示されることを確認する
4. 機種選択から `L東京喰種（22台）` などを選び、「選択機種の詳細を取得」を押す
5. 25台単位で、約2秒以上の間隔を取りながら順次取得する。**取得中はSafariを手前に開いたままにする**
6. Safariがダウンロードを阻止した場合、下部の「取得済みの詳細データを保存」をタップする
7. `goraggio_100831_details_*.json` の保存を確認する

詳細JSONは `goraggio-detail-bundle/v1` 形式。取得時の一覧HTML、対象台番号、台ごとの取得先URL・HTML、取得エラーを含みます。公開リポジトリへのアップロードは避けてください（ページ内に閲覧状態に紐づく情報を含む可能性があります）。

### 1台単位の代替手段

詳細の一括取得が403・429、同意画面、DOM仕様変更等で止まる場合は、パネルの「選択した1台をSafariで開く（手動取得用）」を押してください。詳細ページが開いたら「この台の詳細HTMLを保存」を押します。通常のSafariページ遷移を利用する方式であり、閲覧できないページは取得できません。

## 機種別ページでのHTML保存（v0.2.2）

GitHub Pagesで「機種別に見る」を選択し、GORAGGIOの公式画面から機種を選んで `unit_list` に進みます。下部パネルの「現在表示中のページHTMLを保存」で保存できます。2026-10-13のマイジャグラーV・28台のHTML保存を確認しましたが、**このHTMLを `merge_captures.py` へ直接入力して機種別の統計を結合する機能はまだありません**。

## データ解析（Pythonを実行できる環境で）

取得JSONを解析して、一覧と各台の詳細を結合できます。

```bash
python merge_captures.py --bundle goraggio_100831_details_1.json --out-dir parsed
# 25台を超える機種や全機種は --bundle を複数回指定
python merge_captures.py --bundle first.json --bundle second.json --out-dir parsed
# 1台の手動取得時は、一覧HTMLと一緒に
python merge_captures.py --shop-id 100831 --list-html all_list.html \
  --detail-html goraggio_100831_unit_732_2026.html --out-dir parsed
```

出力:
- `coverage.json` — 取得台数・詳細取得台数・欠損数・警告
- `machines.csv` — 一覧と詳細の結合行
- `machines.json` — 同上JSON

**詳細0件・グラフ未抽出・CZ/ATの履歴が確認できない状態は、設定判別可能とみなさない。** ここで行うのは取得と品質検証のみです。

## 技術的制約（重要）

- 2026-10-13の実HTMLでは一覧451台を解析できましたが、サイトの公式総設置台数を示す情報は含まれず、**全台一致の証明はできていません**。
- 詳細ページの生HTMLは本プロジェクトに添付されておらず、**同一オリジンfetchで取得できるか・CZ履歴やグラフが含まれるかは未検証**です。
- 25台ごとにJSONを保存します。451台を一括で取得する仕様ではありません。Safariのメモリ・バックグラウンド制限やページ負荷のため、意図的に制限しています。
- 通信制限（403/429）、利用規約画面、CAPTCHA、異常なレスポンスを検出したら続行せず停止します。
- グラフが画像やCanvasとして描画されていてHTMLだけでは数値化できない場合は、別途画面内容の検証が必要です。
- 過去日の `hist_num` を詳細URLへ渡す実装は暫定です。サイト側が同じ履歴番号を受理するか、実機で確認が必要です。
- 自動ダウンロードがブロックされても、保存ボタンは動かせるようにしています。ボタンの動作もiPhoneで検証してください。

## 開発品質

GitHub Actions `Offline data-fetcher validation` でPythonの単体テストとJavaScriptの構文検査を実施します。取得テスト（403を返すGitHub Actions）は手動起動のみ残しています。
