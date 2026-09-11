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
| ③ライティング係 | `write_captions.py`（Claude APIで紹介文＋ハッシュタグを生成） |
| ④投稿オペレーター | **実装しない**（規約違反のため）。かわりに人間のあなたが投稿する |
| ⑤スケジュール管理係 | GitHub Actions（`.github/workflows/rakuten_room_daily.yml`）で朝・昼・夜に②③を実行し、LINEに通知 |

## セットアップ

### 1. 楽天ウェブサービス アプリID（無料）
1. https://webservice.rakuten.co.jp/ で楽天IDでログインしアプリ登録
2. 発行された「アプリID」を控える → GitHub Secrets に `RAKUTEN_APP_ID` として登録

これは楽天市場の商品検索API用のIDで、ROOMへのログインとは無関係です。

### 2. LINE公式アカウント（無料・Messaging API）
LINE Notifyは2025年3月末で終了したため、LINE公式アカウント＋Messaging APIのbroadcast配信を使います。
1. https://manager.line.biz/ で公式アカウントを新規作成（無料プランでOK、月200通まで無料。1日3通×30日=90通なので十分収まる）
2. LINE Official Account Manager → 設定 → Messaging API → 有効化
3. 「チャンネルアクセストークン（長期）」を発行 → GitHub Secrets に `LINE_CHANNEL_ACCESS_TOKEN` として登録
4. 自分のLINEアプリで、作成した公式アカウントを友だち追加する
5. **重要:** この公式アカウントは自分専用の通知用なので、LINE Official Account Managerの設定で
   「あいさつメッセージ」以外の外部公開・友だち追加QRの拡散はしないこと（broadcastは友だち全員に届くため）

### 3. Anthropic APIキー
`ANTHROPIC_API_KEY` を GitHub Secrets に登録（既存の `generate_weekly_posts.py` と共通のキーで可）

### 4. Secrets登録先
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
- `RAKUTEN_APP_ID`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `ANTHROPIC_API_KEY`
- （任意）`MAX_PRICE` … 未設定時は8000円

### 5. 自己紹介文の作成（初回のみ・手動）
```
pip install -r rakuten_room/requirements.txt
export ANTHROPIC_API_KEY=...
python rakuten_room/profile_intro.py
```
`rakuten_room/profile_intro.txt` に生成されるので、内容を確認してROOMのプロフィール欄に貼り付ける。

### 6. 動作確認（手動実行）
GitHub Actions タブ →「Rakuten ROOM 下書き通知」→ Run workflow で手動実行し、
LINEに下書き通知が届くか確認する。

## 毎日の運用
朝・昼・夜（JST 8:00 / 13:00 / 20:00）に自動でGitHub Actionsが起動し、
1. バレーボール関連商品を楽天市場APIで検索（売り切れ・`MAX_PRICE`超えは除外）
2. Claudeが紹介文＋ハッシュタグを生成
3. 内容をLINEに通知（`drafts/`フォルダにも保存されリポジトリにコミットされる）

**あなたがやること:** LINEの通知を確認し、良ければROOMアプリ/サイトを開いて手動でコピペ投稿する。
気に入らない候補はスキップしてOK（自動では何も投稿されない）。

## ライティングのルール（重要）
`room_system_prompt.txt` では「使ってみた」等の一人称の体験談を捏造しないルールにしています。
実際に自分で使った商品を紹介したい場合は、その体験談を `write_captions.py` の
`real_experience` 引数（今はCLIパイプラインでは空文字固定）に渡して手動実行すると反映されます。
