# このリポジトリについて

子どもバレーグッズアカウントの運用を自動化する「AI従業員」システム。組織図の5つの係を
コード（Gemini API + 各種SNS/EC API + GitHub Actions）で実装している。

2つの独立したパイプラインがあり、投稿先ごとに自動化の範囲が異なる：

| パイプライン | 投稿先 | 実行場所 | 自動投稿まで実装？ |
|---|---|---|---|
| ルート直下（`daily_pipeline.py`ほか） | Threads（Typefully経由） | `.github/workflows/threads_daily.yml`（水・金18:00 JST） | する（Typefully公式APIで予約投稿） |
| `rakuten_room/` | 楽天ROOM | `.github/workflows/rakuten_room_daily.yml`（毎日8:00/13:00/20:00 JST） | しない（下書き＋LINE通知までで、投稿ボタンは人間が押す） |

各パイプラインの詳細（組織図との対応表、セットアップ手順、必要なSecrets）は
`README.md` と `rakuten_room/README.md` を参照。

## 変更するときに必ず守ること

1. **楽天ROOMへの自動投稿を実装しない。** 楽天ROOMの利用規約は機械的な投稿を禁止している。
   `rakuten_room/`側に「ブラウザにログインして投稿する」ような機能を追加しない。
2. **実体験の捏造をしない。** `system_prompt.txt` / `room_system_prompt.txt` のルールで、
   実体験（`real_experience`）が空のときは一人称の体験談を生成させない仕様になっている。
   このロジックを緩めない。
3. **ステマ規制対応を外さない。** アフィリエイトリンクを含む投稿には `【PR】` と `#PR #広告` を
   自動付与している（`daily_pipeline.py` の `compose_posts()`）。
4. **Typefullyの月間公開上限に注意。** Threads側は「実測10回/月」の上限に収めるため週2回
   （水・金）に間引いている。cronの頻度を上げる場合はTypefully側のプラン上限を先に確認する。
5. **APIキーはハードコードしない。** すべて環境変数 / GitHub Secretsで受け渡す
   （`.env.example` / `rakuten_room/.env.example` 参照）。

## よくある作業

- 投稿ジャンル・トーンを変える → `system_prompt.txt` と `room_system_prompt.txt` の両方を
  同じ方針に揃える（片方だけ変えると2アカウントでトーンがずれる）。
- 商品検索キーワードを変える → `volleyball_keywords.json`（ルート）と
  `rakuten_room/volleyball_keywords.json` は別ファイルなので両方編集する。
- 投稿頻度を変える → `.github/workflows/*.yml` の `cron` を編集（曜日番号: 0=日〜6=土、UTC表記）。
- ローカルで動作確認する → 各READMEの「動作確認」セクションの `--dry-run` / `workflow_dispatch`
  手順に従う。実APIキーがないと最後まで実行できない箇所（Gemini/楽天/Typefully/LINE）がある。
