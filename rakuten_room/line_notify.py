"""LINE Messaging API (broadcast) で下書きを通知する。

LINE Notifyは2025年3月末で終了したため、LINE公式アカウントのbroadcast配信を使う。
このアカウントは通知専用として運用し、自分以外に友だち追加させないこと
（broadcastは友だち全員に届くため）。
"""

import requests

BROADCAST_ENDPOINT = "https://api.line.me/v2/bot/message/broadcast"
MAX_CHARS_PER_MESSAGE = 4500
MAX_MESSAGES_PER_CALL = 5  # LINE Messaging APIの upper bound


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def send_line_broadcast(text: str, channel_access_token: str) -> None:
    chunks = _chunk_text(text, MAX_CHARS_PER_MESSAGE)[:MAX_MESSAGES_PER_CALL]
    messages = [{"type": "text", "text": chunk} for chunk in chunks]

    resp = requests.post(
        BROADCAST_ENDPOINT,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        },
        json={"messages": messages},
        timeout=15,
    )
    resp.raise_for_status()


def build_notification_text(drafts: list[dict]) -> str:
    if not drafts:
        return (
            "【楽天ROOM下書き通知】\n\n"
            "今回は条件（在庫あり・価格上限内・直近未提案）に合うバレーボール関連商品が"
            "見つかりませんでした。"
        )

    lines = ["【楽天ROOM下書き通知】", f"候補 {len(drafts)} 件（内容を確認して自分で投稿してください）", ""]
    for i, d in enumerate(drafts, start=1):
        lines.append(f"■候補{i}: {d['itemName']}")
        lines.append(f"価格: {d['itemPrice']}円 / レビュー{d['reviewCount']}件 平均{d['reviewAverage']}")
        lines.append(d["caption"])
        lines.append(" ".join(d["hashtags"]))
        lines.append(f"商品リンク: {d['itemUrl']}")
        lines.append("")
    return "\n".join(lines).strip()
