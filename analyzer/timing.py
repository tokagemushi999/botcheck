# analyzer/timing.py - タイミング分析クラス

import statistics
from datetime import datetime, timedelta
from typing import List, Any, Dict
from collections import Counter

from .utils import _get

class TimingAnalyzer:
    """投稿タイミングパターンの分析クラス"""
    
    def __init__(self):
        self.min_messages_for_analysis = 3
        self.regular_interval_threshold = 0.2  # 変動係数の閾値
    
    def analyze_timing(self, messages: List[Any]) -> float:
        """メインのタイミング分析関数"""
        if not messages or len(messages) < self.min_messages_for_analysis:
            return 50.0
        
        # 各分析要素のスコア計算
        interval_score = self._analyze_interval_regularity(messages)
        reply_speed_score = self._analyze_reply_speed(messages)
        activity_pattern_score = self._analyze_activity_patterns(messages)
        
        # 重み付き平均
        total_score = (
            interval_score * 0.4 +      # 投稿間隔の規則性
            reply_speed_score * 0.3 +   # 返信速度
            activity_pattern_score * 0.3 # 活動パターン
        )
        
        return min(max(total_score, 0.0), 100.0)
    
    def _analyze_interval_regularity(self, messages: List[Any]) -> float:
        """投稿間隔の規則性分析"""
        intervals = self._calculate_intervals(messages)
        
        if len(intervals) < 2:
            return 50.0
        
        # 間隔の変動係数を計算
        try:
            mean_interval = statistics.mean(intervals)
            if mean_interval <= 0:
                return 50.0
            
            std_interval = statistics.stdev(intervals)
            coefficient_of_variation = std_interval / mean_interval
            
            # 変動係数が小さいほど規則的（Bot疑い）
            if coefficient_of_variation < self.regular_interval_threshold:
                # 非常に規則的 = 高スコア
                regularity_score = 80 + (self.regular_interval_threshold - coefficient_of_variation) * 300
                return min(regularity_score, 100.0)
            else:
                # 変動が大きい = 人間らしい = 低スコア
                return max(5.0, 40 - coefficient_of_variation * 60)
        
        except statistics.StatisticsError:
            return 50.0
    
    def _analyze_reply_speed(self, messages: List[Any]) -> float:
        """返信速度分析"""
        if len(messages) < 4:  # メンションと返信のペアが必要
            return 50.0
        
        rapid_replies = 0
        total_replies = 0
        
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]
            
            # メンションされた後の返信を検出
            if self._is_reply_to_mention(current_msg, next_msg):
                time_diff = self._get_time_difference(current_msg, next_msg)
                total_replies += 1
                
                # 30秒以内の返信は疑わしい
                if time_diff and time_diff < 30:
                    rapid_replies += 1
        
        if total_replies == 0:
            return 50.0
        
        rapid_reply_ratio = rapid_replies / total_replies
        return min(50 + rapid_reply_ratio * 400, 100.0)
    
    def _analyze_activity_patterns(self, messages: List[Any]) -> float:
        """活動パターンの分析"""
        if len(messages) < 10:
            return 50.0
        
        # 時間帯分析
        hour_counter = Counter()
        day_counter = Counter()
        
        for msg in messages:
            timestamp = self._extract_timestamp(msg)
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                hour_counter[dt.hour] += 1
                day_counter[dt.weekday()] += 1
        
        # 時間帯の均等性スコア（24時間均等なら Bot 疑い）
        hour_uniformity = self._calculate_distribution_uniformity(hour_counter, 24)
        
        # 曜日の均等性スコア（7日均等なら Bot 疑い）
        day_uniformity = self._calculate_distribution_uniformity(day_counter, 7)
        
        # 均等すぎると Bot 疑い
        uniformity_score = (hour_uniformity + day_uniformity) / 2
        return min(50 + uniformity_score * 150, 100.0)
    
    def _calculate_intervals(self, messages: List[Any]) -> List[float]:
        """投稿間隔（秒）のリストを計算"""
        timestamps = []
        
        for msg in messages:
            timestamp = self._extract_timestamp(msg)
            if timestamp:
                timestamps.append(timestamp)
        
        timestamps.sort()
        
        if len(timestamps) < 2:
            return []
        
        intervals = []
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i-1]
            if interval > 0:  # 正の間隔のみ
                intervals.append(interval)
        
        return intervals
    
    def _calculate_variance(self, intervals: List[float]) -> float:
        """間隔の分散を計算"""
        if len(intervals) < 2:
            return 0.0
        
        try:
            return statistics.variance(intervals)
        except statistics.StatisticsError:
            return 0.0
    
    def _extract_timestamp(self, msg: Any) -> float:
        """メッセージからタイムスタンプを抽出"""
        created_at = _get(msg, 'created_at')
        if created_at:
            if isinstance(created_at, datetime):
                return created_at.timestamp()
            elif isinstance(created_at, (int, float)):
                return float(created_at)
            elif isinstance(created_at, str):
                try:
                    return datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
                except ValueError:
                    pass
        
        # Fallback to timestamp field
        timestamp = _get(msg, 'timestamp')
        if isinstance(timestamp, (int, float)):
            return float(timestamp)
        
        return None
    
    def _is_reply_to_mention(self, msg1: Any, msg2: Any) -> bool:
        """msg2 が msg1 への返信（メンション）かどうか判定"""
        # 簡易実装：作成者が異なり、msg1 にメンションがある場合
        author1 = _get(msg1, 'author_id')
        author2 = _get(msg2, 'author_id')
        
        if not author1 or not author2 or author1 == author2:
            return False
        
        # msg1 にメンションが含まれているかチェック
        mentions = _get(msg1, 'mentions', [])
        if not mentions and isinstance(msg1, dict):
            mentions = msg1.get('mentions', [])
        
        # メンションがあり、次のメッセージの作成者がメンション対象の場合
        if mentions:
            mentioned_ids = [getattr(mention, 'id', mention) if hasattr(mention, 'id') else mention for mention in mentions]
            return author2 in mentioned_ids
        
        return False
    
    def _get_time_difference(self, msg1: Any, msg2: Any) -> float:
        """2つのメッセージ間の時間差（秒）を取得"""
        timestamp1 = self._extract_timestamp(msg1)
        timestamp2 = self._extract_timestamp(msg2)
        
        if timestamp1 and timestamp2 and timestamp2 > timestamp1:
            return timestamp2 - timestamp1
        
        return None
    
    def _calculate_distribution_uniformity(self, counter: Counter, expected_bins: int) -> float:
        """分布の均等性を計算（均等に近いほど高スコア）"""
        if not counter:
            return 0.0
        
        total_count = sum(counter.values())
        expected_per_bin = total_count / expected_bins
        
        # カイ二乗統計量の簡易版
        chi_square = 0.0
        for bin_count in counter.values():
            chi_square += ((bin_count - expected_per_bin) ** 2) / expected_per_bin
        
        # 正規化（均等分布なら0、偏っているほど大きくなる）
        # 均等性スコアは均等に近いほど高くなるように調整
        max_chi_square = total_count  # おおよその最大値
        uniformity = 1.0 - min(chi_square / max_chi_square, 1.0)
        
        return uniformity