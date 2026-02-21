"""Writing style analysis module for BotCheck."""

from __future__ import annotations

import re
from statistics import mean, pstdev
from typing import Any

TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u4e00-\u9fff]+", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"[。！？.!?]+")
TEMPLATE_PATTERNS = [
    "ご質問ありがとうございます",
    "お問い合わせありがとうございます",
    "承知しました",
    "ご不明点があれば",
    "Let me know if you have any questions",
    "Thank you for your message",
]
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]",
    re.UNICODE,
)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _extract_contents(messages: list[dict[str, Any]]) -> list[str]:
    return [str(msg.get("content", "")).strip() for msg in messages if str(msg.get("content", "")).strip()]


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def vocabulary_diversity_score(contents: list[str]) -> float:
    tokens: list[str] = []
    for content in contents:
        tokens.extend(_tokenize(content))

    if len(tokens) < 20:
        return 50.0

    unique_ratio = len(set(tokens)) / len(tokens)
    # TTRが低いほどBot寄り
    normalized = min(unique_ratio / 0.6, 1.0)
    return _clamp((1.0 - normalized) * 100.0)


def sentence_variance_score(contents: list[str]) -> float:
    lengths: list[int] = []
    for content in contents:
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(content) if s.strip()]
        for sentence in sentences:
            lengths.append(len(_tokenize(sentence)))

    if len(lengths) < 8:
        return 50.0

    avg = mean(lengths)
    if avg <= 0:
        return 50.0

    std = pstdev(lengths)
    cv = std / avg
    # 文章長の変動が小さいほどテンプレ的
    return _clamp(100.0 * (1.0 - min(cv, 1.2) / 1.2))


def template_phrase_score(contents: list[str]) -> float:
    if not contents:
        return 50.0

    hit_count = 0
    for content in contents:
        for pattern in TEMPLATE_PATTERNS:
            if pattern in content:
                hit_count += 1
                break

    ratio = hit_count / len(contents)
    return _clamp(ratio * 100.0)


def emoji_pattern_score(contents: list[str]) -> float:
    if len(contents) < 5:
        return 45.0

    emoji_counts = [len(EMOJI_RE.findall(content)) for content in contents]
    non_zero = [count for count in emoji_counts if count > 0]

    if not non_zero:
        return 55.0

    avg = mean(non_zero)
    std = pstdev(non_zero) if len(non_zero) > 1 else 0.0
    # 絵文字数が毎回ほぼ同じならBot寄り
    score = 100.0 * (1.0 - min(std / (avg + 1e-6), 1.0))
    return _clamp(score)


def analyze_style(messages: list[dict[str, Any]]) -> dict[str, Any]:
    contents = _extract_contents(messages)

    ttr_score = vocabulary_diversity_score(contents)
    sentence_score = sentence_variance_score(contents)
    template_score = template_phrase_score(contents)
    emoji_score = emoji_pattern_score(contents)

    score = _clamp(ttr_score * 0.4 + sentence_score * 0.3 + template_score * 0.2 + emoji_score * 0.1)

    return {
        "score": score,
        "details": {
            "vocabulary_diversity": round(ttr_score, 2),
            "sentence_length_variance": round(sentence_score, 2),
            "template_phrases": round(template_score, 2),
            "emoji_pattern": round(emoji_score, 2),
        },
    }
