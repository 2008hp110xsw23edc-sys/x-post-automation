# X投稿 自動生成 & パフォーマンス分析システム

## 全体フロー

```
【毎日 5:00 JST】
① analyze_reference_accounts.py
   参考アカウント（@SureGoahead/@yama_hsshsp/@sho30_hsshsp）の
   高エンゲージメント投稿を分析 → 分析/reference-insights-latest.json に保存

② generate_posts.py
   ガイドライン + 参考アカウント分析インサイントを反映して
   6タイプ × 2投稿 = 計12投稿を生成 → posts/YYYY-MM-DD.md に保存

③ GitHub にコミット・プッシュ
   → 確認・修正 → X に投稿

【毎週土曜 5:00 JST】
analyze_posts.py
   自分のアカウントの直近7日間メトリクスを取得・分析
   → 分析/YYYY-MM-DD.md + posts/YYYY-MM-DD-analyzed.md に保存
```

---

## 機能一覧

### 1. 参考アカウント分析（`analyze_reference_accounts.py`）

`参考アカウント.txt` に記載された3アカウントの直近30日間の投稿を取得・分析します。

| 分析項目 | 内容 |
|---|---|
| 高エンゲージメント投稿 TOP3 | いいね・RT・返信・引用・ブックマーク合計が多い投稿 |
| バズる冒頭フックのパターン | 反応を集める冒頭の作り方 |
| 効果的なテーマ・切り口 | エンゲージメントが高いテーマ |
| 文体・スタイルのコツ | 絵文字・改行・文字数の使い方 |
| 即日反映すべき改善ポイント | 投稿生成に反映する最重要ポイント3点 |

出力: `分析/reference-accounts-YYYY-MM-DD.md`（詳細レポート）
      `分析/reference-insights-latest.json`（投稿生成に使うインサイント）

### 2. 投稿自動生成（`generate_posts.py`）

参考アカウント分析インサイントを反映し、**6タイプ × 2投稿 = 計12投稿**を生成します。

| タイプ | 内容 | 投稿数 |
|---|---|---|
| 問題提起型 | 職場HSPが詰む「構造的な理由」を本質からえぐる | 2 |
| あるある型 | 職場HSPが「これ私だ！」と感じる共感コンテンツ | 2 |
| 本音告白型 | 職場での実体験・理不尽を正直に語り共感と怒りを引き出す | 2 |
| マヒサイン型 | 職場で心が限界に近づいているサインを可視化する | 2 |
| 逆説気づき型 | 「停滞・消耗・失敗」を「糧・次への一歩」に変換する視点を届ける | 2 |
| 解決策型 | テーマ別の具体的解決策を「明日からできる」レベルで提示する | 2 |

### 3. 週次パフォーマンス分析（`analyze_posts.py`）

直近7日間の自分の投稿メトリクスを取得・分析し、改善提案を生成します。

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

```bash
gh secret set ANTHROPIC_API_KEY       --body "sk-ant-..."
gh secret set X_API_KEY               --body "..."
gh secret set X_API_SECRET            --body "..."
gh secret set X_ACCESS_TOKEN          --body "..."
gh secret set X_ACCESS_TOKEN_SECRET   --body "..."
```

### 参考アカウントの変更

`参考アカウント.txt` を編集してください（1行1アカウント、@付き可）。

```
@SureGoahead
@yama_hsshsp
@sho30_hsshsp
```

---

## ファイル構成

```
x-post-automation/
├── generate_posts.py                    # 投稿自動生成（6タイプ×2投稿）
├── analyze_reference_accounts.py        # 参考アカウント分析
├── analyze_posts.py                     # 自アカウント週次分析
├── analyze_account.py                   # 任意アカウント個別分析（手動）
├── analyze_following_top.py             # フォロー中上位分析（手動）
├── 参考アカウント.txt                   # 分析対象の参考アカウント一覧
├── CLAUDE（X）.md                       # 投稿生成ガイドライン
├── posts/
│   ├── YYYY-MM-DD.md                   # 毎日生成の投稿案（12投稿）
│   └── YYYY-MM-DD-analyzed.md          # 週次分析反映の投稿案
├── 分析/
│   ├── reference-accounts-YYYY-MM-DD.md # 参考アカウント詳細分析レポート
│   ├── reference-insights-latest.json   # 最新インサイントJSON（投稿生成に使用）
│   └── YYYY-MM-DD.md                   # 自アカウント週次分析レポート
└── .github/workflows/
    ├── daily_generate.yml               # 毎日 5:00 JST：参考分析→投稿生成
    └── weekly_analyze.yml               # 毎週土曜 5:00 JST：週次分析
```

---

## 手動実行

GitHub の **Actions** タブ → 対象ワークフロー → **Run workflow** で即時実行できます。

---

## 投稿の使い方

1. `posts/YYYY-MM-DD.md` を GitHub で開く
2. 12投稿の内容を確認・修正する
3. 気に入った投稿を X にコピー＆ペーストして投稿
