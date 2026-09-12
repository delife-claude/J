"""Threads投稿生成マシーン（汎用版）。

テーマと1日の投稿数を渡すと、以下のルールで1日分のThreads投稿セットを生成する。

- 長文投稿: main_post + comment_1 + comment_2 の3部構成、合計900〜1100字
  （体験談＋具体的ノウハウ＋数値を必ず入れる）
- 短文投稿: 「気づき」「共感」系のみ、150〜200字（親近感づくりが目的でCTAは含めない）
- 投稿比率は 長文:短文 ≒ 4:1（1日5投稿なら長文4・短文1、10投稿なら長文8・短文2）

前提:
- pip install -r requirements.txt (google-genai)
- 環境変数 THREADS_GEMINI_API_KEY を設定済み（generate_weekly_posts.py と共用）
- post_machine_system_prompt.txt を同じディレクトリに配置

使い方（対話モード）:
    python post_machine.py

使い方（非対話・引数指定）:
    python post_machine.py --themes "在宅ワークの時短術" --total 5
    python post_machine.py --themes "テーマA" "テーマB" "テーマC" --total 10

生成結果は drafts_machine/ 以下にJSONとMarkdownで保存される。Typefullyへの下書き登録は
--post を付けたときのみ行う（公開予約はせず、必ず下書き登録のみ。人間の確認を挟むため）。
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import errors, types

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT = (BASE_DIR / "post_machine_system_prompt.txt").read_text(encoding="utf-8")

MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 10

LONG_CHAR_RANGE = (900, 1100)
LONG_MAIN_RANGE = (50, 150)
LONG_COMMENT_RANGE = (400, 500)
SHORT_CHAR_RANGE = (150, 200)
LONG_SHORT_RATIO = 0.8  # 長文の割合。5件→長文4:短文1、10件→長文8:短文2 と一致する


def compute_long_short_counts(total: int) -> tuple[int, int]:
    """1日の投稿数から長文・短文の内訳を決める（長文:短文 ≒ 4:1）。"""
    if total <= 0:
        return 0, 0
    long_count = max(0, min(total, round(total * LONG_SHORT_RATIO)))
    return long_count, total - long_count


def build_schedule(total: int) -> list[str]:
    """長文・短文を1日の中でなるべく均等に散らした順番のリストを作る。"""
    long_count, short_count = compute_long_short_counts(total)
    schedule: list[str] = []
    long_done = short_done = 0
    for _ in range(total):
        long_ratio = long_done / long_count if long_count else 1.0
        short_ratio = short_done / short_count if short_count else 1.0
        if long_count and (short_count == 0 or long_ratio <= short_ratio):
            schedule.append("long")
            long_done += 1
        else:
            schedule.append("short")
            short_done += 1
    return schedule


def _char_len(s: str | None) -> int:
    return len(s or "")


def _validate(post: dict) -> list[str]:
    problems = []
    kind = post.get("kind")
    if kind == "short":
        n = _char_len(post.get("main_post"))
        if not (SHORT_CHAR_RANGE[0] <= n <= SHORT_CHAR_RANGE[1]):
            problems.append(f"本文が{n}字（{SHORT_CHAR_RANGE[0]}〜{SHORT_CHAR_RANGE[1]}字の範囲外）")
    elif kind == "long":
        main_n = _char_len(post.get("main_post"))
        c1_n = _char_len(post.get("comment_1"))
        c2_n = _char_len(post.get("comment_2"))
        total_n = main_n + c1_n + c2_n
        if not (LONG_MAIN_RANGE[0] <= main_n <= LONG_MAIN_RANGE[1]):
            problems.append(f"main_postが{main_n}字（{LONG_MAIN_RANGE[0]}〜{LONG_MAIN_RANGE[1]}字の範囲外）")
        if not (LONG_COMMENT_RANGE[0] <= c1_n <= LONG_COMMENT_RANGE[1]):
            problems.append(f"comment_1が{c1_n}字（{LONG_COMMENT_RANGE[0]}〜{LONG_COMMENT_RANGE[1]}字の範囲外）")
        if not (LONG_COMMENT_RANGE[0] <= c2_n <= LONG_COMMENT_RANGE[1]):
            problems.append(f"comment_2が{c2_n}字（{LONG_COMMENT_RANGE[0]}〜{LONG_COMMENT_RANGE[1]}字の範囲外）")
        if not (LONG_CHAR_RANGE[0] <= total_n <= LONG_CHAR_RANGE[1]):
            problems.append(f"3パート合計が{total_n}字（{LONG_CHAR_RANGE[0]}〜{LONG_CHAR_RANGE[1]}字の範囲外）")
    return problems


def generate_post(theme: str, kind: str, real_experience: str = "") -> dict:
    """1件分の投稿をGeminiで生成する。文字数ルール違反時は指摘つきで再生成を試みる。"""
    client = genai.Client(api_key=os.environ["THREADS_GEMINI_API_KEY"])
    payload = {"theme": theme, "kind": kind, "real_experience": real_experience}
    feedback = ""
    last_post: dict | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        user_message = json.dumps(payload, ensure_ascii=False)
        if feedback:
            user_message += f"\n\n# 前回の出力の問題点（必ず修正すること）\n{feedback}"
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                ),
            )
        except errors.ServerError:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(RETRY_WAIT_SECONDS * attempt)
            continue

        # strict=False: Geminiが本文中の改行を生の制御文字のまま返すことがあるため許容する
        post = json.loads(response.text, strict=False)
        last_post = post
        problems = _validate(post)
        if not problems:
            return post
        feedback = "\n".join(problems)

    print(f"[warn] 文字数ルールを満たせないまま返却します: {feedback}")
    return last_post


def format_as_text(post: dict) -> str:
    parts = [post["main_post"]]
    if post["kind"] == "long":
        parts += [post.get("comment_1") or "", post.get("comment_2") or ""]
    hashtags = post.get("hashtags") or []
    text = "\n\n---\n\n".join(p for p in parts if p)
    if hashtags:
        text += "\n\n" + " ".join(hashtags)
    reply_note = post.get("reply_note")
    if reply_note:
        text += f"\n\n[リプ欄]\n{reply_note}"
    return text


def generate_daily_batch(
    themes: list[str], total: int, real_experiences: list[str] | None = None
) -> list[dict]:
    """real_experiences は long投稿のcomment_1用の実体験メモ。long投稿のスロットにだけ順に
    割り当てる（短文投稿は実体験を使わないため）。long投稿数より少なければ使い回す。"""
    schedule = build_schedule(total)
    real_experiences = real_experiences or []
    posts = []
    long_slot = 0
    for i, kind in enumerate(schedule):
        theme = themes[i % len(themes)]
        if kind == "long" and real_experiences:
            real_experience = real_experiences[long_slot % len(real_experiences)]
            long_slot += 1
        else:
            real_experience = ""
        posts.append(generate_post(theme=theme, kind=kind, real_experience=real_experience))
    return posts


def save_batch(posts: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    json_path = out_dir / f"{timestamp}.json"
    json_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = []
    for i, post in enumerate(posts, start=1):
        md_lines.append(f"## {i}. [{post['kind']}] {post.get('theme', '')}")
        md_lines.append(format_as_text(post))
        md_lines.append("")
    (out_dir / f"{timestamp}.md").write_text("\n".join(md_lines), encoding="utf-8")

    return json_path


def post_to_typefully(posts: list[dict]) -> None:
    """Typefullyに下書き登録する（公開予約はしない。必ず人間の確認を挟むため）。"""
    from typefully_client import create_scheduled_draft

    for post in posts:
        parts = [post["main_post"]]
        if post["kind"] == "long":
            parts += [post.get("comment_1") or "", post.get("comment_2") or ""]
        parts = [p for p in parts if p]

        hashtags = post.get("hashtags") or []
        if hashtags:
            parts[-1] = parts[-1] + "\n\n" + " ".join(hashtags)

        title = f"{datetime.now().strftime('%Y-%m-%d')} [{post['kind']}] {post.get('theme', '')}"[:100]
        result = create_scheduled_draft(posts=parts, publish_at_iso=None, draft_title=title)
        print(f"[Typefully] 下書き登録: {title} (id={result.get('id', '不明')})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Threads投稿生成マシーン")
    parser.add_argument("--themes", nargs="+", help="テーマ（複数可。投稿数より少なければ順に使い回す）")
    parser.add_argument("--total", type=int, help="1日の投稿数（例: 5 または 10）")
    parser.add_argument(
        "--real-experience",
        nargs="+",
        default=None,
        help="long投稿のcomment_1で使う実体験メモ（複数可。long投稿数より少なければ使い回す。"
        "未指定の場合は一般化した例文になる）",
    )
    parser.add_argument("--out", default="drafts_machine", help="保存先ディレクトリ名")
    parser.add_argument("--post", action="store_true", help="Typefullyに下書き登録する（公開予約はしない）")
    args = parser.parse_args()

    themes = args.themes
    total = args.total
    if not themes:
        raw = input("テーマを入力してください（複数ある場合はカンマ区切り）: ").strip()
        themes = [t.strip() for t in raw.split(",") if t.strip()] or ["未指定"]
    if not total:
        total = int(input("今日の投稿数を入力してください（例: 5 / 10）: ").strip())

    long_count, short_count = compute_long_short_counts(total)
    print(f"投稿比率: 長文{long_count}件 / 短文{short_count}件（合計{total}件）")

    posts = generate_daily_batch(themes, total, real_experiences=args.real_experience)

    for i, post in enumerate(posts, start=1):
        print(f"\n=== {i}/{total} [{post['kind']}] {post.get('theme', '')} ===")
        print(format_as_text(post))
        if post.get("missing_experience_flag"):
            print("⚠️ 実体験なしで一般化した例になっています。差し替え推奨。")

    out_path = save_batch(posts, BASE_DIR / args.out)
    print(f"\n完了: {out_path} に保存しました。")

    if args.post:
        post_to_typefully(posts)


if __name__ == "__main__":
    main()
