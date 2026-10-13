# iPhone HTML取得ツール — セットアップと検証

## 現在の方針
GitHub Actionsの通常HTTPリクエストでは、2026-10-13のピーアーク北千住SSSのテストで **HTTP 403** が返されました。原因は未確定です。
iPhoneのSafariで通常表示できるページのDOMを、Safari拡張機能が読み取ってHTMLとして保存する試作方式に切り替えました。403の回避用リクエストは実装していません。

## 初回セットアップ（iPhoneのみ）
1. GitHubの `keiyu-per/data-fetcher` を開く。
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch** を選ぶ。
3. `main` / `/(root)` を選択して **Save**。公開されたURLが次の形になることを確認する。
   `https://keiyu-per.github.io/data-fetcher/`
4. App Storeから無料の **Userscripts** をインストール:
   https://apps.apple.com/jp/app/userscripts/id1463298887
5. iPhoneの **設定 → アプリ → Safari → 拡張機能** で Userscripts を有効にする。権限設定では **daidata.goraggio.com** に対して許可する（画面表記はiOSのバージョンにより異なる）。
6. Safariで次のURLを開く。
   `https://keiyu-per.github.io/data-fetcher/userscripts/goraggio-export.user.js`
7. Safariの Userscripts 拡張機能メニューからインストールする。反映されない場合は拡張機能メニューを開いて読み込みを確認する。
8. Safariで `https://keiyu-per.github.io/data-fetcher/` を開き、任意の店舗を選んで **SafariでHTML取得を開始** をタップする。

## 動作の想定
- URLのハッシュ `#df-export` はブラウザ内部だけの印で、GORAGGIOへのHTTPリクエストに含まれない。
- Userscriptsは対象のGORAGGIO全台一覧ページを開いたときだけ保存準備UIを出す。
- 表示されている「設置台数」と、DOMの台番号リンク数が一致し、安定すると、HTMLファイルの自動ダウンロードを *試行* する。
- 自動ダウンロードがブロックされたり台数判定できない場合は、ページ上の **現在のHTMLを保存** ボタンを利用する。
- ファイル名は `goraggio_{店舗ID}_{UTC時刻}.html`。Safariのダウンロード一覧を確認する。
- 表示中のDOMを保存する仕組みのため、ページの遅延読み込みや仮想スクロールで全台分がDOMにないと、データが欠けることがある。**保存ファイルを既存の `goraggio.py` で検証し、全台一致するまで完全取得とみなさない。**

## 現時点の未検証事項
- iPhone実機のUserscriptsからJSが期待通りに動くか
- GORAGGIOページのDOMが既存のHTMLパーサーと一致するか
- Safariで自動ダウンロードが許可されるか
- 一覧が一度に全台分DOMに読み込まれるか
- GitHub Pagesが公開されているか（設定はユーザー側で必要）

## セキュリティ
- 対象ドメインと店舗IDは固定。ページで明示的に `#df-export` を指定したときだけスクリプトを動かす。
- HTMLは端末のSafariからローカル保存する。コードに秘密鍵・Cookie・GitHubトークンを追加しない。
- サイトの利用条件や表示制限には従う。認証・CAPTCHA・403/429の回避はしない。
- 本試作はブラウザ画面に見えている内容の取得が目的であり、サーバー側からの定期巡回ではない。

## 次の開発
取得可能性を実機確認してから、iOSショートカットとの連携や、ファイルの集計・解析・出力画面改善に進む。
