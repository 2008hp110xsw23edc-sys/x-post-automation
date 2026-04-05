# X投稿 自動生成 & パフォーマンス分析システム

## 全体フロー

```
【毎日 5:00 JST】
Claude API → 投稿案を生成 → posts/YYYY-MM-DD.md に保存 → GitHub で確認・修正 → X に投稿

【毎週月曜 6:00 JST】
X API → 直近100件のメトリクス取得 → Claude AI でパターン分析 → analytics/YYYY-MM-DD.md に保存
```

---

## 機能一覧

### 1. 投稿自動生成（`generate_posts.py`）

毎日 3タイプ × 2セット = 6セットの投稿案を生成します。

| タイプ | 内容 | セット数 |
|---|---|---|
| 共感型 | 読者の悩みや感情を言語化 | 2 |
| ストーリー型 | 自分の経験・進捗・葛藤をリアルに語る | 2 |
| 問いかけ型 | 読者に「自分ごと」として考えさせる | 2 |

### 2. パフォーマンス分析（`analyze_posts.py`）

直近100件のツイートを取得し、以下を分析します。

| 分析項目 | 内容 |
|---|---|
| インプレッション TOP5 | 最も多く表示された投稿 |
| エンゲージメント率 TOP5 | いいね・RT・返信・ブックマーク率が高い投稿 |
| URLクリック TOP5 | note誘導に最も効果的だった投稿 |
| ブックマーク TOP5 | 保存価値が高いと判断された投稿 |
| AI分析・改善提案 | Claude によるパターン分析と具体的アドバイス |

---

## セットアップ

### GitHub Secrets の設定（初回のみ）

以下の5つのシークレットを GitHub リポジトリに登録してください。

```bash
gh secret set ANTHROPIC_API_KEY   --body "sk-ant-..."
gh secret set X_API_KEY           --body "..."
gh secret set X_API_SECRET        --body "..."
gh secret set X_ACCESS_TOKEN      --body "..."
gh secret set X_ACCESS_TOKEN_SECRET --body "..."
```

### X API の権限設定

[developer.twitter.com](https://developer.twitter.com) にて：
1. アプリ → **User authentication settings** を開く
2. **OAuth 1.0a** を有効化
3. **App permissions: Read** を選択
4. Access Token & Secret を再生成（権限変更後は再生成が必要）

> `non_public_metrics`（URLクリック数、プロフィールクリック数）の取得には OAuth 1.0a ユーザー認証が必須です。

---

## ファイル構成

```
x-post-automation/
├── generate_posts.py          # 投稿自動生成スクリプト
├── analyze_posts.py           # パフォーマンス分析スクリプト
├── .env.example               # 環境変数テンプレート
├── posts/
│   └── YYYY-MM-DD.md         # 生成された投稿案
├── analytics/
│   └── YYYY-MM-DD.md         # 分析レポート
└── .github/workflows/
    ├── daily_generate.yml     # 毎日 5:00 JST に投稿生成
    └── weekly_analyze.yml     # 毎週月曜 6:00 JST に分析実行
```

---

## 手動実行

GitHub の **Actions** タブ → 対象ワークフロー → **Run workflow** で即時実行できます。

---

## 投稿の使い方

1. `posts/YYYY-MM-DD.md` を GitHub で開く
2. 内容を確認・修正する
3. 気に入った投稿を X にコピー＆ペーストして投稿

## 分析レポートの使い方

1. `analytics/YYYY-MM-DD.md` を GitHub で開く
2. 上位投稿のパターンと AI アドバイスを確認する
3. 次週の投稿案に反映する
