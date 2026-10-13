# iPhone Safariセットアップ

GitHub Pagesの公開とSafariからのアクセスは確認済み。以下は**Userscriptsの更新と実機検証**の手順です。

1. iPhoneのSafari拡張機能で **Userscripts** を有効にし、`daidata.goraggio.com` を許可する。
2. [最新版のJavaScript](https://keiyu-per.github.io/data-fetcher/userscripts/goraggio-export.user.js) をSafariで開き、Userscripts拡張メニューから **GORAGGIO iPhone HTML Export v0.2.2** をインストールまたは更新する。
3. [Data Fetcher Webアプリ](https://keiyu-per.github.io/data-fetcher/) で店舗を選び、**Safariで一覧・詳細取得を開始** を押す。
4. 既存の利用規約画面が現れた場合は、内容を確認して自身で同意し、Webアプリのボタンから再び開く。
5. GORAGGIO上のパネルで機種を選択し、**選択機種の詳細を取得（最大25台）** を押す。
6. 取得中はSafariを前面にして待ち、JSONがダウンロードされなければ **取得済みの詳細データを保存** を押す。
7. 詳細ページへの直接アクセスが必要なら、**選択した1台をSafariで開く（手動取得用）** で保存する。

パネルが出なければUserscriptsのバージョン・有効設定と、URL末尾の `#df-export` を確認します。

手順の詳細、Pythonでの結合、注意点は [DETAIL_CAPTURE.md](DETAIL_CAPTURE.md) を参照してください。

**注意**：2026-10-13時点で、Safariでの一覧保存は実機検証済み、詳細の連続取得と自動ダウンロードは未検証です。403・規約画面は自動回避せず停止します。公開GitHubには生HTMLや詳細JSONをコミットしないでください。

**機種別モードの現状**：公式の機種選択→ `unit_list` に進み、パネルの「現在表示中のページHTMLを保存」を使用します。2026-10-13のマイジャグラーV・28台分の保存HTMLは確認済みですが、機種別HTMLを既存Python結合処理へ直接渡す機能は未実装です。
