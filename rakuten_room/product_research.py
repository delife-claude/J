"""役割②商品リサーチ係。

バレーボール関連キーワードで楽天市場を検索し、
- 在庫なし
- 価格が高すぎる（MAX_PRICE超え）
- 直近で提案済み（history.json。商品は60日、お店は7日）
を除外したうえで、キーワードごとにレビュー実績スコアのいちばん高い1つを選ぶ（2026-10-18〜）。
キーワードは1回ごとに6個ずつ順番に回すので、毎回ちがうジャンルの商品になる（前は全キーワードの上位3つで、毎回似ていた）。
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rakuten_client import search_keywords

BASE_DIR = Path(__file__).parent
KEYWORDS = json.loads((BASE_DIR / "volleyball_keywords.json").read_text(encoding="utf-8"))
HISTORY_PATH = BASE_DIR / "history.json"
HISTORY_RETENTION_DAYS = 60
SHOP_COOLDOWN_DAYS = 7
KEYWORDS_PER_RUN = 6

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


def rotated_keywords(now: float | None = None) -> list[str]:
    """8時間ごと（1日3回の実行ごと）に、次の KEYWORDS_PER_RUN 個のキーワードへ進む"""
    run = int((time.time() if now is None else now) // (8 * 3600))
    off = run * KEYWORDS_PER_RUN % len(KEYWORDS)
    return (KEYWORDS[off:] + KEYWORDS[:off])[:KEYWORDS_PER_RUN]


def pick(items: list[dict], history: list[dict], keywords: list[str], max_price: int, top_n: int) -> list[dict]:
    recent_codes = {e["itemCode"] for e in history}
    cut = datetime.now(JST) - timedelta(days=SHOP_COOLDOWN_DAYS)
    recent_shops = {e.get("shopName") for e in history if e.get("shopName") and datetime.fromisoformat(e["suggested_at"]) >= cut}
    ok = [
        i for i in items
        if i.get("availability") == 1 and i.get("itemPrice") is not None and i["itemPrice"] <= max_price
        and i.get("itemCode") not in recent_codes and i.get("shopName") not in recent_shops
    ]
    picked, shops = [], set()
    for kw in keywords:  # キーワードごとに1つ、同じお店は1回に1つまで
        best = max((i for i in ok if i.get("keyword") == kw and i.get("shopName") not in shops), key=score, default=None)
        if best:
            picked.append(best)
            shops.add(best.get("shopName"))
        if len(picked) == top_n:
            break
    return picked


def find_candidates(app_id: str, access_key: str, max_price: int, top_n: int = 5) -> list[dict]:
    history = prune_history(load_history())
    keywords = rotated_keywords()
    raw_items = search_keywords(keywords, app_id=app_id, access_key=access_key, genre_id=GENRE_ID)
    return pick(raw_items, history, keywords, max_price, top_n)


def record_suggested(items: list[dict]) -> None:
    history = prune_history(load_history())
    now = datetime.now(JST).isoformat()
    for item in items:
        history.append({"itemCode": item["itemCode"], "itemName": item["itemName"], "shopName": item.get("shopName", ""), "suggested_at": now})
    save_history(history)


if __name__ == "__main__":
    app_id = os.environ["RAKUTEN_APP_ID"]
    access_key = os.environ["RAKUTEN_ACCESS_KEY"]
    max_price = int(os.environ.get("MAX_PRICE") or "8000")
    candidates = find_candidates(app_id, access_key, max_price)
    for c in candidates:
        print(c["itemName"], c["itemPrice"], c["reviewCount"], c["reviewAverage"])
