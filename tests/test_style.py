# test_style.py - 文体分析のユニットテスト
import pytest
from unittest.mock import Mock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.style import StyleAnalyzer

class TestStyleAnalyzer:
    
    def test_init(self):
        """StyleAnalyzer初期化テスト"""
        analyzer = StyleAnalyzer()
        assert analyzer is not None
    
    def test_formal_style_high_score(self, sample_messages_formal):
        """定型文体は高スコア（Bot疑い）"""
        analyzer = StyleAnalyzer()
        score = analyzer.analyze_style(sample_messages_formal)
        
        # 定型的な文体は高スコア（60以上）
        assert score >= 60, f"Expected high score for formal style, got {score}"
    
    def test_varied_style_low_score(self, sample_messages_varied):
        """多様な文体は低スコア（人間らしい）"""
        analyzer = StyleAnalyzer()
        score = analyzer.analyze_style(sample_messages_varied)
        
        # 多様な文体は低スコア（40以下）
        assert score <= 40, f"Expected low score for varied style, got {score}"
    
    def test_empty_messages(self):
        """空のメッセージリストは中立スコア"""
        analyzer = StyleAnalyzer()
        score = analyzer.analyze_style([])
        
        assert score == 50
    
    def test_calculate_ttr_diversity(self):
        """TTR（語彙の多様性）計算テスト"""
        analyzer = StyleAnalyzer()
        
        # 低多様性（同じ単語の繰り返し）
        repetitive_messages = []
        for i in range(5):
            msg = Mock()
            msg.content = "ありがとうございます。ありがとうございます。"
            repetitive_messages.append(msg)
        
        low_ttr = analyzer._calculate_ttr(repetitive_messages)
        
        # 高多様性（多様な語彙）
        diverse_messages = []
        diverse_texts = [
            "今日は良い天気ですね。",
            "昨日映画を見ました。",
            "新しいレストランを発見した。",
            "プログラミングは楽しい。",
            "音楽を聴いています。"
        ]
        for text in diverse_texts:
            msg = Mock()
            msg.content = text
            diverse_messages.append(msg)
        
        high_ttr = analyzer._calculate_ttr(diverse_messages)
        
        assert high_ttr > low_ttr, "Diverse vocabulary should have higher TTR"
    
    def test_sentence_length_variance(self):
        """文長のばらつき分析"""
        analyzer = StyleAnalyzer()
        
        # 一定の文長（Bot的）
        uniform_messages = []
        for i in range(5):
            msg = Mock()
            msg.content = "これは一定の長さの文章です。"  # 15文字
            uniform_messages.append(msg)
        
        uniform_variance = analyzer._calculate_sentence_length_variance(uniform_messages)
        
        # ばらつきのある文長（人間的）
        varied_messages = []
        varied_texts = [
            "短い。",  # 3文字
            "これは中程度の長さの文章です。",  # 16文字
            "この文章はかなり長くて、詳細な情報を含んでいます。とても具体的で説明的です。",  # 37文字
            "普通。",  # 3文字
            "ちょうどいい長さかもしれませんね。"  # 18文字
        ]
        
        for text in varied_texts:
            msg = Mock()
            msg.content = text
            varied_messages.append(msg)
        
        varied_variance = analyzer._calculate_sentence_length_variance(varied_messages)
        
        assert varied_variance > uniform_variance, "Varied sentence lengths should have higher variance"
    
    def test_detect_template_phrases(self):
        """定型フレーズの検知"""
        analyzer = StyleAnalyzer()
        
        template_messages = []
        template_phrases = [
            "ご質問ありがとうございます。",
            "お忙しい中ありがとうございます。",
            "ご質問ありがとうございます。",  # 重複
            "承知いたしました。",
            "お忙しい中ありがとうございます。",  # 重複
            "失礼いたします。"
        ]
        
        for phrase in template_phrases:
            msg = Mock()
            msg.content = phrase
            template_messages.append(msg)
        
        template_ratio = analyzer._calculate_template_phrase_ratio(template_messages)
        
        # 定型フレーズが多い場合は比率が高い
        assert template_ratio > 0.5, f"Expected high template ratio, got {template_ratio}"
    
    def test_emoji_usage_patterns(self):
        """絵文字使用パターンの分析"""
        analyzer = StyleAnalyzer()
        
        # Bot的（絵文字なし、または一定パターン）
        bot_messages = []
        for i in range(5):
            msg = Mock()
            msg.content = f"メッセージ{i+1}です。"  # 絵文字なし
            bot_messages.append(msg)
        
        bot_emoji_score = analyzer._analyze_emoji_patterns(bot_messages)
        
        # 人間的（絵文字をバラエティ豊かに使用）
        human_messages = []
        human_texts = [
            "おはよう😊",
            "楽しかった！😄🎉",
            "疲れた...😴",
            "それな💯",
            "ありがとう🙏✨"
        ]
        
        for text in human_texts:
            msg = Mock()
            msg.content = text
            human_messages.append(msg)
        
        human_emoji_score = analyzer._analyze_emoji_patterns(human_messages)
        
        # 人間の方が絵文字使用でより低スコア（自然）
        assert human_emoji_score < bot_emoji_score, "Humans should have more natural emoji patterns"
    
    def test_punctuation_patterns(self):
        """句読点パターンの分析"""
        analyzer = StyleAnalyzer()
        
        # Bot的（完璧な句読点）
        bot_messages = []
        bot_texts = [
            "こんにちは。今日は良い天気ですね。",
            "ありがとうございます。承知いたしました。",
            "失礼いたします。また後ほど。"
        ]
        
        for text in bot_texts:
            msg = Mock()
            msg.content = text
            bot_messages.append(msg)
        
        # 人間的（句読点が不規則）
        human_messages = []
        human_texts = [
            "こんにちは！今日めっちゃ暑いね〜",
            "そうそう、それで結局どうなったの？？",
            "了解です！！！ありがとう♪"
        ]
        
        for text in human_texts:
            msg = Mock()
            msg.content = text
            human_messages.append(msg)
        
        bot_score = analyzer.analyze_style(bot_messages)
        human_score = analyzer.analyze_style(human_messages)
        
        # 完璧すぎる句読点はBot疑い
        assert bot_score > human_score, "Perfect punctuation should raise bot suspicion"
    
    def test_polite_language_detection(self):
        """丁寧語・敬語の一貫性検知"""
        analyzer = StyleAnalyzer()
        
        # 一貫して敬語（Bot疑い）
        polite_messages = []
        polite_texts = [
            "いつもお世話になっております。",
            "ご質問いただきありがとうございます。",
            "承知いたしました。確認いたします。",
            "失礼いたします。"
        ]
        
        for text in polite_texts:
            msg = Mock()
            msg.content = text
            polite_messages.append(msg)
        
        # カジュアルと敬語が混在（人間的）
        mixed_messages = []
        mixed_texts = [
            "ありがとうございます！",
            "了解〜",
            "そうですね、確認しますね",
            "おつかれ！"
        ]
        
        for text in mixed_texts:
            msg = Mock()
            msg.content = text
            mixed_messages.append(msg)
        
        polite_score = analyzer.analyze_style(polite_messages)
        mixed_score = analyzer.analyze_style(mixed_messages)
        
        # 一貫した敬語はBot疑い
        assert polite_score > mixed_score, "Consistent polite language should raise bot suspicion"
    
    def test_japanese_specific_patterns(self):
        """日本語特有のパターン分析"""
        analyzer = StyleAnalyzer()
        
        # です/ます調が完璧すぎる（Bot疑い）
        formal_jp_messages = []
        formal_texts = [
            "これはテストです。",
            "確認いたします。",
            "承知いたしました。",
            "ありがとうございます。"
        ]
        
        for text in formal_texts:
            msg = Mock()
            msg.content = text
            formal_jp_messages.append(msg)
        
        # 自然な日本語（だ/である調も混在）
        natural_jp_messages = []
        natural_texts = [
            "これはテスト。",
            "確認するね！",
            "了解した",
            "ありがとう〜"
        ]
        
        for text in natural_texts:
            msg = Mock()
            msg.content = text
            natural_jp_messages.append(msg)
        
        formal_score = analyzer.analyze_style(formal_jp_messages)
        natural_score = analyzer.analyze_style(natural_jp_messages)
        
        # 完璧な敬語はBot疑い
        assert formal_score > natural_score, "Perfect formal Japanese should raise bot suspicion"