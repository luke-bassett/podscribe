"""Summarize transcripts by shelling out to the `claude` CLI.

Uses `claude -p` (headless mode), so usage draws on the Claude subscription
the CLI is logged into — no API key or metered billing.

Why `claude -p` and not the Anthropic API
------------------------------------------
This is a local, personal, run-on-your-Mac tool. Shelling out means zero
setup for anyone who already has Claude Code logged in, and summaries cost
nothing beyond the existing subscription. That's the whole value prop, so
the trade-offs (no pinned model/temperature, unstructured text out, needs
an interactive login on the box) don't bite here.

When this stops being the right call — any of:
  - it needs to run headless/server-side or in CI, where there's no
    logged-in Claude Code (only an API key);
  - you need a pinned model, temperature, or structured/reproducible output;
  - volume grows enough that the subscription's rolling usage windows become
    the bottleneck, or metered API billing is simply cheaper to reason about;
  - you want to ship it to people who don't have Claude Code installed.

How to switch when that day comes:
  `summarize_text()` below is the *only* seam that talks to Claude — the
  pipeline, filenames, idempotency, and `_prompt()` all stay put. Add the
  `anthropic` dependency + an `ANTHROPIC_API_KEY`, and reimplement the body
  of `summarize_text()` to call the Messages API with a current model id,
  passing `_prompt(meta, words)` and the transcript text. Nothing else moves.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .models import Episode
from .transcribe import load_segments

DEFAULT_DIR = Path("summaries")
DEFAULT_WORDS = 3000
TIMEOUT_SECONDS = 600


def _prompt(meta: dict, words: int) -> str:
    title = meta.get("title") or "a podcast episode"
    show = f" from the show {meta['feed_title']!r}" if meta.get("feed_title") else ""
    return (
        f"The text on stdin is a raw speech-to-text transcript of the podcast episode "
        f"{title!r}{show}. It may contain transcription errors; infer the intended "
        f"words from context.\n\n"
        f"Write a summary of approximately {words} words covering the main topics, "
        f"arguments, and any concrete takeaways. Write an easily digestible summary "
        f"(markdown; use headings and bullet lists where they help organize the "
        f"information). Respond with only the summary text."
    )


def summarize_text(text: str, meta: dict, words: int = DEFAULT_WORDS) -> str:
    if not shutil.which("claude"):
        raise OSError("`claude` CLI not found on PATH; install Claude Code or add it to PATH")
    try:
        result = subprocess.run(
            ["claude", "-p", _prompt(meta, words)],
            input=text,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise OSError(f"claude -p timed out after {TIMEOUT_SECONDS}s") from e
    if result.returncode != 0:
        raise OSError(f"claude -p failed: {result.stderr.strip() or result.stdout.strip()}")
    summary = result.stdout.strip()
    if not summary:
        raise OSError("claude -p returned empty output")
    return summary


def summarize_episode(
    episode: Episode,
    dir: Path = DEFAULT_DIR,
    words: int = DEFAULT_WORDS,
) -> Episode:
    """Summarize episode.transcript_path into dir/<slug>.summary.<N>w.md.

    The word target is part of the filename, so summaries at different
    lengths coexist and skip-if-exists applies per length.
    """
    if not episode.transcript_path:
        raise ValueError(f"episode {episode.title!r} has no transcript_path; run transcribe first")
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / f"{episode.slug()}.summary.{words}w.md"
    if path.exists():
        episode.summary_path = str(path)
        print(f"skip summarize (exists): {path}", file=sys.stderr)
        return episode

    meta, segments = load_segments(episode.transcript_path)
    meta.setdefault("title", episode.title)
    meta.setdefault("feed_title", episode.feed_title)
    text = "\n".join(s.text.strip() for s in segments if s.text.strip())

    print(f"summarizing (~{words} words via claude -p): {episode.transcript_path}", file=sys.stderr)
    summary = summarize_text(text, meta, words=words)

    header = f"# {meta['title']} — summary\n" if meta.get("title") else "# Summary\n"
    path.write_text(f"{header}\n{summary}\n")
    episode.summary_path = str(path)
    print(f"summarized: {path}", file=sys.stderr)
    return episode
