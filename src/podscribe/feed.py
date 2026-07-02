"""Parse a podcast RSS feed into Episode records."""

from __future__ import annotations

import re
import time
from typing import Iterator

import feedparser

from .models import Episode

AUDIO_TYPES = ("audio/", "video/")  # some feeds serve m4a as video/mp4


def _audio_url(entry) -> str:
    for enc in entry.get("enclosures", []):
        url = enc.get("href") or enc.get("url", "")
        if url and enc.get("type", "audio/").startswith(AUDIO_TYPES):
            return url
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and link.get("href"):
            return link["href"]
    return ""


def _published(entry) -> tuple[str, float]:
    """(ISO date, epoch seconds for sorting); ("", 0.0) when the feed has no date."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return "", 0.0
    return time.strftime("%Y-%m-%d", parsed), time.mktime(parsed)


def fetch_episodes(
    source: str,
    limit: int | None = None,
    order: str = "newest",
    match: str | None = None,
) -> Iterator[Episode]:
    """Yield episodes from an RSS URL or local feed file.

    order: "newest" (default) or "oldest" sorts by publish date; "feed"
    keeps the order the publisher wrote. Entries without a date sort last.
    match: case-insensitive regex/substring filter on episode titles.
    limit applies after filtering and sorting.
    """
    pattern = re.compile(match, re.IGNORECASE) if match else None
    parsed = feedparser.parse(source)
    if parsed.get("bozo") and not parsed.entries:
        raise ValueError(f"could not parse feed {source!r}: {parsed.get('bozo_exception')}")
    feed_title = parsed.feed.get("title", "")

    dated = []
    for entry in parsed.entries:
        url = _audio_url(entry)
        if not url:
            continue
        if pattern and not pattern.search(entry.get("title", "")):
            continue
        date, epoch = _published(entry)
        episode = Episode(
            title=entry.get("title", ""),
            audio_url=url,
            guid=entry.get("id", ""),
            published=date,
            feed_title=feed_title,
        )
        dated.append((epoch, episode))
    if order == "newest":
        dated.sort(key=lambda pair: pair[0], reverse=True)
    elif order == "oldest":
        dated.sort(key=lambda pair: (pair[0] == 0.0, pair[0]))
    elif order != "feed":
        raise ValueError(f"unknown order {order!r}; expected newest, oldest, or feed")

    yield from (episode for _, episode in dated[:limit])
