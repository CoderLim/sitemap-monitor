"""Parse interval strings and shared config helpers."""

from __future__ import annotations

_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def interval_to_seconds(interval: str) -> int:
    """Convert values like ``6h`` / ``30m`` to seconds."""
    text = interval.strip()
    if len(text) < 2:
        raise ValueError(f"invalid interval: {interval}")
    unit = text[-1].lower()
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"invalid interval unit: {interval}")
    amount = int(text[:-1])
    if amount <= 0:
        raise ValueError(f"invalid interval amount: {interval}")
    return amount * _UNIT_SECONDS[unit]
