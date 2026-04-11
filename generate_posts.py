"""
X投稿 自動生成スクリプト
- CLAUDE（X）.md を読み込んでガイドラインを取得
- 6タイプ × 1投稿 = 計6投稿を生成（1投稿完結）
- posts/YYYY-MM-DD.md に保存

投稿タイプ：
  問題提起型 / あるある型 / 本音告白型 / マヒサイン型 / 逆説気づき型 / 解決策型

使用フォーマット（①〜⑤から自動選択）：
  ①サンドイッチ凝縮 / ②あるある列挙 / ③心のマヒサイン / ④逆説転換 / ⑤本音告白
"""

import anthropic
import os
from datetime import datetime


def load_guide() -> str:
    """CLAUDE（X）.md を読み込む"""
    guide_path = os.path.join(os.path.dirname(__file__), "CLAUDE（X）.md")
    with open(guide_path, encoding="utf-8") as f:
        return f.read()


def main():
    guide = load_guide()

    prompt = f"""
以下のガイドラインに従って、X（Twitter）投稿を生成してください。

{guide}

---

以下の6タイプをそれぞれ1投稿、合計6投稿を生成してください。
テーマは各タイプで異なる職場HSPの悩みを選んでください（重複不可）。

【問題提起型】：職場HSPが詰む「構造的な理由」を本質からえぐる
【あるある型】：職場HSPが「これ私だ！」と感じる共感コンテンツ
【本音告白型】：職場での実体験・理不尽を正直に語り共感と怒りを引き出す
【マヒサイン型】：職場で心が限界に近づいているサインを可視化する
【逆説気づき型】：「停滞・消耗・失敗」を「糧・次への一歩」に変換する視点を届ける
【解決策型】：テーマ別の具体的解決策を「明日からできる」レベルで提示する

ルール（必ず守ること）:
- 各投稿は1投稿完結
- 140字以内
- ガイドラインの①〜⑤のフォーマットのいずれかを選んで使う
  （①サンドイッチ凝縮 / ②あるある列挙 / ③心のマヒサイン / ④逆説転換 / ⑤本音告白）
- タイプとフォーマットの相性を意識して選ぶこと
  例：あるある型→②、マヒサイン型→③、本音告白型→⑤、問題提起型→①④ など
- 絵文字は1投稿1〜2個
- ハッシュタグなし
- 「〜です」「〜ます」調を基本にする

出力形式（以下のフォーマットを厳守）:
---
## 問題提起型

（使用フォーマット：① など）

（本文・140字以内）

---
## あるある型

（使用フォーマット：②）

（本文・140字以内）

---
## 本音告白型

（使用フォーマット：⑤）

（本文・140字以内）

---
## マヒサイン型

（使用フォーマット：③）

（本文・140字以内）

---
## 逆説気づき型

（使用フォーマット：④）

（本文・140字以内）

---
## 解決策型

（使用フォーマット：①または③）

（本文・140字以内）
"""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    posts = message.content[0].text
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("posts", exist_ok=True)
    filename = f"posts/{today}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# X投稿案 {today}\n\n")
        f.write("> このファイルを確認・修正してからXに投稿してください。\n\n")
        f.write(posts)

    print(f"生成完了: {filename}")


if __name__ == "__main__":
    main()
