"""Download episode audio files."""

from __future__ import annotations

import mimetypes
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .models import Episode

DEFAULT_DIR = Path("audio")


def _extension(url: str, content_type: str) -> str:
    ext = Path(urlparse(url).path).suffix
    if ext:
        return ext
    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return guessed or ".mp3"


def download_episode(episode: Episode, dir: Path = DEFAULT_DIR) -> Episode:
    """Download audio to dir, set episode.audio_path. Skips if already present."""
    dir.mkdir(parents=True, exist_ok=True)
    existing = list(dir.glob(episode.slug() + ".*"))
    if existing:
        episode.audio_path = str(existing[0])
        print(f"skip download (exists): {existing[0]}", file=sys.stderr)
        return episode

    with httpx.stream("GET", episode.audio_url, follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        ext = _extension(str(response.url), response.headers.get("content-type", ""))
        path = dir / (episode.slug() + ext)
        tmp = path.with_suffix(path.suffix + ".part")
        try:
            with open(tmp, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            tmp.rename(path)
        finally:
            tmp.unlink(missing_ok=True)

    episode.audio_path = str(path)
    print(f"downloaded: {path}", file=sys.stderr)
    return episode
