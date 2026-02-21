"""BotCheck Analysis Engine — クラスベース統合エンジン"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from analyzer.timing import TimingAnalyzer
from analyzer.style import StyleAnalyzer
from analyzer.behavior import BehaviorAnalyzer
from analyzer.ai_detect import AIDetector
from analyzer.profile import ProfileAnalyzer
from analyzer.network import NetworkAnalyzer


class AnalysisEngine:
    """6軸分析を統合するメインエンジン"""

    def __init__(self, weights: dict[str, float] | None = None):
        self.timing_analyzer = TimingAnalyzer()
        self.style_analyzer = StyleAnalyzer()
        self.behavior_analyzer = BehaviorAnalyzer()
        self.ai_detector = AIDetector()
        self.profile_analyzer = ProfileAnalyzer()
        self.network_analyzer = NetworkAnalyzer()
        self.weights = weights or {
            "timing": 0.20,
            "style": 0.20,
            "behavior": 0.20,
            "ai": 0.15,
            "profile": 0.15,
            "network": 0.10,
        }

    def analyze_user(
        self,
        messages: list[Any],
        user_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """ユーザーのメッセージを分析してスコアを返す"""
        count = len(messages)

        if count == 0:
            return self._empty_result()

        # 各軸の分析
        timing_score = self.timing_analyzer.analyze_timing(messages)
        style_score = self.style_analyzer.analyze_style(messages)
        behavior_score = self.behavior_analyzer.analyze_behavior(messages)
        ai_score = self.ai_detector.detect_ai_text(messages)
        profile_score = self.profile_analyzer.analyze_profile(user_info or {})
        network_score = self.network_analyzer.analyze_network(messages)

        # 重み付き合計
        w = self.weights
        total = sum(w.values())
        if total <= 0:
            total = 1.0

        total_score = (
            timing_score * w.get("timing", 0.20)
            + style_score * w.get("style", 0.20)
            + behavior_score * w.get("behavior", 0.20)
            + ai_score * w.get("ai", 0.15)
            + profile_score * w.get("profile", 0.15)
            + network_score * w.get("network", 0.10)
        ) / total

        total_score = _clamp(total_score)

        # 信頼度: メッセージ数に基づく信頼度計算
        # 20件で80%、50件で90%、100件以上で100%
        if count >= 100:
            confidence = 100.0
        elif count >= 50:
            confidence = 90.0 + (count - 50) * 0.2  # 90% to 100%
        elif count >= 20:
            confidence = 80.0 + (count - 20) * (10.0 / 30)  # 80% to 90%
        else:
            confidence = count * 4.0  # Linear scale up to 80%
        
        confidence = _clamp(confidence, 0.0, 100.0)

        # メタデータ
        user_id = self._extract_user_id(messages)
        timestamps = self._extract_timestamps(messages)
        period_hours = 0.0
        if len(timestamps) >= 2:
            period_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0

        return {
            "total_score": round(total_score, 2),
            "timing_score": round(timing_score, 2),
            "style_score": round(style_score, 2),
            "behavior_score": round(behavior_score, 2),
            "ai_score": round(ai_score, 2),
            "profile_score": round(profile_score, 2),
            "network_score": round(network_score, 2),
            "confidence": round(confidence, 2),
            "message_count": count,
            "user_id": user_id,
            "analysis_date": datetime.now(),
            "analysis_period_hours": round(period_hours, 2),
        }

    def _empty_result(self) -> dict[str, Any]:
        return {
            "total_score": 50,
            "timing_score": 50,
            "style_score": 50,
            "behavior_score": 50,
            "ai_score": 50,
            "profile_score": 50,
            "network_score": 50,
            "confidence": 0,
            "message_count": 0,
            "user_id": None,
            "analysis_date": datetime.now(),
            "analysis_period_hours": 0,
        }

    def _extract_user_id(self, messages: list[Any]) -> Any:
        for msg in messages:
            if hasattr(msg, "author_id"):
                return msg.author_id
            if isinstance(msg, dict) and "user_id" in msg:
                return msg["user_id"]
        return None

    def _extract_timestamps(self, messages: list[Any]) -> list[datetime]:
        timestamps = []
        for msg in messages:
            if hasattr(msg, "created_at") and msg.created_at is not None:
                ts = msg.created_at
                if isinstance(ts, datetime):
                    timestamps.append(ts)
            elif isinstance(msg, dict) and "created_at" in msg:
                ts = msg["created_at"]
                if isinstance(ts, datetime):
                    timestamps.append(ts)
        return timestamps


# ---- 後方互換用 ----

class EngineResult:
    """後方互換用のデータクラス"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def analyze_messages(messages: list[dict[str, Any]], weights: dict[str, float] | None = None) -> EngineResult:
    """後方互換: dict形式メッセージを分析"""
    engine = AnalysisEngine(weights=weights)
    result = engine.analyze_user(messages)
    return EngineResult(
        total_score=result["total_score"],
        timing_score=result["timing_score"],
        style_score=result["style_score"],
        behavior_score=result["behavior_score"],
        ai_score=result["ai_score"],
        profile_score=result["profile_score"],
        network_score=result["network_score"],
        confidence=result["confidence"],
        message_count=result["message_count"],
        details={},
    )


def compute_score(features: dict[str, Any]) -> float:
    """後方互換ヘルパー"""
    if not isinstance(features, dict):
        return 0.0
    numeric = [float(v) for v in features.values() if isinstance(v, (int, float))]
    if not numeric:
        return 0.0
    return round(_clamp(sum(numeric)), 2)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))
