# conftest.py - 共通フィクスチャとテスト設定
import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
import random
import string

# テスト用SQLiteファイル
@pytest.fixture
def test_db():
    """テスト用の一時的なSQLiteデータベース"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # テスト後にクリーンアップ
    yield db_path
    
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass

@pytest.fixture
def mock_message():
    """モックDiscordメッセージ"""
    msg = Mock()
    msg.id = 123456789
    msg.content = "これはテストメッセージです。"
    msg.created_at = datetime.now()
    msg.author = Mock()
    msg.author.id = 987654321
    msg.author.name = "test_user"
    msg.channel = Mock()
    msg.channel.id = 111222333
    msg.guild = Mock()
    msg.guild.id = 444555666
    return msg

@pytest.fixture
def sample_messages_regular():
    """規則的なタイミングのメッセージ群（Bot疑い）"""
    messages = []
    base_time = datetime.now()
    
    for i in range(10):
        msg = Mock()
        msg.id = 100 + i
        msg.content = f"メッセージ{i+1}です。"
        # 5分間隔で規則的
        msg.created_at = base_time + timedelta(minutes=i * 5)
        msg.author_id = 999
        messages.append(msg)
    
    return messages

@pytest.fixture
def sample_messages_random():
    """ランダムなタイミングのメッセージ群（人間らしい）"""
    messages = []
    base_time = datetime.now()
    
    for i in range(10):
        msg = Mock()
        msg.id = 200 + i
        msg.content = f"ランダム{i+1}だよ！"
        # 1-30分のランダム間隔
        random_minutes = random.randint(1, 30)
        msg.created_at = base_time + timedelta(minutes=sum(random.randint(1, 30) for _ in range(i)))
        msg.author_id = 888
        messages.append(msg)
    
    return messages

@pytest.fixture
def sample_messages_formal():
    """定型的な文体のメッセージ（Bot疑い）"""
    formal_texts = [
        "ご質問ありがとうございます。",
        "お忙しい中お疲れさまです。",
        "承知いたしました。",
        "ご確認のほどよろしくお願いいたします。",
        "失礼いたします。",
    ]
    
    messages = []
    for i, text in enumerate(formal_texts * 2):  # 10件
        msg = Mock()
        msg.id = 300 + i
        msg.content = text
        msg.created_at = datetime.now() + timedelta(minutes=i)
        msg.author_id = 777
        messages.append(msg)
    
    return messages

@pytest.fixture
def sample_messages_varied():
    """多様な文体のメッセージ（人間らしい）"""
    varied_texts = [
        "おはよう！",
        "今日は寒いね〜",
        "そういえばさ、昨日のあれどうなった？",
        "wwwwwww",
        "マジかよ！！！😱",
        "了解です👍",
        "ちょっと用事があるから離席します",
        "戻りました〜お疲れ様でした！",
        "これ面白そうだね https://example.com",
        "今度みんなでやろうよ",
    ]
    
    messages = []
    for i, text in enumerate(varied_texts):
        msg = Mock()
        msg.id = 400 + i
        msg.content = text
        msg.created_at = datetime.now() + timedelta(minutes=i * 3)
        msg.author_id = 666
        messages.append(msg)
    
    return messages

@pytest.fixture
def sample_ai_text():
    """AI生成っぽい文章"""
    return [
        "このような状況においては、まず最初に問題の本質を理解することが重要です。次に、適切な解決策を検討し、最終的に実行に移すことが求められます。",
        "ご質問いただいた件につきまして、詳細に検討させていただいた結果、以下のような回答をさせていただきます。",
        "このトピックについて考える際には、複数の観点から検討することが重要です。第一に、技術的な側面を考慮する必要があります。第二に、ビジネス上の影響を評価することが求められます。"
    ]

@pytest.fixture
def sample_human_text():
    """人間らしい文章"""
    return [
        "あー、それめっちゃわかる！私も同じこと思ってた",
        "うーん、どうだろうね...まあでも試してみる価値はありそう",
        "それな！😂 でもまあしょうがないよね〜",
        "マジで？！知らなかった...ありがとう！",
        "ちょっと待って、もう一回説明してもらえる？"
    ]

@pytest.fixture
def mock_discord_client():
    """モックDiscordクライアント"""
    client = AsyncMock()
    client.user = Mock()
    client.user.id = 123456789
    return client

# イベントループ設定（asyncio テスト用）
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()