# analyzer/ai_detect.py - AI検知強化版（MeCab不要、英語対応、外部モデル連携オプション）

import re
import os
import statistics
from collections import Counter
from math import log2
from typing import List, Dict, Any, Optional
from unittest.mock import Mock

from .utils import _get, extract_contents

# 外部モデル連携（環境変数でON/OFF）
USE_EXTERNAL_MODELS = os.getenv("BOTCHECK_USE_EXTERNAL_AI", "false").lower() == "true"

class AIDetector:
    """AI生成テキスト検知クラス"""
    
    def __init__(self):
        # 日本語パターン（MeCab不要）
        self.jp_polite_endings = re.compile(r'(です|ます|でした|ました|ません|でしょう|ございます|いたします|させていただきます)$')
        self.jp_connectors = re.compile(r'(また|さらに|そして|しかし|そのため|なお|一方で|加えて|つまり|すなわち|ただし|もっとも|したがって)')
        
        # 英語パターン
        self.en_connectors = re.compile(r'\b(However|Furthermore|Moreover|Nevertheless|Additionally|Therefore|Consequently|In conclusion|On the other hand|In addition|As a result)\b')
        self.en_passive_voice = re.compile(r'\b(was|were|is|are|been|being)\s+\w+(ed|en)\b')
        
        # 共通パターン
        self.sentence_endings = re.compile(r'[.!?。！？]+')
        self.word_tokens = re.compile(r'[\w\u3040-\u30ff\u4e00-\u9fff]+')
    
    def detect_ai_text(self, messages: List[Any]) -> float:
        """メインのAI検知関数"""
        if not messages:
            return 50.0
        
        contents = self._extract_contents(messages)
        if len(contents) < 3:
            return 50.0
        
        # 各分析スコア
        jp_score = self._analyze_japanese_patterns(contents)
        en_score = self._analyze_english_patterns(contents)
        repetition_score = self._detect_repeated_phrases(contents)
        uniformity_score = self._analyze_sentence_length_uniformity(contents)
        ngram_score = self._calculate_ngram_repetition(contents)
        
        # 言語検出に基づく重み調整
        lang_weights = self._detect_language_weights(contents)
        
        # 統合スコア計算
        total_score = (
            jp_score * lang_weights['japanese'] * 0.25 +
            en_score * lang_weights['english'] * 0.25 +
            repetition_score * 0.20 +
            uniformity_score * 0.15 +
            ngram_score * 0.15
        )
        
        # Boost overall AI detection sensitivity
        total_score = total_score * 1.8  # Increase all AI scores by 80%
        
        # 外部モデル連携（オプション）
        if USE_EXTERNAL_MODELS:
            external_score = self._query_external_model(contents)
            total_score = total_score * 0.7 + external_score * 0.3
        
        return min(max(total_score, 0.0), 100.0)
    
    def _extract_contents(self, messages: List[Any]) -> List[str]:
        """メッセージから内容を抽出"""
        return extract_contents(messages, min_length=5)
    
    def _analyze_japanese_patterns(self, contents) -> float:
        """日本語特有パターンの分析（MeCab不要）"""
        if not contents:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        total_sentences = 0
        polite_sentences = 0
        connector_count = 0
        
        for text in contents:
            # 文を分割（簡易版）
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            total_sentences += len(sentences)
            
            # 丁寧語の一貫性チェック
            for sentence in sentences:
                if self.jp_polite_endings.search(sentence):
                    polite_sentences += 1
            
            # 接続詞の使用頻度
            connector_matches = len(self.jp_connectors.findall(text))
            connector_count += connector_matches
        
        if total_sentences == 0:
            return 50.0
        
        # 丁寧語の一貫性スコア（80%以上で高スコア）
        polite_ratio = polite_sentences / total_sentences
        polite_consistency_score = 0
        if polite_ratio > 0.8:
            polite_consistency_score = min(50 + (polite_ratio - 0.8) * 250, 90)  # 50-90点
        elif polite_ratio > 0.6:
            polite_consistency_score = 30 + (polite_ratio - 0.6) * 100  # 30-50点
        
        # 接続詞多用スコア
        connector_ratio = connector_count / max(total_sentences, 1)
        connector_score = min(20 + connector_ratio * 200, 60)  # 最大60点
        
        return min(polite_consistency_score + connector_score, 100.0)
    
    def _analyze_english_patterns(self, contents) -> float:
        """英語パターンの分析"""
        if not contents:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        total_text = ' '.join(contents)
        sentences = [s.strip() for s in re.split(r'[.!?]+', total_text) if s.strip()]
        
        if not sentences:
            return 50.0
        
        # 接続詞の頻度分析
        connector_matches = len(self.en_connectors.findall(total_text))
        connector_ratio = connector_matches / len(sentences)
        connector_score = min(30 + connector_ratio * 300, 70)  # 30-70点
        
        # 受動態の比率分析
        passive_matches = len(self.en_passive_voice.findall(total_text))
        words = len(self.word_tokens.findall(total_text))
        if words > 0:
            passive_ratio = passive_matches / (words / 100)  # 100語あたり
            passive_score = min(20 + passive_ratio * 40, 60)  # 20-60点
        else:
            passive_score = 20
        
        return min(connector_score + passive_score, 100.0)
    
    def _detect_repeated_phrases(self, contents) -> float:
        """繰り返しフレーズの検知"""
        if not contents or len(contents) < 3:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        # フレーズを抽出（5文字以上の共通部分）
        phrase_counter = Counter()
        
        for i, text1 in enumerate(contents):
            for j, text2 in enumerate(contents[i+1:], i+1):
                # 共通部分文字列を検索
                common_phrases = self._find_common_substrings(text1, text2, min_length=5)
                for phrase in common_phrases:
                    if len(phrase) >= 5:  # 5文字以上
                        phrase_counter[phrase] += 1
        
        if not phrase_counter:
            return 0.0
        
        # 繰り返し率の計算
        total_comparisons = len(contents) * (len(contents) - 1) // 2
        repeated_phrases = sum(count for count in phrase_counter.values() if count >= 2)
        
        if total_comparisons == 0:
            return 30.0
        
        repetition_ratio = repeated_phrases / total_comparisons
        return min(40 + repetition_ratio * 400, 100.0)  # 40-100点
    
    def _analyze_sentence_length_uniformity(self, contents) -> float:
        """文長の均一性分析"""
        if not contents:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        sentence_lengths = []
        
        for text in contents:
            sentences = [s.strip() for s in self.sentence_endings.split(text) if s.strip()]
            sentence_lengths.extend([len(s) for s in sentences])
        
        if len(sentence_lengths) < 5:
            return 50.0
        
        # 標準偏差を計算
        try:
            std_dev = statistics.stdev(sentence_lengths)
            mean_length = statistics.mean(sentence_lengths)
            
            if mean_length == 0:
                return 50.0
            
            # 変動係数（標準偏差/平均）が小さいほどAI疑い
            cv = std_dev / mean_length
            
            # 変動係数が0.2以下で高スコア
            if cv < 0.2:
                uniformity_score = 50 + (0.2 - cv) * 250  # 50-100点
                return min(uniformity_score, 100.0)
            
            return max(10.0, 50.0 - cv * 80)  # 変動が大きいほど低スコア
            
        except statistics.StatisticsError:
            return 50.0
    
    def _calculate_ngram_repetition(self, contents) -> float:
        """n-gram重複率の分析"""
        if not contents:
            return 50.0
        
        # If contents is a list of Mock objects, extract strings first
        if contents and hasattr(contents[0], 'content'):
            contents = extract_contents(contents)
        
        all_text = ' '.join(contents)
        words = self.word_tokens.findall(all_text.lower())
        
        if len(words) < 10:
            return 50.0
        
        # 3-gramの重複率を計算
        trigrams = []
        for i in range(len(words) - 2):
            trigram = ' '.join(words[i:i+3])
            trigrams.append(trigram)
        
        if not trigrams:
            return 50.0
        
        trigram_counts = Counter(trigrams)
        duplicated_trigrams = sum(count - 1 for count in trigram_counts.values() if count > 1)
        
        duplication_ratio = duplicated_trigrams / len(trigrams)
        if duplication_ratio < 0.05:  # Very low duplication = human-like  
            return 15.0
        elif duplication_ratio < 0.15:  # Low duplication = likely human
            return 25.0 + duplication_ratio * 100
        return min(60 + duplication_ratio * 300, 100.0)  # High duplication = AI-like
    
    def _detect_language_weights(self, contents: List[str]) -> Dict[str, float]:
        """言語検出と重み計算"""
        all_text = ' '.join(contents)
        
        # 日本語文字の比率
        japanese_chars = len(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]', all_text))
        # 英語文字の比率
        english_chars = len(re.findall(r'[a-zA-Z]', all_text))
        
        total_chars = japanese_chars + english_chars
        
        if total_chars == 0:
            return {'japanese': 0.5, 'english': 0.5}
        
        jp_ratio = japanese_chars / total_chars
        en_ratio = english_chars / total_chars
        
        return {
            'japanese': jp_ratio,
            'english': en_ratio
        }
    
    def _find_common_substrings(self, str1: str, str2: str, min_length: int = 5) -> List[str]:
        """2つの文字列間の共通部分文字列を検索"""
        common = []
        
        for i in range(len(str1) - min_length + 1):
            for j in range(min_length, min(len(str1) - i + 1, 20)):  # 最大19文字まで
                substring = str1[i:i+j]
                if substring in str2 and len(substring) >= min_length:
                    common.append(substring)
        
        return list(set(common))  # 重複削除
    
    def _query_external_model(self, contents: List[str]) -> float:
        """外部AIモデルとの連携（オプション）"""
        # 実際の実装では、OpenAI API, Anthropic Claude, Google Gemini などを使用
        # ここではダミー実装
        
        try:
            # 環境変数から外部API設定を取得
            api_endpoint = os.getenv("BOTCHECK_AI_API_ENDPOINT")
            api_key = os.getenv("BOTCHECK_AI_API_KEY")
            
            if not api_endpoint or not api_key:
                return 50.0  # 設定なしの場合は中立
            
            # 実際のAPI呼び出し（ダミー）
            # response = requests.post(api_endpoint, ...)
            # return parse_response(response)
            
            return 50.0  # ダミー値
            
        except Exception:
            return 50.0  # エラー時は中立スコア