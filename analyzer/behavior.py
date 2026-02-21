"""Behavior analysis module for BotCheck."""

from __future__ import annotations

from collections import Counter
from math import log2
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def mention_pattern_score(messages: list[dict[str, Any]]) -> float:
    if len(messages) < 5:
        return 50.0

    mention_counts = [int(msg.get("mention_count", 0) or 0) for msg in messages]
    total_mentions = sum(mention_counts)

    if total_mentions == 0:
        return 60.0

    targets: list[str] = []
    for msg in messages:
        raw = msg.get("mention_targets", [])
        if isinstance(raw, list):
            targets.extend([str(item) for item in raw if item])

    if not targets:
        ratio = total_mentions / max(1, len(messages))
        return _clamp(min(ratio, 5.0) / 5.0 * 85.0)

    counter = Counter(targets)
    max_share = max(counter.values()) / len(targets)
    # 特定ユーザーへの集中メンションは自動応答に見えやすい
    return _clamp(max_share * 100.0)


def channel_usage_score(messages: list[dict[str, Any]]) -> float:
    channels = [str(msg.get("channel_id", "")) for msg in messages if msg.get("channel_id")]
    if len(channels) < 5:
        return 50.0

    counts = Counter(channels)
    total = len(channels)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * log2(p)

    max_entropy = log2(len(counts)) if len(counts) > 1 else 1.0
    normalized = entropy / max_entropy if max_entropy else 0.0

    # 少数チャンネル固定運用はBot傾向
    return _clamp((1.0 - normalized) * 100.0)


def edit_frequency_score(messages: list[dict[str, Any]]) -> float:
    if not messages:
        return 50.0

    edited = sum(1 for msg in messages if msg.get("is_edited"))
    ratio = edited / len(messages)
    # 編集が全く無い場合はややBot寄り
    if ratio == 0:
        return 75.0
    if ratio >= 0.12:
        return 20.0
    normalized = ratio / 0.12
    return _clamp(75.0 - normalized * 55.0)


def reaction_usage_score(messages: list[dict[str, Any]]) -> float:
    if not messages:
        return 50.0

    used = sum(1 for msg in messages if int(msg.get("reaction_count", 0) or 0) > 0)
    ratio = used / len(messages)

    # リアクション利用が少ないほどBot寄り
    return _clamp((1.0 - min(ratio, 0.5) / 0.5) * 100.0)


def analyze_behavior(messages: list[dict[str, Any]]) -> dict[str, Any]:
    mention_score = mention_pattern_score(messages)
    channel_score = channel_usage_score(messages)
    edit_score = edit_frequency_score(messages)
    reaction_score = reaction_usage_score(messages)

    score = _clamp(mention_score * 0.25 + channel_score * 0.3 + edit_score * 0.2 + reaction_score * 0.25)

    return {
        "score": score,
        "details": {
            "mention_pattern": round(mention_score, 2),
            "channel_usage": round(channel_score, 2),
            "edit_frequency": round(edit_score, 2),
            "reaction_usage": round(reaction_score, 2),
        },
    }
