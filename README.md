# 🤖 BotCheck — AI/Bot Detection for Discord

Discordサーバーに導入できるBot/AI投稿検知ツール。  
ユーザーの投稿パターンを4軸で分析し、「Bot度スコア」(0-100)を算出します。

## 特徴

- **4軸分析**: タイミング・文体・行動・AI検知の独立スコアを重み付き統合
- **日本語対応**: です/ます調の一貫性、接続詞パターンなど日本語特有の分析
- **リアルタイム収集**: メッセージをSQLiteに自動保存
- **スラッシュコマンド**: `/botcheck` でサーバー内から即座に分析
- **REST API**: 外部サービスからの利用も可能
- **アラート機能**: 閾値超えユーザーを管理者にDM通知

## クイックスタート

```bash
# 1. クローン & 依存インストール
git clone https://github.com/tokagemushi999/botcheck.git
cd botcheck
pip install -r requirements.txt

# 2. 環境変数設定
cp .env.example .env
# .env に DISCORD_TOKEN を設定

# 3. Discord Bot 起動
python -m discord_bot.bot

# 4. API サーバー起動（別ターミナル）
uvicorn api.server:app --reload
```

## Discord コマンド

| コマンド | 説明 |
|---------|------|
| `/botcheck user @user` | 特定ユーザーのBot度分析 |
| `/botcheck server` | サーバー全体のサマリー |
| `/botcheck watch` | リアルタイム監視ON/OFF |
| `/botcheck report` | 週次レポート生成 |

## スコアの見方

| スコア | 判定 |
|--------|------|
| 0-39 | ✅ 人間らしい |
| 40-59 | 🤔 やや疑わしい |
| 60-79 | ⚠️ 要注意 |
| 80-100 | 🚨 高確率でBot/AI |

## 4軸分析の詳細

### ⏱ タイミング分析 (25%)
- **投稿間隔の規則性**: 等間隔投稿はBot傾向
- **返信速度**: 即座の返信はBot疑い
- **活動時間帯**: 24時間均等はBot、偏りは人間

### ✍️ 文体分析 (25%)
- **語彙多様性 (TTR)**: 語彙が単調ならBot
- **文長のばらつき**: 一定ならテンプレ的
- **定型フレーズ**: 「ご質問ありがとうございます」等の頻出
- **絵文字パターン**: 毎回同数ならBot

### 🔄 行動分析 (25%)
- **メンションパターン**: 特定ユーザーに集中は自動応答
- **チャンネル利用**: 少数固定はBot傾向
- **編集頻度**: 編集なしはBot寄り
- **リアクション**: 使わないのはBot寄り

### 🤖 AI文章検知 (25%)
- **語彙予測可能性**: 予測しやすい文章はAI生成
- **日本語パターン**: です/ます調の過度な一貫性、接続詞多用
- **繰り返し**: 同じフレーズの反復

## API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | ヘルスチェック |
| POST | `/analyze` | メッセージ配列を分析 |
| GET | `/user/{id}/score` | ユーザーの最新スコア |
| GET | `/user/{id}/history` | スコア履歴 |
| GET | `/stats` | 全体統計 |

## プロジェクト構成

```
botcheck/
├── analyzer/           # Python分析エンジン
│   ├── engine.py       # メインスコアリング（4軸統合）
│   ├── timing.py       # タイミング分析
│   ├── style.py        # 文体分析
│   ├── behavior.py     # 行動分析
│   └── ai_detect.py    # AI文章検知
├── api/
│   └── server.py       # FastAPI サーバー
├── discord_bot/
│   └── bot.py          # Discord Bot（メッセージ収集 + コマンド）
├── db/
│   └── schema.sql      # SQLite スキーマ
├── openclaw_skill/     # OpenClaw スキル
├── data/               # SQLite DBファイル（自動生成）
├── requirements.txt
├── .env.example
└── SPEC.md
```

## 技術スタック

- **Python 3.9+**
- **discord.py** — Discord Bot
- **FastAPI + uvicorn** — REST API
- **SQLite (aiosqlite)** — データストア
- **Pydantic** — バリデーション

## ライセンス

MIT
