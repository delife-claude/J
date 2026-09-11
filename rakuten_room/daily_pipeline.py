"""役割⑤スケジュール管理係の実体。GitHub Actionsから1日3回呼ばれる想定。

やること: ②商品リサーチ → ③紹介文生成 → drafts/に保存 → LINEに通知。
やらないこと: 楽天ROOMへのログイン・投稿（規約上の理由により実装しない）。
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from product_research import find_candidates, record_suggested
from write_captions import build_drafts
from line_notify import build_notification_text, send_line_broadcast

BASE_DIR = Path(__file__).parent
DRAFTS_DIR = BASE_DIR / "drafts"
JST = timezone(timedelta(hours=9))


def main():
    app_id = os.environ["RAKUTEN_APP_ID"]
    access_key = os.environ["RAKUTEN_ACCESS_KEY"]
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    max_price = int(os.environ.get("MAX_PRICE") or "8000")

    candidates = find_candidates(app_id=app_id, access_key=access_key, max_price=max_price, top_n=5)
    drafts = build_drafts(candidates) if candidates else []

    DRAFTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(JST).strftime("%Y-%m-%d_%H%M")
    draft_path = DRAFTS_DIR / f"{timestamp}.md"

    if drafts:
        lines = [f"# 楽天ROOM 下書き ({timestamp} JST)\n"]
        for i, d in enumerate(drafts, start=1):
            lines.append(f"## 候補{i}: {d['itemName']}")
            lines.append(f"- 価格: {d['itemPrice']}円")
            lines.append(f"- レビュー: {d['reviewCount']}件 / 平均{d['reviewAverage']}")
            lines.append(f"- リンク: {d['itemUrl']}")
            lines.append(f"- 紹介文: {d['caption']}")
            lines.append(f"- ハッシュタグ: {' '.join(d['hashtags'])}")
            lines.append("")
        draft_path.write_text("\n".join(lines), encoding="utf-8")
        record_suggested(candidates)
    else:
        draft_path.write_text(f"# 楽天ROOM 下書き ({timestamp} JST)\n\n候補なし\n", encoding="utf-8")

    notification_text = build_notification_text(drafts)
    send_line_broadcast(notification_text, channel_access_token=line_token)
    print(notification_text)


if __name__ == "__main__":
    main()
