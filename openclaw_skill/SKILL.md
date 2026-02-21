---
name: botcheck
description: Discord Bot/AI検知ツール。ユーザーの投稿パターンを分析してBot度スコア(0-100)を算出。
metadata:
  openclaw:
    emoji: "🤖"
---

# BotCheck Skill

Discordサーバーのメッセージを分析して、Bot/AIによる自動投稿を検知するツール。

## 使い方

### 分析エンジンを直接使う
```python
from analyzer.engine import analyze_messages

messages = [
    {"content": "こんにちは", "created_at": 1708000000, "channel_id": "123"},
    {"content": "ご質問ありがとうございます", "created_at": 1708000060, "channel_id": "123"},
]

result = analyze_messages(messages)
print(f"Bot度: {result.total_score}/100")
```

### API サーバー
```bash
cd ~/Projects/botcheck
uvicorn api.server:app --reload
# POST http://localhost:8000/analyze
```

### Discord Bot
```bash
cp .env.example .env
# .env に DISCORD_TOKEN を設定
python -m discord_bot.bot
```

## スコアの見方
- **0-39**: ✅ 人間らしい
- **40-59**: 🤔 やや疑わしい
- **60-79**: ⚠️ 要注意
- **80-100**: 🚨 高確率でBot/AI

## 4軸分析
1. **タイミング**: 投稿間隔の規則性、返信速度、活動時間帯
2. **文体**: 語彙多様性(TTR)、文長のばらつき、定型フレーズ
3. **行動**: メンションパターン、チャンネル利用、編集頻度
4. **AI検知**: 語彙予測可能性、日本語パターン（です/ます一貫性）、繰り返し
