"""
X投稿 自動生成スクリプト（参考アカウント分析ベース）

フロー:
  1. CLAUDE（X）.md を読み込んでガイドラインを取得
  2. 分析/reference-insights-latest.json があれば参考アカウント分析インサイトを反映
  3. 参考アカウントの分析をベースに計9投稿を生成（1投稿完結・140字以内）
     └ 投稿1〜6：通常分析反映投稿
     └ 投稿7〜9：前向きな心もち・希望や対策系投稿
  4. posts/YYYY-MM-DD.md に保存

投稿タイプ・テーマ・構成は固定ではなく、参考アカウントの分析から導く。
"""

import anthropic
import os
import json
from datetime import datetime


# ──────────────────────────────────────────
# ガイドライン・インサイント・アカウント読み込み
# ──────────────────────────────────────────

def load_reference_accounts() -> list:
    """参考アカウント.txt を読み込む（@付き可・1行1アカウント）"""
    accounts_path = os.path.join(os.path.dirname(__file__), "参考アカウント.txt")
    accounts = []
    with open(accounts_path, encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name:
                accounts.append(name if name.startswith("@") else f"@{name}")
    return accounts


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
以下のガイドラインと参考アカウントの分析インサイトをもとに、X（Twitter）投稿を合計9本生成してください。
・投稿1〜6：通常投稿（分析インサイト反映）
・投稿7〜9：前向きな心もち・希望や対策系（別ルール適用）

{guide}
{insights_section}

---

【最重要指示：参考アカウントの分析を投稿に直接反映すること】

分析インサイトが提示されている場合、以下を**必ず**守ってください（投稿1〜6に適用）。

1. **冒頭フックは分析で判明したパターンをそのまま使う**
   - 「▼ バズる冒頭フックのパターン」に列挙されたフレーズを6本の冒頭に割り当てる
   - 分析のフックを「参考程度」に使うのは不可。冒頭の文体・構造をそのまま採用すること

2. **テーマは分析で反応が多かったものを選ぶ**
   - 「▼ 反応が多いテーマ・切り口」から6本のテーマを選ぶ
   - 分析に載っていないテーマは使わない

3. **文体・スタイルは分析のコツを参考にしつつ、口調だけは必ず上書きする**
   - 絵文字の有無・改行の使い方・鉤括弧の使い方など構成面は分析に寄せる
   - **ただし口調は参考アカウントに関係なく必ず「〜です」「〜ます」調にする**
   - 「〜だよ」「〜なんだよね」などの口語体・タメ口は一切使わない

4. **「★ 即日反映すべき改善ポイント」を6本全てに適用する**
   - 最重要ポイントなので、1本も例外なく全投稿に反映すること

分析インサイントがない場合のみ、ガイドラインの基本ルールに従って生成する。

---

【投稿7〜9：前向きな心もち・希望や対策系ルール】

投稿7〜9は「読者が明日への一歩を踏み出せる」投稿を作成してください。

- **必ず含める要素**:
  1. 前向きな心もち・気持ちの持ち方（「こう考えると少し楽になります」「視点を変えると〜」等）
  2. 希望のある未来像・出口のイメージ（「焦らなくていい」「今の積み重ねが必ず〜」等）
  3. 具体的な対策・行動のヒント（1〜2点に絞り、ハードルを低く提示する）

- **テーマ例**（3本で重複しないこと）:
  - 今のしんどさが「変わりたい」というサインである気づき
  - 小さな一歩でいい、完璧にやらなくていいという許可
  - 副業・外の世界に目を向けることで心が楽になる話
  - 自分を責めるのをやめると動けるようになる話
  - 今日より明日が少しだけ良くなるための具体的な行動
  - 今の状況を変える最初の一歩は小さくていい

- **文体ルール**:
  - 口調は「〜です」「〜ます」調で統一
  - 押しつけにならず「こんな方法もあります」のトーン
  - 読み終えたあと「やってみようかな」と思えるような余韻を残す
  - 「絶対うまくいく！」などの根拠のない断言は使わない

---

【共通ルール（全9本に必ず守ること）】
- 各投稿は1投稿完結・140字以内
- 同じテーマ・同じ切り口の重複不可
- ハッシュタグなし
- **口調は全投稿「〜です」「〜ます」調で統一（絶対ルール・例外なし）**

【出力形式（厳守）】
---
## 投稿1

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿2

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿3

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿4

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿5

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿6

（使用した分析フック・テーマを1行で明記）

（本文・140字以内）

---
## 投稿7【前向きな心もち・希望や対策】

（テーマを1行で明記）

（本文・140字以内）

---
## 投稿8【前向きな心もち・希望や対策】

（テーマを1行で明記）

（本文・140字以内）

---
## 投稿9【前向きな心もち・希望や対策】

（テーマを1行で明記）

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
    posts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = os.path.join(posts_dir, f"{today}.md")

    ref_accounts = load_reference_accounts()
    ref_note = "（参考アカウント分析反映）" if insights_text else ""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# X投稿案 {today} {ref_note}\n\n")
        f.write("> 投稿1〜6：通常投稿　／　投稿7〜9：前向きな心もち・希望や対策\n")
        f.write("> このファイルを確認・修正してからXに投稿してください。\n")
        if insights_text:
            f.write(f"> 参考アカウント（{'・'.join(ref_accounts)}）の分析を反映しています。\n")
        f.write("\n")
        f.write(posts)

    print(f"生成完了: {filename}")
    print(f"  投稿数: 9本（通常6 + 前向き・希望・対策3）")
    if insights_text:
        print("  参考アカウント分析インサイトを反映しました")
    else:
        print("  インサイトなし（analyze_reference_accounts.py を先に実行するとより良い投稿が生成されます）")


if __name__ == "__main__":
    main()
