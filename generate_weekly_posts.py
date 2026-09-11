"""
週間Threads投稿を自動生成するサンプルスクリプト。

前提:
- pip install -r requirements.txt (google-genai / requests)
- 環境変数 GEMINI_API_KEY を設定済み（無料枠あり。取得方法は README.md 参照）
- system_prompt.txt / theme_bank.json を同じディレクトリに配置

使い方:
    python generate_weekly_posts.py

このスクリプトはAPIから投稿JSONを受け取り、weekly_posts.json に保存するところまでを行う。
Typefully等への実際の投稿・下書き登録は post_to_typefully() 内に自分のAPI仕様に合わせて実装すること
（Typefully側の認証キー・エンドポイントはユーザー自身のアカウント設定に依存するため、ここではスタブのみ用意）。
自動投稿込みで動かす場合は daily_pipeline.py を使う（こちらは typefully_client.py を実際に呼ぶ）。
"""

import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "system_prompt.txt").read_text(encoding="utf-8")
THEME_BANK = json.loads((BASE_DIR / "theme_bank.json").read_text(encoding="utf-8"))

# 曜日カレンダー（system_prompt.txt内の定義と一致させること。ここを変える場合はプロンプト側も変更する）
WEEKLY_CALENDAR = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 10

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


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
    payload = build_user_payload(day, week_theme, focus_goal, real_experience)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=payload,
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
