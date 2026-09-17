"""毎日自動作成（全媒体）: GitHub Actionsから毎日呼ばれる想定のバッチ。

webapp/app.py の「毎日自動作成」画面と同じロジックを、非対話・CI用にラップしたもの。
sns_rules.json の attach_every_n_posts に従い、媒体ごとに何投稿おきかアフィリエイトを
自動で挿入するかどうかが判定される（状態は state/post_counts.json に保存され、実行のたびに進む）。

生成結果は generated_posts/<platform>/ にコミットされ、LINEに要約が通知される。
商品リンクの自動挿入はデフォルトでは行わない（テーマと実体験のローテーションのみ）。
挿入したい場合は AFFILIATE_KEYWORD 環境変数（楽天検索キーワード）を指定する。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import content_engine
from notify import send_line_push

BASE_DIR = Path(__file__).parent


def today_theme() -> str:
    themes = json.loads((BASE_DIR / "theme_bank.json").read_text(encoding="utf-8"))
    idx = datetime.now().toordinal() % len(themes)
    return themes[idx]["title"]


def today_real_experience() -> str:
    path = BASE_DIR / "real_experience_bank.json"
    if not path.exists():
        return ""
    bank = json.loads(path.read_text(encoding="utf-8"))
    return bank.get(datetime.now().strftime("%Y-%m-%d"), "")


def fetch_affiliate_url() -> str | None:
    keyword = os.environ.get("AFFILIATE_KEYWORD")
    app_id = os.environ.get("RAKUTEN_APP_ID")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID")
    if not keyword or not app_id or not access_key:
        return None
    import rakuten_client

    try:
        items = rakuten_client.search_items(
            keyword, app_id=app_id, access_key=access_key, affiliate_id=affiliate_id, hits=5
        )
        return items[0]["affiliateUrl"] if items else None
    except Exception as e:  # 楽天API障害等で全体を止めない
        print(f"[warn] 楽天商品取得に失敗: {e}")
        return None


def main() -> None:
    theme = today_theme()
    real_experience = today_real_experience()
    affiliate_url = fetch_affiliate_url()
    platforms = content_engine.list_platforms()

    summary_lines = [f"【毎日自動作成】{datetime.now().strftime('%Y-%m-%d')}", f"テーマ: {theme}", ""]

    for platform in platforms:
        post = content_engine.generate_post(platform=platform, theme=theme, real_experience=real_experience)
        if affiliate_url and post.get("attach_affiliate"):
            post = content_engine.insert_affiliate_link(post, affiliate_url)
        rendered = content_engine.render_for_display(post)
        content_engine.save_draft(platform, post, rendered)

        flag = "💰" if rendered["attach_affiliate"] else "・"
        summary_lines.append(f"{flag} {platform}: {rendered['main_text'][:60].replace(chr(10), ' ')}...")

    print("\n".join(summary_lines))

    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    if line_token and line_user_id:
        send_line_push("\n".join(summary_lines), channel_access_token=line_token, user_id=line_user_id)
    else:
        print("[warn] LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定のため通知をスキップしました。")


if __name__ == "__main__":
    main()
