"""
X投稿 パフォーマンス分析スクリプト
- X API v2 (tweepy) で直近100件のツイートのメトリクスを取得
- public_metrics: インプレッション・いいね・RT・返信・ブックマーク
- non_public_metrics: URLクリック・プロフィールクリック（OAuth 1.0a必須）
- Claude API でパターン分析・改善提案を生成
- analytics/YYYY-MM-DD.md に保存
"""

import anthropic
import tweepy
import os
import json
from datetime import datetime, timezone


# ──────────────────────────────────────────
# X API クライアント初期化
# ──────────────────────────────────────────

def get_x_client() -> tweepy.Client:
    """OAuth 1.0a ユーザーコンテキストで接続（non_public_metrics 取得に必要）"""
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        wait_on_rate_limit=True,
    )


# ──────────────────────────────────────────
# ツイート・メトリクス取得
# ──────────────────────────────────────────

def fetch_tweets(client: tweepy.Client, max_results: int = 100) -> list:
    """認証ユーザー自身の直近ツイートをメトリクス付きで取得"""
    # GET /2/users/me — 認証済みユーザー自身の情報を取得（Free/Basicプラン両対応）
    try:
        me_resp = client.get_me(user_auth=True)
    except tweepy.errors.Forbidden as e:
        raise SystemExit(
            "\n[エラー] X API 403 Forbidden\n"
            "考えられる原因と対処法:\n"
            "  1. developer.twitter.com > アプリ設定 > 'User authentication settings' で\n"
            "     OAuth 1.0a を有効化し、App permissions を 'Read' に設定してください\n"
            "  2. 設定変更後はアクセストークンを再生成し、GitHubシークレットを更新してください\n"
            "  3. X API が Basic プラン以上であることを確認してください\n"
            f"  詳細: {e}"
        ) from e
    except tweepy.errors.Unauthorized as e:
        raise SystemExit(
            "\n[エラー] X API 401 Unauthorized\n"
            "APIキーまたはアクセストークンが正しくない可能性があります。\n"
            "GitHubシークレット (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET) を確認してください。\n"
            f"  詳細: {e}"
        ) from e

    if not me_resp.data:
        raise ValueError("認証ユーザー情報が取得できませんでした")
    user_id = me_resp.data.id
    print(f"      → ユーザーID: {user_id}")

    # ツイート取得（non_public_metrics/organic_metrics は自分のツイートのみ取得可能）
    tweet_fields = [
        "created_at",
        "text",
        "public_metrics",
        "non_public_metrics",
        "organic_metrics",
    ]
    try:
        resp = client.get_users_tweets(
            id=user_id,
            max_results=min(max_results, 100),
            tweet_fields=tweet_fields,
            user_auth=True,
        )
    except tweepy.errors.Forbidden:
        # non_public_metrics が取得できない場合は public_metrics のみで再試行
        print("      [INFO] non_public_metrics は取得不可。public_metrics のみで取得します")
        resp = client.get_users_tweets(
            id=user_id,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "text", "public_metrics"],
            user_auth=True,
        )
    return resp.data or []


# ──────────────────────────────────────────
# メトリクス集計
# ──────────────────────────────────────────

def extract_metrics(tweet) -> dict:
    """ツイートオブジェクトからメトリクスを抽出"""
    pm = tweet.public_metrics   or {}
    nm = tweet.non_public_metrics or {}
    om = tweet.organic_metrics  or {}

    # impressionはorganic > public の順で取得
    impressions = (
        (om.get("impression_count") if om else None)
        or (pm.get("impression_count") if pm else None)
        or 0
    )

    likes     = (om.get("like_count")    if om else None) or (pm.get("like_count")    if pm else None) or 0
    retweets  = (om.get("retweet_count") if om else None) or (pm.get("retweet_count") if pm else None) or 0
    replies   = (om.get("reply_count")   if om else None) or (pm.get("reply_count")   if pm else None) or 0
    quotes    = (om.get("quote_count")   if om else None) or (pm.get("quote_count")   if pm else None) or 0
    bookmarks = (pm.get("bookmark_count") if pm else None) or 0
    url_clicks     = (nm.get("url_link_clicks")     if nm else None) or (om.get("url_link_clicks")     if om else None) or 0
    profile_clicks = (nm.get("user_profile_clicks") if nm else None) or (om.get("user_profile_clicks") if om else None) or 0

    total_engagements = likes + retweets + replies + quotes + bookmarks
    engagement_rate = round(total_engagements / impressions * 100, 2) if impressions > 0 else 0.0

    return {
        "id":              str(tweet.id),
        "created_at":      tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "",
        "text":            tweet.text or "",
        "impressions":     impressions,
        "likes":           likes,
        "retweets":        retweets,
        "replies":         replies,
        "quotes":          quotes,
        "bookmarks":       bookmarks,
        "url_clicks":      url_clicks,
        "profile_clicks":  profile_clicks,
        "engagement_rate": engagement_rate,
    }


def build_metrics_table(tweets: list) -> list[dict]:
    rows = []
    for tweet in tweets:
        try:
            rows.append(extract_metrics(tweet))
        except Exception as e:
            print(f"      [WARN] ツイートID {tweet.id} のメトリクス取得に失敗: {e}")
    return rows


def top_n(rows: list[dict], key: str, n: int = 5) -> list[dict]:
    return sorted(rows, key=lambda x: x[key], reverse=True)[:n]


# ──────────────────────────────────────────
# Claude による AI 分析
# ──────────────────────────────────────────

def analyze_with_claude(metrics_table: list[dict]) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    top_impressions  = top_n(metrics_table, "impressions",    10)
    top_engagement   = top_n(metrics_table, "engagement_rate", 10)
    top_url_clicks   = top_n(metrics_table, "url_clicks",      10)

    # Claude に渡すデータ（テキストを短縮）
    def shorten(rows):
        return [
            {**r, "text": r["text"][:100].replace("\n", " ")}
            for r in rows
        ]

    summary = {
        "top_impressions":  shorten(top_impressions),
        "top_engagement":   shorten(top_engagement),
        "top_url_clicks":   shorten(top_url_clicks),
    }

    prompt = f"""
あなたはXアカウント（@JUN1007S）の投稿アナリストです。
以下は直近のツイートのパフォーマンスデータです（上位10件ずつ）。

このアカウントのプロフィール：
- 30代男性・3歳娘持ちのサラリーマン
- 根回し・自己アピールが苦手な「コツコツ型」副業挑戦者
- 45歳脱サラ・月200万円を目標に、X発信+note販売中
- ターゲット：正当評価されないサラリーマン、副業に興味ある人

データ：
{json.dumps(summary, ensure_ascii=False, indent=2)}

以下の観点で日本語で分析してください（合計600〜800字程度）：

### 1. インプレッションが多い投稿の共通パターン
（書き出し・テーマ・構成・時間帯など）

### 2. エンゲージメント率が高い投稿の特徴
（読者の反応を引き出す要素）

### 3. URLクリックが多い投稿の特徴
（note誘導に効果的なパターン）

### 4. 今後の投稿改善アドバイス（3〜5点）
（明日から実践できる具体的な内容）

### 5. 避けるべきパターン
（パフォーマンスが低い投稿の特徴）

分析は箇条書きと見出しを使い、具体的なアドバイスにしてください。
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

def format_tweet_card(rank: int, row: dict) -> str:
    preview = row["text"][:80].replace("\n", " ")
    if len(row["text"]) > 80:
        preview += "…"
    return (
        f"**{rank}位** （{row['created_at']}）\n"
        f"> {preview}\n"
        f"- インプレッション: {row['impressions']:,} ／ エンゲージメント率: {row['engagement_rate']}%\n"
        f"- いいね: {row['likes']:,}　RT: {row['retweets']:,}　返信: {row['replies']:,}　引用: {row['quotes']:,}\n"
        f"- ブックマーク: {row['bookmarks']:,}　URLクリック: {row['url_clicks']:,}　プロフクリック: {row['profile_clicks']:,}\n"
    )


def generate_report(metrics_table: list[dict], ai_analysis: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(metrics_table)

    avg_imp = sum(r["impressions"]    for r in metrics_table) / total if total else 0
    avg_eng = sum(r["engagement_rate"] for r in metrics_table) / total if total else 0
    total_clicks = sum(r["url_clicks"] for r in metrics_table)

    lines = [
        f"# X投稿 パフォーマンス分析レポート ({today})",
        "",
        "## 概要",
        f"| 指標 | 値 |",
        f"|---|---|",
        f"| 分析ツイート数 | {total}件 |",
        f"| 平均インプレッション | {avg_imp:,.0f} |",
        f"| 平均エンゲージメント率 | {avg_eng:.2f}% |",
        f"| URLクリック合計 | {total_clicks:,} |",
        "",
        "---",
        "",
        "## インプレッション TOP5",
        "",
    ]
    for i, row in enumerate(top_n(metrics_table, "impressions"), 1):
        lines.append(format_tweet_card(i, row))

    lines += ["---", "", "## エンゲージメント率 TOP5", ""]
    for i, row in enumerate(top_n(metrics_table, "engagement_rate"), 1):
        lines.append(format_tweet_card(i, row))

    lines += ["---", "", "## URLクリック TOP5（note誘導効果）", ""]
    for i, row in enumerate(top_n(metrics_table, "url_clicks"), 1):
        lines.append(format_tweet_card(i, row))

    lines += ["---", "", "## ブックマーク TOP5（保存価値の高い投稿）", ""]
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

    print(f"[1/5] X APIクライアント初期化")
    client = get_x_client()

    print(f"[2/5] ツイート取得中: @{username}（最大100件）")
    tweets = fetch_tweets(client)
    print(f"      → {len(tweets)}件取得")

    print("[3/5] メトリクス集計中...")
    metrics_table = build_metrics_table(tweets)
    print(f"      → {len(metrics_table)}件集計完了")

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
