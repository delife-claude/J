"""post_machine.py のCI自動実行版。GitHub Actionsから毎日呼ばれる想定。

daily_pipeline.py（曜日固定カレンダー版）とは別に、post_machine.py（汎用テーマ版）を
毎日自動で回すための薄いラッパー。

やること:
  1. theme_bank.json からその日のテーマを選ぶ（日付でローテーション。10件あるので10日周期）
  2. real_experience_bank.json にその日の実体験があれば読み込む（空でも動く。空の場合は
     post_machine_system_prompt.txt のルールに従い一般化した例文になり、
     missing_experience_flag が立つ。捏造防止のための安全弁）
  3. POST_MACHINE_DAILY_TOTAL件（デフォルト5件）を post_machine.py の比率ルール
     （長文:短文 ≒ 4:1）で生成する
  4. 生成結果を drafts_machine/ に保存する
  5. 全件をTypefullyに「下書き」として登録する（公開予約はしない）
     Typefullyの月間公開上限は「予約/公開」にのみ適用され、下書き登録だけなら消費しない
     ため、生成した分は毎日全部下書きに残せる。実際に公開するかどうかは人間が
     Typefully側で選んで操作する
  6. LINEに「今日の下書きが準備できました」という要約を通知する

事前準備: pip install -r requirements.txt
必要な環境変数: THREADS_GEMINI_API_KEY, TYPEFULLY_API_KEY, TYPEFULLY_SOCIAL_SET_ID,
（任意）LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID, POST_MACHINE_DAILY_TOTAL（未設定なら5）
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from post_machine import compute_long_short_counts, generate_daily_batch, save_batch
from notify import send_line_push

BASE_DIR = Path(__file__).parent
JST = timezone(timedelta(hours=9))


def today_jst() -> datetime:
    return datetime.now(JST)


def pick_theme(dt: datetime) -> str:
    """theme_bank.json のtitleを日付でローテーションして選ぶ。"""
    bank = json.loads((BASE_DIR / "theme_bank.json").read_text(encoding="utf-8"))
    titles = [item["title"] for item in bank]
    return titles[dt.timetuple().tm_yday % len(titles)]


def load_real_experience(dt: datetime) -> str:
    path = BASE_DIR / "real_experience_bank.json"
    if not path.exists():
        return ""
    bank = json.loads(path.read_text(encoding="utf-8"))
    return bank.get(dt.strftime("%Y-%m-%d"), "")


def post_all_as_drafts(posts: list[dict], dt: datetime) -> list[dict]:
    """全件をTypefullyの下書き（公開予約なし）として登録する。"""
    from typefully_client import create_scheduled_draft

    results = []
    for post in posts:
        parts = [post["main_post"]]
        if post["kind"] == "long":
            parts += [post.get("comment_1") or "", post.get("comment_2") or ""]
        parts = [p for p in parts if p]

        hashtags = post.get("hashtags") or []
        if hashtags:
            parts[-1] = parts[-1] + "\n\n" + " ".join(hashtags)

        title = f"{dt.strftime('%Y-%m-%d')} [{post['kind']}] {post.get('theme', '')}"[:100]
        result = create_scheduled_draft(posts=parts, publish_at_iso=None, draft_title=title)
        results.append({"title": title, "id": result.get("id", "不明")})
    return results


def main() -> None:
    dt = today_jst()
    total = int(os.environ.get("POST_MACHINE_DAILY_TOTAL") or "5")
    theme = pick_theme(dt)
    real_experience = load_real_experience(dt)

    long_count, short_count = compute_long_short_counts(total)
    posts = generate_daily_batch(
        [theme], total, real_experiences=[real_experience] if real_experience else None
    )

    out_path = save_batch(posts, BASE_DIR / "drafts_machine")
    print(f"生成結果を {out_path} に保存しました。")

    typefully_error: Exception | None = None
    try:
        post_all_as_drafts(posts, dt)
    except Exception as e:  # LINE通知まで止まらないようにする
        typefully_error = e

    summary_lines = [
        f"【Threads投稿マシーン】{dt.strftime('%Y-%m-%d')}",
        f"テーマ: {theme}",
        f"長文{long_count}件・短文{short_count}件をTypefullyに下書き登録しました。",
        "※公開予約はしていません。内容を確認してTypefully側で手動公開してください。",
        "",
    ]
    for i, post in enumerate(posts, start=1):
        flag = "（⚠️実体験なし・一般化した例文）" if post.get("missing_experience_flag") else ""
        summary_lines.append(f"{i}. [{post['kind']}]{flag}")
    if typefully_error:
        summary_lines.append(
            f"\n❌ Typefullyへの登録に失敗しました: {typefully_error}\n"
            "本文は drafts_machine/ に保存済みなので手動でご確認ください。"
        )

    notification = "\n".join(summary_lines)
    print(notification)

    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    if line_token and line_user_id:
        send_line_push(notification, channel_access_token=line_token, user_id=line_user_id)
    else:
        print("[warn] LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定のため通知をスキップしました。")

    if typefully_error:
        raise typefully_error  # LINE通知は届けたうえで、ジョブ自体は失敗として扱う


if __name__ == "__main__":
    main()
