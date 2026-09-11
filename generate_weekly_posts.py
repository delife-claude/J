"""
週間Threads投稿を自動生成するサンプルスクリプト。

前提:
- pip install anthropic
- 環境変数 ANTHROPIC_API_KEY を設定済み
- system_prompt.txt / theme_bank.json を同じディレクトリに配置

使い方:
    python generate_weekly_posts.py

このスクリプトはAPIから投稿JSONを受け取り、weekly_posts.json に保存するところまでを行う。
Typefully等への実際の投稿・下書き登録は post_to_typefully() 内に自分のAPI仕様に合わせて実装すること
（Typefully側の認証キー・エンドポイントはユーザー自身のアカウント設定に依存するため、ここではスタブのみ用意）。
"""

import json
import os
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "system_prompt.txt").read_text(encoding="utf-8")
THEME_BANK = json.loads((BASE_DIR / "theme_bank.json").read_text(encoding="utf-8"))

# 曜日カレンダー（system_prompt.txt内の定義と一致させること。ここを変える場合はプロンプト側も変更する）
WEEKLY_CALENDAR = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から自動取得


def build_user_payload(day: str, week_theme: str, focus_goal: str, real_experience: str) -> str:
    """その曜日用の入力変数をJSON文字列にまとめてユーザーメッセージとして渡す"""
    payload = {
        "day": day,
        "week_theme": week_theme,
        "focus_goal": focus_goal,
        "real_experience": real_experience,
        "theme_bank": THEME_BANK,
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_post_for_day(day: str, week_theme: str, focus_goal: str, real_experience: str) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_user_payload(day, week_theme, focus_goal, real_experience)}
        ],
    )
    raw_text = "".join(block.text for block in message.content if block.type == "text")
    return json.loads(raw_text)


def post_to_typefully(post: dict) -> None:
    """
    TypefullyのドラフトAPIへ登録する処理のスタブ。
    実際のエンドポイント・APIキー・スレッド分割仕様(main_post/comment_1/comment_2をどう繋げるか)は
    Typefully側の最新API仕様に合わせて実装してください。
    ここでは登録内容をログ出力するだけにしています。
    """
    print(f"[STUB] Typefullyへ登録予定: {post['day']} / {post['type_name']} / format={post['format']}")


def main():
    week_theme = input("今週のテーマを入力してください: ").strip()
    focus_goal = input("今週の重点目標 (follower_growth / rakuten_revenue / note_sales): ").strip()

    results = []
    for day in WEEKLY_CALENDAR:
        real_experience = input(f"[{day}] 使える実体験メモがあれば入力（なければ空Enter）: ").strip()
        post = generate_post_for_day(day, week_theme, focus_goal, real_experience)

        if post.get("missing_experience_flag"):
            print(f"⚠️ {day}: 実体験が不足しています。本文中の【ここに体験】部分を埋めてから投稿してください。")

        results.append(post)
        post_to_typefully(post)

    output_path = BASE_DIR / "weekly_posts.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完了: {output_path} に1週間分の投稿を保存しました。")


if __name__ == "__main__":
    main()
