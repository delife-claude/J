"""役割①自己紹介文作成係。立ち上げ時に1回だけ手動実行する想定。"""

import os
from pathlib import Path

from google import genai
from google.genai import types

BASE_DIR = Path(__file__).parent
MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """あなたは楽天ROOMのプロフィール自己紹介文を書くライターです。
出力は自己紹介文の本文のみとし、説明文や前置きは書かないでください。

# ルール
- 150〜200字程度
- ジャンル：子どものバレーグッズ紹介
- ターゲット：①レギュラーを目指す子 ②バレー未経験の保護者
- 実績・エピソードは入力された内容の範囲でのみ書き、誇張・捏造をしない
- 「〜な方に向けて」「〜を紹介しています」等、何を発信するアカウントかが一目でわかる文にする
- 上から目線・専門用語の多用を避ける
"""

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def main():
    print("楽天ROOMの自己紹介文を作ります。以下の質問に答えてください（わからなければ空Enterで飛ばせます）。\n")
    background = input("あなた自身・お子さんとバレーボールの関わり（例: 子どもが中学からバレーを始めて3年目）: ").strip()
    focus = input("発信の軸（例: 初心者ママでも失敗しない練習グッズ選び）: ").strip()
    tone = input("希望するトーン（例: フレンドリー / 専門的 / 応援団っぽい）: ").strip()

    user_content = (
        f"背景: {background or '未入力'}\n発信の軸: {focus or '未入力'}\n希望トーン: {tone or '未入力'}"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=400,
        ),
    )
    intro_text = response.text

    output_path = BASE_DIR / "profile_intro.txt"
    output_path.write_text(intro_text, encoding="utf-8")
    print(f"\n生成結果:\n{intro_text}\n\n{output_path} に保存しました。内容を確認してROOMのプロフィールに貼り付けてください。")


if __name__ == "__main__":
    main()
