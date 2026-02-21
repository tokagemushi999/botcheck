# test_behavior.py - 行動分析のユニットテスト
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.behavior import BehaviorAnalyzer

class TestBehaviorAnalyzer:
    
    def test_init(self):
        """BehaviorAnalyzer初期化テスト"""
        analyzer = BehaviorAnalyzer()
        assert analyzer is not None
    
    def test_analyze_mention_patterns_bot_like(self):
        """メンションパターン分析 - Bot的パターン"""
        analyzer = BehaviorAnalyzer()
        messages = []
        
        # 特定のユーザーにばかりメンション（Bot的）
        for i in range(10):
            msg = Mock()
            msg.author_id = 100
            msg.mentions = [Mock(id=999)]  # 同じユーザーにばかり
            msg.content = f"@user999 質問{i+1}です"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            messages.append(msg)
        
        score = analyzer.analyze_behavior(messages)
        
        # 特定ユーザーへの集中はBot疑い
        assert score >= 60, f"Expected high score for concentrated mentions, got {score}"
    
    def test_analyze_mention_patterns_human_like(self):
        """メンションパターン分析 - 人間的パターン"""
        analyzer = BehaviorAnalyzer()
        messages = []
        
        # 多様なユーザーにメンション（人間的）
        target_users = [111, 222, 333, 444, 555]
        for i in range(10):
            msg = Mock()
            msg.author_id = 100
            # ランダムにユーザーを選択
            target = target_users[i % len(target_users)]
            msg.mentions = [Mock(id=target)]
            msg.content = f"@user{target} こんにちは"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            messages.append(msg)
        
        score = analyzer.analyze_behavior(messages)
        
        # 多様なメンションは人間的
        assert score <= 45, f"Expected low score for diverse mentions, got {score}"
    
    def test_channel_usage_patterns(self):
        """チャンネル利用パターンの分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：少数のチャンネルのみ使用
        bot_messages = []
        for i in range(20):
            msg = Mock()
            msg.author_id = 200
            msg.channel_id = 1001 if i < 15 else 1002  # ほぼ1つのチャンネル
            msg.content = f"メッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            bot_messages.append(msg)
        
        # 人間的：多様なチャンネル使用
        human_messages = []
        channels = [2001, 2002, 2003, 2004, 2005, 2006]
        for i in range(20):
            msg = Mock()
            msg.author_id = 300
            msg.channel_id = channels[i % len(channels)]
            msg.content = f"メッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            human_messages.append(msg)
        
        bot_score = analyzer.analyze_behavior(bot_messages)
        human_score = analyzer.analyze_behavior(human_messages)
        
        # Botは少数チャンネルに集中するため高スコア
        assert bot_score > human_score, "Bot should have higher score for limited channel usage"
    
    def test_message_editing_patterns(self):
        """メッセージ編集パターンの分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：編集なし
        bot_messages = []
        for i in range(10):
            msg = Mock()
            msg.author_id = 400
            msg.edited_at = None  # 編集なし
            msg.content = f"完璧なメッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            bot_messages.append(msg)
        
        # 人間的：編集あり
        human_messages = []
        for i in range(10):
            msg = Mock()
            msg.author_id = 500
            # 半分のメッセージを編集
            msg.edited_at = datetime.now() + timedelta(minutes=i+1) if i % 2 == 0 else None
            msg.content = f"訂正したメッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            human_messages.append(msg)
        
        bot_score = analyzer._calculate_editing_score(bot_messages)
        human_score = analyzer._calculate_editing_score(human_messages)
        
        # 編集しないのはBot的
        assert bot_score > human_score, "Never editing messages is bot-like behavior"
    
    def test_reaction_usage_patterns(self):
        """リアクション使用パターンの分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：リアクション使わない
        bot_messages = []
        for i in range(10):
            msg = Mock()
            msg.author_id = 600
            msg.reactions = []  # リアクションなし
            msg.content = f"リアクションしないメッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            bot_messages.append(msg)
        
        # 人間的：リアクション使用
        human_messages = []
        for i in range(10):
            msg = Mock()
            msg.author_id = 700
            # 時々リアクション
            if i % 3 == 0:
                reaction = Mock()
                reaction.emoji = "👍"
                reaction.me = True
                msg.reactions = [reaction]
            else:
                msg.reactions = []
            msg.content = f"リアクションするメッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            human_messages.append(msg)
        
        bot_score = analyzer._calculate_reaction_score(bot_messages)
        human_score = analyzer._calculate_reaction_score(human_messages)
        
        # リアクションを使わないのはBot的
        assert bot_score > human_score, "Never using reactions is bot-like behavior"
    
    def test_reply_patterns(self):
        """返信パターンの分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：メンションされた時だけ即座に返信
        bot_messages = []
        base_time = datetime.now()
        
        for i in range(5):
            # 他人からのメンション
            mention_msg = Mock()
            mention_msg.author_id = 999
            mention_msg.mentions = [Mock(id=800)]
            mention_msg.content = f"@bot 質問{i}"
            mention_msg.created_at = base_time + timedelta(minutes=i*10)
            
            # Botの即座の返信
            reply_msg = Mock()
            reply_msg.author_id = 800
            reply_msg.mentions = []
            reply_msg.content = f"お答えします{i}"
            reply_msg.created_at = base_time + timedelta(minutes=i*10, seconds=5)  # 5秒後
            
            bot_messages.extend([mention_msg, reply_msg])
        
        # 人間的：自然な会話の流れ
        human_messages = []
        
        for i in range(10):
            msg = Mock()
            msg.author_id = 900
            msg.mentions = []
            msg.content = f"自然な会話{i}"
            # 不規則な間隔
            msg.created_at = base_time + timedelta(minutes=i*7, seconds=i*23)
            human_messages.append(msg)
        
        bot_score = analyzer.analyze_behavior(bot_messages)
        human_score = analyzer.analyze_behavior(human_messages)
        
        # 即座の返信パターンはBot疑い
        assert bot_score > human_score, "Instant reply patterns should raise bot suspicion"
    
    def test_activity_consistency(self):
        """活動の一貫性分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：非常に一貫した活動
        bot_messages = []
        base_time = datetime.now().replace(hour=9, minute=0)  # 毎日9時から
        
        for day in range(7):  # 1週間
            for hour in range(8):  # 8時間活動
                msg = Mock()
                msg.author_id = 1000
                msg.content = f"定期投稿 day{day} hour{hour}"
                msg.created_at = base_time + timedelta(days=day, hours=hour)
                bot_messages.append(msg)
        
        # 人間的：不規則な活動
        human_messages = []
        import random
        
        for day in range(7):
            # 日によって活動時間が異なる
            activity_hours = random.randint(2, 12)
            start_hour = random.randint(6, 18)
            
            for _ in range(activity_hours):
                msg = Mock()
                msg.author_id = 1100
                msg.content = f"不規則な投稿 day{day}"
                hour_offset = random.randint(0, 16)
                msg.created_at = base_time + timedelta(days=day, hours=start_hour + hour_offset)
                human_messages.append(msg)
        
        bot_score = analyzer.analyze_behavior(bot_messages)
        human_score = analyzer.analyze_behavior(human_messages)
        
        # 一貫しすぎた活動はBot疑い
        assert bot_score >= human_score, "Too consistent activity should raise bot suspicion"
    
    def test_empty_messages(self):
        """空のメッセージリスト処理"""
        analyzer = BehaviorAnalyzer()
        score = analyzer.analyze_behavior([])
        
        # データ不足の場合は中立
        assert score == 50
    
    def test_conversation_threading(self):
        """会話のスレッド化・文脈理解の分析"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：文脈を無視した返信
        bot_conversation = []
        topics = ["天気", "料理", "スポーツ", "映画", "音楽"]
        
        for i, topic in enumerate(topics * 2):
            # 他人のトピック
            other_msg = Mock()
            other_msg.author_id = 1001
            other_msg.content = f"{topic}について話しましょう"
            other_msg.created_at = datetime.now() + timedelta(minutes=i*2)
            
            # Botの関係ない返信
            bot_msg = Mock()
            bot_msg.author_id = 1200
            bot_msg.content = "ご質問ありがとうございます。承知いたしました。"  # 毎回同じ
            bot_msg.created_at = datetime.now() + timedelta(minutes=i*2 + 1)
            
            bot_conversation.extend([other_msg, bot_msg])
        
        bot_score = analyzer.analyze_behavior(bot_conversation)
        
        # 文脈無視はBot疑い
        assert bot_score >= 48, f"Expected elevated score for ignoring context, got {bot_score}"
    
    def test_cross_channel_consistency(self):
        """チャンネル横断での行動一貫性"""
        analyzer = BehaviorAnalyzer()
        
        # Bot的：どのチャンネルでも同じ行動
        bot_messages = []
        channels = [3001, 3002, 3003]
        
        for channel in channels:
            for i in range(5):
                msg = Mock()
                msg.author_id = 1300
                msg.channel_id = channel
                msg.content = "いつも同じメッセージです。"  # どこでも同じ
                msg.created_at = datetime.now() + timedelta(minutes=len(bot_messages))
                bot_messages.append(msg)
        
        bot_score = analyzer.analyze_behavior(bot_messages)
        
        # チャンネル間で行動が同じなのはBot疑い
        assert bot_score >= 55, f"Expected elevated score for cross-channel consistency, got {bot_score}"