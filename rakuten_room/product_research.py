"""役割②商品リサーチ係。

バレーボール関連キーワードで楽天市場を検索し、
- 在庫なし
- 価格が高すぎる（MAX_PRICE超え）
- 直近で提案済み（history.json）
を除外したうえで、レビュー実績スコアの高い順に候補を返す。
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rakuten_client import search_keywords

BASE_DIR = Path(__file__).parent
KEYWORDS = json.loads((BASE_DIR / "volleyball_keywords.json").read_text(encoding="utf-8"))
HISTORY_PATH = BASE_DIR / "history.json"
HISTORY_RETENTION_DAYS = 14

# 楽天市場の「バレーボール」ジャンル。これで絞らないと、商品名にバレーボールを
# 含むだけの無関係な他競技グッズ（SEO詰め込みタイトル）まで拾ってしまう。
GENRE_ID = "201963"

JST = timezone(timedelta(hours=9))


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(history: list[dict]) -> None:
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def prune_history(history: list[dict]) -> list[dict]:
    cutoff = datetime.now(JST) - timedelta(days=HISTORY_RETENTION_DAYS)
    kept = []
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry["suggested_at"])
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            kept.append(entry)
    return kept


def score(item: dict) -> float:
    review_count = item.get("reviewCount") or 0
    review_average = item.get("reviewAverage") or 0.0
    return review_count * review_average


def find_candidates(app_id: str, access_key: str, max_price: int, top_n: int = 5) -> list[dict]:
    history = prune_history(load_history())
    recent_codes = {entry["itemCode"] for entry in history}

    raw_items = search_keywords(KEYWORDS, app_id=app_id, access_key=access_key, genre_id=GENRE_ID)

    filtered = [
        item
        for item in raw_items
        if item.get("availability") == 1
        and item.get("itemPrice") is not None
        and item["itemPrice"] <= max_price
        and item.get("itemCode") not in recent_codes
    ]
    filtered.sort(key=score, reverse=True)
    return filtered[:top_n]


def record_suggested(items: list[dict]) -> None:
    history = prune_history(load_history())
    now = datetime.now(JST).isoformat()
    for item in items:
        history.append({"itemCode": item["itemCode"], "itemName": item["itemName"], "suggested_at": now})
    save_history(history)


if __name__ == "__main__":
    app_id = os.environ["RAKUTEN_APP_ID"]
    access_key = os.environ["RAKUTEN_ACCESS_KEY"]
    max_price = int(os.environ.get("MAX_PRICE") or "8000")
    candidates = find_candidates(app_id, access_key, max_price)
    for c in candidates:
        print(c["itemName"], c["itemPrice"], c["reviewCount"], c["reviewAverage"])
