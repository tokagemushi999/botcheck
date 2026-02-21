# test_profile.py - プロフィール分析のユニットテスト
import pytest
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.profile import ProfileAnalyzer


class TestProfileAnalyzer:

    def test_init(self):
        """ProfileAnalyzer初期化テスト"""
        analyzer = ProfileAnalyzer()
        assert analyzer is not None

    def test_empty_user_info(self):
        """空のユーザー情報は中立スコア"""
        analyzer = ProfileAnalyzer()
        score = analyzer.analyze_profile({})
        assert score == 50.0

    def test_none_user_info(self):
        """Noneは中立スコア"""
        analyzer = ProfileAnalyzer()
        score = analyzer.analyze_profile(None)
        assert score == 50.0

    def test_new_account_high_score(self):
        """新しいアカウントは高スコア（Bot疑い）"""
        analyzer = ProfileAnalyzer()
        user_info = {
            "created_at": datetime.now() - timedelta(hours=12),
            "avatar": None,
            "username": "xkq7r9m2p",
        }
        score = analyzer.analyze_profile(user_info)
        assert score >= 60, f"Expected high score for new account, got {score}"

    def test_old_account_with_avatar_low_score(self):
        """古いアカウント + アバターありは低スコア（人間らしい）"""
        analyzer = ProfileAnalyzer()
        user_info = {
            "created_at": datetime.now() - timedelta(days=500),
            "avatar": "abc123.png",
            "username": "sakura_chan",
            "status": "online",
            "activities": [{"name": "Visual Studio Code"}],
            "custom_status": "作業中",
        }
        score = analyzer.analyze_profile(user_info)
        assert score <= 30, f"Expected low score for established account, got {score}"

    def test_no_avatar_increases_score(self):
        """デフォルトアバターはスコア上昇"""
        analyzer = ProfileAnalyzer()
        score_with = analyzer._analyze_avatar({"avatar": "custom.png"})
        score_without = analyzer._analyze_avatar({"avatar": None})
        assert score_without > score_with

    def test_random_username_high_score(self):
        """ランダム文字列のユーザー名は高スコア"""
        analyzer = ProfileAnalyzer()
        score_random = analyzer._analyze_username_pattern({"username": "xk7qr9m2pw5"})
        score_normal = analyzer._analyze_username_pattern({"username": "takeshi"})
        assert score_random > score_normal

    def test_account_age_scoring(self):
        """アカウント年齢による段階的スコア"""
        analyzer = ProfileAnalyzer()
        score_1day = analyzer._analyze_account_age({"created_at": datetime.now() - timedelta(hours=12)})
        score_1year = analyzer._analyze_account_age({"created_at": datetime.now() - timedelta(days=400)})
        assert score_1day > score_1year

    def test_custom_status_lowers_score(self):
        """カスタムステータスありは低スコア"""
        analyzer = ProfileAnalyzer()
        score_with = analyzer._analyze_custom_status({"custom_status": "作業中"})
        score_without = analyzer._analyze_custom_status({})
        assert score_with < score_without

    def test_activities_lower_score(self):
        """アクティビティありは低スコア"""
        analyzer = ProfileAnalyzer()
        score_with = analyzer._analyze_status({"activities": [{"name": "Minecraft"}]})
        score_without = analyzer._analyze_status({})
        assert score_with < score_without

    def test_score_range(self):
        """スコアは0-100の範囲"""
        analyzer = ProfileAnalyzer()
        for user_info in [
            {"created_at": datetime.now(), "avatar": None, "username": "a1b2c3d4e5"},
            {"created_at": datetime.now() - timedelta(days=1000), "avatar": "x.png", "username": "taro"},
            {},
        ]:
            score = analyzer.analyze_profile(user_info)
            assert 0.0 <= score <= 100.0, f"Score {score} out of range"
