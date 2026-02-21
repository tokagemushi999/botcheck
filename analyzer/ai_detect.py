"""AI text detection heuristics for BotCheck."""

from __future__ import annotations

import re
from collections import Counter
from math import log2
from typing import Any

TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u4e00-\u9fff]+", re.UNICODE)
SENTENCE_RE = re.compile(r"[^。！？.!?]+")
CONNECTIVE_RE = re.compile(r"(また|さらに|そして|しかし|そのため|なお|一方で|Moreover|Additionally|Therefore)")
POLITE_END_RE = re.compile(r"(です|ます|でした|ません|でしょう|ください)$")


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _contents(messages: list[dict[str, Any]]) -> list[str]:
    return [str(msg.get("content", "")).strip() for msg in messages if str(msg.get("content", "")).strip()]


def pseudo_perplexity_score(contents: list[str]) -> float:
    """近似 perplexity: 語彙分布が過度に予測可能ならBot寄り。"""
    tokens: list[str] = []
    for text in contents:
        tokens.extend(token.lower() for token in TOKEN_RE.findall(text))

    if len(tokens) < 30:
        return 50.0

    counts = Counter(tokens)
    total = len(tokens)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * log2(p)

    # 語彙の最大エントロピーに対する不足分をスコア化
    max_entropy = log2(max(len(counts), 2))
    predictability = 1.0 - (entropy / max_entropy if max_entropy else 0.0)
    return _clamp(predictability * 100.0)


def japanese_pattern_score(contents: list[str]) -> float:
    sentences: list[str] = []
    for text in contents:
        sentences.extend([s.strip() for s in SENTENCE_RE.findall(text) if s.strip()])

    if len(sentences) < 5:
        return 45.0

    polite_hits = sum(1 for sentence in sentences if POLITE_END_RE.search(sentence))
    polite_ratio = polite_hits / len(sentences)

    connective_hits = sum(len(CONNECTIVE_RE.findall(text)) for text in contents)
    avg_connectives = connective_hits / max(1, len(sentences))

    # 丁寧語の一貫性 + 接続詞多用を総合
    polite_component = min(max((polite_ratio - 0.4) / 0.5, 0.0), 1.0) * 60.0
    connective_component = min(avg_connectives / 0.35, 1.0) * 40.0

    return _clamp(polite_component + connective_component)


def repetition_score(contents: list[str]) -> float:
    if len(contents) < 5:
        return 45.0

    joined = "\n".join(contents)
    tokens = [token.lower() for token in TOKEN_RE.findall(joined)]
    if len(tokens) < 20:
        return 45.0

    trigrams = [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    if not trigrams:
        return 45.0

    counts = Counter(trigrams)
    repeated = sum(1 for count in counts.values() if count >= 3)
    repetition_ratio = repeated / max(1, len(counts))
    return _clamp(min(repetition_ratio / 0.15, 1.0) * 100.0)


def analyze_ai(messages: list[dict[str, Any]]) -> dict[str, Any]:
    contents = _contents(messages)

    perplexity_like = pseudo_perplexity_score(contents)
    jp_pattern = japanese_pattern_score(contents)
    repetition = repetition_score(contents)

    score = _clamp(perplexity_like * 0.45 + jp_pattern * 0.35 + repetition * 0.2)

    return {
        "score": score,
        "details": {
            "perplexity_like": round(perplexity_like, 2),
            "japanese_patterns": round(jp_pattern, 2),
            "repetition": round(repetition, 2),
        },
    }
