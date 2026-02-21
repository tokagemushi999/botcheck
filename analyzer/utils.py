"""Common utilities for analyzers."""

from typing import Any


def _get(obj: Any, attr: str, default: Any = None) -> Any:
    """Extract attribute from Mock object or dict."""
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


def extract_content(msg: Any) -> str:
    """Extract content string from message object or dict."""
    if hasattr(msg, 'content'):
        return str(msg.content).strip()
    elif isinstance(msg, dict):
        return str(msg.get('content', '')).strip()
    else:
        return str(msg).strip()


def extract_contents(messages: list[Any], min_length: int = 0) -> list[str]:
    """Extract content strings from multiple messages."""
    contents = []
    for msg in messages:
        content = extract_content(msg)
        if content and len(content) > min_length:
            contents.append(content)
    return contents