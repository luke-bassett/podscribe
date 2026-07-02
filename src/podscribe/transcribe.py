"""Transcribe audio with mlx-whisper, saving raw segments as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import Episode, Segment

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_DIR = Path("transcripts")


def _quiet_hub_unless_downloading(model: str) -> None:
    """HF prints 'Fetching N files' bars even on pure cache hits; silence
    those, but keep real download progress visible on first use."""
    from huggingface_hub import constants
    from huggingface_hub.utils import disable_progress_bars

    cache = Path(constants.HF_HUB_CACHE) / ("models--" + model.replace("/", "--"))
    if cache.exists():
        disable_progress_bars()
    else:
        print(f"downloading model {model} (one-time, >1.5 GB for large models)", file=sys.stderr)


def transcribe_file(
    audio_path: str | Path,
    model: str = DEFAULT_MODEL,
    verbose: bool | None = False,
) -> dict:
    """Run Whisper on one audio file, returning the raw result dict.

    verbose=False shows a progress bar (mlx-whisper's convention),
    verbose=True prints decoded text live, verbose=None is silent.
    """
    import mlx_whisper  # deferred: imports mlx/torch, slow

    _quiet_hub_unless_downloading(model)
    # condition_on_previous_text=False: with the default (True), one unpunctuated
    # window contaminates every window after it — long podcasts come out as
    # all-lowercase text with no sentence breaks.
    return mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model,
        verbose=verbose,
        condition_on_previous_text=False,
    )


def transcribe_episode(
    episode: Episode,
    dir: Path = DEFAULT_DIR,
    model: str = DEFAULT_MODEL,
    verbose: bool | None = False,
) -> Episode:
    """Transcribe episode.audio_path into dir/<slug>.json. Skips if present."""
    if not episode.audio_path:
        raise ValueError(f"episode {episode.title!r} has no audio_path; run download first")
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / (episode.slug() + ".json")
    if path.exists():
        episode.transcript_path = str(path)
        print(f"skip transcribe (exists): {path}", file=sys.stderr)
        return episode

    print(f"transcribing with {model}: {episode.audio_path}", file=sys.stderr)
    result = transcribe_file(episode.audio_path, model=model, verbose=verbose)
    payload = {
        "title": episode.title,
        "published": episode.published,
        "feed_title": episode.feed_title,
        "audio_url": episode.audio_url,
        "language": result.get("language", ""),
        "model": model,
        "segments": [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in result["segments"]
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    episode.transcript_path = str(path)
    print(f"transcribed: {path}", file=sys.stderr)
    return episode


def load_segments(transcript_path: str | Path) -> tuple[dict, list[Segment]]:
    """Read a saved transcript JSON, returning (metadata, segments)."""
    data = json.loads(Path(transcript_path).read_text())
    segments = [Segment(s["start"], s["end"], s["text"]) for s in data.pop("segments")]
    return data, segments
