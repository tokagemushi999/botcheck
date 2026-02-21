"""Main scoring engine for BotCheck."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analyzer.ai_detect import analyze_ai
from analyzer.behavior import analyze_behavior
from analyzer.style import analyze_style
from analyzer.timing import analyze_timing


DEFAULT_WEIGHTS = {
    "timing": 0.25,
    "style": 0.25,
    "behavior": 0.25,
    "ai": 0.25,
}


@dataclass
class EngineResult:
    total_score: float
    timing_score: float
    style_score: float
    behavior_score: float
    ai_score: float
    confidence: float
    message_count: int
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "timing_score": self.timing_score,
            "style_score": self.style_score,
            "behavior_score": self.behavior_score,
            "ai_score": self.ai_score,
            "confidence": self.confidence,
            "message_count": self.message_count,
            "details": self.details,
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in merged and isinstance(value, (int, float)) and value >= 0:
                merged[key] = float(value)

    total = sum(merged.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)

    return {key: value / total for key, value in merged.items()}


def _validate_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid_messages: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if "content" not in msg:
            msg = {**msg, "content": ""}
        valid_messages.append(msg)

    return valid_messages


def analyze_messages(messages: list[dict[str, Any]], weights: dict[str, float] | None = None) -> EngineResult:
    """Analyze messages and return bot-likelihood score (0-100)."""
    valid_messages = _validate_messages(messages)
    count = len(valid_messages)

    if count == 0:
        empty = {
            "timing": {"score": 0.0, "details": {}},
            "style": {"score": 0.0, "details": {}},
            "behavior": {"score": 0.0, "details": {}},
            "ai": {"score": 0.0, "details": {}},
        }
        return EngineResult(
            total_score=0.0,
            timing_score=0.0,
            style_score=0.0,
            behavior_score=0.0,
            ai_score=0.0,
            confidence=0.0,
            message_count=0,
            details=empty,
        )

    timing = analyze_timing(valid_messages)
    style = analyze_style(valid_messages)
    behavior = analyze_behavior(valid_messages)
    ai = analyze_ai(valid_messages)

    normalized = _normalize_weights(weights)
    total = _clamp(
        timing["score"] * normalized["timing"]
        + style["score"] * normalized["style"]
        + behavior["score"] * normalized["behavior"]
        + ai["score"] * normalized["ai"]
    )

    # 100件で信頼度100に漸近
    confidence = _clamp((count / 100.0) * 100.0)

    details = {
        "timing": timing,
        "style": style,
        "behavior": behavior,
        "ai": ai,
        "weights": normalized,
    }

    return EngineResult(
        total_score=round(total, 2),
        timing_score=round(timing["score"], 2),
        style_score=round(style["score"], 2),
        behavior_score=round(behavior["score"], 2),
        ai_score=round(ai["score"], 2),
        confidence=round(confidence, 2),
        message_count=count,
        details=details,
    )


def compute_score(features: dict[str, Any]) -> float:
    """Backward-compatible helper."""
    if not isinstance(features, dict):
        return 0.0
    numeric_values = [float(v) for v in features.values() if isinstance(v, (int, float))]
    if not numeric_values:
        return 0.0
    return round(_clamp(sum(numeric_values)), 2)
