"""
X投稿 自動生成スクリプト（参考アカウント分析インサイント反映版）

フロー:
  1. CLAUDE（X）.md を読み込んでガイドラインを取得
  2. 分析/reference-insights-latest.json があれば参考アカウント分析インサイントを反映
  3. 6タイプ × 2投稿 = 計12投稿を生成（1投稿完結・140字以内）
  4. posts/YYYY-MM-DD.md に保存

投稿タイプ（各2投稿）:
  問題提起型 / あるある型 / 本音告白型 / マヒサイン型 / 逆説気づき型 / 解決策型
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
    最新の参考アカウント分析インサイントを読み込む
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
        f"【参考アカウント分析インサイント（{analyzed_at} 分析）】",
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

    # インサイントセクションの組み立て
    if insights_text:
        insights_section = f"""
---

## 参考アカウント分析から学んだバズるパターン

以下のインサイントを**必ず**投稿に反映してください。
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

以下の6タイプをそれぞれ2投稿、合計12投稿を生成してください。
各タイプで異なる職場HSPのテーマを選んでください（同じテーマの重複不可）。

【問題提起型】×2：職場HSPが詰む「構造的な理由」を本質からえぐる
【あるある型】×2：職場HSPが「これ私だ！」と感じる共感コンテンツ
【本音告白型】×2：職場での実体験・理不尽を正直に語り共感と怒りを引き出す
【マヒサイン型】×2：職場で心が限界に近づいているサインを可視化する
【逆説気づき型】×2：「停滞・消耗・失敗」を「糧・次への一歩」に変換する視点を届ける
【解決策型】×2：テーマ別の具体的解決策を「明日からできる」レベルで提示する

ルール（必ず守ること）:
- 各投稿は1投稿完結（ツリー形式・2投稿セットは不可）
- 140字以内
- ガイドラインの①〜⑤のフォーマットのいずれかを選んで使う
  （①サンドイッチ凝縮 / ②あるある列挙 / ③心のマヒサイン / ④逆説転換 / ⑤本音告白）
- タイプとフォーマットの相性を意識して選ぶ
  例：あるある型→②、マヒサイン型→③、本音告白型→⑤、問題提起型→①または④ など
- 同じタイプの2投稿は異なるフォーマットを使うこと
- 絵文字は1投稿1〜2個
- ハッシュタグなし
- 「〜です」「〜ます」調を基本にする
- 参考アカウントのインサイント（提示されている場合）を積極的に活かす

出力形式（以下のフォーマットを厳守）:
---
## 問題提起型 1

（使用フォーマット：①など）

（本文・140字以内）

---
## 問題提起型 2

（使用フォーマット：④など）

（本文・140字以内）

---
## あるある型 1

（使用フォーマット：②）

（本文・140字以内）

---
## あるある型 2

（使用フォーマット：②など）

（本文・140字以内）

---
## 本音告白型 1

（使用フォーマット：⑤）

（本文・140字以内）

---
## 本音告白型 2

（使用フォーマット：⑤など）

（本文・140字以内）

---
## マヒサイン型 1

（使用フォーマット：③）

（本文・140字以内）

---
## マヒサイン型 2

（使用フォーマット：③など）

（本文・140字以内）

---
## 逆説気づき型 1

（使用フォーマット：④）

（本文・140字以内）

---
## 逆説気づき型 2

（使用フォーマット：④など）

（本文・140字以内）

---
## 解決策型 1

（使用フォーマット：①または③）

（本文・140字以内）

---
## 解決策型 2

（使用フォーマット：①または③）

（本文・140字以内）
"""

    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    posts = message.content[0].text
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("posts", exist_ok=True)
    filename = f"posts/{today}.md"

    ref_note = "（参考アカウント分析反映）" if insights_text else ""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# X投稿案 {today} {ref_note}\n\n")
        f.write("> このファイルを確認・修正してからXに投稿してください。\n")
        if insights_text:
            f.write("> 参考アカウント（@SureGoahead・@yama_hsshsp・@sho30_hsshsp）の分析を反映しています。\n")
        f.write("\n")
        f.write(posts)

    print(f"生成完了: {filename}")
    if insights_text:
        print("  参考アカウント分析インサイントを反映しました")
    else:
        print("  インサイントなし（analyze_reference_accounts.py を先に実行するとより良い投稿が生成されます）")


if __name__ == "__main__":
    main()
