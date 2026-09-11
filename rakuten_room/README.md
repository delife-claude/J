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
LINE Notifyは2025年3月末で終了したため、LINE公式アカウント＋Messaging APIのbroadcast配信を使います。
1. https://manager.line.biz/ で公式アカウントを新規作成（無料プランでOK、月200通まで無料。1日3通×30日=90通なので十分収まる）
2. LINE Official Account Manager → 設定 → Messaging API → 有効化
3. 「チャンネルアクセストークン（長期）」を発行 → GitHub Secrets に `LINE_CHANNEL_ACCESS_TOKEN` として登録
4. 自分のLINEアプリで、作成した公式アカウントを友だち追加する
5. **重要:** この公式アカウントは自分専用の通知用なので、LINE Official Account Managerの設定で
   「あいさつメッセージ」以外の外部公開・友だち追加QRの拡散はしないこと（broadcastは友だち全員に届くため）

### 3. Gemini APIキー（無料枠あり）
1. https://aistudio.google.com/apikey にアクセス（Googleアカウントでログイン、クレジットカード登録不要）
2. 「Create API key」でキーを発行
3. 発行された文字列を控える → GitHub Secrets に `GEMINI_API_KEY` として登録

無料枠には呼び出し回数の上限があるが、1日3回×商品5件程度の生成であれば収まる想定。
上限に達した場合はその回の通知が失敗するので、`MAX_PRICE`同様に必要なら候補数(`top_n`)を減らして調整する。

### 4. Secrets登録先
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
- `RAKUTEN_APP_ID`
- `RAKUTEN_ACCESS_KEY`
- `LINE_CHANNEL_ACCESS_TOKEN`
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
