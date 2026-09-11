# Threads 自動投稿パイプライン（子どもバレーグッズアカウント）

`generate_weekly_posts.py` / `system_prompt.txt` / `theme_bank.json` で投稿文を生成し、
`daily_pipeline.py` が楽天市場のアフィリエイトリンクを埋め込んだうえで Typefully 経由で
Threads に自動投稿（予約）します。`rakuten_room/` 配下は楽天ROOM向けの別パイプラインです
（規約上の理由で下書き＋人間投稿までしか自動化していません。詳細は `rakuten_room/README.md`）。

## 組織図との対応

| 組織図の係 | このリポジトリでの実装 |
|---|---|
| ①自己紹介文作成係 | （Threads側は未実装。プロフィール文は手動で用意してください） |
| ②商品リサーチ係 | `rakuten_client.py`（楽天市場商品検索API・アフィリエイトID付き） |
| ③ライティング係 | `generate_weekly_posts.py` + `system_prompt.txt`（Gemini APIで曜日別に生成） |
| ④投稿オペレーター | `typefully_client.py`（Typefully公式APIでThreadsに予約投稿。ブラウザ自動ログインは使わない） |
| ⑤スケジュール管理係 | `.github/workflows/threads_daily.yml`（毎日18:00 JSTに自動実行） |

`daily_pipeline.py` が②〜⑤を一気通貫でつなぐエントリーポイントです。

## なぜ「完全無人・無条件で自動投稿」にしなかったか

2点、安全弁を入れています。

1. **実体験の捏造禁止**（`system_prompt.txt` のルール）：その日の実体験
   （`real_experience_bank.json`）が空だと、本文は「〜を使ってみた」のような一人称の
   体験談を捏造せず、代わりに `missing_experience_flag: true` を返す仕様になっています。
   このフラグが立った投稿は **Typefullyへ予約はせず、下書き登録＋LINE通知のみ** です。
2. **広告表示（ステマ規制対応）**：日本では2023年10月から、アフィリエイト等の広告を
   一般の投稿のように見せかける「ステルスマーケティング」が景品表示法で禁止されています。
   `cta_target: rakuten` の日（商品紹介・アフィリエイトリンクを含む日）は、
   本文冒頭に自動で `【PR】` を付け、ハッシュタグに `#PR #広告` を追加します。

いずれの投稿も、Typefullyに登録した時点ではまだ公開されていません（予約投稿）。
LINE通知を確認し、内容がおかしければ公開時刻までにTypefully側でキャンセル・編集できます。

## セットアップ

### 1. Gemini APIキー（無料枠あり。`rakuten_room`で設定済みなら使い回し可）
1. https://aistudio.google.com/apikey にアクセス（Googleアカウントでログイン、クレジットカード登録不要）
2. 「Create API key」でキーを発行
3. GitHub Secrets に `GEMINI_API_KEY` として登録（`rakuten_room`パイプライン用に既に登録済みなら
   同じ値をそのまま使い回してOKです）

無料枠には呼び出し回数の上限があるが、1日1投稿の生成であれば十分収まる想定。

### 2. 楽天ウェブサービス（アプリID・アクセスキー・アフィリエイトID）
1. https://webservice.rakuten.co.jp/ でアプリ登録し、**アプリケーションID** と
   **アクセスキー**（`pk_`から始まる文字列）を取得
2. https://affiliate.rakuten.co.jp/ で**アフィリエイトID**を取得（これがないと商品リンクに
   報酬が発生しません）
3. GitHub Secrets に `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID` として登録
4. アプリ登録時の「Allowed websites」と実際のOriginが一致していないとAPIが拒否されるため、
   必要なら環境変数 `RAKUTEN_ALLOWED_ORIGIN` で登録済みURLを指定してください
   （`rakuten_room/rakuten_client.py` と同じ制約です）

### 3. Typefully APIキー
1. Typefullyの管理画面でThreadsアカウントを連携済みにしておく
2. Settings → Integrations からAPIキーを発行
3. GitHub Secrets に `TYPEFULLY_API_KEY` として登録
4. 実行前に公式ドキュメント（https://support.typefully.com/en/articles/8718287-typefully-api ）
   でエンドポイント仕様が変わっていないか確認してください
   （このコードはネットワーク制限のある環境で実地確認せず実装したため）

### 4. LINE通知（`rakuten_room` とは別のSecrets名を使用）
このパイプラインは `rakuten_room` とは別のLINE公式アカウント／別のSecrets名
（`THREADS_LINE_CHANNEL_ACCESS_TOKEN` / `THREADS_LINE_USER_ID`）を使う想定です。
取得手順自体は `rakuten_room/README.md` の「2. LINE公式アカウント」と同じなので、
**Threads用に新しく公式アカウントを作成**したうえで、その手順に従ってトークンとuserIdを
取得し、上記の名前でSecrets登録してください。未設定でも動作はします（通知だけスキップ）。

### 5. Secrets登録先
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
- `GEMINI_API_KEY`
- `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID`
- `TYPEFULLY_API_KEY`
- `THREADS_LINE_CHANNEL_ACCESS_TOKEN` / `THREADS_LINE_USER_ID`
- （任意）`MAX_PRICE`（未設定時8000円）、`FOCUS_GOAL`（未設定時 `rakuten_revenue`）

### 6. 動作確認
```
pip install -r requirements.txt
export GEMINI_API_KEY=... RAKUTEN_APP_ID=... RAKUTEN_ACCESS_KEY=... RAKUTEN_AFFILIATE_ID=...
python daily_pipeline.py --dry-run
```
`--dry-run` はTypefully/LINEへは送信せず、生成された投稿文をターミナルに表示するだけです。
内容を確認できたら、GitHub Actions タブ →「Threads 自動投稿パイプライン」→ Run workflow で
手動実行し、実際にTypefullyへ予約登録されるか確認してください。

## 実体験の登録方法

`real_experience_bank.json` に `"YYYY-MM-DD"（JST）: "実体験メモ"` の形で追記してください。
その日付がヒットすると、生成AIがその体験を踏まえた本文にします。書かないままだと、
その日は自動投稿されず下書き＋LINE通知どまりになります（捏造防止のため）。

## 毎日の運用

毎日18:00 JSTに GitHub Actions が自動起動し、
1. その曜日の `type_name` / `format` / `cta_target` に従って投稿文をGeminiが生成
2. `cta_target: rakuten` の日は楽天市場APIで商品を検索し、アフィリエイトリンクと`【PR】`を付与
3. 実体験あり・商品リンクも埋まっていれば、その場でTypefullyに18:00投稿予約として登録
4. 埋まらなければ下書きのみ登録し、LINEで「要確認」として通知
5. いずれの場合も生成結果を `drafts/` に保存してコミット（監査ログ）

**あなたがやること:** LINE通知を確認する。特に「要確認」の投稿は、実体験を追記するか
Typefully側で手動編集・削除してください。
