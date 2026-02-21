# test_network.py - ネットワーク分析のユニットテスト
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.network import NetworkAnalyzer


def _make_msg(author_id, mentions=None, channel_id="ch1"):
    msg = Mock()
    msg.author_id = author_id
    msg.channel_id = channel_id
    msg.mentions = mentions or []
    msg.created_at = datetime.now()
    msg.content = "テスト"
    return msg


class TestNetworkAnalyzer:

    def test_init(self):
        """NetworkAnalyzer初期化テスト"""
        analyzer = NetworkAnalyzer()
        assert analyzer is not None

    def test_empty_messages(self):
        """空のメッセージリストは中立スコア"""
        analyzer = NetworkAnalyzer()
        score = analyzer.analyze_network([])
        assert score == 50.0

    def test_few_messages(self):
        """少ないメッセージは中立スコア"""
        analyzer = NetworkAnalyzer()
        msgs = [_make_msg("user1") for _ in range(3)]
        score = analyzer.analyze_network(msgs)
        assert score == 50.0

    def test_isolated_user_high_score(self):
        """孤立ユーザー（誰ともメンションなし）は高スコア"""
        analyzer = NetworkAnalyzer()
        msgs = [_make_msg("user1") for _ in range(10)]
        score = analyzer.analyze_network(msgs, target_user_id="user1")
        assert score >= 55, f"Expected high score for isolated user, got {score}"

    def test_mutual_conversation_low_score(self):
        """相互に会話しているユーザーは低スコア"""
        analyzer = NetworkAnalyzer()
        user2 = Mock()
        user2.id = "user2"
        user1 = Mock()
        user1.id = "user1"

        msgs = []
        for i in range(6):
            if i % 2 == 0:
                msgs.append(_make_msg("user1", mentions=[user2], channel_id="ch1"))
            else:
                msgs.append(_make_msg("user2", mentions=[user1], channel_id="ch1"))

        score = analyzer.analyze_network(msgs, target_user_id="user1")
        assert score <= 50, f"Expected low score for mutual conversation, got {score}"

    def test_one_way_mention_high_score(self):
        """一方的なメンションは高スコア"""
        analyzer = NetworkAnalyzer()
        user2 = Mock()
        user2.id = "user2"
        user3 = Mock()
        user3.id = "user3"

        msgs = [
            _make_msg("user1", mentions=[user2]),
            _make_msg("user1", mentions=[user3]),
            _make_msg("user1", mentions=[user2]),
            _make_msg("user1", mentions=[user3]),
            _make_msg("user1", mentions=[user2]),
            _make_msg("user1"),
        ]
        score = analyzer.analyze_network(msgs, target_user_id="user1")
        assert score >= 50, f"Expected high score for one-way mentions, got {score}"

    def test_multi_channel_interaction(self):
        """複数チャンネルでの交流は低スコア"""
        analyzer = NetworkAnalyzer()
        user2 = Mock()
        user2.id = "user2"

        msgs = [
            _make_msg("user1", mentions=[user2], channel_id="ch1"),
            _make_msg("user2", mentions=[Mock(id="user1")], channel_id="ch1"),
            _make_msg("user1", mentions=[user2], channel_id="ch2"),
            _make_msg("user2", mentions=[Mock(id="user1")], channel_id="ch2"),
            _make_msg("user1", mentions=[user2], channel_id="ch3"),
            _make_msg("user2", mentions=[Mock(id="user1")], channel_id="ch3"),
        ]
        score_multi = analyzer._analyze_channel_relations(msgs, "user1")
        
        msgs_single = [_make_msg("user1", channel_id="ch1") for _ in range(6)]
        score_single = analyzer._analyze_channel_relations(msgs_single, "user1")

        assert score_multi < score_single

    def test_score_range(self):
        """スコアは0-100の範囲"""
        analyzer = NetworkAnalyzer()
        msgs = [_make_msg("user1") for _ in range(10)]
        score = analyzer.analyze_network(msgs, target_user_id="user1")
        assert 0.0 <= score <= 100.0

    def test_infer_target_user(self):
        """最も多くメッセージを送っているユーザーを推定"""
        analyzer = NetworkAnalyzer()
        msgs = [_make_msg("user1") for _ in range(5)] + [_make_msg("user2") for _ in range(3)]
        target = analyzer._infer_target_user(msgs)
        assert target == "user1"
