# test_ai_detect.py - AI検知のユニットテスト
import pytest
from unittest.mock import Mock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.ai_detect import AIDetector

class TestAIDetector:
    
    def test_init(self):
        """AIDetector初期化テスト"""
        detector = AIDetector()
        assert detector is not None
    
    def test_ai_text_high_score(self, sample_ai_text):
        """AI生成テキストは高スコア"""
        detector = AIDetector()
        messages = []
        
        for text in sample_ai_text:
            msg = Mock()
            msg.content = text
            messages.append(msg)
        
        score = detector.detect_ai_text(messages)
        
        # AI生成文章は高スコア（60以上）
        assert score >= 60, f"Expected high score for AI text, got {score}"
    
    def test_human_text_low_score(self, sample_human_text):
        """人間らしいテキストは低スコア"""
        detector = AIDetector()
        messages = []
        
        for text in sample_human_text:
            msg = Mock()
            msg.content = text
            messages.append(msg)
        
        score = detector.detect_ai_text(messages)
        
        # 人間らしい文章は低スコア（40以下）
        assert score <= 40, f"Expected low score for human text, got {score}"
    
    def test_empty_messages(self):
        """空のメッセージリストは中立スコア"""
        detector = AIDetector()
        score = detector.detect_ai_text([])
        
        assert score == 50
    
    def test_japanese_formal_consistency_detection(self):
        """日本語の敬語一貫性検知"""
        detector = AIDetector()
        
        # AI的：です/ます調が完璧に一貫
        formal_consistent_messages = []
        formal_texts = [
            "本日はお忙しい中お時間をいただきありがとうございます。",
            "ご質問につきまして詳しくご説明させていただきます。",
            "こちらの件につきまして確認いたします。",
            "何かご不明な点がございましたらお気軽にお申し付けください。",
            "今後ともどうぞよろしくお願いいたします。"
        ]
        
        for text in formal_texts:
            msg = Mock()
            msg.content = text
            formal_consistent_messages.append(msg)
        
        # 人間的：敬語とカジュアルが混在
        mixed_messages = []
        mixed_texts = [
            "ありがとうございます！",
            "そうですね〜確認してみます",
            "了解！よろしく",
            "すみません、ちょっと確認しますね",
            "おつかれさまでした"
        ]
        
        for text in mixed_texts:
            msg = Mock()
            msg.content = text
            mixed_messages.append(msg)
        
        formal_score = detector._analyze_japanese_patterns(formal_consistent_messages)
        mixed_score = detector._analyze_japanese_patterns(mixed_messages)
        
        # 一貫しすぎた敬語はAI疑い
        assert formal_score > mixed_score, "Overly consistent formal Japanese should raise AI suspicion"
    
    def test_english_connector_frequency(self):
        """英語接続詞の頻度分析"""
        detector = AIDetector()
        
        # AI的：接続詞を多用
        ai_english_messages = []
        ai_texts = [
            "However, this approach has several limitations. Furthermore, we need to consider the implications. Moreover, the results suggest that additional research is required.",
            "Nevertheless, the findings are significant. Additionally, we should examine the methodology. Consequently, this leads to important conclusions.",
            "Therefore, we can conclude that the hypothesis is valid. Furthermore, the data supports our initial assumptions."
        ]
        
        for text in ai_texts:
            msg = Mock()
            msg.content = text
            ai_english_messages.append(msg)
        
        # 人間的：接続詞の使用が自然
        human_english_messages = []
        human_texts = [
            "I think this is pretty cool. What do you guys think?",
            "Yeah, that makes sense. Maybe we should try it.",
            "Nah, I don't really agree with that. Seems kinda weird to me."
        ]
        
        for text in human_texts:
            msg = Mock()
            msg.content = text
            human_english_messages.append(msg)
        
        ai_score = detector._analyze_english_patterns(ai_english_messages)
        human_score = detector._analyze_english_patterns(human_english_messages)
        
        # 接続詞の多用はAI疑い
        assert ai_score > human_score, "Overuse of connectors should raise AI suspicion"
    
    def test_repeated_phrase_detection(self):
        """繰り返しフレーズ検知"""
        detector = AIDetector()
        
        # 繰り返しフレーズが多い（AI的）
        repetitive_messages = []
        base_phrases = [
            "ご質問ありがとうございます",
            "承知いたしました",
            "確認いたします"
        ]
        
        # 各フレーズを複数回使用
        for phrase in base_phrases * 3:  # 3回ずつ繰り返し
            msg = Mock()
            msg.content = f"{phrase}。詳細については後ほど。"
            repetitive_messages.append(msg)
        
        # バリエーション豊富（人間的）
        varied_messages = []
        varied_texts = [
            "ありがとう！",
            "そうなんだ〜",
            "なるほどね",
            "わかった！",
            "いいね",
            "そう思う",
            "確かに",
            "マジで？",
            "すごいね"
        ]
        
        for text in varied_texts:
            msg = Mock()
            msg.content = text
            varied_messages.append(msg)
        
        repetitive_score = detector._detect_repeated_phrases(repetitive_messages)
        varied_score = detector._detect_repeated_phrases(varied_messages)
        
        # 繰り返しが多いとAI疑い
        assert repetitive_score > varied_score, "Repeated phrases should raise AI suspicion"
    
    def test_sentence_length_uniformity(self):
        """文長の均一性検知"""
        detector = AIDetector()
        
        # AI的：文長が異常に均一
        uniform_messages = []
        # 全て20文字前後で統一
        uniform_texts = [
            "これは標準的な長さの文章です。",  # 16文字
            "今日は良い天気でした。",      # 12文字
            "明日の予定を確認します。",     # 12文字
            "お疲れ様でした。",           # 8文字
            "ありがとうございました。"     # 12文字
        ]
        
        for text in uniform_texts:
            msg = Mock()
            msg.content = text
            uniform_messages.append(msg)
        
        # 人間的：文長がバラバラ
        varied_length_messages = []
        varied_texts = [
            "うん",  # 2文字
            "そういえば昨日話してたあれ、結局どうなったの？詳しく教えて",  # 32文字
            "了解！",  # 3文字
            "そうですね、確認してみますが、少し時間がかかるかもしれません",  # 33文字
            "OK"  # 2文字
        ]
        
        for text in varied_texts:
            msg = Mock()
            msg.content = text
            varied_length_messages.append(msg)
        
        uniform_score = detector._analyze_sentence_length_uniformity(uniform_messages)
        varied_score = detector._analyze_sentence_length_uniformity(varied_length_messages)
        
        # 文長が均一すぎるとAI疑い
        assert uniform_score > varied_score, "Uniform sentence lengths should raise AI suspicion"
    
    def test_passive_voice_ratio_english(self):
        """英語の受動態比率分析"""
        detector = AIDetector()
        
        # AI的：受動態を多用
        passive_heavy_messages = []
        passive_texts = [
            "The report was written by our team. The analysis was conducted thoroughly. The results were reviewed by experts.",
            "The decision was made after careful consideration. The proposal was accepted by management.",
            "The system was designed to be user-friendly. The interface was created with simplicity in mind."
        ]
        
        for text in passive_texts:
            msg = Mock()
            msg.content = text
            passive_heavy_messages.append(msg)
        
        # 人間的：能動態が多い
        active_heavy_messages = []
        active_texts = [
            "I wrote the report. We conducted the analysis. Experts reviewed the results.",
            "Management made the decision after we considered it carefully. They accepted our proposal.",
            "We designed the system to help users. I created the interface with simplicity in mind."
        ]
        
        for text in active_texts:
            msg = Mock()
            msg.content = text
            active_heavy_messages.append(msg)
        
        passive_score = detector._analyze_english_patterns(passive_heavy_messages)
        active_score = detector._analyze_english_patterns(active_heavy_messages)
        
        # 受動態の多用はAI疑い
        assert passive_score > active_score, "Overuse of passive voice should raise AI suspicion"
    
    def test_n_gram_repetition_analysis(self):
        """n-gram重複率分析"""
        detector = AIDetector()
        
        # 高い重複率（AI的）
        repetitive_messages = []
        base_text = "この問題について詳しく検討した結果"
        
        for i in range(5):
            msg = Mock()
            msg.content = f"{base_text}、解決策{i+1}を提案します。"
            repetitive_messages.append(msg)
        
        # 低い重複率（人間的）
        unique_messages = []
        unique_texts = [
            "今日は寒いね",
            "映画見に行かない？",
            "宿題終わった？",
            "お疲れ様！",
            "また明日〜"
        ]
        
        for text in unique_texts:
            msg = Mock()
            msg.content = text
            unique_messages.append(msg)
        
        repetitive_score = detector._calculate_ngram_repetition(repetitive_messages)
        unique_score = detector._calculate_ngram_repetition(unique_messages)
        
        # n-gramの重複が多いとAI疑い
        assert repetitive_score > unique_score, "High n-gram repetition should raise AI suspicion"
    
    def test_comprehensive_ai_detection(self):
        """総合的なAI検知テスト"""
        detector = AIDetector()
        
        # 典型的なAI生成文章
        ai_messages = []
        ai_comprehensive_texts = [
            "ご質問いただきありがとうございます。この件につきまして詳細に検討させていただいた結果、以下のような回答をさせていただきます。",
            "まず第一に考慮すべき点は、技術的な実現可能性です。次に、コスト面での検討が必要となります。最後に、スケジュールの調整が重要になります。",
            "このような状況においては、段階的なアプローチを取ることが推奨されます。初期段階では基本的な機能の実装を行い、その後に高度な機能を追加していく方針が適切と考えられます。"
        ]
        
        for text in ai_comprehensive_texts:
            msg = Mock()
            msg.content = text
            ai_messages.append(msg)
        
        # 典型的な人間の文章
        human_messages = []
        human_comprehensive_texts = [
            "あー、それね！昨日も同じこと考えてた😅",
            "うーん、どうしよう...ちょっと難しそうだけど、やってみる？",
            "マジで！？知らなかった〜ありがとう！！"
        ]
        
        for text in human_comprehensive_texts:
            msg = Mock()
            msg.content = text
            human_messages.append(msg)
        
        ai_score = detector.detect_ai_text(ai_messages)
        human_score = detector.detect_ai_text(human_messages)
        
        # AI文章は明確に高スコア
        assert ai_score >= 70, f"Expected very high score for AI text, got {ai_score}"
        assert human_score <= 30, f"Expected very low score for human text, got {human_score}"
        assert ai_score - human_score >= 40, "Score difference should be significant"