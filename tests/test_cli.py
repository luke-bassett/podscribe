import json
import os
import stat
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

FAKE_CLAUDE = """#!/bin/sh
cat > /dev/null
echo "A fine summary."
"""


def _env_with_fake_claude(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return env


def test_summarize_transcript_json(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "podscribe.cli", "summarize", str(FIXTURES / "transcript.json")],
        capture_output=True, text=True, env=_env_with_fake_claude(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / result.stdout.strip()
    assert out.name == "transcript.summary.3000w.md"
    assert "A fine summary." in out.read_text()


def test_summarize_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "podscribe.cli", "summarize", "nope.mp3"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "no such file" in result.stderr


def test_run_help_lists_two_commands():
    result = subprocess.run(
        [sys.executable, "-m", "podscribe.cli", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "run" in result.stdout and "summarize" in result.stdout
