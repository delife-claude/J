"""役割③ライティング係。

商品データをClaudeに渡し、ROOM投稿用の紹介文＋ハッシュタグを生成する。
"""

import json
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "room_system_prompt.txt").read_text(encoding="utf-8")

client = anthropic.Anthropic()


def write_caption(item: dict, real_experience: str = "") -> dict:
    payload = {
        "itemName": item["itemName"],
        "itemPrice": item["itemPrice"],
        "shopName": item.get("shopName", ""),
        "reviewCount": item.get("reviewCount", 0),
        "reviewAverage": item.get("reviewAverage", 0.0),
        "real_experience": real_experience,
    }
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw_text = "".join(block.text for block in message.content if block.type == "text")
    return json.loads(raw_text)


def build_drafts(items: list[dict]) -> list[dict]:
    drafts = []
    for item in items:
        caption_data = write_caption(item)
        drafts.append(
            {
                "itemName": item["itemName"],
                "itemPrice": item["itemPrice"],
                "itemUrl": item["itemUrl"],
                "shopName": item.get("shopName", ""),
                "reviewCount": item.get("reviewCount", 0),
                "reviewAverage": item.get("reviewAverage", 0.0),
                "caption": caption_data["caption"],
                "hashtags": caption_data["hashtags"],
            }
        )
    return drafts
