# podscribe

Podcast audio → readable transcript → long summary, from a single command:

```sh
podscribe run https://feeds.example.com/bada-bing-radio/rss --match soprano --words 3000
```

Transcription runs **locally** on Apple Silicon via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper); summarization runs through **Claude** by shelling out to `claude -p`, billed to your Claude subscription — no API key, no metered usage.

## How it works

`run` takes each episode through four stages, each writing one artifact:

| Stage | What it does | Artifact | Runs |
|---|---|---|---|
| fetch | Parses the RSS feed into episode records (title, date, audio URL) | — | local (fetches the feed XML) |
| download | Streams the episode audio | `audio/<slug>.mp3` | local (downloads from the podcast host) |
| transcribe | Whisper speech-to-text on the GPU | `transcripts/<slug>.json` (timestamped segments + metadata) | **fully local** |
| format | Groups segments into paragraphs (split on speech pauses > 2s, capped length) | `transcripts/<slug>.md` (readable transcript) | **fully local** |
| summarize | Sends the transcript text to Claude with a ~N-word summary prompt | `summaries/<slug>.summary.<N>w.<model>.md` | **cloud** (via `claude -p`) |

`<slug>` is the publish date plus a slugified episode title, e.g. `2026-06-25-tony-soprano-overrated-and-underrated-factors-in-waste-management`.

### Local vs cloud

- **Audio never leaves your machine.** Whisper inference happens on the local GPU; the only things sent anywhere are ordinary HTTP fetches (the RSS feed, the audio download, the one-time Whisper model download from Hugging Face).
- **Summarization sends the transcript text (not audio) to Anthropic** through the `claude` CLI. It uses whatever account Claude Code is logged into, so usage draws on your subscription's rate limits (the 5-hour usage windows on Pro/Max) rather than metered API billing. An hour-long episode is roughly a 25k-token request.
- Want transcripts without touching Claude? Each stage saves its artifact as it finishes, so the audio, `.json`, and `.md` are on disk before the summarize stage starts — Ctrl-C there loses nothing. For a no-Claude workflow, use the library functions (below) and stop after `format_episode`.

### Idempotency

Every stage skips work whose output file already exists, so re-running a feed only processes new episodes — safe to run on a schedule. Summary filenames record the word count **and** the model (`.summary.3000w.opus.md`), but the skip check ignores the model: a summary at that word count from *any* model counts as done, so switching `--claude-model` mid-backlog doesn't redo finished episodes. Use `--force` to generate anyway (e.g. to add an opus version of an episode already summarized with sonnet). Opus is the default (noticeably better summaries in side-by-side checks); `--claude-model sonnet` is faster and consumes subscription quota more slowly on a big backlog.

## Requirements

- Apple Silicon Mac (mlx-whisper uses the Metal GPU)
- `ffmpeg` on PATH (audio decoding): `brew install ffmpeg`
- [uv](https://docs.astral.sh/uv/)
- [Claude Code](https://claude.com/claude-code) installed and logged in (only needed for summaries)

The Whisper model downloads from Hugging Face on first use (~1.6 GB for the default; podscribe prints a notice when that's happening — it's a one-time wait, not a hang).

## Install

```sh
uv sync              # in this repo, then: uv run podscribe ...
# or install globally so `podscribe` is on PATH:
uv tool install .
```

## Usage

### Summarize the latest episode of a feed

```sh
podscribe run <rss-url>
```

### Pick a specific episode

`--match` is a case-insensitive regex/substring on episode titles, applied before `--limit`:

```sh
podscribe run <rss-url> --match "paulie walnuts"
```

### Work through a backlog

```sh
podscribe run <rss-url> --order oldest --limit 10   # first ten episodes ever
podscribe run <rss-url> --limit 9999                # everything (idempotent — rerun anytime)
```

### Summarize a local file

`summarize` takes an audio file (transcribes it first) or a transcript `.json` that `run` already produced:

```sh
podscribe summarize interview.mp3
podscribe summarize transcripts/<slug>.json --words 500
```

### Flags

| Flag | Commands | Default | Meaning |
|---|---|---|---|
| `--words N` | both | 3000 | approximate summary length |
| `--limit N` | run | 1 | max episodes, applied after sorting/matching |
| `--order newest\|oldest\|feed` | run | newest | sort by publish date, or keep the publisher's order |
| `--match PATTERN` | run | — | filter episode titles |
| `--model <hf-repo>` | both | `mlx-community/whisper-large-v3-turbo` | Whisper model |
| `--claude-model M` | both | `opus` | Claude model for summaries (any `claude --model` value) |
| `--verbose` | both | off | stream decoded text live instead of a progress bar |

Progress goes to stderr; the paths of finished summaries go to stdout (so `podscribe run ... | pbcopy` grabs the paths).

## Performance and model choice

On an M2 Max, the default `whisper-large-v3-turbo` transcribes at roughly **1–2 minutes per hour of audio**. Summarizing is one Claude call, typically under a couple of minutes even for `--words 3000`.

| Whisper model | Speed | Quality | Download |
|---|---|---|---|
| `mlx-community/whisper-large-v3-turbo` (default) | ~1–2 min/hour of audio | best for podcast speech | ~1.6 GB |
| `mlx-community/whisper-tiny` | seconds/hour | noticeable errors — fine for smoke tests | ~150 MB |

Whisper still fumbles proper nouns occasionally ("polly walnuts" for Paulie Walnuts). The summary prompt tells Claude the text is raw speech-to-text, and it reliably corrects those from context — summaries usually read cleaner than the transcript.

## Output example

```
audio/2026-06-25-tony-soprano-overrated-and-underrated-....mp3         # original audio
transcripts/2026-06-25-tony-soprano-....json                           # raw segments + metadata
transcripts/2026-06-25-tony-soprano-....md                             # readable transcript
summaries/2026-06-25-tony-soprano-....summary.3000w.opus.md           # the summary
```

`audio/`, `transcripts/`, and `summaries/` are created in the current working directory and are gitignored.

## Library use

The CLI is a thin wrapper; every stage is an importable function that takes and returns an `Episode`:

```python
from podscribe import fetch_episodes, download_episode, transcribe_episode, format_episode, summarize_episode

for ep in fetch_episodes("https://example.com/feed.xml", limit=1):
    ep = download_episode(ep)
    ep = transcribe_episode(ep)          # ep.transcript_path
    ep = format_episode(ep)              # ep.output_path
    ep = summarize_episode(ep, words=3000)  # ep.summary_path
```

`transcribe_file(path)` is also exported for one-off Whisper runs on arbitrary audio, and `load_segments(json_path)` reads a saved transcript back as `(metadata, segments)`.

## Troubleshooting

- **Looks stuck at "Fetching N files"** — that's the one-time Whisper model download (~1.6 GB). Interrupting is safe; it resumes.
- **`claude` CLI not found** — install Claude Code and log in; summaries need it. Transcription works without it.
- **`ffmpeg` errors** — `brew install ffmpeg`.
- **Summary command exits with a Claude usage-limit error** — you've hit your subscription's 5-hour usage window; the transcript stages already completed and are saved, so re-run later and it resumes at summarize.
- **"Credit balance is too low"** — that's the *metered API* error, meaning `claude` authenticated with an `ANTHROPIC_API_KEY` instead of your subscription login. podscribe strips that variable from the subprocess since v0.1, so if you see this, update podscribe; the underlying cause is an API key in your environment (check `env`, shell rc files, and `launchctl getenv ANTHROPIC_API_KEY`).
- **Transcript is lowercase with no punctuation** — shouldn't happen (podscribe disables Whisper's cross-window conditioning, the usual cause); if it does, delete the `.json` and re-transcribe, or try the full `mlx-community/whisper-large-v3` model.

## Development

```sh
uv run pytest
```

Fixtures in `tests/fixtures/` (a small RSS feed and a transcript); the summarize tests stub the `claude` binary, so the suite runs offline.
