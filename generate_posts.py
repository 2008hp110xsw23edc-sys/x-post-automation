"""
X投稿 自動生成スクリプト
- CLAUDE（X）.md を読み込んでガイドラインを取得
- 共感型×2・ストーリー型×2・問いかけ型×2 の計6投稿を生成（1投稿完結）
- posts/YYYY-MM-DD.md に保存
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

（使用フォーマット：）

（本文・140字以内）

---
## ストーリー型 1
...（以下同様）
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
