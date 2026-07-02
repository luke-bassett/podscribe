"""Core data types."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Episode:
    """One episode moving through the pipeline."""

    title: str
    audio_url: str = ""
    guid: str = ""
    published: str = ""  # ISO date, e.g. "2026-06-28"
    feed_title: str = ""
    audio_path: str = ""  # set by download
    transcript_path: str = ""  # set by transcribe
    output_path: str = ""  # set by format
    summary_path: str = ""  # set by summarize

    def slug(self) -> str:
        """Filesystem-safe base name, e.g. '2026-06-28-episode-title'."""
        text = self.title or self.guid or self.audio_url.rsplit("/", 1)[-1]
        s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "episode"
        return f"{self.published}-{s}" if self.published else s


@dataclass
class Segment:
    start: float
    end: float
    text: str
