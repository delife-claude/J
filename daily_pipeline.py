"""役割④⑤の実体（Threads版）。GitHub Actionsから1日1回(18:00 JST)呼ばれる想定。

やること:
  1. 今日の曜日に応じた投稿を生成（Claude API, generate_weekly_posts.py の system_prompt.txt ルールに従う）
  2. cta_target=rakuten の日は楽天市場APIで商品を検索し、アフィリエイトリンクを埋め込む
  3. 実体験が空 / 商品が見つからない場合は自動投稿せず、Typefullyには下書きのみ登録してLINEで通知
     （捏造防止・壊れたリンクでの公開を防ぐため。room_system_prompt.txt と同じ思想）
  4. それ以外は Typefully に本日18:00(JST)投稿予約として登録し、LINEにも念のため通知する
     （何かおかしければ Typefully 側で投稿前にキャンセル・編集できるようにするため）

事前準備: pip install -r requirements.txt
必要な環境変数は .env.example を参照。
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generate_weekly_posts import generate_post_for_day
from rakuten_client import search_keywords
from typefully_client import create_scheduled_draft
from notify import send_line_push

BASE_DIR = Path(__file__).parent
JST = timezone(timedelta(hours=9))

WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# 週替りテーマのローテーション。ISO週番号で割って選ぶので、同じ週は同じテーマになる。
WEEK_THEMES = [
    "自主練グッズの選び方",
    "レギュラーを掴むための基礎作り",
    "保護者ができるサポートの工夫",
    "熱中症・ケガ対策グッズ",
    "進路選びで後悔しないために",
    "道具選びの失敗あるある",
]


def today_jst() -> datetime:
    return datetime.now(JST)


def pick_week_theme(dt: datetime) -> str:
    week_num = dt.isocalendar()[1]
    return WEEK_THEMES[week_num % len(WEEK_THEMES)]


def load_real_experience(dt: datetime) -> str:
    path = BASE_DIR / "real_experience_bank.json"
    if not path.exists():
        return ""
    bank = json.loads(path.read_text(encoding="utf-8"))
    return bank.get(dt.strftime("%Y-%m-%d"), "")


def fetch_rakuten_product() -> dict | None:
    app_id = os.environ.get("RAKUTEN_APP_ID")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID")
    if not app_id or not access_key:
        return None

    keywords = json.loads((BASE_DIR / "volleyball_keywords.json").read_text(encoding="utf-8"))
    max_price = int(os.environ.get("MAX_PRICE") or "8000")

    items = search_keywords(
        keywords, app_id=app_id, access_key=access_key, affiliate_id=affiliate_id, hits_per_keyword=10
    )
    items = [i for i in items if i.get("itemPrice") and i["itemPrice"] <= max_price]
    items.sort(key=lambda i: (i.get("reviewCount") or 0) * (i.get("reviewAverage") or 0), reverse=True)
    return items[0] if items else None


def compose_full_text(post: dict, product: dict | None) -> tuple[str, bool]:
    """生成結果からThreads投稿用の最終テキストを組み立てる。

    戻り値: (本文, ok_to_auto_post)
    ok_to_auto_post が False の場合、本文に未完成の穴（体験談プレースホルダーや
    埋まっていないアフィリエイトリンク）が残っている可能性があるので自動投稿しない。
    """
    hashtags = list(post.get("hashtags") or [])
    cta = post.get("cta_target")
    missing = bool(post.get("missing_experience_flag"))

    main_post = post["main_post"]
    comment_1 = post.get("comment_1") or ""
    comment_2 = post.get("comment_2") or ""

    if cta == "rakuten":
        if product:
            comment_2 = comment_2.replace("{AFFILIATE_LINK}", product["affiliateUrl"])
        else:
            missing = True  # プレースホルダーが埋まらないので自動投稿NG
        main_post = "【PR】\n" + main_post
        hashtags += ["#PR", "#広告"]

    parts = [main_post]
    if post["format"] == "long":
        parts += [comment_1, comment_2]

    full_text = "\n\n\n\n".join(p for p in parts if p)
    if hashtags:
        full_text += "\n\n\n\n" + " ".join(hashtags)

    return full_text, not missing


def next_18_00_jst_as_utc_iso() -> str:
    now = today_jst()
    target = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if target < now:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Typefully/LINEへは送信せず、生成結果を表示するだけ"
    )
    args = parser.parse_args()

    dt = today_jst()
    day = WEEKDAY_NAMES[dt.weekday()]
    week_theme = pick_week_theme(dt)
    real_experience = load_real_experience(dt)
    focus_goal = os.environ.get("FOCUS_GOAL", "rakuten_revenue")

    post = generate_post_for_day(day, week_theme, focus_goal, real_experience)

    product = None
    if post.get("cta_target") == "rakuten":
        try:
            product = fetch_rakuten_product()
        except Exception as e:  # 楽天API障害等で全体を落とさない
            print(f"[warn] 楽天商品取得に失敗: {e}")
            product = None

    full_text, ok_to_auto_post = compose_full_text(post, product)

    drafts_dir = BASE_DIR / "drafts"
    drafts_dir.mkdir(exist_ok=True)
    timestamp = dt.strftime("%Y-%m-%d_%H%M")
    (drafts_dir / f"{timestamp}_{day}.md").write_text(full_text, encoding="utf-8")

    print(f"=== {dt.strftime('%Y-%m-%d')} ({day} / {post.get('type_name')} / {post.get('format')}) ===")
    print(full_text)
    print(f"\nok_to_auto_post: {ok_to_auto_post}")

    if args.dry_run:
        print("\n[dry-run] Typefully/LINEへの送信はスキップしました。")
        return

    if ok_to_auto_post:
        schedule_iso = next_18_00_jst_as_utc_iso()
        result = create_scheduled_draft(content=full_text, schedule_date_iso=schedule_iso)
        status_line = f"✅ Typefullyに予約投稿しました（{schedule_iso} 公開予定 / draft_id={result.get('id', '不明')}）"
    else:
        create_scheduled_draft(content=full_text, schedule_date_iso=None)
        status_line = (
            "⚠️ 実体験が未入力、または商品候補が見つからなかったため自動投稿はスキップしました。\n"
            "real_experience_bank.json に今日の日付で体験を追記するか、Typefullyの下書きを確認して"
            "手動で仕上げてから投稿/予約してください。"
        )

    notification = f"【Threads自動投稿】{dt.strftime('%Y-%m-%d')}({day})\n\n{status_line}\n\n---\n{full_text}"

    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    if line_token and line_user_id:
        send_line_push(notification, channel_access_token=line_token, user_id=line_user_id)


if __name__ == "__main__":
    main()
