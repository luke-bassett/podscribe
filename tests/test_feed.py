from pathlib import Path

import pytest

from podscribe.feed import fetch_episodes

FEED = str(Path(__file__).parent / "fixtures" / "feed.xml")


def test_parses_episodes_with_audio_only():
    episodes = list(fetch_episodes(FEED))
    assert [e.title for e in episodes] == ["Episode Two: The Return", "Episode One!"]
    assert episodes[0].audio_url == "https://example.com/audio/ep2.mp3"
    assert episodes[0].published == "2026-06-28"
    assert episodes[0].feed_title == "Test Podcast"
    assert episodes[0].guid == "ep-2"


def test_limit():
    episodes = list(fetch_episodes(FEED, limit=1))
    assert len(episodes) == 1


def test_default_order_is_newest_even_if_feed_is_oldest_first(tmp_path):
    # rewrite the fixture with entries reversed (oldest first in the XML)
    xml = Path(FEED).read_text()
    items = xml.split("<item>")
    reversed_xml = items[0] + "<item>" + "<item>".join(reversed(items[1:]))
    feed_file = tmp_path / "reversed.xml"
    feed_file.write_text(reversed_xml)

    episodes = list(fetch_episodes(str(feed_file)))
    assert [e.published for e in episodes] == ["2026-06-28", "2026-06-21"]

    oldest = list(fetch_episodes(str(feed_file), order="oldest"))
    assert [e.published for e in oldest] == ["2026-06-21", "2026-06-28"]


def test_match_filters_titles():
    episodes = list(fetch_episodes(FEED, match="return"))
    assert [e.title for e in episodes] == ["Episode Two: The Return"]

    episodes = list(fetch_episodes(FEED, match="episode (one|two)"))
    assert len(episodes) == 2


def test_bad_order_raises():
    with pytest.raises(ValueError):
        list(fetch_episodes(FEED, order="sideways"))


def test_slug():
    episode = next(fetch_episodes(FEED))
    assert episode.slug() == "2026-06-28-episode-two-the-return"


def test_bad_feed_raises():
    with pytest.raises(ValueError):
        list(fetch_episodes("/nonexistent/feed.xml"))
