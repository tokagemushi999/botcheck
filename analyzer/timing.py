"""Timing analysis module for BotCheck."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import log2
from statistics import mean, pstdev
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _extract_timestamps(messages: list[dict[str, Any]]) -> list[int]:
    timestamps: list[int] = []
    for msg in messages:
        ts = msg.get("created_at")
        if isinstance(ts, (int, float)):
            timestamps.append(int(ts))
    return sorted(timestamps)


def interval_regularity_score(messages: list[dict[str, Any]]) -> float:
    """Equal posting intervals imply stronger bot-like behavior."""
    timestamps = _extract_timestamps(messages)
    if len(timestamps) < 3:
        return 50.0

    intervals = [b - a for a, b in zip(timestamps, timestamps[1:]) if (b - a) > 0]
    if len(intervals) < 2:
        return 50.0

    avg = mean(intervals)
    if avg <= 0:
        return 50.0

    std = pstdev(intervals)
    cv = std / avg

    # CVが小さい(規則的)ほどBotっぽい
    score = 100.0 * (1.0 - min(cv, 1.5) / 1.5)
    return _clamp(score)


def reply_speed_score(messages: list[dict[str, Any]]) -> float:
    """Very fast replies tend to be bot-like."""
    delays: list[float] = []

    for index, msg in enumerate(messages):
        if not msg.get("is_reply"):
            continue

        explicit_delay = msg.get("reply_delay_seconds")
        if isinstance(explicit_delay, (int, float)) and explicit_delay >= 0:
            delays.append(float(explicit_delay))
            continue

        # parent timestampがない場合は直前メッセージとの近接を代替利用
        if index > 0:
            current_ts = msg.get("created_at")
            prev_ts = messages[index - 1].get("created_at")
            if isinstance(current_ts, (int, float)) and isinstance(prev_ts, (int, float)):
                delta = float(current_ts) - float(prev_ts)
                if delta >= 0:
                    delays.append(delta)

    if not delays:
        return 45.0

    avg_delay = mean(delays)
    # 5秒以下は高スコア、120秒以上で低スコア
    if avg_delay <= 5:
        return 95.0
    if avg_delay >= 120:
        return 15.0

    normalized = (avg_delay - 5) / 115
    return _clamp(95.0 - normalized * 80.0)


def activity_hours_score(messages: list[dict[str, Any]]) -> float:
    """24h uniformly distributed activity implies automation."""
    timestamps = _extract_timestamps(messages)
    if len(timestamps) < 10:
        return 50.0

    hours = [datetime.fromtimestamp(ts, tz=timezone.utc).hour for ts in timestamps]
    counts = Counter(hours)

    total = len(hours)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * log2(p)

    # 24時間一様分布時の最大エントロピー
    max_entropy = log2(24)
    normalized = entropy / max_entropy if max_entropy else 0.0

    # エントロピーが高いほどBot寄り
    return _clamp(normalized * 100.0)


def analyze_timing(messages: list[dict[str, Any]]) -> dict[str, Any]:
    interval_score = interval_regularity_score(messages)
    reply_score = reply_speed_score(messages)
    hours_score = activity_hours_score(messages)

    score = _clamp(interval_score * 0.45 + reply_score * 0.3 + hours_score * 0.25)

    return {
        "score": score,
        "details": {
            "interval_regularity": round(interval_score, 2),
            "reply_speed": round(reply_score, 2),
            "activity_hours": round(hours_score, 2),
        },
    }
