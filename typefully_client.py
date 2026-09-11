"""Typefully APIのクライアント(下書き作成 + 予約投稿)。役割④投稿オペレーターの実体。

2026年9月時点の実際のTypefully API(MCP経由で実地確認済み)は、単純な文字列連結ではなく
プラットフォームごとに投稿を配列で渡す構造になっている。
Typefullyは公式にThreadsアカウントとの連携をサポートしており、ここで作成した下書きは
Typefully側でThreadsアカウントに接続済みであれば、そのままThreadsに投稿される。
楽天ROOMと違い、ブラウザログインの自動化(規約違反リスク)は不要。

※このモジュールのエンドポイント/認証ヘッダーはネットワーク制限のある環境で実地確認せず
  実装した(MCPツール経由での構造確認はできたが、生のHTTPリクエスト形式は未検証)。
  初回実行が失敗する場合は、公式ドキュメント
  (https://support.typefully.com/en/articles/8718287-typefully-api) で
  エンドポイントURL・認証ヘッダー名を確認すること。
"""
from __future__ import annotations

import os
import requests

API_BASE = "https://api.typefully.com/v1"


def create_scheduled_draft(
    posts: list[str],
    social_set_id: int | None = None,
    publish_at_iso: str | None = None,
    draft_title: str | None = None,
    api_key: str | None = None,
) -> dict:
    """Threadsの下書き(スレッド)を作成する。

    posts: スレッドを構成する各投稿のテキスト。[main_post, comment_1, comment_2] のように渡すと
           Threads上でメイン投稿への返信として連結される。
    publish_at_iso: 例 "2026-09-11T09:00:00Z" (UTC)。指定するとその日時に自動投稿される。
                     None を渡すと予約せず下書きのまま残す
                     （missing_experience_flagが立っている投稿など、人間の確認が必要な場合に使う）。
    social_set_id: 投稿先のTypefullyアカウント(social set)のID。未指定なら環境変数から取得。
    """
    key = api_key or os.environ["TYPEFULLY_API_KEY"]
    sid = social_set_id or int(os.environ["TYPEFULLY_SOCIAL_SET_ID"])

    headers = {
        "X-API-KEY": key,
        "Content-Type": "application/json",
    }
    payload = {
        "social_set_id": sid,
        "platforms": {
            "threads": {
                "enabled": True,
                "posts": [{"text": p} for p in posts],
            }
        },
    }
    if draft_title:
        payload["draft_title"] = draft_title
    if publish_at_iso:
        payload["publish_at"] = publish_at_iso

    resp = requests.post(f"{API_BASE}/drafts/", json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()
