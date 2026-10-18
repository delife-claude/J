"""役割③ライティング係。

商品データをGemini APIに渡し、ROOM投稿用の紹介文＋ハッシュタグを生成する。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 共通の gemini_util（リポジトリの直下）
from gemini_util import generate_json  # noqa: E402

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "room_system_prompt.txt").read_text(encoding="utf-8")



def write_caption(item: dict, real_experience: str = "") -> dict:
    payload = {
        "itemName": item["itemName"],
        "itemPrice": item["itemPrice"],
        "shopName": item.get("shopName", ""),
        "reviewCount": item.get("reviewCount", 0),
        "reviewAverage": item.get("reviewAverage", 0.0),
        "real_experience": real_experience,
    }
    data = generate_json("GEMINI_API_KEY", SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))  # 再試行・モデル切り替えは gemini_util
    # ROOMは商品ページが自動で付くので、本文にリンクの誘導は要らない。プレースホルダーが残ったらその文ごと消す
    if "{AFFILIATE_LINK}" in data.get("caption", ""):
        data["caption"] = "".join(x for x in re.split(r"(?<=。)", data["caption"]) if "{AFFILIATE_LINK}" not in x).strip()
    return data


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
