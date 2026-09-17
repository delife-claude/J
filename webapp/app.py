"""アフィリエイト投稿専用アプリ（Flask）。

戦略確認・単発作成・SNS選択作成・毎日自動作成の4画面を提供する。
生成ロジックは content_engine.py（媒体別ルール・アフィリエイト添付頻度の判定込み）に委譲し、
商品リンクは rakuten_client.py（楽天）/ amazon_client.py（Amazon）から取得する。

起動:
    pip install -r requirements.txt
    export THREADS_GEMINI_API_KEY=...
    python webapp/app.py
    # http://127.0.0.1:5000 を開く
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import amazon_client  # noqa: E402
import content_engine  # noqa: E402
import rakuten_client  # noqa: E402

app = Flask(__name__)

THEME_BANK_PATH = BASE_DIR / "theme_bank.json"
REAL_EXPERIENCE_PATH = BASE_DIR / "real_experience_bank.json"


def today_theme() -> str:
    themes = json.loads(THEME_BANK_PATH.read_text(encoding="utf-8"))
    idx = datetime.now().toordinal() % len(themes)
    return themes[idx]["title"]


def today_real_experience() -> str:
    if not REAL_EXPERIENCE_PATH.exists():
        return ""
    bank = json.loads(REAL_EXPERIENCE_PATH.read_text(encoding="utf-8"))
    return bank.get(datetime.now().strftime("%Y-%m-%d"), "")


def fetch_affiliate_url(source: str, query: str) -> tuple[str | None, str | None]:
    """戻り値: (affiliateUrl, エラーメッセージ)"""
    if not source or source == "none" or not query:
        return None, None
    try:
        if source == "rakuten":
            app_id = os.environ.get("RAKUTEN_APP_ID")
            access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
            affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID")
            if not app_id or not access_key:
                return None, "RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が未設定です"
            items = rakuten_client.search_items(
                query, app_id=app_id, access_key=access_key, affiliate_id=affiliate_id, hits=5
            )
            if not items:
                return None, f"楽天市場で「{query}」の商品が見つかりませんでした"
            return items[0]["affiliateUrl"], None
        if source == "amazon":
            tag = os.environ.get("AMAZON_ASSOCIATE_TAG")
            if not tag:
                return None, "AMAZON_ASSOCIATE_TAG が未設定です"
            url = amazon_client.build_affiliate_link(query, tag)
            if not url:
                return None, f"「{query}」からASINを取得できませんでした（ASINまたはamazon.co.jpのURLを入力してください）"
            return url, None
    except Exception as e:  # 商品取得失敗で画面全体を落とさない
        return None, f"商品取得に失敗しました: {e}"
    return None, None


@app.route("/")
def index():
    return render_template("index.html", platforms=content_engine.list_platforms())


@app.route("/strategy")
def strategy():
    rules = content_engine.load_rules()
    rules = {k: v for k, v in rules.items() if not k.startswith("_")}
    return render_template("strategy.html", rules=rules)


@app.route("/create/single", methods=["GET", "POST"])
def create_single():
    platforms = content_engine.list_platforms()
    result = None
    error = None
    form = {"platform": platforms[0], "theme": "", "real_experience": "", "affiliate_source": "none", "affiliate_query": ""}

    if request.method == "POST":
        form.update({k: request.form.get(k, "") for k in form})
        platform = form["platform"]
        rules = content_engine.platform_rules(platform)
        try:
            affiliate_url, aff_error = fetch_affiliate_url(form["affiliate_source"], form["affiliate_query"])
            attach = affiliate_url is not None
            post = content_engine.generate_post(
                platform=platform,
                theme=form["theme"] or today_theme(),
                real_experience=form["real_experience"],
                attach_affiliate=attach if affiliate_url else None,
            )
            if affiliate_url:
                post = content_engine.insert_affiliate_link(post, affiliate_url)
            rendered = content_engine.render_for_display(post)
            path = content_engine.save_draft(platform, post, rendered)
            result = {"post": post, "rendered": rendered, "saved_to": str(path.relative_to(BASE_DIR)), "aff_error": aff_error, "rules": rules}
        except Exception as e:
            error = str(e)

    return render_template("create_single.html", platforms=platforms, form=form, result=result, error=error)


@app.route("/create/platform", methods=["GET", "POST"])
def create_platform():
    platforms = content_engine.list_platforms()
    results = []
    error = None
    form = {"platform": platforms[0], "theme": "", "count": "3", "affiliate_source": "none", "affiliate_query": ""}

    if request.method == "POST":
        form.update({k: request.form.get(k, "") for k in form})
        platform = form["platform"]
        rules = content_engine.platform_rules(platform)
        count = max(1, min(10, int(form["count"] or 1)))
        try:
            affiliate_url, aff_error = fetch_affiliate_url(form["affiliate_source"], form["affiliate_query"])
            for i in range(count):
                post = content_engine.generate_post(
                    platform=platform,
                    theme=form["theme"] or today_theme(),
                )
                if affiliate_url and post.get("attach_affiliate"):
                    post = content_engine.insert_affiliate_link(post, affiliate_url)
                rendered = content_engine.render_for_display(post)
                content_engine.save_draft(platform, post, rendered)
                results.append({"post": post, "rendered": rendered})
            if aff_error:
                error = aff_error
        except Exception as e:
            error = str(e)

    return render_template("create_platform.html", platforms=platforms, form=form, results=results, error=error)


@app.route("/create/daily", methods=["GET", "POST"])
def create_daily():
    platforms = content_engine.list_platforms()
    theme = today_theme()
    real_experience = today_real_experience()
    results = None
    error = None

    if request.method == "POST":
        results = []
        try:
            for platform in platforms:
                rules = content_engine.platform_rules(platform)
                if rules.get("attach_every_n_posts", 0) == 0 and platform != "brain":
                    pass  # そのまま生成対象に含める（counterが0なら自動でfalse判定になる）
                post = content_engine.generate_post(platform=platform, theme=theme, real_experience=real_experience)
                rendered = content_engine.render_for_display(post)
                content_engine.save_draft(platform, post, rendered)
                results.append({"platform": platform, "post": post, "rendered": rendered})
        except Exception as e:
            error = str(e)

    return render_template(
        "create_daily.html", platforms=platforms, theme=theme, real_experience=real_experience, results=results, error=error
    )


@app.route("/history")
def history():
    platform = request.args.get("platform") or None
    drafts = content_engine.list_drafts(platform=platform)
    return render_template("history.html", drafts=drafts, platforms=content_engine.list_platforms(), selected=platform)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
