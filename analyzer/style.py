# analyzer/style.py - 文体分析クラス

import re
import statistics
from collections import Counter
from typing import List, Any, Dict

from .utils import extract_contents

class StyleAnalyzer:
    """文体パターンの分析クラス"""
    
    def __init__(self):
        # 日本語パターン
        self.jp_polite_endings = re.compile(r'(です|ます|でした|ました|ません|でしょう|ございます|いたします)$')
        self.jp_template_phrases = [
            'ご質問ありがとうございます',
            'お忙しい中ありがとうございます',
            '承知いたしました',
            '失礼いたします',
            'お疲れさまでした',
            'よろしくお願いします',
            'ご確認ください',
            'お世話になっております'
        ]
        
        # 共通パターン
        self.emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+')
        self.word_pattern = re.compile(r'[\w\u3040-\u30ff\u4e00-\u9fff]+')
        self.sentence_endings = re.compile(r'[.!?。！？]+')
    
    def analyze_style(self, messages: List[Any]) -> float:
        """メインの文体分析関数"""
        if not messages:
            return 50.0
        
        contents = self._extract_contents(messages)
        if len(contents) < 3:
            return 50.0
        
        # 各分析要素のスコア計算
        ttr_score = self._analyze_vocabulary_diversity(contents)
        length_variance_score = self._analyze_sentence_length_variance(contents)
        template_score = self._analyze_template_phrases(contents)
        emoji_score = self._analyze_emoji_patterns(contents)
        politeness_score = self._analyze_politeness_consistency(contents)
        punctuation_score = self._analyze_punctuation_patterns(contents)
        
        # 重み付き平均
        total_score = (
            ttr_score * 0.25 +              # 語彙多様性
            length_variance_score * 0.2 +   # 文長のばらつき
            template_score * 0.2 +          # 定型フレーズ
            emoji_score * 0.15 +            # 絵文字パターン
            politeness_score * 0.1 +        # 丁寧語一貫性
            punctuation_score * 0.1         # 句読点パターン
        ) * 1.05  # Slight boost for formal style detection
        
        return min(max(total_score, 0.0), 100.0)
    
    def _extract_contents(self, messages: List[Any]) -> List[str]:
        """メッセージから内容を抽出"""
        return extract_contents(messages)
    
    def _analyze_vocabulary_diversity(self, contents: List[str]) -> float:
        """語彙多様性（TTR: Type-Token Ratio）の分析"""
        all_text = ' '.join(contents)
        tokens = self.word_pattern.findall(all_text.lower())
        
        if len(tokens) < 10:
            return 50.0
        
        unique_tokens = set(tokens)
        ttr = len(unique_tokens) / len(tokens)
        
        # TTRが低い（語彙が単調）ほどBot疑い
        if ttr < 0.3:
            diversity_score = 70 + (0.3 - ttr) * 100
            return min(diversity_score, 100.0)
        else:
            # 多様性が高いほど人間らしい
            return max(10.0, 50 - (ttr - 0.3) * 60)
    
    def _calculate_ttr(self, messages: List[Any]) -> float:
        """TTR計算（テスト用）"""
        contents = self._extract_contents(messages)
        all_text = ' '.join(contents)
        tokens = self.word_pattern.findall(all_text.lower())
        
        if len(tokens) == 0:
            return 0.0
        
        unique_tokens = set(tokens)
        return len(unique_tokens) / len(tokens)
    
    def _analyze_sentence_length_variance(self, contents: List[str]) -> float:
        """文長のばらつき分析"""
        sentence_lengths = []
        
        for text in contents:
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            sentence_lengths.extend([len(s) for s in sentences])
        
        if len(sentence_lengths) < 5:
            return 50.0
        
        try:
            variance = statistics.variance(sentence_lengths)
            mean_length = statistics.mean(sentence_lengths)
            
            if mean_length == 0:
                return 50.0
            
            # 変動係数が小さいほど一様（Bot疑い）
            cv = (variance ** 0.5) / mean_length
            
            if cv < 0.3:
                # 一様すぎる = Bot疑い
                uniformity_score = 60 + (0.3 - cv) * 100
                return min(uniformity_score, 100.0)
            else:
                # 変動が大きい = 人間らしい
                return max(20.0, 50 - (cv - 0.3) * 40)
        
        except statistics.StatisticsError:
            return 50.0
    
    def _calculate_sentence_length_variance(self, messages: List[Any]) -> float:
        """文長分散計算（テスト用）"""
        contents = self._extract_contents(messages)
        sentence_lengths = []
        
        for text in contents:
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            sentence_lengths.extend([len(s) for s in sentences])
        
        if len(sentence_lengths) < 2:
            return 0.0
        
        try:
            return statistics.variance(sentence_lengths)
        except statistics.StatisticsError:
            return 0.0
    
    def _analyze_template_phrases(self, contents: List[str]) -> float:
        """定型フレーズの分析"""
        template_count = 0
        total_messages = len(contents)
        
        for text in contents:
            text_lower = text.lower()
            for phrase in self.jp_template_phrases:
                if phrase.lower() in text_lower:
                    template_count += 1
                    break  # 1メッセージにつき1カウント
        
        if total_messages == 0:
            return 50.0
        
        template_ratio = template_count / total_messages
        return min(template_ratio * 150, 100.0)
    
    def _calculate_template_phrase_ratio(self, messages: List[Any]) -> float:
        """定型フレーズ比率計算（テスト用）"""
        contents = self._extract_contents(messages)
        template_count = 0
        
        for text in contents:
            text_lower = text.lower()
            for phrase in self.jp_template_phrases:
                if phrase.lower() in text_lower:
                    template_count += 1
                    break
        
        if len(contents) == 0:
            return 0.0
        
        return template_count / len(contents)
    
    def _analyze_emoji_patterns(self, contents) -> float:
        """絵文字使用パターンの分析"""
        if not contents:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        emoji_counts = []
        messages_with_emoji = 0
        
        for text in contents:
            emojis = self.emoji_pattern.findall(text)
            emoji_count = len(emojis)
            emoji_counts.append(emoji_count)
            
            if emoji_count > 0:
                messages_with_emoji += 1
        
        if len(contents) == 0:
            return 50.0
        
        # 絵文字使用パターン分析
        emoji_usage_ratio = messages_with_emoji / len(contents)
        
        # 絵文字を全く使わない = Bot疑い
        if messages_with_emoji == 0:
            return 75.0
        
        # 絵文字使用の変動分析
        if len(emoji_counts) > 2:
            try:
                emoji_variance = statistics.variance(emoji_counts)
                mean_emoji = statistics.mean(emoji_counts)
                
                # 絵文字使用が一様すぎるとBot疑い
                if mean_emoji > 0:
                    cv = emoji_variance ** 0.5 / (mean_emoji + 0.1)  # Coefficient of variation
                    if cv < 0.3:  # Low variation = bot-like
                        return 65.0
                    else:  # High variation = human-like
                        return 25.0
                        
            except (statistics.StatisticsError, ZeroDivisionError):
                pass
        
        # Natural emoji usage (fallback)
        return 35.0
    
    def _analyze_politeness_consistency(self, contents: List[str]) -> float:
        """丁寧語・敬語の一貫性分析"""
        total_sentences = 0
        polite_sentences = 0
        
        for text in contents:
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            total_sentences += len(sentences)
            
            for sentence in sentences:
                if self.jp_polite_endings.search(sentence):
                    polite_sentences += 1
        
        if total_sentences == 0:
            return 50.0
        
        polite_ratio = polite_sentences / total_sentences
        
        # 90%以上の一貫性でBot疑い
        if polite_ratio > 0.9:
            consistency_score = 60 + (polite_ratio - 0.9) * 400
            return min(consistency_score, 100.0)
        # 10%以下も一様でBot疑い
        elif polite_ratio < 0.1:
            return 70.0
        else:
            # 中間的な使用は人間的
            return 25.0
    
    def _analyze_punctuation_patterns(self, contents: List[str]) -> float:
        """句読点パターンの分析"""
        perfect_punctuation_count = 0
        total_sentences = 0
        
        for text in contents:
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            total_sentences += len(sentences)
            
            for sentence in sentences:
                # 完璧な句読点使用を検出（。で終わる、など）
                if sentence.endswith('。') and '、' in sentence:
                    perfect_punctuation_count += 1
        
        if total_sentences == 0:
            return 50.0
        
        perfect_ratio = perfect_punctuation_count / total_sentences
        
        # 完璧すぎる句読点はBot疑い
        if perfect_ratio > 0.8:
            return 60 + perfect_ratio * 40
        else:
            return 30.0