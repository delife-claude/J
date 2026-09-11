"""LINE Messaging API (push) で運用者本人だけに実行結果を通知する。

rakuten_room/line_notify.py と同じ仕組み（broadcastではなくpush、userId指定）を
Threadsパイプライン用に流用したもの。LINE公式アカウントのSecretsを共有できる。
"""

import requests

PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
MAX_CHARS_PER_MESSAGE = 4500
MAX_MESSAGES_PER_CALL = 5  # LINE Messaging APIの upper bound


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def send_line_push(text: str, channel_access_token: str, user_id: str) -> None:
    chunks = _chunk_text(text, MAX_CHARS_PER_MESSAGE)[:MAX_MESSAGES_PER_CALL]
    messages = [{"type": "text", "text": chunk} for chunk in chunks]

    resp = requests.post(
        PUSH_ENDPOINT,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        },
        json={"to": user_id, "messages": messages},
        timeout=15,
    )
    resp.raise_for_status()
