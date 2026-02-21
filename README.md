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

| コマンド | 説明 | プラン |
|---------|------|--------|
| `/botcheck user @user` | 特定ユーザーのBot度分析 | Free / Pro |
| `/botcheck server` | サーバー全体のサマリー | Free / Pro |
| `/botcheck scan` | チャンネル過去メッセージ取込 | Free / Pro |
| `/botcheck watch` | リアルタイム監視ON/OFF | Free / Pro |
| `/botcheck report` | 週次レポート生成 | Pro のみ |

## 料金プラン

### 🆓 Free プラン
- 1サーバー/アカウント
- 基本分析（総合スコアのみ）
- 1日10回分析
- スキャン100件まで

### 💎 Pro プラン ($5/月)
- 無制限サーバー
- 詳細分析（4エンジン個別スコア）
- 無制限分析
- スキャン1000件
- API アクセス
- 週次レポート

### 🎁 投票ボーナス
[top.gg](https://top.gg/bot/1474728574320640011)で投票すると24時間Pro機能が無料で使えます！

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

| メソッド | パス | 説明 | プラン |
|----------|------|------|--------|
| GET | `/health` | ヘルスチェック | Public |
| GET | `/` | ランディングページ | Public |
| GET | `/dashboard` | Webダッシュボード | Public |
| POST | `/analyze` | メッセージ配列を分析 | Pro |
| GET | `/user/{id}/score` | ユーザーの最新スコア | Pro |
| GET | `/user/{id}/history` | スコア履歴 | Pro |
| GET | `/stats` | 全体統計 | Public |
| GET | `/plans` | プラン一覧 | Public |
| GET | `/subscription/{guild_id}` | サブスクリプション情報 | Pro |
| POST | `/subscription/{guild_id}/upgrade` | プランアップグレード（モック） | Pro |
| POST | `/webhook/topgg` | top.gg投票webhook | Internal |

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
│   └── schema.sql      # SQLite スキーマ（subscriptionsテーブル追加）
├── static/
│   └── lp/
│       └── index.html  # ランディングページ（料金表追加）
├── openclaw_skill/     # OpenClaw スキル
├── data/               # SQLite DBファイル（自動生成）
├── requirements.txt
├── .env.example
├── TOP_GG_REGISTRATION.md  # top.gg登録用情報
└── README.md
```

## 技術スタック

- **Python 3.9+**
- **discord.py** — Discord Bot
- **FastAPI + uvicorn** — REST API
- **SQLite (aiosqlite)** — データストア
- **Pydantic** — バリデーション

## ライセンス

MIT
