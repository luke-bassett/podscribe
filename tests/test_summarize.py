import os
import stat
from pathlib import Path

from podscribe.models import Episode
from podscribe.summarize import summarize_episode

FIXTURES = Path(__file__).parent / "fixtures"

FAKE_CLAUDE = """#!/bin/sh
# echo the word target from the prompt plus a fixed summary
cat > /dev/null  # drain stdin
echo "A fine summary. args: $*"
"""


def _install_fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_summarize_writes_file_and_sets_path(tmp_path, monkeypatch):
    _install_fake_claude(tmp_path, monkeypatch)
    episode = Episode(
        title="Episode Two: The Return",
        audio_url="u",
        published="2026-06-28",
        transcript_path=str(FIXTURES / "transcript.json"),
    )
    episode = summarize_episode(episode, dir=tmp_path, words=42)
    out = Path(episode.summary_path)
    content = out.read_text()
    assert out.name == "2026-06-28-episode-two-the-return.summary.42w.sonnet.md"
    assert content.startswith("A fine summary.")  # claude output verbatim, no added header
    assert "approximately 42 words" in content  # prompt reached the CLI


def test_summarize_skips_existing(tmp_path, monkeypatch, capsys):
    _install_fake_claude(tmp_path, monkeypatch)
    existing = tmp_path / "2026-06-28-episode-two-the-return.summary.3000w.sonnet.md"
    existing.write_text("already here")
    episode = Episode(
        title="Episode Two: The Return",
        audio_url="u",
        published="2026-06-28",
        transcript_path=str(FIXTURES / "transcript.json"),
    )
    episode = summarize_episode(episode, dir=tmp_path)
    assert episode.summary_path == str(existing)
    assert existing.read_text() == "already here"
