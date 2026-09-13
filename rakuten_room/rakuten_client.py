"""楽天市場 商品検索API（IchibaItem/Search）の薄いラッパー。

これは楽天の公開Web APIで、楽天ROOMへのログインとは無関係。
2026年の楽天API刷新以降、旧エンドポイント(app.rakuten.co.jp)は廃止され、
openapi.rakuten.co.jp + applicationId/accessKeyの組み合わせが必須になった。
アプリ登録: https://webservice.rakuten.co.jp/
"""

import os
import time

import requests

SEARCH_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

# アプリ登録時の「Allowed websites」と一致していないとリクエストが拒否されるため、
# 未設定時はRakuten Developersに登録済みのURLをデフォルトにする。
DEFAULT_ORIGIN = "https://rakutenrev-m3xvgqws.manus.space"


def search_items(
    keyword: str, app_id: str, access_key: str, hits: int = 30, genre_id: str | None = None
) -> list[dict]:
    """指定キーワードで商品検索し、在庫ありの商品のみをRaw dictのリストで返す。

    genre_idを指定すると、その楽天ジャンル配下の商品に絞り込む。キーワードだけだと
    商品名にたまたま含まれる無関係な他競技グッズ（SEO詰め込みタイトル）まで拾って
    しまうため、バレーボールジャンル(201963)を指定して精度を上げるのに使う。
    """
    origin = os.environ.get("RAKUTEN_ALLOWED_ORIGIN", DEFAULT_ORIGIN)
    params = {
        "format": "json",
        "applicationId": app_id,
        "accessKey": access_key,
        "keyword": keyword,
        "hits": hits,
        "availability": 1,  # 在庫ありのみ
        "sort": "-reviewCount",
    }
    if genre_id:
        params["genreId"] = genre_id
    headers = {
        "Origin": origin,
        "Referer": origin,
    }
    resp = requests.get(SEARCH_ENDPOINT, params=params, headers=headers, timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Rakuten API error {resp.status_code} for keyword={keyword!r}: {resp.text}")
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


def search_keywords(
    keywords: list[str],
    app_id: str,
    access_key: str,
    hits_per_keyword: int = 20,
    genre_id: str | None = None,
) -> list[dict]:
    """複数キーワードをまとめて検索し、itemCodeで重複除去した結果を返す。

    楽天APIはレート制限があるため、キーワード間に短いsleepを挟む。
    """
    seen = {}
    for kw in keywords:
        for item in search_items(kw, app_id=app_id, access_key=access_key, hits=hits_per_keyword, genre_id=genre_id):
            code = item.get("itemCode")
            if code and code not in seen:
                seen[code] = item
        time.sleep(1)  # 楽天API レート制限対策
    return list(seen.values())


if __name__ == "__main__":
    app_id = os.environ["RAKUTEN_APP_ID"]
    access_key = os.environ["RAKUTEN_ACCESS_KEY"]
    for it in search_items("バレーボール ジュニア シューズ", app_id=app_id, access_key=access_key, hits=5):
        print(it["itemName"], it["itemPrice"], it["reviewCount"], it["reviewAverage"])
