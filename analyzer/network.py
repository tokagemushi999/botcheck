"""Network analysis module for BotCheck."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, List, Set

from .utils import _get


class NetworkAnalyzer:
    """ユーザー間のネットワーク関係性の分析クラス"""

    def __init__(self):
        self.min_messages = 5

    def analyze_network(
        self, messages: List[Any], target_user_id: Any = None
    ) -> float:
        """メインのネットワーク分析関数。0-100のスコアを返す。"""
        if not messages or len(messages) < self.min_messages:
            return 50.0

        if target_user_id is None:
            target_user_id = self._infer_target_user(messages)

        if target_user_id is None:
            return 50.0

        reciprocity_score = self._analyze_reciprocity(messages, target_user_id)
        mention_balance_score = self._analyze_mention_balance(messages, target_user_id)
        channel_relations_score = self._analyze_channel_relations(messages, target_user_id)
        isolation_score = self._analyze_isolation(messages, target_user_id)

        total = (
            reciprocity_score * 0.30
            + mention_balance_score * 0.25
            + channel_relations_score * 0.20
            + isolation_score * 0.25
        )
        return _clamp(total)

    # ------------------------------------------------------------------
    # 会話の相互性
    # ------------------------------------------------------------------
    def _analyze_reciprocity(self, messages: List[Any], target_user_id: Any) -> float:
        sent_to: Counter = Counter()  # target が誰にメンションしたか
        received_from: Counter = Counter()  # 誰が target にメンションしたか

        for msg in messages:
            author_id = _get(msg, "author_id")
            mentions = _get(msg, "mentions", [])
            if not mentions:
                continue

            mentioned_ids = self._extract_mention_ids(mentions)

            if str(author_id) == str(target_user_id):
                for mid in mentioned_ids:
                    sent_to[str(mid)] += 1
            elif str(target_user_id) in [str(m) for m in mentioned_ids]:
                received_from[str(author_id)] += 1

        if not sent_to and not received_from:
            return 60.0  # メンションなし = やや怪しい

        # 相互にやり取りしている相手の数
        sent_set = set(sent_to.keys())
        received_set = set(received_from.keys())
        mutual = sent_set & received_set

        total_contacts = len(sent_set | received_set)
        if total_contacts == 0:
            return 60.0

        mutual_ratio = len(mutual) / total_contacts

        if mutual_ratio > 0.5:
            return _clamp(10 + (1.0 - mutual_ratio) * 40)  # 高相互性 = 人間
        elif mutual_ratio > 0.2:
            return 45.0
        else:
            return _clamp(65 + (0.2 - mutual_ratio) * 175)  # 低相互性 = Bot疑い

    # ------------------------------------------------------------------
    # メンションバランス
    # ------------------------------------------------------------------
    def _analyze_mention_balance(self, messages: List[Any], target_user_id: Any) -> float:
        sent_mentions = 0
        received_mentions = 0

        for msg in messages:
            author_id = _get(msg, "author_id")
            mentions = _get(msg, "mentions", [])
            if not mentions:
                continue

            mentioned_ids = self._extract_mention_ids(mentions)

            if str(author_id) == str(target_user_id):
                sent_mentions += len(mentioned_ids)
            if str(target_user_id) in [str(m) for m in mentioned_ids]:
                received_mentions += 1

        total = sent_mentions + received_mentions
        if total == 0:
            return 55.0

        # 一方的にメンションするだけ = Bot的
        if received_mentions == 0 and sent_mentions > 0:
            return 80.0
        if sent_mentions == 0 and received_mentions > 0:
            return 65.0  # メンションされるだけ = やや怪しい

        balance = min(sent_mentions, received_mentions) / max(sent_mentions, received_mentions)
        # バランスが良い = 人間らしい
        if balance > 0.5:
            return _clamp(15 + (1.0 - balance) * 40)
        return _clamp(50 + (0.5 - balance) * 100)

    # ------------------------------------------------------------------
    # チャンネル横断的な関係性
    # ------------------------------------------------------------------
    def _analyze_channel_relations(self, messages: List[Any], target_user_id: Any) -> float:
        channels_with_interaction: Set[str] = set()
        channels_active: Set[str] = set()

        for msg in messages:
            author_id = _get(msg, "author_id")
            channel_id = _get(msg, "channel_id")
            if not channel_id:
                continue

            if str(author_id) == str(target_user_id):
                channels_active.add(str(channel_id))

                mentions = _get(msg, "mentions", [])
                if mentions:
                    channels_with_interaction.add(str(channel_id))

        if not channels_active:
            return 50.0

        # 1チャンネルのみ = 怪しい
        if len(channels_active) == 1:
            return 65.0

        # 複数チャンネルで会話がある = 人間らしい
        interaction_ratio = len(channels_with_interaction) / len(channels_active)
        if interaction_ratio > 0.5:
            return _clamp(15 + (1.0 - interaction_ratio) * 30)
        return _clamp(50 + (0.5 - interaction_ratio) * 60)

    # ------------------------------------------------------------------
    # 孤立度
    # ------------------------------------------------------------------
    def _analyze_isolation(self, messages: List[Any], target_user_id: Any) -> float:
        interacted_users: Set[str] = set()
        target_message_count = 0

        for msg in messages:
            author_id = _get(msg, "author_id")
            mentions = _get(msg, "mentions", [])

            if str(author_id) == str(target_user_id):
                target_message_count += 1
                if mentions:
                    for mid in self._extract_mention_ids(mentions):
                        interacted_users.add(str(mid))

            elif mentions:
                mentioned_ids = self._extract_mention_ids(mentions)
                if str(target_user_id) in [str(m) for m in mentioned_ids]:
                    interacted_users.add(str(author_id))

        if target_message_count == 0:
            return 50.0

        # 完全孤立 = 高スコア
        if not interacted_users:
            return 85.0

        # インタラクション相手数 vs メッセージ数
        interaction_density = len(interacted_users) / target_message_count
        if interaction_density > 0.3:
            return 15.0  # 豊富な交流 = 人間
        elif interaction_density > 0.1:
            return 35.0
        else:
            return _clamp(60 + (0.1 - interaction_density) * 250)

    # ------------------------------------------------------------------
    # ヘルパー
    # ------------------------------------------------------------------
    def _infer_target_user(self, messages: List[Any]) -> Any:
        """最も多くメッセージを送っているユーザーを推定"""
        author_counts: Counter = Counter()
        for msg in messages:
            author_id = _get(msg, "author_id")
            if author_id is not None:
                author_counts[str(author_id)] += 1
        if author_counts:
            return author_counts.most_common(1)[0][0]
        return None

    def _extract_mention_ids(self, mentions: Any) -> list:
        """メンションリストからIDを抽出"""
        ids = []
        if not mentions:
            return ids
        try:
            for m in mentions:
                if hasattr(m, "id"):
                    ids.append(m.id)
                else:
                    ids.append(m)
        except (TypeError, AttributeError):
            pass
        return ids


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))
