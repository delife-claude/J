"""Typefully APIのシンプルなクライアント(下書き作成 + 予約投稿)。役割④投稿オペレーターの実体。

公式仕様: https://support.typefully.com/en/articles/8718287-typefully-api
Typefullyは公式にThreadsアカウントとの連携をサポートしており、ここで作成した下書きは
Typefully側でThreadsアカウントに接続済みであれば、そのままThreadsに投稿される。
楽天ROOMと違い、ブラウザログインの自動化(規約違反リスク)は不要。

※実行環境のネットワーク制限により、このコードは公式ドキュメントを実地確認せずに実装した。
  初回実行前に、公式ドキュメントでエンドポイント/パラメータ名が変わっていないか確認すること。
"""
from __future__ import annotations

import os
import requests

API_BASE = "https://api.typefully.com/v1"


def create_scheduled_draft(
    content: str,
    schedule_date_iso: str | None,
    threadify: bool = False,
    api_key: str | None = None,
) -> dict:
    """下書きを作成する。schedule_date_iso を指定すると、その日時に自動投稿されるよう予約する。

    schedule_date_iso: 例 "2026-09-11T09:00:00Z" (UTC)。None を渡すと予約せず下書きのまま残す
    （missing_experience_flagが立っている投稿など、人間の確認が必要な場合に使う）。
    """
    key = api_key or os.environ["TYPEFULLY_API_KEY"]
    headers = {
        "X-API-KEY": key,
        "Content-Type": "application/json",
    }
    payload = {
        "content": content,
        "threadify": threadify,
    }
    if schedule_date_iso:
        payload["schedule-date"] = schedule_date_iso

    resp = requests.post(f"{API_BASE}/drafts/", json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()
