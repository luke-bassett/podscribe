"""podscribe CLI: podcast audio -> readable transcript -> long summary.

    podscribe run <rss-url> --match kolie --words 3000
    podscribe summarize <episode.mp3 | transcript.json> --words 3000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import download as dl
from . import feed, format as fmt, summarize as summ, transcribe as tr
from .models import Episode


def _process(episode: Episode, args) -> Episode:
    """Audio (or transcript) -> transcript JSON + readable .md + summary."""
    if not episode.transcript_path:
        episode = tr.transcribe_episode(episode, model=args.model,
                                        verbose=True if args.verbose else False)
        episode = fmt.format_episode(episode)
    episode = summ.summarize_episode(episode, words=args.words, model=args.claude_model)
    print(episode.summary_path)
    return episode


def cmd_run(args) -> None:
    episodes = list(feed.fetch_episodes(args.url, limit=args.limit, order=args.order,
                                        match=args.match))
    print(f"run: {len(episodes)} episode(s)", file=sys.stderr)
    failures = 0
    for i, episode in enumerate(episodes):
        print(f"[{i + 1}/{len(episodes)}] {episode.title}", file=sys.stderr)
        try:
            episode = dl.download_episode(episode)
            _process(episode, args)
        except Exception as e:  # one bad episode shouldn't kill a backlog run
            failures += 1
            print(f"error ({episode.title!r}): {e}", file=sys.stderr)
    if failures:
        sys.exit(f"{failures} of {len(episodes)} episode(s) failed")


def cmd_summarize(args) -> None:
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"error: no such file: {path}")
    episode = Episode(title=path.stem)
    if path.suffix == ".json":
        episode.transcript_path = str(path)
    else:
        episode.audio_path = str(path)
    _process(episode, args)


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--words", type=int, default=summ.DEFAULT_WORDS,
                   help=f"approximate summary length in words (default: {summ.DEFAULT_WORDS})")
    p.add_argument("--model", default=tr.DEFAULT_MODEL,
                   help=f"Whisper model (default: {tr.DEFAULT_MODEL})")
    p.add_argument("--claude-model", default=summ.DEFAULT_CLAUDE_MODEL, metavar="MODEL",
                   help=f"Claude model for summaries (default: {summ.DEFAULT_CLAUDE_MODEL})")
    p.add_argument("--verbose", action="store_true",
                   help="print decoded text live instead of a progress bar")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="podscribe", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="RSS feed -> transcripts + summaries")
    p.add_argument("url", help="RSS feed URL or local XML file")
    p.add_argument("--limit", type=int, default=1, help="max episodes (default: 1)")
    p.add_argument("--order", choices=["newest", "oldest", "feed"], default="newest",
                   help="sort by publish date, or keep feed order (default: newest)")
    p.add_argument("--match", default=None, metavar="PATTERN",
                   help="only episodes whose title matches (case-insensitive regex/substring)")
    _add_common_args(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("summarize", help="audio file or transcript JSON -> summary")
    p.add_argument("file", help="an audio file, or a transcript .json produced by run")
    _add_common_args(p)
    p.set_defaults(func=cmd_summarize)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError) as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
