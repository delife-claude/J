"""役割③ライティング係。

商品データをGemini APIに渡し、ROOM投稿用の紹介文＋ハッシュタグを生成する。
"""

import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "room_system_prompt.txt").read_text(encoding="utf-8")
MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 10

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def write_caption(item: dict, real_experience: str = "") -> dict:
    payload = {
        "itemName": item["itemName"],
        "itemPrice": item["itemPrice"],
        "shopName": item.get("shopName", ""),
        "reviewCount": item.get("reviewCount", 0),
        "reviewAverage": item.get("reviewAverage", 0.0),
        "real_experience": real_experience,
    }
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                ),
            )
            return json.loads(response.text)
        except errors.ServerError:
            # Geminiが混雑時に返す一時的な5xx。指数バックオフしてリトライする。
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(RETRY_WAIT_SECONDS * attempt)


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
