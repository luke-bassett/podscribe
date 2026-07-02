"""Turn Whisper segments into a readable Markdown transcript."""

from __future__ import annotations

import sys
from pathlib import Path

from .models import Episode, Segment
from .transcribe import load_segments

DEFAULT_DIR = Path("transcripts")
PARAGRAPH_GAP = 2.0  # seconds of silence that starts a new paragraph
PARAGRAPH_MAX_CHARS = 1000


def to_paragraphs(
    segments: list[Segment],
    gap: float = PARAGRAPH_GAP,
    max_chars: int = PARAGRAPH_MAX_CHARS,
) -> list[tuple[float, str]]:
    """Group segments into (start_time, text) paragraphs.

    A new paragraph starts after a pause longer than `gap`, when the current
    paragraph exceeds `max_chars` at a sentence boundary, or unconditionally
    at 2x max_chars (so unpunctuated transcripts still get broken up).
    """
    paragraphs: list[tuple[float, str]] = []
    current: list[str] = []
    start = 0.0
    prev_end = 0.0

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        length = sum(len(t) for t in current)
        breaks = current and (
            seg.start - prev_end > gap
            or (length > max_chars and current[-1][-1:] in ".!?")
            or length > 2 * max_chars
        )
        if breaks:
            paragraphs.append((start, " ".join(current)))
            current = []
        if not current:
            start = seg.start
        current.append(text)
        prev_end = seg.end

    if current:
        paragraphs.append((start, " ".join(current)))
    return paragraphs


def render(meta: dict, segments: list[Segment]) -> str:
    body = "\n\n".join(text for _, text in to_paragraphs(segments))
    lines = [f"# {meta['title']}" if meta.get("title") else "# Transcript"]
    info = " · ".join(filter(None, [meta.get("feed_title"), meta.get("published")]))
    if info:
        lines.append(f"\n*{info}*")
    if meta.get("audio_url"):
        lines.append(f"\n[Audio]({meta['audio_url']})")
    return "\n".join(lines) + "\n\n" + body + "\n"


def format_episode(episode: Episode, dir: Path = DEFAULT_DIR) -> Episode:
    """Render episode.transcript_path into dir/<slug>.md. Skips if present."""
    if not episode.transcript_path:
        raise ValueError(f"episode {episode.title!r} has no transcript_path; run transcribe first")
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / (episode.slug() + ".md")
    if path.exists():
        episode.output_path = str(path)
        print(f"skip format (exists): {path}", file=sys.stderr)
        return episode

    meta, segments = load_segments(episode.transcript_path)
    meta.setdefault("title", episode.title)
    meta.setdefault("published", episode.published)
    meta.setdefault("feed_title", episode.feed_title)
    meta.setdefault("audio_url", episode.audio_url)
    path.write_text(render(meta, segments))
    episode.output_path = str(path)
    print(f"formatted: {path}", file=sys.stderr)
    return episode
