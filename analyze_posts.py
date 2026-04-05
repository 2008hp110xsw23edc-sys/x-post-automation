"""
X投稿 パフォーマンス分析スクリプト
- X API v2 で直近100件のツイートのメトリクスを取得
- Claude API でパターン分析・改善提案を生成
- analytics/YYYY-MM-DD.md に保存
"""

import anthropic
import os
import json
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import hmac
import hashlib
import base64
import time
import random
import string


# ──────────────────────────────────────────
# X API OAuth 1.0a ヘルパー
# ──────────────────────────────────────────

def _percent_encode(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def _build_oauth_header(method: str, url: str, params: dict, credentials: dict) -> str:
    """OAuth 1.0a Authorization ヘッダーを生成する"""
    oauth_params = {
        "oauth_consumer_key":     credentials["api_key"],
        "oauth_nonce":            "".join(random.choices(string.ascii_letters + string.digits, k=32)),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            credentials["access_token"],
        "oauth_version":          "1.0",
    }

    # 署名ベース文字列を構築
    all_params = {**params, **oauth_params}
    sorted_params = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        _percent_encode(method.upper()),
        _percent_encode(url),
        _percent_encode(sorted_params),
    ])

    # 署名キー
    signing_key = "&".join([
        _percent_encode(credentials["api_secret"]),
        _percent_encode(credentials["access_token_secret"]),
    ])

    # HMAC-SHA1 署名
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature

    header_value = "OAuth " + ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return header_value


def x_api_get(endpoint: str, params: dict, credentials: dict) -> dict:
    """X API v2 GETリクエスト（OAuth 1.0a）"""
    base_url = f"https://api.twitter.com/2/{endpoint}"
    auth_header = _build_oauth_header("GET", base_url, params, credentials)

    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{base_url}?{query}",
        headers={
            "Authorization": auth_header,
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


# ──────────────────────────────────────────
# メトリクス取得
# ──────────────────────────────────────────

def get_user_id(username: str, credentials: dict) -> str:
    """ユーザー名からユーザーIDを取得"""
    data = x_api_get(f"users/by/username/{username}", {}, credentials)
    return data["data"]["id"]


def fetch_tweets(user_id: str, credentials: dict, max_results: int = 100) -> list[dict]:
    """直近のツイートとメトリクスを取得"""
    params = {
        "max_results":  str(min(max_results, 100)),
        "tweet.fields": "created_at,text,public_metrics,non_public_metrics,organic_metrics",
        "expansions":   "author_id",
    }
    data = x_api_get(f"users/{user_id}/tweets", params, credentials)
    return data.get("data", [])


# ──────────────────────────────────────────
# メトリクス集計・ランキング
# ──────────────────────────────────────────

def calc_engagement_rate(tweet: dict) -> float:
    """エンゲージメント率（%）= エンゲージメント合計 / インプレッション × 100"""
    pm = tweet.get("public_metrics", {})
    om = tweet.get("organic_metrics", {})

    impressions = om.get("impression_count") or pm.get("impression_count") or 0
    if impressions == 0:
        return 0.0

    engagements = (
        (om.get("like_count")    or pm.get("like_count")    or 0)
        + (om.get("retweet_count") or pm.get("retweet_count") or 0)
        + (om.get("reply_count")   or pm.get("reply_count")   or 0)
        + (om.get("quote_count")   or pm.get("quote_count")   or 0)
        + (pm.get("bookmark_count") or 0)
    )
    return round(engagements / impressions * 100, 2)


def build_metrics_table(tweets: list[dict]) -> list[dict]:
    """各ツイートのメトリクスを整理した辞書リストを返す"""
    rows = []
    for t in tweets:
        pm = t.get("public_metrics", {})
        nm = t.get("non_public_metrics", {})
        om = t.get("organic_metrics", {})

        impressions = (
            om.get("impression_count")
            or pm.get("impression_count")
            or 0
        )
        rows.append({
            "id":               t["id"],
            "created_at":       t.get("created_at", ""),
            "text":             t.get("text", ""),
            "impressions":      impressions,
            "likes":            om.get("like_count")    or pm.get("like_count")    or 0,
            "retweets":         om.get("retweet_count") or pm.get("retweet_count") or 0,
            "replies":          om.get("reply_count")   or pm.get("reply_count")   or 0,
            "quotes":           om.get("quote_count")   or pm.get("quote_count")   or 0,
            "bookmarks":        pm.get("bookmark_count") or 0,
            "url_clicks":       nm.get("url_link_clicks")    or om.get("url_link_clicks")    or 0,
            "profile_clicks":   nm.get("user_profile_clicks") or om.get("user_profile_clicks") or 0,
            "engagement_rate":  calc_engagement_rate(t),
        })
    return rows


def top_n(rows: list[dict], key: str, n: int = 5) -> list[dict]:
    return sorted(rows, key=lambda x: x[key], reverse=True)[:n]


def format_tweet_card(rank: int, row: dict) -> str:
    text_preview = row["text"][:80].replace("\n", " ")
    if len(row["text"]) > 80:
        text_preview += "…"
    date_str = row["created_at"][:10] if row["created_at"] else "不明"
    return (
        f"**{rank}位** （{date_str}）\n"
        f"> {text_preview}\n"
        f"- インプレッション: {row['impressions']:,}\n"
        f"- いいね: {row['likes']:,}　RT: {row['retweets']:,}　返信: {row['replies']:,}\n"
        f"- ブックマーク: {row['bookmarks']:,}　URLクリック: {row['url_clicks']:,}\n"
        f"- エンゲージメント率: {row['engagement_rate']}%\n"
    )


# ──────────────────────────────────────────
# Claude による AI 分析
# ──────────────────────────────────────────

def analyze_with_claude(metrics_table: list[dict]) -> str:
    """上位投稿のパターンを Claude で分析し、改善提案を返す"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Claude に渡すデータを簡潔にする
    top_by_impressions   = top_n(metrics_table, "impressions",    10)
    top_by_engagement    = top_n(metrics_table, "engagement_rate", 10)
    top_by_url_clicks    = top_n(metrics_table, "url_clicks",      10)

    summary_json = json.dumps({
        "top_impressions":    top_by_impressions,
        "top_engagement":     top_by_engagement,
        "top_url_clicks":     top_by_url_clicks,
    }, ensure_ascii=False, indent=2)

    prompt = f"""
あなたはXアカウント（@JUN1007S）の投稿アナリストです。
以下は直近のツイートのパフォーマンスデータです（上位10件ずつ）。

このアカウントのプロフィール：
- 30代男性・3歳娘持ちのサラリーマン
- 根回し・自己アピールが苦手な「コツコツ型」副業挑戦者
- 45歳脱サラ・月200万円を目標に、X発信+note販売中
- ターゲット：評価されないサラリーマン、副業に興味ある人

データ：
{summary_json}

以下の観点で日本語で分析してください（合計600〜800字程度）：

1. **インプレッションが多い投稿の共通パターン**（書き出し・テーマ・構成など）
2. **エンゲージメント率が高い投稿の特徴**（読者の反応を引き出す要素）
3. **URLクリックが多い投稿の特徴**（note誘導に効果的なパターン）
4. **今後の投稿改善アドバイス**（具体的に3〜5点）
5. **避けるべきパターン**（パフォーマンスが低い投稿の特徴）

分析は箇条書きと見出しを使い、明日から実践できる具体的なアドバイスにしてください。
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ──────────────────────────────────────────
# レポート生成・保存
# ──────────────────────────────────────────

def generate_report(metrics_table: list[dict], ai_analysis: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(metrics_table)

    avg_impressions = (
        sum(r["impressions"] for r in metrics_table) / total if total else 0
    )
    avg_engagement = (
        sum(r["engagement_rate"] for r in metrics_table) / total if total else 0
    )

    lines = [
        f"# X投稿 パフォーマンス分析レポート ({today})",
        "",
        "## 概要",
        f"- 分析対象ツイート数: {total}件",
        f"- 平均インプレッション: {avg_impressions:,.0f}",
        f"- 平均エンゲージメント率: {avg_engagement:.2f}%",
        "",
        "---",
        "",
        "## インプレッションTOP5",
        "",
    ]
    for i, row in enumerate(top_n(metrics_table, "impressions"), 1):
        lines.append(format_tweet_card(i, row))

    lines += [
        "---",
        "",
        "## エンゲージメント率TOP5",
        "",
    ]
    for i, row in enumerate(top_n(metrics_table, "engagement_rate"), 1):
        lines.append(format_tweet_card(i, row))

    lines += [
        "---",
        "",
        "## URLクリックTOP5（note誘導効果）",
        "",
    ]
    for i, row in enumerate(top_n(metrics_table, "url_clicks"), 1):
        lines.append(format_tweet_card(i, row))

    lines += [
        "---",
        "",
        "## ブックマークTOP5（保存価値の高い投稿）",
        "",
    ]
    for i, row in enumerate(top_n(metrics_table, "bookmarks"), 1):
        lines.append(format_tweet_card(i, row))

    lines += [
        "---",
        "",
        "## AI分析・改善提案",
        "",
        ai_analysis,
        "",
        "---",
        f"*生成日時: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    username = "JUN1007S"

    credentials = {
        "api_key":            os.environ["X_API_KEY"],
        "api_secret":         os.environ["X_API_SECRET"],
        "access_token":       os.environ["X_ACCESS_TOKEN"],
        "access_token_secret": os.environ["X_ACCESS_TOKEN_SECRET"],
    }

    print(f"[1/5] ユーザーID取得: @{username}")
    user_id = get_user_id(username, credentials)

    print("[2/5] ツイート取得中（最大100件）...")
    tweets = fetch_tweets(user_id, credentials)
    print(f"      → {len(tweets)}件取得")

    print("[3/5] メトリクス集計中...")
    metrics_table = build_metrics_table(tweets)

    print("[4/5] Claude AIで分析中...")
    ai_analysis = analyze_with_claude(metrics_table)

    print("[5/5] レポート保存中...")
    report = generate_report(metrics_table, ai_analysis)

    os.makedirs("analytics", exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = f"analytics/{today}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n完了: {filepath}")


if __name__ == "__main__":
    main()
