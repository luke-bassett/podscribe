from pathlib import Path

from podscribe.format import render, to_paragraphs
from podscribe.models import Segment
from podscribe.transcribe import load_segments

TRANSCRIPT = Path(__file__).parent / "fixtures" / "transcript.json"


def test_paragraph_break_on_gap():
    meta, segments = load_segments(TRANSCRIPT)
    paragraphs = to_paragraphs(segments)
    assert len(paragraphs) == 2
    assert paragraphs[0] == (0.0, "Welcome back to the show. Today we talk about pipelines.")
    assert paragraphs[1][0] == 12.0


def test_paragraph_break_on_length():
    long_sentence = "word " * 100 + "end."
    segments = [Segment(i * 10.0, i * 10.0 + 9.9, long_sentence) for i in range(3)]
    paragraphs = to_paragraphs(segments, max_chars=600)
    assert len(paragraphs) > 1


def test_paragraph_hard_cap_without_punctuation():
    # unpunctuated speech with no gaps must still break up
    segments = [Segment(i * 5.0, i * 5.0 + 5.0, "so yeah we kept talking " * 10) for i in range(20)]
    paragraphs = to_paragraphs(segments, max_chars=1000)
    assert len(paragraphs) > 1
    assert all(len(text) <= 2 * 1000 + 300 for _, text in paragraphs)


def test_render_markdown():
    meta, segments = load_segments(TRANSCRIPT)
    out = render(meta, segments)
    assert out.startswith("# Episode Two: The Return\n")
    assert "*Test Podcast · 2026-06-28*" in out
    assert "[Audio](https://example.com/audio/ep2.mp3)" in out
    assert "Welcome back to the show." in out
