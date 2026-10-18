"""LINE Messaging API (push) で運用者本人だけに実行結果を通知する。

rakuten_room/line_notify.py と同じ仕組み（broadcastではなくpush、userId指定）を
Threadsパイプライン用に流用したもの。LINE公式アカウントのSecretsを共有できる。
"""

import os

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


def notify_failure(name: str, e: Exception) -> None:
    """自動実行が途中で止まったとき、理由をLINEに送る（Typefullyの失敗のように、もう通知済みのものは送らない）"""
    token, user = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"), os.environ.get("LINE_USER_ID")
    if not token or not user or getattr(e, "notified", False):
        return
    text = (f"【{name}】❌ 途中で止まりました\n{type(e).__name__}: {str(e)[:500]}\n"
            "GitHub（delife-claude/J）の Actions で詳しいログが見られます。")
    try:
        send_line_push(text, channel_access_token=token, user_id=user)
    except Exception as e2:  # 通知の失敗で元のエラーを隠さない
        print(f"[warn] 失敗の通知も送れませんでした: {e2}")
