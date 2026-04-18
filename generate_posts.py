"""
X投稿 自動生成スクリプト（参考アカウント分析ベース）

フロー:
  1. CLAUDE（X）.md を読み込んでガイドラインを取得
  2. 分析/reference-insights-latest.json があれば参考アカウント分析インサイトを反映
  3. 参考アカウントの分析をベースに計6投稿を生成（1投稿完結・140字以内）
  4. posts/YYYY-MM-DD.md に保存

投稿タイプ・テーマ・構成は固定ではなく、参考アカウントの分析から導く。
"""

import anthropic
import os
import json
from datetime import datetime


# ──────────────────────────────────────────
# ガイドライン・インサイント読み込み
# ──────────────────────────────────────────

def load_guide() -> str:
    """CLAUDE（X）.md を読み込む"""
    guide_path = os.path.join(os.path.dirname(__file__), "CLAUDE（X）.md")
    with open(guide_path, encoding="utf-8") as f:
        return f.read()


def load_insights() -> str:
    """
    最新の参考アカウント分析インサイトを読み込む
    ファイルが存在しない場合は空文字を返す
    """
    insights_path = os.path.join(
        os.path.dirname(__file__), "分析", "reference-insights-latest.json"
    )
    if not os.path.exists(insights_path):
        return ""

    with open(insights_path, encoding="utf-8") as f:
        insights = json.load(f)

    analyzed_at  = insights.get("analyzed_at", "不明")
    accounts     = insights.get("accounts", [])
    top_hooks    = insights.get("top_hooks", [])
    top_themes   = insights.get("top_themes", [])
    style_tips   = insights.get("style_tips", [])
    improvements = insights.get("immediate_improvements", [])
    summary      = insights.get("summary", "")

    accounts_str = "、".join(f"@{a}" for a in accounts) if accounts else "参考アカウント"

    lines = [
        f"【参考アカウント分析インサイト（{analyzed_at} 分析）】",
        f"分析対象: {accounts_str}",
        "",
        "▼ バズる冒頭フックのパターン",
    ]
    for h in top_hooks:
        lines.append(f"  ・{h}")
    lines += ["", "▼ 反応が多いテーマ・切り口"]
    for t in top_themes:
        lines.append(f"  ・{t}")
    lines += ["", "▼ 文体・スタイルのコツ"]
    for s in style_tips:
        lines.append(f"  ・{s}")
    lines += ["", "▼ 即日反映すべき改善ポイント（最重要）"]
    for imp in improvements:
        lines.append(f"  ★ {imp}")
    if summary:
        lines += ["", f"▼ 総まとめ: {summary}"]

    return "\n".join(lines)


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    guide         = load_guide()
    insights_text = load_insights()

    # インサイトセクションの組み立て
    if insights_text:
        insights_section = f"""
---

## 参考アカウント分析から学んだバズるパターン

以下のインサイトを**必ず**投稿に反映してください。
特に「★ 即日反映すべき改善ポイント」は最優先で取り入れること。

{insights_text}

---
"""
    else:
        insights_section = ""

    prompt = f"""
以下のガイドラインに従って、X（Twitter）投稿を生成してください。

{guide}
{insights_section}

---

参考アカウントの分析インサイトをベースに、計6投稿を生成してください。

【生成の指針】
- 分析で判明した「バズる冒頭フック」を最優先で採用する
- エンゲージメントが高かったテーマ・切り口を選ぶ
- 分析で見えた文体・絵文字・改行のコツを踏襲する
- 「★ 即日反映すべき改善ポイント」を必ず取り入れる
- 分析インサイトがない場合はガイドラインの基本ルールに従う

【ルール（必ず守ること）】
- 各投稿は1投稿完結・140字以内
- 同じテーマ・同じ切り口の重複不可
- 絵文字は1投稿1〜2個
- ハッシュタグなし
- 「〜です」「〜ます」調を基本にする

【出力形式（厳守）】
---
## 投稿1

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）

---
## 投稿2

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）

---
## 投稿3

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）

---
## 投稿4

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）

---
## 投稿5

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）

---
## 投稿6

（この投稿のテーマ・ねらいを1行で）

（本文・140字以内）
"""

    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    posts = message.content[0].text
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("posts", exist_ok=True)
    filename = f"posts/{today}.md"

    accounts = ["@Influencer侍", "@paya_paya_kun", "@IObousan"]
    ref_note = "（参考アカウント分析反映）" if insights_text else ""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# X投稿案 {today} {ref_note}\n\n")
        f.write("> このファイルを確認・修正してからXに投稿してください。\n")
        if insights_text:
            f.write(f"> 参考アカウント（{'・'.join(accounts)}）の分析を反映しています。\n")
        f.write("\n")
        f.write(posts)

    print(f"生成完了: {filename}")
    if insights_text:
        print("  参考アカウント分析インサイトを反映しました")
    else:
        print("  インサイトなし（analyze_reference_accounts.py を先に実行するとより良い投稿が生成されます）")


if __name__ == "__main__":
    main()
