"""
X投稿 週次パフォーマンス分析 + 分析結果を反映した投稿自動生成

フロー:
  1. X API v2 で直近7日間のツイートのメトリクスを取得
  2. 指標ごとにランキング集計
  3. Claude AI でパターン分析・改善提案を生成
  4. 分析レポートを 分析/YYYY-MM-DD.md に保存
  5. 分析結果を反映した投稿案6セットを posts/YYYY-MM-DD-analyzed.md に保存
"""

import anthropic
import tweepy
import os
import json
from datetime import datetime, timezone, timedelta


# ──────────────────────────────────────────
# ガイドライン読み込み
# ──────────────────────────────────────────

def load_guide() -> str:
    """CLAUDE（X）.md を読み込む"""
    guide_path = os.path.join(os.path.dirname(__file__), "CLAUDE（X）.md")
    with open(guide_path, encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────
# X API クライアント
# ──────────────────────────────────────────

def get_x_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        wait_on_rate_limit=True,
    )


# ──────────────────────────────────────────
# ツイート取得（直近7日間）
# ──────────────────────────────────────────

def fetch_tweets_last_7days(client: tweepy.Client) -> list:
    """認証ユーザーの直近7日間のツイートをメトリクス付きで取得"""
    try:
        me_resp = client.get_me(user_auth=True)
    except tweepy.errors.Forbidden as e:
        raise SystemExit(
            "\n[エラー] X API 403 Forbidden\n"
            "対処法:\n"
            "  developer.twitter.com > アプリ > User authentication settings で\n"
            "  OAuth 1.0a を有効化・App permissions を Read に設定し、\n"
            "  アクセストークンを再生成してGitHubシークレットを更新してください\n"
            f"  詳細: {e}"
        ) from e
    except tweepy.errors.Unauthorized as e:
        raise SystemExit(
            "\n[エラー] X API 401 Unauthorized\n"
            "GitHubシークレット (X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET) を確認してください\n"
            f"  詳細: {e}"
        ) from e

    user_id = me_resp.data.id
    print(f"      → ユーザーID: {user_id}")

    start_time = datetime.now(timezone.utc) - timedelta(days=7)
    tweet_fields = [
        "created_at", "text",
        "public_metrics", "non_public_metrics", "organic_metrics",
    ]

    try:
        resp = client.get_users_tweets(
            id=user_id,
            max_results=100,
            start_time=start_time,
            tweet_fields=tweet_fields,
            user_auth=True,
        )
    except tweepy.errors.Forbidden:
        print("      [INFO] non_public_metrics は取得不可。public_metrics のみで取得します")
        resp = client.get_users_tweets(
            id=user_id,
            max_results=100,
            start_time=start_time,
            tweet_fields=["created_at", "text", "public_metrics"],
            user_auth=True,
        )

    return resp.data or []


# ──────────────────────────────────────────
# メトリクス集計
# ──────────────────────────────────────────

def extract_metrics(tweet) -> dict:
    pm = tweet.public_metrics      or {}
    nm = tweet.non_public_metrics  or {}
    om = tweet.organic_metrics     or {}

    impressions = (om.get("impression_count") or pm.get("impression_count") or 0)
    likes       = (om.get("like_count")    or pm.get("like_count")    or 0)
    retweets    = (om.get("retweet_count") or pm.get("retweet_count") or 0)
    replies     = (om.get("reply_count")   or pm.get("reply_count")   or 0)
    quotes      = (om.get("quote_count")   or pm.get("quote_count")   or 0)
    bookmarks   = pm.get("bookmark_count") or 0
    url_clicks      = (nm.get("url_link_clicks")     or om.get("url_link_clicks")     or 0)
    profile_clicks  = (nm.get("user_profile_clicks") or om.get("user_profile_clicks") or 0)

    total_eng = likes + retweets + replies + quotes + bookmarks
    eng_rate  = round(total_eng / impressions * 100, 2) if impressions > 0 else 0.0

    return {
        "id":             str(tweet.id),
        "created_at":     tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "",
        "text":           tweet.text or "",
        "impressions":    impressions,
        "likes":          likes,
        "retweets":       retweets,
        "replies":        replies,
        "quotes":         quotes,
        "bookmarks":      bookmarks,
        "url_clicks":     url_clicks,
        "profile_clicks": profile_clicks,
        "engagement_rate": eng_rate,
    }


def build_metrics_table(tweets: list) -> list[dict]:
    rows = []
    for tweet in tweets:
        try:
            rows.append(extract_metrics(tweet))
        except Exception as e:
            print(f"      [WARN] ツイートID {tweet.id}: {e}")
    return rows


def top_n(rows: list[dict], key: str, n: int = 5) -> list[dict]:
    return sorted(rows, key=lambda x: x[key], reverse=True)[:n]


# ──────────────────────────────────────────
# Claude: パターン分析
# ──────────────────────────────────────────

def analyze_with_claude(metrics_table: list[dict], client: anthropic.Anthropic) -> str:
    def shorten(rows):
        return [{**r, "text": r["text"][:100].replace("\n", " ")} for r in rows]

    summary = {
        "top_impressions":   shorten(top_n(metrics_table, "impressions",    10)),
        "top_engagement":    shorten(top_n(metrics_table, "engagement_rate", 10)),
        "top_url_clicks":    shorten(top_n(metrics_table, "url_clicks",      10)),
        "top_bookmarks":     shorten(top_n(metrics_table, "bookmarks",       10)),
    }

    prompt = f"""
あなたはXアカウント（@JUN1007S）の投稿アナリストです。
以下は直近7日間のツイートのパフォーマンスデータです。

アカウントプロフィール：
- 30代男性・3歳娘持ちのサラリーマン
- 根回し・アピールが苦手な「コツコツ型」副業挑戦者
- 45歳脱サラ・月200万円目標 / X発信+note販売中

データ：
{json.dumps(summary, ensure_ascii=False, indent=2)}

以下の観点で日本語で分析してください（600〜800字）：

### 1. インプレッションが多い投稿の共通パターン
### 2. エンゲージメント率が高い投稿の特徴
### 3. URLクリック（note誘導）に効果的なパターン
### 4. 今後の投稿改善アドバイス（具体的に3〜5点）
### 5. 避けるべきパターン

箇条書きと見出しを使い、明日から実践できる具体的な内容にしてください。
"""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ──────────────────────────────────────────
# Claude: 分析結果を反映した投稿生成
# ──────────────────────────────────────────

def generate_posts_with_insights(analysis: str, client: anthropic.Anthropic) -> str:
    guide = load_guide()
    prompt = f"""
以下のガイドラインと今週の分析結果を踏まえて、X（Twitter）投稿を生成してください。

{guide}

【今週の分析結果・改善ポイント】
{analysis}

上記の分析から得た「バズりやすいパターン」「エンゲージメントが高い書き方」を意識しながら、
以下の3タイプをそれぞれ2投稿、合計6投稿を生成してください。

【共感型】×2：読者の悩みや感情を言語化する
【ストーリー型】×2：自分の経験・進捗・葛藤をリアルに語る
【問いかけ型】×2：読者に「自分ごと」として考えさせる

ルール（必ず守ること）:
- 各投稿は1投稿完結（ツリー形式・2投稿セットは不可）
- 140字以内
- ガイドラインの①〜⑤の構成フォーマットのいずれかを使う（複数のフォーマットを混ぜて使うこと）
- 絵文字は1投稿2個程度
- ハッシュタグなし

出力形式（以下のフォーマットを厳守）:
---
## 共感型 1

（使用フォーマット：①サンドイッチ形式 など）

（本文・140字以内）

---
## 共感型 2
...（以下同様）
"""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ──────────────────────────────────────────
# レポート生成
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
        f"- ブックマーク: {row['bookmarks']:,}　URLクリック: {row['url_clicks']:,}\n"
    )


def generate_report(metrics_table: list[dict], analysis: str, period_start: str, period_end: str) -> str:
    total     = len(metrics_table)
    avg_imp   = sum(r["impressions"]     for r in metrics_table) / total if total else 0
    avg_eng   = sum(r["engagement_rate"] for r in metrics_table) / total if total else 0
    total_url = sum(r["url_clicks"]      for r in metrics_table)

    lines = [
        f"# X投稿 週次パフォーマンス分析レポート",
        f"**集計期間**: {period_start} 〜 {period_end}",
        "",
        "## サマリー",
        "| 指標 | 値 |",
        "|---|---|",
        f"| 分析ツイート数 | {total}件 |",
        f"| 平均インプレッション | {avg_imp:,.0f} |",
        f"| 平均エンゲージメント率 | {avg_eng:.2f}% |",
        f"| URLクリック合計 | {total_url:,} |",
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

    lines += ["---", "", "## ブックマーク TOP5", ""]
    for i, row in enumerate(top_n(metrics_table, "bookmarks"), 1):
        lines.append(format_tweet_card(i, row))

    lines += [
        "---",
        "",
        "## AI分析・改善提案",
        "",
        analysis,
        "",
        "---",
        f"*生成日時: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    today      = datetime.now(timezone.utc)
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    date_str   = today.strftime("%Y-%m-%d")

    print("[1/6] X APIクライアント初期化")
    x_client = get_x_client()

    print(f"[2/6] 直近7日間のツイート取得中（{week_start} 〜 {week_end}）")
    tweets = fetch_tweets_last_7days(x_client)
    print(f"      → {len(tweets)}件取得")

    if not tweets:
        print("      [INFO] 対象ツイートが0件のため終了します")
        return

    print("[3/6] メトリクス集計中...")
    metrics_table = build_metrics_table(tweets)

    print("[4/6] Claude AIでパターン分析中...")
    claude_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    analysis = analyze_with_claude(metrics_table, claude_client)

    print("[5/6] 分析レポート保存中...")
    report = generate_report(metrics_table, analysis, week_start, week_end)
    os.makedirs("分析", exist_ok=True)
    report_path = f"分析/{date_str}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"      → {report_path}")

    print("[6/6] 分析結果を反映した投稿案を生成中...")
    posts = generate_posts_with_insights(analysis, claude_client)
    os.makedirs("posts", exist_ok=True)
    posts_path = f"posts/{date_str}-analyzed.md"
    with open(posts_path, "w", encoding="utf-8") as f:
        f.write(f"# X投稿案（分析結果反映版） {date_str}\n\n")
        f.write("> 今週のパフォーマンス分析を踏まえて生成した投稿案です。\n")
        f.write(f"> 分析レポート: [分析/{date_str}.md](../分析/{date_str}.md)\n\n")
        f.write(posts)
    print(f"      → {posts_path}")

    print(f"\n完了！")
    print(f"  分析レポート : {report_path}")
    print(f"  投稿案       : {posts_path}")


if __name__ == "__main__":
    main()
