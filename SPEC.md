# BotCheck - AI/Bot Detection for Discord

## 概要
Discordサーバーに導入できるBot/AI投稿検知ツール。
ユーザーの投稿パターンを分析して「Bot度スコア」を算出する。

## ターゲット
- Discordサーバー管理者
- コミュニティモデレーター

## 技術スタック
- Discord Bot: discord.js v14 (Node.js)
- 分析エンジン: Python (FastAPI)
- DB: SQLite
- フロント: なし（MVP）

## コア機能（MVP）

### 1. メッセージ収集
- Botがサーバーのメッセージをリアルタイム監視
- ユーザーごとにメッセージ履歴をDBに保存

### 2. 分析エンジン (analyzer/engine.py)
以下の特徴量からBot度スコア(0-100)を算出:

**タイミング分析:**
- 投稿間隔の規則性（等間隔=Bot臭い、ばらつき=人間らしい）
- 返信速度（即座に返信=Bot疑い）
- 活動時間帯（24時間均等=Bot、偏り=人間）

**文体分析:**
- 語彙の多様性（TTR: Type-Token Ratio）
- 文長のばらつき（標準偏差が小さい=Bot）
- 定型フレーズの頻度（「ご質問ありがとうございます」等）
- 絵文字使用パターン

**行動分析:**
- メンション/返信の偏り
- チャンネル利用パターン
- メッセージ編集頻度（Botは編集しない）
- リアクション使用

**AI文章検知:**
- perplexity（困惑度）ベースの判定
- 日本語特有のパターン（です/ます調の一貫性、接続詞の多用）
- 繰り返しフレーズ検知

### 3. Discordコマンド
- `/botcheck @user` — 特定ユーザーのBot度スコア表示
- `/botcheck server` — サーバー全体のサマリー
- `/botcheck watch` — リアルタイム監視ON/OFF
- `/botcheck report` — 週次レポート生成

### 4. API (api/server.py)
- POST /analyze — テキスト配列を受け取りスコア返却
- GET /user/{id}/score — ユーザースコア取得
- GET /stats — 全体統計

### 5. アラート
- スコア80以上のユーザーを管理者にDM通知
- 設定可能な閾値

## ファイル構成
```
botcheck/
├── discord_bot/
│   ├── bot.js          — メインBot
│   ├── commands/       — スラッシュコマンド
│   └── collectors/     — メッセージ収集
├── analyzer/
│   ├── engine.py       — スコア算出メイン
│   ├── timing.py       — タイミング分析
│   ├── style.py        — 文体分析
│   ├── behavior.py     — 行動分析
│   └── ai_detect.py    — AI文章検知
├── api/
│   └── server.py       — FastAPI
├── db/
│   └── schema.sql      — SQLite
├── openclaw_skill/     — OpenClawスキル
├── tests/
└── package.json
```

## 将来的な収益化
- Freemium: 100メッセージ/日無料、Pro $5/月
- API販売
- 日本語特化を強みに
