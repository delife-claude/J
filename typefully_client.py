"""Typefully APIのクライアント(下書き作成 + 予約投稿)。役割④投稿オペレーターの実体。

Typefully API v1はAPIキー認証が廃止されており(実行時に
"API v1 access via API keys is disabled. Please update your integration to API v2"
というエラーで判明)、v2エンドポイントを使う必要がある。
Typefullyは公式にThreadsアカウントとの連携をサポートしており、ここで作成した下書きは
Typefully側でThreadsアカウントに接続済みであれば、そのままThreadsに投稿される。
楽天ROOMと違い、ブラウザログインの自動化(規約違反リスク)は不要。
"""
from __future__ import annotations

import os
import requests

# v2のエンドポイント(公式ドキュメント https://typefully.com/docs/api で確認済み)。
# social_set_idはリクエストボディではなくURLパスに入れる。認証は Authorization: Bearer のみ。
DRAFTS_ENDPOINT = "https://api.typefully.com/v2/social-sets/{social_set_id}/drafts"


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
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
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

    url = DRAFTS_ENDPOINT.format(social_set_id=sid)
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if not resp.ok:
        print(f"[warn] {url} -> {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()
