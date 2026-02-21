# test_timing.py - タイミング分析のユニットテスト
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.timing import TimingAnalyzer

class TestTimingAnalyzer:
    
    def test_init(self):
        """TimingAnalyzer初期化テスト"""
        analyzer = TimingAnalyzer()
        assert analyzer is not None
    
    def test_regular_intervals_high_score(self, sample_messages_regular):
        """規則的な投稿間隔は高スコア（Bot疑い）"""
        analyzer = TimingAnalyzer()
        score = analyzer.analyze_timing(sample_messages_regular)
        
        # 規則的な投稿は高スコア（60以上）
        assert score >= 60, f"Expected high score for regular intervals, got {score}"
    
    def test_random_intervals_low_score(self, sample_messages_random):
        """ランダムな投稿間隔は低スコア（人間らしい）"""
        analyzer = TimingAnalyzer()
        score = analyzer.analyze_timing(sample_messages_random)
        
        # ランダムな投稿は低スコア（40以下）
        assert score <= 40, f"Expected low score for random intervals, got {score}"
    
    def test_empty_messages(self):
        """空のメッセージリストは中立スコア"""
        analyzer = TimingAnalyzer()
        score = analyzer.analyze_timing([])
        
        # データが少ない場合は中立スコア（50）
        assert score == 50
    
    def test_single_message(self):
        """単一メッセージは中立スコア"""
        analyzer = TimingAnalyzer()
        
        msg = Mock()
        msg.created_at = datetime.now()
        msg.author_id = 123
        
        score = analyzer.analyze_timing([msg])
        assert score == 50
    
    def test_rapid_fire_messages_high_score(self):
        """短時間大量投稿は高スコア（Bot疑い）"""
        analyzer = TimingAnalyzer()
        messages = []
        base_time = datetime.now()
        
        # 10秒間隔で10件投稿（明らかにBot的）
        for i in range(10):
            msg = Mock()
            msg.created_at = base_time + timedelta(seconds=i * 10)
            msg.author_id = 456
            messages.append(msg)
        
        score = analyzer.analyze_timing(messages)
        assert score >= 70, f"Expected very high score for rapid-fire messages, got {score}"
    
    def test_night_time_activity_scoring(self):
        """深夜活動パターンの分析"""
        analyzer = TimingAnalyzer()
        messages = []
        
        # 深夜2-5時に大量投稿（Bot疑い）
        base_date = datetime.now().replace(hour=2, minute=0, second=0, microsecond=0)
        
        for i in range(8):
            msg = Mock()
            msg.created_at = base_date + timedelta(minutes=i * 15)
            msg.author_id = 789
            messages.append(msg)
        
        score = analyzer.analyze_timing(messages)
        # 深夜の規則的活動はBot疑い要素の一つ
        assert score >= 55, f"Expected elevated score for night activity, got {score}"
    
    def test_weekday_vs_weekend_patterns(self):
        """平日・週末活動パターンの差異を検証"""
        analyzer = TimingAnalyzer()
        
        # 平日のみ活動（Bot疑い）
        weekday_messages = []
        # 月曜日（weekday=0）から開始
        monday = datetime(2024, 1, 1)  # 2024年1月1日は月曜日
        
        for day in range(5):  # 月-金
            for hour in range(9, 18):  # 9-17時（勤務時間）
                msg = Mock()
                msg.created_at = monday + timedelta(days=day, hours=hour)
                msg.author_id = 100
                weekday_messages.append(msg)
        
        score = analyzer.analyze_timing(weekday_messages)
        # あまりに規則的すぎる平日パターンはBot疑い
        assert score >= 40, f"Expected elevated score for too-regular weekday pattern, got {score}"
    
    def test_calculate_intervals_variance(self):
        """投稿間隔のばらつき計算テスト"""
        analyzer = TimingAnalyzer()
        
        # 完全に等間隔なメッセージ（60分間隔）
        equal_messages = []
        base_time = datetime.now()
        
        for i in range(5):
            msg = Mock()
            msg.created_at = base_time + timedelta(hours=i)
            msg.author_id = 200
            equal_messages.append(msg)
        
        # プライベートメソッドを直接テスト
        intervals = analyzer._calculate_intervals(equal_messages)
        variance = analyzer._calculate_variance(intervals)
        
        # 等間隔なら分散は0に近い
        assert variance < 100, f"Expected low variance for equal intervals, got {variance}"
        
        # ランダム間隔なメッセージ
        random_messages = []
        random_intervals = [30, 120, 15, 240, 45]  # 分
        
        for i, interval in enumerate(random_intervals):
            msg = Mock()
            msg.created_at = base_time + timedelta(minutes=sum(random_intervals[:i+1]))
            msg.author_id = 300
            random_messages.append(msg)
        
        random_variance = analyzer._calculate_variance(analyzer._calculate_intervals(random_messages))
        
        # ランダム間隔なら分散は大きい
        assert random_variance > variance, "Random intervals should have higher variance"
    
    def test_reply_speed_analysis(self):
        """返信速度分析のテスト"""
        analyzer = TimingAnalyzer()
        messages = []
        base_time = datetime.now()
        
        # ユーザーAの質問
        msg_a = Mock()
        msg_a.created_at = base_time
        msg_a.author_id = 1
        msg_a.content = "@user_b 質問があります"
        msg_a.mentions = [Mock(id=2)]
        messages.append(msg_a)
        
        # ユーザーBの即座の返信（5秒後）
        msg_b = Mock()
        msg_b.created_at = base_time + timedelta(seconds=5)
        msg_b.author_id = 2
        msg_b.content = "はい、お答えします"
        msg_b.mentions = []
        messages.append(msg_b)
        
        # もう一度同じパターン
        msg_a2 = Mock()
        msg_a2.created_at = base_time + timedelta(minutes=10)
        msg_a2.author_id = 1
        msg_a2.content = "@user_b 別の質問です"
        msg_a2.mentions = [Mock(id=2)]
        messages.append(msg_a2)
        
        msg_b2 = Mock()
        msg_b2.created_at = base_time + timedelta(minutes=10, seconds=3)
        msg_b2.author_id = 2
        msg_b2.content = "承知いたしました"
        msg_b2.mentions = []
        messages.append(msg_b2)
        
        # ユーザーB（即座に返信するユーザー）のスコアをチェック
        user_b_messages = [msg for msg in messages if msg.author_id == 2]
        score = analyzer.analyze_timing(user_b_messages)
        
        # 即座の返信は自動Bot疑い
        assert score >= 45, f"Expected elevated score for instant replies, got {score}"