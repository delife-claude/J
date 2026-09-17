"""Amazonアソシエイト用の薄いリンクビルダー。

Amazon Product Advertising API (PA-API) は「直近180日で3件以上の紹介実績」がないと
利用申請が通らない/使えなくなる仕様のため、立ち上げ初期は使えないことが多い。
そのため商品検索は行わず、ASIN（またはAmazon商品URL）とアソシエイトタグから
成果測定可能なアフィリエイトリンクを組み立てるだけの実装にしている。

商品検索が必要な場合は、Amazonの商品ページを開いて「Amazonアソシエイト・SiteStripe」
ツールバーから直接リンクを発行する運用でも構わない（このモジュールはCLI/自動生成用の補助）。
"""
from __future__ import annotations

import re

ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")


def extract_asin(url_or_asin: str) -> str | None:
    """Amazon商品URL、またはASINそのものからASINを取り出す。"""
    candidate = url_or_asin.strip()
    if re.fullmatch(r"[A-Z0-9]{10}", candidate):
        return candidate
    match = ASIN_RE.search(candidate)
    return match.group(1) if match else None


def build_affiliate_link(url_or_asin: str, associate_tag: str) -> str | None:
    """ASINまたは商品URLとアソシエイトタグから成果測定リンクを作る。"""
    asin = extract_asin(url_or_asin)
    if not asin or not associate_tag:
        return None
    return f"https://www.amazon.co.jp/dp/{asin}?tag={associate_tag}"


if __name__ == "__main__":
    import os
    import sys

    tag = os.environ.get("AMAZON_ASSOCIATE_TAG", "")
    if len(sys.argv) < 2:
        print("usage: python amazon_client.py <ASIN or amazon.co.jp URL>")
    else:
        print(build_affiliate_link(sys.argv[1], tag))
