"""Gemini 呼び出しの共通部分（Threads投稿マシーン・Threads自動投稿・楽天ROOMの3つで共有。2026-10-18）

- 5xx（混雑）と 429 の「1分あたりの上限」は、待ってから同じモデルで再試行する
- 429 の「1日の上限」・モデルが使えない（404など）は、次のモデルに切り替える（無料枠はモデルごとに別）
- 返事が空・JSONが壊れているときも再試行する
"""
from __future__ import annotations

import json
import os
import time

from google import genai
from google.genai import errors, types

MODELS = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
ATTEMPTS = 3
WAIT_SECONDS = 15

_clients: dict[str, genai.Client] = {}


class GeminiFailed(RuntimeError):
    pass


def _per_minute_limit(e: errors.ClientError) -> bool:
    s = str(e).lower()
    return e.code == 429 and "perday" not in s and "per day" not in s


def generate_json(api_key_env: str, system: str, contents: str, max_output_tokens: int = 8192) -> dict:
    if api_key_env not in _clients:
        _clients[api_key_env] = genai.Client(api_key=os.environ[api_key_env])
    client = _clients[api_key_env]
    last: Exception | None = None
    for model in MODELS:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                r = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        max_output_tokens=max_output_tokens,
                    ),
                )
                # strict=False: 本文中の改行が生の制御文字のまま返ることがあるため
                return json.loads(r.text or "", strict=False)
            except errors.ServerError as e:
                last = e
            except errors.ClientError as e:
                last = e
                if not _per_minute_limit(e):
                    break  # 1日の上限・モデルなし・リクエスト不正 → 次のモデルへ
            except ValueError as e:  # 空の返事・壊れたJSON
                last = e
            if attempt < ATTEMPTS:
                time.sleep(WAIT_SECONDS * attempt)
        print(f"[warn] {model} で作れませんでした: {str(last)[:200]}")
    raise GeminiFailed(f"Geminiで作れませんでした（最後のエラー: {str(last)[:300]}）")
