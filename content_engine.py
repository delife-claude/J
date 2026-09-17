"""複数SNS横断の投稿生成エンジン。

sns_rules.json（媒体ごとのルール・アフィリエイト添付頻度）と multi_sns_system_prompt.txt
（Gemini向けの共通システムプロンプト）を使って、媒体に最適化した投稿を生成する。
既存の post_machine.py / daily_pipeline.py（Threads専用）とは独立しており、webapp/app.py
と daily_multi_sns.py の両方から呼ばれる共通ロジック。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import errors, types

BASE_DIR = Path(__file__).parent
RULES_PATH = BASE_DIR / "sns_rules.json"
SYSTEM_PROMPT = (BASE_DIR / "multi_sns_system_prompt.txt").read_text(encoding="utf-8")
STATE_PATH = BASE_DIR / "state" / "post_counts.json"
DRAFTS_DIR = BASE_DIR / "generated_posts"

MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 10


def load_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def platform_rules(platform: str) -> dict:
    rules = load_rules()
    if platform not in rules or platform == "_readme":
        raise ValueError(f"unknown platform: {platform}")
    return rules[platform]


def list_platforms() -> list[str]:
    return [k for k in load_rules().keys() if not k.startswith("_")]


def _load_counts() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_counts(counts: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")


def should_attach_affiliate(platform: str, rules: dict | None = None) -> bool:
    """sns_rules.jsonのattach_every_n_postsに従い、今回アフィリエイトを付けるか決めて
    カウンタをインクリメントする（呼び出すたびに状態が進む副作用あり）。"""
    rules = rules or platform_rules(platform)
    n = int(rules.get("attach_every_n_posts") or 0)
    if n <= 0:
        return False
    counts = _load_counts()
    count = counts.get(platform, 0) + 1
    counts[platform] = count
    _save_counts(counts)
    return count % n == 0


def generate_post(
    platform: str,
    theme: str,
    kind: str | None = None,
    real_experience: str = "",
    attach_affiliate: bool | None = None,
) -> dict:
    """1件分の投稿をGeminiで生成する。attach_affiliateを省略すると頻度ルールから自動判定する。"""
    rules = platform_rules(platform)
    kind = kind or rules["kind_options"][0]
    if attach_affiliate is None:
        attach_affiliate = should_attach_affiliate(platform, rules)

    client = genai.Client(api_key=os.environ["THREADS_GEMINI_API_KEY"])
    payload = {
        "platform": platform,
        "platform_rules": rules,
        "kind": kind,
        "theme": theme,
        "attach_affiliate": attach_affiliate,
        "real_experience": real_experience,
    }

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

        post = json.loads(response.text, strict=False)
        last_post = post
        problems = []
        if post.get("attach_affiliate") and not attach_affiliate:
            problems.append("attach_affiliate=falseなのにアフィリエイト誘導が含まれています")
        char_limit = rules.get("char_limit")
        if char_limit:
            total_len = sum(len(p) for p in post.get("body_parts") or []) + len(post.get("hook") or "")
            if total_len > char_limit * 3:  # 記事系(配列)は緩めに、単発系は厳しめにチェック
                problems.append(f"本文が長すぎます（合計{total_len}字、目安{char_limit}字）")
        if not problems:
            post["attach_affiliate"] = attach_affiliate  # コード側の判定を正とする
            return post
        feedback = "\n".join(problems)

    print(f"[warn] ルールを満たせないまま返却します: {feedback}")
    if last_post:
        last_post["attach_affiliate"] = attach_affiliate
    return last_post


def insert_affiliate_link(post: dict, affiliate_url: str | None) -> dict:
    """affiliate_link_slot=in_bodyの投稿で{AFFILIATE_LINK}プレースホルダーを実URLに置換する。"""
    if not affiliate_url:
        return post
    post = dict(post)
    post["hook"] = (post.get("hook") or "").replace("{AFFILIATE_LINK}", affiliate_url)
    post["body_parts"] = [
        (p or "").replace("{AFFILIATE_LINK}", affiliate_url) for p in (post.get("body_parts") or [])
    ]
    post["cta_line"] = (post.get("cta_line") or "").replace("{AFFILIATE_LINK}", affiliate_url) or None
    post["_affiliate_url"] = affiliate_url
    return post


def render_for_display(post: dict) -> dict:
    """UI表示・下書き保存用に、本文/コメント欄/プロフィール誘導などをまとめて組み立てる。

    戻り値:
      main_text: メイン投稿として貼る本文
      followup_text: コメント欄・自己リプライに貼る文（affiliate_link_slot=replyの場合のみ）
      bio_note: プロフィールリンク誘導が必要な場合の注意書き（affiliate_link_slot=bioの場合のみ）
    """
    parts = [post.get("hook") or ""]
    parts += list(post.get("body_parts") or [])
    cta = post.get("cta_line")
    if cta:
        parts.append(cta)
    hashtags = post.get("hashtags") or []

    slot = post.get("affiliate_link_slot")
    affiliate_url = post.get("_affiliate_url")

    if post.get("attach_affiliate") and slot in ("in_body", "reply"):
        parts_display = [p for p in parts if p]
        text_pr_prefix = "【PR】\n" if slot == "in_body" else ""
        main_text = text_pr_prefix + "\n\n".join(parts_display)
        if hashtags:
            main_text += "\n\n" + " ".join(hashtags)
    else:
        main_text = "\n\n".join(p for p in parts if p)
        if hashtags:
            main_text += "\n\n" + " ".join(hashtags)

    followup_text = None
    bio_note = None
    if post.get("attach_affiliate") and slot == "reply" and affiliate_url:
        followup_text = f"【PR】商品リンクはこちら → {affiliate_url}\n#PR #広告"
    elif post.get("attach_affiliate") and slot == "bio":
        bio_note = "※プロフィールのリンク（またはストーリーズ/概要欄）にアフィリエイトリンクを設定してから投稿してください。"

    return {
        "main_text": main_text,
        "followup_text": followup_text,
        "bio_note": bio_note,
        "missing_experience_flag": bool(post.get("missing_experience_flag")),
        "attach_affiliate": bool(post.get("attach_affiliate")),
    }


def save_draft(platform: str, post: dict, rendered: dict) -> Path:
    out_dir = DRAFTS_DIR / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    record = {"post": post, "rendered": rendered}
    path = out_dir / f"{timestamp}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [f"# [{platform}] {post.get('theme', '')}", "", rendered["main_text"]]
    if rendered.get("followup_text"):
        md_lines += ["", "---", "[コメント欄/自己リプライ用]", rendered["followup_text"]]
    if rendered.get("bio_note"):
        md_lines += ["", rendered["bio_note"]]
    if rendered.get("missing_experience_flag"):
        md_lines += ["", "⚠️ 実体験なしで一般化した例になっています。差し替え推奨。"]
    (out_dir / f"{timestamp}.md").write_text("\n".join(md_lines), encoding="utf-8")
    return path


def list_drafts(platform: str | None = None, limit: int = 50) -> list[dict]:
    """保存済み下書きを新しい順に返す（webapp履歴タブ用）。"""
    results = []
    dirs = [DRAFTS_DIR / platform] if platform else list(DRAFTS_DIR.glob("*"))
    for d in dirs:
        if not d.is_dir():
            continue
        for path in d.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_platform"] = d.name
            data["_file"] = path.stem
            results.append(data)
    results.sort(key=lambda r: r["_file"], reverse=True)
    return results[:limit]
