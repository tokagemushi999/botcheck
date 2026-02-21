# test_engine.py - 統合テスト（全軸組み合わせ）
import pytest
import random
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.engine import AnalysisEngine

class TestAnalysisEngine:
    
    def test_init(self):
        """AnalysisEngine初期化テスト"""
        engine = AnalysisEngine()
        assert engine is not None
    
    def test_empty_messages_neutral_score(self):
        """空のメッセージリストは中立スコア"""
        engine = AnalysisEngine()
        result = engine.analyze_user([])
        
        assert result['total_score'] == 50
        assert result['timing_score'] == 50
        assert result['style_score'] == 50
        assert result['behavior_score'] == 50
        assert result['ai_score'] == 50
    
    def test_obvious_bot_high_scores(self):
        """明らかなBot行動は全軸で高スコア"""
        engine = AnalysisEngine()
        
        # Bot的な特徴を全て含むメッセージセット
        bot_messages = []
        base_time = datetime.now()
        
        for i in range(20):
            msg = Mock()
            msg.id = 1000 + i
            msg.author_id = 999
            msg.content = "ご質問ありがとうございます。承知いたしました。"  # 定型文
            msg.created_at = base_time + timedelta(minutes=i * 5)  # 等間隔（5分）
            msg.edited_at = None  # 編集なし
            msg.mentions = [Mock(id=888)] if i % 2 == 0 else []  # 特定ユーザーにのみメンション
            msg.reactions = []  # リアクションなし
            msg.channel_id = 1001  # 単一チャンネル
            bot_messages.append(msg)
        
        result = engine.analyze_user(bot_messages)
        
        # 全軸で高スコア期待
        assert result['timing_score'] >= 70, f"Expected high timing score, got {result['timing_score']}"
        assert result['style_score'] >= 70, f"Expected high style score, got {result['style_score']}"
        assert result['behavior_score'] >= 70, f"Expected high behavior score, got {result['behavior_score']}"
        assert result['ai_score'] >= 70, f"Expected high AI score, got {result['ai_score']}"
        assert result['total_score'] >= 70, f"Expected high total score, got {result['total_score']}"
    
    def test_obvious_human_low_scores(self):
        """明らかな人間的行動は全軸で低スコア"""
        engine = AnalysisEngine()
        
        # 人間的な特徴を全て含むメッセージセット
        human_messages = []
        base_time = datetime.now()
        varied_channels = [2001, 2002, 2003, 2004]
        varied_texts = [
            "おはよう！😊",
            "今日めっちゃ寒くない？",
            "そうそう、昨日のあれどうだった？",
            "www面白い",
            "マジか！すげー",
            "了解〜ありがと",
            "ちょっと買い物行ってくる",
            "戻った！お疲れ様",
            "それな😂",
            "今度みんなでやろうよ",
        ]
        
        import random
        for i, text in enumerate(varied_texts):
            msg = Mock()
            msg.id = 2000 + i
            msg.author_id = 777
            msg.content = text
            # ランダムな間隔
            msg.created_at = base_time + timedelta(minutes=sum(random.randint(10, 180) for _ in range(i+1)))
            # 時々編集
            msg.edited_at = msg.created_at + timedelta(minutes=2) if i % 4 == 0 else None
            # 多様なメンション
            msg.mentions = [Mock(id=random.randint(100, 900))] if i % 3 == 0 else []
            # 時々リアクション
            if i % 3 == 1:
                reaction = Mock()
                reaction.emoji = random.choice(["👍", "😊", "😂"])
                reaction.me = True
                msg.reactions = [reaction]
            else:
                msg.reactions = []
            # 多様なチャンネル
            msg.channel_id = varied_channels[i % len(varied_channels)]
            human_messages.append(msg)
        
        result = engine.analyze_user(human_messages)
        
        # 全軸で低スコア期待
        assert result['timing_score'] <= 35, f"Expected low timing score, got {result['timing_score']}"
        assert result['style_score'] <= 35, f"Expected low style score, got {result['style_score']}"
        assert result['behavior_score'] <= 55, f"Expected low-moderate behavior score, got {result['behavior_score']}"
        assert result['ai_score'] <= 35, f"Expected low AI score, got {result['ai_score']}"
        assert result['total_score'] <= 40, f"Expected low total score, got {result['total_score']}"
    
    def test_mixed_characteristics_moderate_score(self):
        """Bot的・人間的特徴が混在する場合は中間スコア"""
        engine = AnalysisEngine()
        
        mixed_messages = []
        base_time = datetime.now()
        
        # 前半：Bot的（規則的、定型文）
        for i in range(10):
            msg = Mock()
            msg.id = 3000 + i
            msg.author_id = 555
            msg.content = "承知いたしました。"
            msg.created_at = base_time + timedelta(minutes=i * 5)
            msg.edited_at = None
            msg.mentions = []
            msg.reactions = []
            msg.channel_id = 3001
            mixed_messages.append(msg)
        
        # 後半：人間的（不規則、多様）
        human_texts = ["楽しかった！", "疲れた〜", "また今度", "ありがとう😊", "おつかれ"]
        for i, text in enumerate(human_texts):
            msg = Mock()
            msg.id = 3010 + i
            msg.author_id = 555
            msg.content = text
            msg.created_at = base_time + timedelta(minutes=50 + i * 37)  # 不規則
            msg.edited_at = msg.created_at + timedelta(minutes=1) if i % 2 == 0 else None
            msg.mentions = [Mock(id=random.randint(100, 200))] if i % 2 == 1 else []
            if i % 2 == 0:
                reaction = Mock()
                reaction.emoji = "👍"
                reaction.me = True
                msg.reactions = [reaction]
            else:
                msg.reactions = []
            msg.channel_id = 3002 if i % 2 else 3001
            mixed_messages.append(msg)
        
        result = engine.analyze_user(mixed_messages)
        
        # 中間的なスコア期待（40-60）
        assert 40 <= result['total_score'] <= 60, f"Expected moderate total score, got {result['total_score']}"
    
    def test_score_weighting_system(self):
        """スコア重み付けシステムのテスト"""
        engine = AnalysisEngine()
        
        # 重みをテスト用に設定（通常は均等）
        with patch.object(engine, 'weights', {'timing': 0.4, 'style': 0.3, 'behavior': 0.2, 'ai': 0.1}):
            # タイミングだけ異常に高い状況を作成
            messages = []
            base_time = datetime.now()
            
            for i in range(10):
                msg = Mock()
                msg.id = 4000 + i
                msg.author_id = 444
                # 極端に規則的なタイミング（1分間隔）
                msg.created_at = base_time + timedelta(minutes=i)
                # その他は人間的
                msg.content = f"普通のメッセージ{i}だよ〜"
                msg.edited_at = None if i % 3 else msg.created_at + timedelta(seconds=30)
                msg.mentions = []
                msg.reactions = []
                msg.channel_id = 4001 + (i % 3)
                messages.append(msg)
            
            result = engine.analyze_user(messages)
            
            # タイミングの重みが高いので、総合スコアもある程度高くなる
            timing_contribution = result['timing_score'] * 0.4
            assert timing_contribution > 20  # タイミングスコアが高いなら寄与も大きい
    
    def test_confidence_calculation(self):
        """信頼度計算のテスト"""
        engine = AnalysisEngine()
        
        # 十分なデータ（20件）
        sufficient_messages = []
        for i in range(20):
            msg = Mock()
            msg.id = 5000 + i
            msg.author_id = 333
            msg.content = f"メッセージ{i}"
            msg.created_at = datetime.now() + timedelta(minutes=i)
            msg.edited_at = None
            msg.mentions = []
            msg.reactions = []
            msg.channel_id = 5001
            sufficient_messages.append(msg)
        
        # 不十分なデータ（3件）
        insufficient_messages = sufficient_messages[:3]
        
        sufficient_result = engine.analyze_user(sufficient_messages)
        insufficient_result = engine.analyze_user(insufficient_messages)
        
        # 十分なデータの方が高い信頼度
        assert sufficient_result['confidence'] > insufficient_result['confidence']
        assert sufficient_result['confidence'] >= 80  # 20件あれば高信頼度
        assert insufficient_result['confidence'] <= 60  # 3件では低信頼度
    
    def test_analysis_metadata(self):
        """分析メタデータの正確性テスト"""
        engine = AnalysisEngine()
        
        messages = []
        base_time = datetime.now()
        
        for i in range(15):
            msg = Mock()
            msg.id = 6000 + i
            msg.author_id = 222
            msg.content = f"テストメッセージ{i}"
            msg.created_at = base_time + timedelta(hours=i)
            msg.edited_at = None
            msg.mentions = []
            msg.reactions = []
            msg.channel_id = 6001
            messages.append(msg)
        
        result = engine.analyze_user(messages)
        
        # メタデータの検証
        assert result['message_count'] == 15
        assert result['analysis_date'] is not None
        assert result['user_id'] == 222
        assert isinstance(result['analysis_date'], datetime)
        
        # 期間の検証
        expected_period_hours = 14  # 15件のメッセージで14時間の期間
        actual_period = result.get('analysis_period_hours', 0)
        assert abs(actual_period - expected_period_hours) < 1  # 1時間以内の誤差
    
    def test_edge_case_single_message(self):
        """単一メッセージのエッジケーステスト"""
        engine = AnalysisEngine()
        
        single_message = [Mock()]
        single_message[0].id = 7000
        single_message[0].author_id = 111
        single_message[0].content = "単一メッセージです"
        single_message[0].created_at = datetime.now()
        single_message[0].edited_at = None
        single_message[0].mentions = []
        single_message[0].reactions = []
        single_message[0].channel_id = 7001
        
        result = engine.analyze_user(single_message)
        
        # 単一メッセージでも分析は動作する
        assert result['message_count'] == 1
        assert result['confidence'] < 50  # 信頼度は低い
        assert 0 <= result['total_score'] <= 100
    
    def test_score_boundaries(self):
        """スコア境界値のテスト"""
        engine = AnalysisEngine()
        
        # 極端なBot特徴
        extreme_bot_messages = []
        base_time = datetime.now()
        
        for i in range(50):  # 大量のメッセージ
            msg = Mock()
            msg.id = 8000 + i
            msg.author_id = 999
            msg.content = "完全に同一のメッセージです。"  # 完全一致
            msg.created_at = base_time + timedelta(seconds=i * 60)  # 1分間隔で完璧
            msg.edited_at = None
            msg.mentions = [Mock(id=888)]  # 常に同じユーザーメンション
            msg.reactions = []
            msg.channel_id = 8001  # 同一チャンネル
            extreme_bot_messages.append(msg)
        
        result = engine.analyze_user(extreme_bot_messages)
        
        # 各スコアは0-100の範囲内
        assert 0 <= result['timing_score'] <= 100
        assert 0 <= result['style_score'] <= 100
        assert 0 <= result['behavior_score'] <= 100
        assert 0 <= result['ai_score'] <= 100
        assert 0 <= result['total_score'] <= 100
        
        # 極端なケースでは高スコア期待
        assert result['total_score'] >= 60, f"Expected high total score for extreme bot, got {result['total_score']}"
    
    def test_analyzer_integration(self):
        """各分析器の統合テスト"""
        engine = AnalysisEngine()
        
        # エンジンインスタンスの各分析器を直接モック
        with patch.object(engine, 'timing_analyzer') as mock_timing, \
             patch.object(engine, 'style_analyzer') as mock_style, \
             patch.object(engine, 'behavior_analyzer') as mock_behavior, \
             patch.object(engine, 'ai_detector') as mock_ai:
            
            # モックの戻り値設定
            mock_timing.analyze_timing.return_value = 75
            mock_style.analyze_style.return_value = 60
            mock_behavior.analyze_behavior.return_value = 85
            mock_ai.detect_ai_text.return_value = 70
            
            messages = [Mock()]
            messages[0].id = 9000
            messages[0].author_id = 666
            messages[0].content = "統合テスト"
            messages[0].created_at = datetime.now()
            
            result = engine.analyze_user(messages)
            
            # 各分析器が呼び出されたことを確認
            mock_timing.analyze_timing.assert_called_once()
            mock_style.analyze_style.assert_called_once()
            mock_behavior.analyze_behavior.assert_called_once()
            mock_ai.detect_ai_text.assert_called_once()
            
            # スコアが正しく統合されているか（均等重み付けの場合）
            expected_total = (75 + 60 + 85 + 70) / 4
            assert abs(result['total_score'] - expected_total) < 1