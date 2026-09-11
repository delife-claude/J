"""楽天市場 商品検索API（IchibaItem/Search）の薄いラッパー。

これは楽天の公開Web APIで、楽天ROOMへのログインとは無関係。
アプリID登録: https://webservice.rakuten.co.jp/
"""

import os
import time

import requests

SEARCH_ENDPOINT = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"


def search_items(keyword: str, app_id: str, hits: int = 30) -> list[dict]:
    """指定キーワードで商品検索し、在庫ありの商品のみをRaw dictのリストで返す。"""
    params = {
        "format": "json",
        "applicationId": app_id,
        "keyword": keyword,
        "hits": hits,
        "availability": 1,  # 在庫ありのみ
        "sort": "-reviewCount",
    }
    resp = requests.get(SEARCH_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = []
    for wrapped in data.get("Items", []):
        item = wrapped.get("Item", {})
        if not item:
            continue
        items.append(
            {
                "itemCode": item.get("itemCode"),
                "itemName": item.get("itemName"),
                "itemPrice": item.get("itemPrice"),
                "itemUrl": item.get("itemUrl"),
                "shopName": item.get("shopName"),
                "reviewCount": item.get("reviewCount", 0),
                "reviewAverage": item.get("reviewAverage", 0.0),
                "availability": item.get("availability", 0),
            }
        )
    return items


def search_keywords(keywords: list[str], app_id: str, hits_per_keyword: int = 20) -> list[dict]:
    """複数キーワードをまとめて検索し、itemCodeで重複除去した結果を返す。

    楽天APIはレート制限があるため、キーワード間に短いsleepを挟む。
    """
    seen = {}
    for kw in keywords:
        for item in search_items(kw, app_id=app_id, hits=hits_per_keyword):
            code = item.get("itemCode")
            if code and code not in seen:
                seen[code] = item
        time.sleep(1)  # 楽天API レート制限対策
    return list(seen.values())


if __name__ == "__main__":
    app_id = os.environ["RAKUTEN_APP_ID"]
    for it in search_items("バレーボール ジュニア シューズ", app_id=app_id, hits=5):
        print(it["itemName"], it["itemPrice"], it["reviewCount"], it["reviewAverage"])
