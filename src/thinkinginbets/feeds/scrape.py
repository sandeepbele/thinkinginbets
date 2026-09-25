"""Respectful scraping primitives for free match data sources.

Scraping is a fallback when a public endpoint is unavailable. Keep it slow,
cache aggressively, and never treat scraped data as low-latency truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable


@dataclass(frozen=True)
class ScrapedStat:
    name: str
    home_value: float
    away_value: float


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return " ".join(self._chunks)


def visible_text_from_html(html: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html)
    return parser.text()


def find_stat_triplets(tokens: Iterable[str]) -> list[ScrapedStat]:
    """Parse simple stat triplets like `58 Possession 42`.

    This is intentionally conservative. Provider-specific scrapers should use
    structured embedded JSON whenever possible.
    """

    values = list(tokens)
    stats: list[ScrapedStat] = []
    for index in range(2, len(values)):
        home = _float_or_none(values[index - 2])
        label = values[index - 1]
        away = _float_or_none(values[index])
        if home is None or away is None or not label.isalpha():
            continue
        stats.append(ScrapedStat(name=label.lower(), home_value=home, away_value=away))
    return stats


def _float_or_none(value: object) -> float | None:
    try:
        return float(str(value).strip().replace("%", ""))
    except ValueError:
        return None
