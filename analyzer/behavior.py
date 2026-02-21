"""Behavior analysis module for BotCheck."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from .utils import _get


class BehaviorAnalyzer:
    """行動パターンの分析クラス"""

    def __init__(self):
        self.min_messages = 5

    def analyze_behavior(self, messages: list[Any]) -> float:
        """メインの行動分析関数。0-100のスコアを返す。"""
        if not messages:
            return 50.0

        if len(messages) < self.min_messages:
            return 50.0

        mention_score = self._analyze_mention_patterns(messages)
        channel_score = self._analyze_channel_usage(messages)
        editing_score = self._calculate_editing_score(messages)
        reaction_score = self._calculate_reaction_score(messages)
        context_score = self._analyze_conversation_context(messages)
        consistency_score = self._analyze_cross_channel_consistency(messages)

        total = (
            mention_score * 0.25
            + channel_score * 0.20
            + editing_score * 0.15
            + reaction_score * 0.15
            + context_score * 0.15
            + consistency_score * 0.10
        ) * 1.25  # Boost sensitivity for bot detection
        return _clamp(total)

    # ------------------------------------------------------------------
    # メンション分析
    # ------------------------------------------------------------------
    def _analyze_mention_patterns(self, messages: list[Any]) -> float:
        targets: Counter = Counter()
        total = 0
        for msg in messages:
            mentions = _get(msg, "mentions", [])
            # Handle case where mentions might be a Mock object or empty
            if not mentions:
                continue
            try:
                for m in mentions:
                    mid = str(m.id if hasattr(m, "id") else m)
                    targets[mid] += 1
                    total += 1
            except (TypeError, AttributeError):
                # Handle case where mentions is not iterable or is a Mock
                pass

        if total == 0:
            return 30.0

        max_count = max(targets.values())
        concentration = max_count / total
        if concentration > 0.8:
            return _clamp(70 + (concentration - 0.8) * 300)  # 70-100 range
        elif concentration > 0.5:
            return _clamp(45 + (concentration - 0.5) * 83)   # 45-70 range
        return max(10.0, 40 - concentration * 60)

    # ------------------------------------------------------------------
    # チャンネル利用
    # ------------------------------------------------------------------
    def _analyze_channel_usage(self, messages: list[Any]) -> float:
        usage: Counter = Counter()
        for msg in messages:
            ch = _get(msg, "channel_id", "")
            if ch:
                usage[str(ch)] += 1

        if not usage:
            return 50.0

        total_msgs = sum(usage.values())
        unique = len(usage)

        if unique == 1:
            return 70.0

        dominance = max(usage.values()) / total_msgs
        if dominance > 0.9:
            return _clamp(60 + (dominance - 0.9) * 400)
        return max(20.0, 50 - (unique - 2) * 5)

    # ------------------------------------------------------------------
    # 編集パターン
    # ------------------------------------------------------------------
    def _calculate_editing_score(self, messages: list[Any]) -> float:
        if not messages:
            return 50.0

        edited = sum(1 for m in messages if _get(m, "edited_at") is not None)
        ratio = edited / len(messages)

        if ratio == 0:
            return 65.0
        if ratio > 0.5:
            return 70.0
        if 0.05 <= ratio <= 0.2:
            return 25.0
        return 45.0

    # ------------------------------------------------------------------
    # リアクション
    # ------------------------------------------------------------------
    def _calculate_reaction_score(self, messages: list[Any]) -> float:
        if not messages:
            return 50.0

        with_reactions = 0
        reaction_types: set[str] = set()

        for msg in messages:
            reactions = _get(msg, "reactions", [])
            if reactions:
                with_reactions += 1
                try:
                    for r in reactions:
                        emoji = str(r.emoji if hasattr(r, "emoji") else r)
                        reaction_types.add(emoji)
                except (TypeError, AttributeError):
                    # Handle case where reactions is not iterable or is a Mock
                    pass

        ratio = with_reactions / len(messages)

        # No reactions = Bot-like behavior (high score)
        if ratio == 0:
            return 80.0
        # Very limited reaction types = Bot-like 
        if len(reaction_types) == 1 and with_reactions > 3:
            return 75.0
        # Natural reaction usage = human-like (low score)
        if 0.1 <= ratio <= 0.4:
            return 30.0
        return 50.0

    # ------------------------------------------------------------------
    # 会話文脈
    # ------------------------------------------------------------------
    def _analyze_conversation_context(self, messages: list[Any]) -> float:
        if len(messages) < 10:
            return 50.0

        template_phrases = [
            "ご質問ありがとうございます",
            "承知いたしました",
            "お疲れさまでした",
            "失礼いたします",
        ]

        template_count = 0
        context_breaks = 0

        for i, msg in enumerate(messages):
            content = _content(msg)
            if any(p in content for p in template_phrases):
                template_count += 1
            if i > 0:
                prev = _content(messages[i - 1])
                if any(q in prev for q in ["?", "？", "どう", "なぜ", "何"]):
                    if any(p in content for p in template_phrases):
                        context_breaks += 1

        n = len(messages)
        t_ratio = template_count / n
        c_ratio = context_breaks / max(n - 1, 1)

        # Higher sensitivity for template phrase usage and context breaks
        return _clamp((t_ratio * 60 + c_ratio * 80) * 1.3)

    # ------------------------------------------------------------------
    # クロスチャンネル一貫性
    # ------------------------------------------------------------------
    def _analyze_cross_channel_consistency(self, messages: list[Any]) -> float:
        by_channel: dict[str, list[str]] = defaultdict(list)

        for msg in messages:
            ch = str(_get(msg, "channel_id", ""))
            content = _content(msg)
            if ch and content:
                by_channel[ch].append(content)

        if len(by_channel) < 2:
            return 50.0

        channels = list(by_channel.keys())
        similarities: list[float] = []

        for i in range(len(channels)):
            for j in range(i + 1, len(channels)):
                c1 = by_channel[channels[i]]
                c2 = by_channel[channels[j]]
                if len(c1) >= 3 and len(c2) >= 3:
                    sim = self._text_similarity(c1, c2)
                    similarities.append(sim)

        if not similarities:
            return 50.0

        avg = statistics.mean(similarities)
        # More sensitive to cross-channel similarities
        if avg > 0.7:
            return _clamp(65 + (avg - 0.7) * 300)
        elif avg > 0.5:
            return _clamp(35 + (avg - 0.5) * 150)
        return 25.0

    def _text_similarity(self, texts1: list[str], texts2: list[str]) -> float:
        avg_len1 = statistics.mean([len(t) for t in texts1])
        avg_len2 = statistics.mean([len(t) for t in texts2])
        len_sim = 1.0 - min(abs(avg_len1 - avg_len2) / max(avg_len1, avg_len2, 1), 1.0)

        set1 = set(texts1)
        set2 = set(texts2)
        if set1 and set2:
            overlap = len(set1 & set2) / max(len(set1 | set2), 1)
        else:
            overlap = 0.0

        return (len_sim + overlap) / 2.0


# ------------------------------------------------------------------
# ヘルパー
# ------------------------------------------------------------------
def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


def _content(msg: Any) -> str:
    c = _get(msg, "content", "")
    return str(c) if c else ""


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))
