"""podscribe: composable audio transcription pipeline.

Usable as a library too:

    from podscribe import fetch_episodes, download_episode, transcribe_episode, format_episode
"""

from .download import download_episode
from .feed import fetch_episodes
from .format import format_episode, render, to_paragraphs
from .models import Episode, Segment
from .summarize import summarize_episode, summarize_text
from .transcribe import load_segments, transcribe_episode, transcribe_file

__all__ = [
    "Episode",
    "Segment",
    "download_episode",
    "fetch_episodes",
    "format_episode",
    "load_segments",
    "render",
    "summarize_episode",
    "summarize_text",
    "to_paragraphs",
    "transcribe_episode",
    "transcribe_file",
]
