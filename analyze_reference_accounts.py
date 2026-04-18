"""
参考アカウントの高エンゲージメント投稿を分析し、
投稿生成に活用するインサイトを抽出するスクリプト

参考アカウント.txt に記載されたアカウントの投稿を取得・分析して:
  - 分析/reference-accounts-YYYY-MM-DD.md  （詳細レポート）
  - 分析/reference-insights-latest.json    （generate_posts.py が読み込む最新インサイト）
に保存する

取得指標:
  他アカウントのインプレッションは非公開のため、
  いいね・RT・返信・引用・ブックマークの合計をエンゲージメント指標として使用
"""

import anthropic
import tweepy
import requests
import base64
import os
import re
import json
import time
from datetime import datetime, timezone, timedelta


# ──────────────────────────────────────────
# X API クライアント（Bearer Token / App-only）
# ──────────────────────────────────────────

def fetch_bearer_token(api_key: str, api_secret: str) -> str:
    """API Key + Secret から Bearer Token を取得"""
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    resp = requests.post(
        "https://api.twitter.com/oauth2/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        data="grant_type=client_credentials",
    )
    if resp.status_code != 200:
        raise SystemExit(
            f"\n[エラー] Bearer Token 取得失敗 (HTTP {resp.status_code})\n{resp.text}"
        )
    return resp.json()["access_token"]


def get_x_client() -> tweepy.Client:
    api_key    = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    if not api_key or not api_secret:
        raise SystemExit("\n[エラー] 環境変数 X_API_KEY / X_API_SECRET が設定されていません")
    bearer_token = fetch_bearer_token(api_key, api_secret)
    return tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)


# ──────────────────────────────────────────
# 参考アカウント読み込み
# ──────────────────────────────────────────

def load_reference_accounts() -> list:
    """参考アカウント.txt を読み込む（@付き可・1行1アカウント）"""
    accounts_path = os.path.join(os.path.dirname(__file__), "参考アカウント.txt")
    accounts = []
    with open(accounts_path, encoding="utf-8") as f:
        for line in f:
            name = line.strip().lstrip("@")
            if name:
                accounts.append(name)
    return accounts


# ──────────────────────────────────────────
# ユーザー情報取得
# ──────────────────────────────────────────

def get_user_info(client: tweepy.Client, username: str) -> dict:
    try:
        resp = client.get_user(
            username=username,
            user_fields=["name", "description", "public_metrics", "created_at"],
        )
    except tweepy.errors.NotFound:
        print(f"      [WARN] @{username} が見つかりません")
        return {}
    except Exception as e:
        print(f"      [WARN] @{username} の情報取得失敗: {e}")
        return {}

    if not resp.data:
        print(f"      [WARN] @{username} のデータが空です")
        return {}

    u  = resp.data
    pm = u.public_metrics or {}
    return {
        "id":          str(u.id),
        "username":    username,
        "name":        u.name,
        "description": u.description or "",
        "followers":   pm.get("followers_count", 0),
        "tweet_count": pm.get("tweet_count", 0),
    }


# ──────────────────────────────────────────
# ツイート取得（オリジナル投稿のみ）
# ──────────────────────────────────────────

def fetch_user_tweets(
    client: tweepy.Client,
    user_id: str,
    max_count: int = 50,
    days: int = 30,
) -> list:
    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    tweets     = []
    pagination_token = None

    while len(tweets) < max_count:
        batch_size = max(5, min(100, max_count - len(tweets)))
        try:
            resp = client.get_users_tweets(
                id=user_id,
                max_results=batch_size,
                start_time=start_time,
                tweet_fields=["created_at", "text", "public_metrics"],
                exclude=["retweets", "replies"],
                pagination_token=pagination_token,
            )
        except tweepy.errors.TooManyRequests:
            print("      [INFO] レート制限。取得済みデータで続行します")
            break
        except Exception as e:
            print(f"      [WARN] ツイート取得エラー: {e}")
            break

        if not resp.data:
            break

        for tweet in resp.data:
            pm        = tweet.public_metrics or {}
            likes     = pm.get("like_count",     0)
            retweets  = pm.get("retweet_count",  0)
            replies   = pm.get("reply_count",    0)
            quotes    = pm.get("quote_count",    0)
            bookmarks = pm.get("bookmark_count", 0)
            total_eng = likes + retweets + replies + quotes + bookmarks

            tweets.append({
                "id":         str(tweet.id),
                "created_at": tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "",
                "text":       tweet.text or "",
                "likes":      likes,
                "retweets":   retweets,
                "replies":    replies,
                "quotes":     quotes,
                "bookmarks":  bookmarks,
                "total_eng":  total_eng,
            })

        meta = resp.meta or {}
        pagination_token = meta.get("next_token")
        if not pagination_token:
            break

    return tweets


# ──────────────────────────────────────────
# Claude: 参考アカウント分析
# ──────────────────────────────────────────

def analyze_with_claude(
    accounts_data: list,
    claude_client: anthropic.Anthropic,
) -> tuple:
    """
    参考アカウントを分析し、インサイトを返す

    Returns:
        (詳細分析テキスト, インサイントdict)
    """
    # Claude に渡すデータを整形（上位5件の高エンゲージメント投稿）
    data_for_claude = []
    for acc in accounts_data:
        top_tweets = sorted(acc["tweets"], key=lambda t: t["total_eng"], reverse=True)[:5]
        data_for_claude.append({
            "username":    acc["username"],
            "name":        acc["name"],
            "followers":   acc["followers"],
            "description": acc["description"],
            "tweet_count": len(acc["tweets"]),
            "avg_eng":     acc["avg_eng"],
            "top_tweets": [
                {
                    "created_at": t["created_at"],
                    "text":       t["text"][:200].replace("\n", " "),
                    "likes":      t["likes"],
                    "retweets":   t["retweets"],
                    "bookmarks":  t["bookmarks"],
                    "total_eng":  t["total_eng"],
                }
                for t in top_tweets
            ],
        })

    # ── パート1: 詳細分析 ──
    analysis_prompt = f"""
あなたはSNSアカウント分析の専門家です。
以下は、職場HSP向けに発信するXアカウント（@JUN1007S）が参考にしている
3アカウントの直近30日間のデータです。

{json.dumps(data_for_claude, ensure_ascii=False, indent=2)}

---

以下を日本語で分析してください。

## 【各アカウントの分析】

各アカウントごとに以下を出力してください：

### @{{username}}（{{name}}）
- **エンゲージメントが高い投稿の共通パターン**（冒頭フックの作り方・構成・テーマ）
- **文体・トーンの特徴**（言葉遣い・絵文字・改行・文字数の使い方）
- **バズった投稿の具体例**（上記データから1〜2件を引用して解説）
- **@JUN1007S が今すぐ取り入れられるポイント**（1〜2点）

---

## 【3アカウント共通の「バズるパターン」サマリー】

### バズる冒頭フックのパターン（3〜5点）
### 反応が多いテーマ・切り口（3〜5点）
### 構成・フォーマットの傾向（3〜5点）
### 絵文字・改行・文字数の使い方（2〜3点）
### @JUN1007S の投稿に即日反映できる改善ポイント（最重要3点）

---
実践的で具体的に。曖昧な表現を避け、データの根拠を示してください。
"""

    analysis_msg = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": analysis_prompt}],
    )
    analysis_text = analysis_msg.content[0].text

    # ── パート2: インサイトJSON生成（generate_posts.py が読み込む用）──
    insights_prompt = f"""
以下は参考アカウントの分析結果です。

{analysis_text}

---

この分析から、X投稿を生成する際に必ず反映すべき「バズるポイント」を
以下のJSON形式で出力してください。

{{
  "analyzed_at": "{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
  "accounts": {json.dumps([acc["username"] for acc in accounts_data], ensure_ascii=False)},
  "top_hooks": ["冒頭フックのパターン1", "パターン2", "パターン3"],
  "top_themes": ["効果的なテーマ1", "テーマ2", "テーマ3"],
  "style_tips": ["文体・スタイルのコツ1", "コツ2", "コツ3"],
  "immediate_improvements": ["即日改善ポイント1", "ポイント2", "ポイント3"],
  "summary": "3アカウントに共通するバズるパターンの要約（100字以内）"
}}

JSONのみを出力してください。余分な説明不要。
"""

    insights_msg = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="あなたはJSONのみを出力するアシスタントです。説明文・前置き・コードブロック記号は一切不要です。JSONオブジェクトだけを出力してください。",
        messages=[{"role": "user", "content": insights_prompt}],
    )
    raw_response = insights_msg.content[0].text.strip()
    print(f"      [DEBUG] インサイントJSON応答（先頭200字）: {raw_response[:200]}")

    insights = _parse_insights_json(raw_response, accounts_data)
    return analysis_text, insights


def _parse_insights_json(raw: str, accounts_data: list) -> dict:
    """
    Claude のレスポンスから JSON を堅牢に抽出する。
    コードブロック・余分なテキスト・改行ズレに対応。
    """
    candidates = []

    # 1. コードブロック内を試す
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if m:
        candidates.append(m.group(1).strip())

    # 2. 最外の { } ブロックを試す
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        candidates.append(m.group(0).strip())

    # 3. そのまま試す
    candidates.append(raw)

    for candidate in candidates:
        try:
            result = json.loads(candidate)
            print("      [OK] インサイントJSON のパースに成功しました")
            return result
        except json.JSONDecodeError:
            continue

    # すべて失敗 → フォールバック（デバッグ用に生レスポンスを保存）
    print(f"      [WARN] JSON パース失敗。生レスポンス:\n{raw[:500]}")
    return {
        "analyzed_at":            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "accounts":               [acc["username"] for acc in accounts_data],
        "top_hooks":              [],
        "top_themes":             [],
        "style_tips":             [],
        "immediate_improvements": [],
        "summary":                "参考アカウントの分析データを取得しました（JSONパース失敗）",
    }


# ──────────────────────────────────────────
# レポート生成
# ──────────────────────────────────────────

def generate_report(accounts_data: list, analysis: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# 参考アカウント分析レポート",
        f"**生成日時**: {date_str}",
        "**集計期間**: 直近30日間",
        "",
        "---",
        "",
        "## 分析対象アカウント",
        "",
        "| アカウント | フォロワー | 取得投稿数 | 平均エンゲージメント |",
        "|---|---|---|---|",
    ]

    for acc in accounts_data:
        lines.append(
            f"| @{acc['username']}（{acc['name']}） "
            f"| {acc['followers']:,} "
            f"| {len(acc['tweets'])}件 "
            f"| {acc['avg_eng']} |"
        )

    lines += ["", "---", ""]

    # 各アカウントのトップ投稿
    for acc in accounts_data:
        top3 = sorted(acc["tweets"], key=lambda t: t["total_eng"], reverse=True)[:3]
        lines += [
            f"## @{acc['username']}（{acc['name']}） エンゲージメントTOP3",
            "",
        ]
        for i, t in enumerate(top3, 1):
            preview = t["text"][:100].replace("\n", " ")
            if len(t["text"]) > 100:
                preview += "…"
            lines += [
                f"**{i}位**（{t['created_at']}）",
                f"> {preview}",
                f"- いいね: {t['likes']:,}　RT: {t['retweets']:,}　返信: {t['replies']:,}"
                f"　引用: {t['quotes']:,}　ブックマーク: {t['bookmarks']:,}",
                f"- 合計エンゲージメント: {t['total_eng']:,}",
                "",
            ]

    lines += [
        "---",
        "",
        "## AI分析・インサイト",
        "",
        analysis,
        "",
        "---",
        "*Powered by Claude Sonnet / Tweepy*",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("[1/5] 参考アカウントを読み込み中...")
    accounts = load_reference_accounts()
    print(f"      → {len(accounts)}件: {', '.join('@' + a for a in accounts)}")

    print("[2/5] X APIクライアント初期化（Bearer Token）")
    client = get_x_client()

    print("[3/5] 各アカウントの投稿を取得中...")
    accounts_data = []
    for username in accounts:
        print(f"      @{username} を取得中...")
        user_info = get_user_info(client, username)
        if not user_info:
            continue

        tweets = fetch_user_tweets(client, user_info["id"], max_count=50, days=30)
        print(f"        → {len(tweets)}件取得 / フォロワー: {user_info['followers']:,}")

        total_eng = sum(t["total_eng"] for t in tweets)
        avg_eng   = round(total_eng / len(tweets), 1) if tweets else 0.0

        accounts_data.append({
            **user_info,
            "tweets":    tweets,
            "total_eng": total_eng,
            "avg_eng":   avg_eng,
        })
        time.sleep(1)  # レート制限対策

    if not accounts_data:
        print("      [INFO] データが取得できませんでした。スキップします")
        return

    print("[4/5] Claude AIで分析中...")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise SystemExit("\n[エラー] 環境変数 ANTHROPIC_API_KEY が設定されていません")
    claude_client = anthropic.Anthropic(api_key=anthropic_key)
    analysis_text, insights = analyze_with_claude(accounts_data, claude_client)

    print("[5/5] レポートとインサイトを保存中...")
    output_dir = os.path.join(os.path.dirname(__file__), "分析")
    os.makedirs(output_dir, exist_ok=True)

    # 詳細レポート（日付付き）
    report      = generate_report(accounts_data, analysis_text)
    report_path = os.path.join(output_dir, f"reference-accounts-{date_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"      → {report_path}")

    # 最新インサイントJSON（generate_posts.py が読み込む）
    insights_path = os.path.join(output_dir, "reference-insights-latest.json")
    with open(insights_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    print(f"      → {insights_path}")

    print("\n完了！")
    print(f"  詳細レポート   : {report_path}")
    print(f"  インサイントJSON: {insights_path}")


if __name__ == "__main__":
    main()
