# 楽天ROOM 下書き自動生成パイプライン（人間投稿・規約準拠版）

## なぜ「自動投稿」にしなかったか

楽天ROOMの利用規約（禁止事項）は
「スクリプトその他のプログラムを実行する等の方法により、機械的に投稿、コメント等をする行為」
を明示的に禁止しています。ブラウザにログインしてROOMへ自動投稿する仕組みを作ると、
規約違反＝アカウント停止のリスクを直接負うことになるため、このツールは**投稿の下書き作成まで**を
自動化し、**実際にROOMへ投稿するボタンを押すのは常にあなた自身**という構成にしています。

## 全体の流れ（組織図との対応）

| 組織図の係 | このリポジトリでの実装 |
|---|---|
| ①自己紹介文作成係 | `profile_intro.py`（初回に1回だけ手動実行） |
| ②商品リサーチ係 | `product_research.py`（楽天市場商品検索API・バレーボール関連キーワード） |
| ③ライティング係 | `write_captions.py`（Gemini APIで紹介文＋ハッシュタグを生成） |
| ④投稿オペレーター | **実装しない**（規約違反のため）。かわりに人間のあなたが投稿する |
| ⑤スケジュール管理係 | GitHub Actions（`.github/workflows/rakuten_room_daily.yml`）で朝・昼・夜に②③を実行し、LINEに通知 |

## セットアップ

### 1. 楽天ウェブサービス アプリID・アクセスキー（無料）
2026年の楽天API刷新以降、`アプリケーションID`だけでなく`アクセスキー`も必須になっている。
1. https://webservice.rakuten.co.jp/ で楽天IDでログインし、アプリ一覧（`/app/list`）を開く
2. 「詳細」で確認し、APIアクセススコープに **Rakuten Ichiba API** が含まれていることを確認
3. 表示されている **アプリケーションID** → GitHub Secrets に `RAKUTEN_APP_ID` として登録
4. 表示されている **アクセスキー**（`pk_`から始まる文字列）→ GitHub Secrets に `RAKUTEN_ACCESS_KEY` として登録

これは楽天市場の商品検索API用のIDで、ROOMへのログインとは無関係です。
アプリ登録時の「Allowed websites」欄に設定したURLと、実際のリクエストの`Origin`/`Referer`が
一致していないと拒否されるため、`rakuten_client.py`はデフォルトで登録済みのURLを送信する
（変更したい場合は環境変数`RAKUTEN_ALLOWED_ORIGIN`で上書き可能）。

### 2. LINE公式アカウント（無料・Messaging API）
LINE Notifyは2025年3月末で終了したため、LINE公式アカウント＋Messaging APIのpush配信（運用者本人だけに届く）を使います。
1. https://manager.line.biz/ で公式アカウントを新規作成（無料プランでOK、月200通まで無料。1日3通×30日=90通なので十分収まる）
2. LINE Official Account Manager → 設定 → Messaging API → 有効化
3. https://developers.line.biz/console/ → 対象チャネル → 「Messaging API」タブ → 「チャネルアクセストークン（長期）」を発行 → GitHub Secrets に `LINE_CHANNEL_ACCESS_TOKEN` として登録
4. 自分のLINEアプリで、作成した公式アカウントを友だち追加する
5. **自分のuserIdを取得する**（push配信に必須。「Get follower IDs」APIは無料プランで使えないため、以下のWebhook経由の方法で取得する）
   1. https://webhook.site を開き、表示された固有URL（`https://webhook.site/xxxxxxxx-...`）を控える
   2. LINE Developersコンソール → 対象チャネルの「Messaging API」タブ → 「Webhook設定」→ Webhook URLに上記URLを貼り付けて保存 → 「Webhookの利用」をONにする
   3. 自分のLINEアプリから、作成した公式アカウントのトーク画面で何かメッセージを送る（内容は何でもよい）
   4. webhook.siteのタブに戻って更新すると、受信したリクエストが表示される。その中のJSONから`"events":[{"source":{"userId":"U..."`の`userId`（`U`から始まる33文字）をコピー
   5. GitHub Secrets に `LINE_USER_ID` として登録
   6. （任意）確認が終わったらWebhook設定はOFFに戻してよい（オフにしても発行済みのpush配信には影響しない）

### 3. Gemini APIキー（無料枠あり）
1. https://aistudio.google.com/apikey にアクセス（Googleアカウントでログイン、クレジットカード登録不要）
2. 「Create API key」でキーを発行
3. 発行された文字列を控える → GitHub Secrets に `GEMINI_API_KEY` として登録

**重要:** 無料枠は`gemini-3.6-flash`で1日20リクエストまでという厳しい制限がある
（Google Cloudプロジェクト/APIキー単位のカウント）。このツールは1日3回×商品3件＝
9リクエストに抑えて運用する設定にしている（`daily_pipeline.py`の`top_n=3`）。
手動実行での動作確認を繰り返すとその日の枠をすぐ使い切り、以降の自動実行が
`429 RESOURCE_EXHAUSTED`で失敗する点に注意（枠は米国時間の日付でリセットされる）。
別のGemini連携（例: Threads投稿ツールの`THREADS_GEMINI_API_KEY`）と**同じAPIキーの値**を
使い回している場合、そちらの消費分も合算されてこの上限にぶつかるので、
できれば別のGoogle Cloudプロジェクトで発行したキーを使うこと。

### 4. Secrets登録先
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
- `RAKUTEN_APP_ID`
- `RAKUTEN_ACCESS_KEY`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `GEMINI_API_KEY`
- （任意）`MAX_PRICE` … 未設定時は8000円

### 5. 自己紹介文の作成（初回のみ・手動）
```
pip install -r rakuten_room/requirements.txt
export GEMINI_API_KEY=...
python rakuten_room/profile_intro.py
```
`rakuten_room/profile_intro.txt` に生成されるので、内容を確認してROOMのプロフィール欄に貼り付ける。

### 6. 動作確認（手動実行）
GitHub Actions タブ →「Rakuten ROOM 下書き通知」→ Run workflow で手動実行し、
LINEに下書き通知が届くか確認する。

## 毎日の運用
朝・昼・夜（JST 8:00 / 13:00 / 20:00）に自動でGitHub Actionsが起動し、
1. バレーボール関連商品を楽天市場APIで検索（売り切れ・`MAX_PRICE`超えは除外）
2. Geminiが紹介文＋ハッシュタグを生成
3. 内容をLINEに通知（`drafts/`フォルダにも保存されリポジトリにコミットされる）

**あなたがやること:** LINEの通知を確認し、良ければROOMアプリ/サイトを開いて手動でコピペ投稿する。
気に入らない候補はスキップしてOK（自動では何も投稿されない）。

## ライティングのルール（重要）
`room_system_prompt.txt` では「使ってみた」等の一人称の体験談を捏造しないルールにしています。
実際に自分で使った商品を紹介したい場合は、その体験談を `write_captions.py` の
`real_experience` 引数（今はCLIパイプラインでは空文字固定）に渡して手動実行すると反映されます。
