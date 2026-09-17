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

### 1. Gemini APIキー（無料枠あり。`rakuten_room`とは別キーで発行）
無料枠は1日20リクエスト/モデルとかなり少なく、`rakuten_room`（1日3回×候補5件分）と
同じキーを共用すると簡単に枠を使い切ってしまうことが分かったため、**Threads専用に
別のキーを発行**します（プロジェクトを分ければ、それぞれ別に20リクエスト/日を持てます）。
1. https://aistudio.google.com/apikey にアクセス（`rakuten_room`用とは別のGoogleアカウント、
   または同じアカウントで新規プロジェクトを選んでログイン、クレジットカード登録不要）
2. 「Create API key」でキーを発行
3. GitHub Secrets に `THREADS_GEMINI_API_KEY` として登録（`rakuten_room`の`GEMINI_API_KEY`とは
   別の値にしてください）

### 2. 楽天ウェブサービス（アプリID・アクセスキー・アフィリエイトID）
1. https://webservice.rakuten.co.jp/ でアプリ登録し、**アプリケーションID** と
   **アクセスキー**（`pk_`から始まる文字列）を取得
2. https://affiliate.rakuten.co.jp/ で**アフィリエイトID**を取得（これがないと商品リンクに
   報酬が発生しません）
3. GitHub Secrets に `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID` として登録
4. アプリ登録時の「Allowed websites」と実際のOriginが一致していないとAPIが拒否されるため、
   必要なら環境変数 `RAKUTEN_ALLOWED_ORIGIN` で登録済みURLを指定してください
   （`rakuten_room/rakuten_client.py` と同じ制約です）

### 3. Typefully APIキー・social_set_id
1. Typefullyの管理画面でThreadsアカウントを連携済みにしておく
2. Settings → API → 「+ New API Key」でAPIキーを発行 → GitHub Secrets に `TYPEFULLY_API_KEY`
   として登録
3. **投稿先アカウントのID(`social_set_id`)も必要**です。Typefully MCP等で
   `list_social_sets` を呼ぶか、Typefullyのサポートに確認して数値IDを取得し、
   GitHub Secrets に `TYPEFULLY_SOCIAL_SET_ID` として登録してください
4. **月間の公開(publish)回数に上限があります**（プランによる。実測で「10回/月」だったケースあり）。
   このパイプラインは平日毎日投稿予約を試みるため、上限に達すると予約が失敗します。
   毎日投稿したい場合は、上限が十分なプランかTypefully側で確認してください

### 4. LINE通知（`rakuten_room` で設定済みなら使い回し可）
`rakuten_room/README.md` の「2. LINE公式アカウント」の手順で取得した
`LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID` をそのまま使えます。未設定でも動作はしますが
（通知だけスキップされる）、内容確認のためLINE通知の設定を強く推奨します。

### 5. Secrets登録先
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
- `THREADS_GEMINI_API_KEY`
- `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID`
- `TYPEFULLY_API_KEY` / `TYPEFULLY_SOCIAL_SET_ID`
- `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`
- （任意）`MAX_PRICE`（未設定時8000円）、`FOCUS_GOAL`（未設定時 `rakuten_revenue`）

### 6. 動作確認
```
pip install -r requirements.txt
export THREADS_GEMINI_API_KEY=... RAKUTEN_APP_ID=... RAKUTEN_ACCESS_KEY=... RAKUTEN_AFFILIATE_ID=...
python daily_pipeline.py --dry-run
```
`--dry-run` はTypefully/LINEへは送信せず、生成された投稿文をターミナルに表示するだけです。
内容を確認できたら、GitHub Actions タブ →「Threads 自動投稿パイプライン」→ Run workflow で
手動実行し、実際にTypefullyへ予約登録されるか確認してください。

## 実体験の登録方法

`real_experience_bank.json` に `"YYYY-MM-DD"（JST）: "実体験メモ"` の形で追記してください。
その日付がヒットすると、生成AIがその体験を踏まえた本文にします。書かないままだと、
その日は自動投稿されず下書き＋LINE通知どまりになります（捏造防止のため）。

## 運用スケジュール（週2回: 水・金 18:00 JST）

Typefullyの月間公開上限（実測10回/月）に収まるよう、水曜・金曜の週2回（月8〜9回）に
間引いています。ちょうど `cta_target: rakuten`（楽天アフィリエイトリンクを含む「稼げる投稿」）
の曜日と一致しているため、収益化の観点でも効率的です。頻度を変えたい場合は
`.github/workflows/threads_daily.yml` の `cron` を編集してください（曜日番号: 0=日, 1=月, …, 6=土）。

水・金 18:00 JSTに GitHub Actions が自動起動し、
1. その曜日の `type_name` / `format` / `cta_target` に従って投稿文をGeminiが生成
2. `cta_target: rakuten` の日は楽天市場APIで商品を検索し、アフィリエイトリンクと`【PR】`を付与
3. 実体験あり・商品リンクも埋まっていれば、その場でTypefullyに18:00投稿予約として登録
4. 埋まらなければ下書きのみ登録し、LINEで「要確認」として通知
5. いずれの場合も生成結果を `drafts/` に保存してコミット（監査ログ）

**あなたがやること:** LINE通知を確認する。特に「要確認」の投稿は、実体験を追記するか
Typefully側で手動編集・削除してください。

## 汎用版: Threads投稿生成マシーン（`post_machine.py`）

上記の週間パイプラインとは別に、**任意のテーマ・任意の投稿数**でThreads投稿セットを
その場で生成できる汎用ツールです。子どもバレー以外のジャンル・アカウントでも使えます。

### 生成ルール
- **長文投稿**：`main_post`（フック, 50〜150字）＋`comment_1`（体験談＋具体的ノウハウ＋数値, 400〜500字）
  ＋`comment_2`（応用＋注意点＋CTA, 400〜500字）の3部構成、合計900〜1100字
- **短文投稿**：「気づき」「共感」系のみ・150〜200字（ノウハウ売り込みなし。滞在時間ではなく
  親近感・対話づくりが目的）
- **投稿比率**：長文:短文 ≒ 4:1（1日5投稿→長文4・短文1、1日10投稿→長文8・短文2）を自動計算し、
  1日の中で均等に散らして順番を組む
- 文字数ルールを満たさない出力は、指摘つきで自動的に再生成を試みる（最大3回）

### 使い方
```
pip install -r requirements.txt
export THREADS_GEMINI_API_KEY=...   # generate_weekly_posts.py と共用のキーでOK

# 対話モード
python post_machine.py

# 非対話モード
python post_machine.py --themes "在宅ワークの時短術" --total 5
python post_machine.py --themes "テーマA" "テーマB" "テーマC" --total 10
```
生成結果は `drafts_machine/` にJSON（構造化データ）とMarkdown（プレビュー用）で保存されます。
`--post` を付けるとTypefullyにも下書き登録されますが、**公開予約はせず下書きのままにします**
（内容確認は必ず人間が行う想定）。

`comment_1`はデフォルトでは実体験なしの一般化した具体例になります（捏造防止）。実体験を使いたい
場合は `--real-experience` で渡してください（long投稿のスロットに順に割り当てられます。
short投稿では使われません）。
```
python post_machine.py --themes "熱中症・ケガ対策グッズ" --total 5 \
  --real-experience "去年の夏、体育館内が35度近くあり保護者が熱中症でダウンしかけた。塩分タブレットと経口補水液を多めに持っていくようにしたら後半戦でふらついていた選手が回復した。"
```

### 毎日の自動実行（`post_machine_daily_ci.py` / `.github/workflows/post_machine_daily.yml`）

`daily_pipeline.py`（週2回・曜日固定）とは別に、こちらは**毎日 JST 08:00 に自動実行**され、
テーマの選定から生成・Typefully下書き登録・LINE通知までを一気通貫で行います。

- **テーマ**：`theme_bank.json` の`title`を日付でローテーション（10件あるので10日周期）
- **実体験**：`real_experience_bank.json` にその日の日付のメモがあれば使う。なければ
  一般化した例文（`missing_experience_flag: true`）になる
- **投稿数**：環境変数 `POST_MACHINE_DAILY_TOTAL`（未設定なら5件。手動実行(workflow_dispatch)時は
  `total` inputで指定可能）
- **Typefully登録は必ず「下書き」のみ**（`publish_at`を指定しない）。Typefullyの月間公開上限は
  「予約・公開」にのみ適用され下書き登録では消費しないため、生成した分は毎日ぶん登録して構わない。
  **実際に公開するかどうかは人間がTypefully側で選んで操作する**（公開回数の上限管理も人間の役目）
- 生成結果は`drafts_machine/`にコミットされ、LINEに要約が通知される

必要なSecrets（`daily_pipeline.py`と共用可）：`THREADS_GEMINI_API_KEY` / `TYPEFULLY_API_KEY` /
`TYPEFULLY_SOCIAL_SET_ID` /（任意）`LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`。
`RAKUTEN_*`は不要（このツールはアフィリエイト連携をしない）。

## 全SNS横断版: アフィリエイト投稿専用アプリ（`webapp/`, `content_engine.py`）

上記2つはThreads専用だが、こちらは **Threads / Instagram / X / TikTok / note / Brain**
（＋おすすめ追加候補: 自社ブログ・Pinterest・YouTube Shorts）を横断して、楽天アフィリエイト・
Amazonアソシエイトの両方に対応した投稿を生成できる汎用アプリ。

### なぜ媒体ごとにリンクの貼り方を変えるのか（戦略の要点）

媒体によって「本文にリンクを貼るとリーチが落ちる／リンクが貼れない」という制約が異なるため、
`sns_rules.json` に媒体ごとのルールを定義し、`content_engine.py` が生成時にそれを踏まえて
本文とリンク誘導文言を作り分ける。

| 媒体 | リンクの貼り方 | 添付頻度の目安 |
|---|---|---|
| Threads | 本文には貼らず、コメント欄・自己リプライへ誘導 | 4投稿に1回 |
| Instagram | 本文には貼らず、プロフィールリンク（またはストーリーズ）へ誘導 | 4投稿に1回 |
| X | 本文/スレッド末尾に直接貼ってOK（スレッド最後のツイート推奨） | 3投稿に1回 |
| TikTok | 動画内で「プロフィールのリンクから」と誘導。キャプションには貼らない | 6投稿に1回 |
| note | 本文中に直接貼る（noteは記事内リンクが機能する数少ない媒体） | 毎回 |
| Brain | 原則アフィリエイト誘導なし（自社教材販売のCTA先として使う） | 添付しない |
| 自社ブログ（おすすめ） | 本文中に直接貼る。SEOで半永久的に流入するストック資産 | 毎回 |
| Pinterest（おすすめ） | ピンの説明文・リンク先に直接貼る | 毎回 |
| YouTube Shorts（おすすめ） | 概要欄へ誘導 | 5投稿に1回 |

いずれも**ステマ規制対応**として、アフィリエイトを含む投稿には【PR】表記・広告ハッシュタグを付ける
仕様になっている。詳細な理由・貼り方・文章の型は、アプリの「戦略」タブ（`webapp/templates/strategy.html`）
または `sns_rules.json` を参照。

### アプリの4つの画面

1. **戦略**：上記ルールをブラウザで一覧表示（`sns_rules.json`を編集すれば反映される）
2. **単発作成**：媒体・テーマ・実体験・商品（楽天キーワード or AmazonのASIN/URL）を指定して1件だけ生成
3. **SNS選択作成**：媒体を1つ選び、まとめて複数件（最大10件）生成。アフィリエイト添付は頻度ルールで自動判定
4. **毎日自動作成**：本日のテーマ・実体験を使い、全媒体ぶんをまとめて生成（`daily_multi_sns.py`が
   GitHub Actionsで自動実行するのと同じ処理を手動で試せる）

生成結果は `generated_posts/<媒体名>/` にJSON（構造化データ）とMarkdown（プレビュー用）で保存される
（履歴タブから閲覧可能）。**どの媒体もTypefully等への自動投稿は行わず、必ず人間が内容を確認してから
各SNSに手動で投稿する想定**（Threadsのみ、確認後は既存の`typefully_client.py`を使って予約投稿も可能）。

### セットアップ

```
pip install -r requirements.txt
export THREADS_GEMINI_API_KEY=...
python webapp/app.py
# http://127.0.0.1:5000 を開く
```

- 楽天商品を使う場合：`RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` /（任意）`RAKUTEN_AFFILIATE_ID`
- Amazon商品を使う場合：`AMAZON_ASSOCIATE_TAG`（アソシエイトタグ）。Amazon Product Advertising API
  は直近180日で3件以上の紹介実績がないと申請が通らないことが多いため、`amazon_client.py`は
  ASINまたは商品URLからアフィリエイトリンクを組み立てるだけの簡易実装にしてある
  （商品検索はAmazonのSiteStripeツールバー等で行い、そのASIN/URLをアプリに入力する運用）

### 毎日の自動実行（`daily_multi_sns.py` / `.github/workflows/multi_sns_daily.yml`）

毎日 JST 07:00 に全媒体ぶんの投稿を自動生成し、`generated_posts/`にコミット、LINEに要約を通知する。
Secrets（すべて任意。未設定の機能はスキップされる）：
`THREADS_GEMINI_API_KEY`（必須）/ `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID` /
`AMAZON_ASSOCIATE_TAG` / `AFFILIATE_KEYWORD`（設定すると楽天でその日の商品を自動検索して該当投稿に挿入）/
`LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`。

各媒体のアフィリエイト添付頻度は `state/post_counts.json` にカウンタとして保存され、
実行のたびに進む（このファイルもコミット対象）。
