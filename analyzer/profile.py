"""Profile analysis module for BotCheck."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .utils import _get


class ProfileAnalyzer:
    """アカウントプロフィールの分析クラス"""

    def __init__(self):
        self.min_account_age_days = 7  # 7日未満は怪しい
        self.random_name_threshold = 0.6

    def analyze_profile(self, user_info: dict[str, Any]) -> float:
        """メインのプロフィール分析関数。0-100のスコアを返す。"""
        if not user_info:
            return 50.0

        age_score = self._analyze_account_age(user_info)
        avatar_score = self._analyze_avatar(user_info)
        name_score = self._analyze_username_pattern(user_info)
        status_score = self._analyze_status(user_info)
        custom_status_score = self._analyze_custom_status(user_info)

        total = (
            age_score * 0.25
            + avatar_score * 0.20
            + name_score * 0.25
            + status_score * 0.15
            + custom_status_score * 0.15
        )
        return _clamp(total)

    # ------------------------------------------------------------------
    # アカウント年齢
    # ------------------------------------------------------------------
    def _analyze_account_age(self, user_info: dict[str, Any]) -> float:
        created_at = user_info.get("created_at")
        if created_at is None:
            return 50.0

        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                return 50.0

        if isinstance(created_at, datetime):
            now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
            age_days = (now - created_at).days
        elif isinstance(created_at, (int, float)):
            age_days = (datetime.now().timestamp() - created_at) / 86400
        else:
            return 50.0

        if age_days < 1:
            return 95.0
        elif age_days < 7:
            return 80.0
        elif age_days < 30:
            return 60.0
        elif age_days < 90:
            return 40.0
        elif age_days < 365:
            return 25.0
        else:
            return 10.0

    # ------------------------------------------------------------------
    # アバター有無
    # ------------------------------------------------------------------
    def _analyze_avatar(self, user_info: dict[str, Any]) -> float:
        avatar = user_info.get("avatar")
        if avatar is None or avatar == "" or avatar is False:
            return 75.0  # デフォルトアバター = 怪しい
        return 15.0  # カスタムアバターあり = 人間らしい

    # ------------------------------------------------------------------
    # ユーザー名パターン
    # ------------------------------------------------------------------
    def _analyze_username_pattern(self, user_info: dict[str, Any]) -> float:
        username = user_info.get("username", "")
        if not username:
            return 50.0

        scores = []

        # ランダム文字列検出
        randomness = self._calculate_randomness(username)
        if randomness > self.random_name_threshold:
            scores.append(70 + (randomness - self.random_name_threshold) * 75)
        else:
            scores.append(20.0)

        # 数字の割合
        digit_ratio = sum(1 for c in username if c.isdigit()) / len(username)
        if digit_ratio > 0.5:
            scores.append(75.0)
        elif digit_ratio > 0.3:
            scores.append(55.0)
        else:
            scores.append(20.0)

        # 末尾の連番パターン (user12345 等)
        if re.search(r'\d{4,}$', username):
            scores.append(70.0)
        else:
            scores.append(25.0)

        return _clamp(sum(scores) / len(scores))

    def _calculate_randomness(self, text: str) -> float:
        """文字列のランダムさを0-1で計算。高いほどランダム。"""
        if len(text) < 3:
            return 0.5

        # 子音と母音の交互パターンをチェック
        vowels = set("aeiouAEIOU")
        transitions = 0
        for i in range(1, len(text)):
            if text[i].isalpha() and text[i - 1].isalpha():
                is_vowel_curr = text[i] in vowels
                is_vowel_prev = text[i - 1] in vowels
                if is_vowel_curr != is_vowel_prev:
                    transitions += 1

        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars < 2:
            return 0.5

        transition_ratio = transitions / (alpha_chars - 1)

        # 連続する同一文字がない
        has_repeats = any(text[i] == text[i - 1] for i in range(1, len(text)))

        # ユニーク文字比率
        unique_ratio = len(set(text.lower())) / len(text)

        # 高いユニーク比率 + 適度なtransition = ランダムっぽい
        randomness = unique_ratio * 0.5 + (1.0 - abs(transition_ratio - 0.5)) * 0.3
        if not has_repeats and len(text) > 8:
            randomness += 0.2

        return min(randomness, 1.0)

    # ------------------------------------------------------------------
    # ステータス/アクティビティ
    # ------------------------------------------------------------------
    def _analyze_status(self, user_info: dict[str, Any]) -> float:
        status = user_info.get("status")
        activities = user_info.get("activities", [])

        if not status and not activities:
            return 65.0  # ステータスなし = やや怪しい

        if activities:
            return 15.0  # アクティビティあり = 人間らしい

        if status in ("online", "idle", "dnd"):
            return 35.0
        return 50.0

    # ------------------------------------------------------------------
    # カスタムステータス
    # ------------------------------------------------------------------
    def _analyze_custom_status(self, user_info: dict[str, Any]) -> float:
        custom_status = user_info.get("custom_status")
        if custom_status:
            return 10.0  # カスタムステータスあり = 人間らしい
        return 60.0  # なし = やや怪しい


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))
