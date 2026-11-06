from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock
from xml.etree import ElementTree as ET
import pytest
import requests
from scripts.generate_feed import load_archive, parser, publish_files, run
from scripts.models import Announcement
from scripts.render import render_feed, render_html
from scripts.scraper import SourceError, parse_page

NOW = "2026-11-06T08:00:00Z"
LATER = "2026-11-06T09:00:00Z"
ITEM = Announcement("kvkk-1", 'İhlal & <şirket> "örnek"', "https://www.kvkk.gov.tr/Icerik/1/x", "2026-11-04", NOW)


def test_rss_contract_and_html_escaping():
    feed = render_feed([ITEM], NOW, site_base_url="https://example.github.io/kvkk-rss")
    root = ET.fromstring(feed)
    assert root.attrib == {"version": "2.0"}
    assert root.findtext("channel/language") == "tr-TR"
    assert root.findtext("channel/item/title") == ITEM.title
    assert "&lt;şirket&gt;" in root.findtext("channel/item/description")
    assert root.find("channel/item/guid").attrib == {"isPermaLink": "false"}
    assert root.findtext("channel/item/pubDate") == "Wed, 04 Nov 2026 12:00:00 +0300"
    html = render_html([ITEM], NOW).decode()
    assert "&lt;şirket&gt;" in html
    assert '<şirket>' not in html
    assert 'type="application/rss+xml"' in html
    assert "Europe/Istanbul" in html


def test_stable_feed_limit_and_changes():
    older = replace(ITEM, id="kvkk-2", url="https://www.kvkk.gov.tr/Icerik/2/x", published_date="2026-01-01")
    feed = render_feed([ITEM, older], NOW, limit=1)
    assert render_feed([older, ITEM], LATER, feed, limit=1) == feed
    assert render_feed([ITEM, replace(older, title="Eski kayıt düzeltildi")], LATER, feed, limit=1) == feed
    updated = render_feed([replace(ITEM, title="Düzeltme")], LATER, feed, limit=1)
    assert updated != feed
    assert ET.fromstring(updated).findtext("channel/lastBuildDate") == "Fri, 06 Nov 2026 09:00:00 +0000"


def args_for(tmp_path, *extra):
    return parser().parse_args(["--output-root", str(tmp_path), *extra])


def observed():
    html = (Path(__file__).parent / "fixtures/list-page-1.html").read_text()
    return parse_page(html)[0]


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_pipeline_idempotent_history_and_check_only(tmp_path):
    scraper = Mock()
    scraper.collect.return_value = observed()
    args = args_for(tmp_path)
    run(args, scraper, NOW)
    feed = (tmp_path / "docs/feed.xml").read_bytes()
    archive = (tmp_path / "data/announcements.json").read_bytes()
    run(args, scraper, LATER)
    assert (tmp_path / "docs/feed.xml").read_bytes() == feed
    assert (tmp_path / "data/announcements.json").read_bytes() == archive
    assert json.loads((tmp_path / "docs/status.json").read_text())["new_announcements"] == 0
    scraper.collect.return_value = observed()[:1]
    run(args, scraper, LATER)
    assert len(load_archive(tmp_path / "data/announcements.json")) == 12
    before = snapshot(tmp_path)
    run(args_for(tmp_path, "--check-only"), scraper, LATER)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("failure", [SourceError("şablon değişti"), requests.Timeout(), requests.HTTPError("500"), None])
def test_failed_source_preserves_all_files(tmp_path, failure):
    scraper = Mock()
    scraper.collect.return_value = observed()
    run(args_for(tmp_path), scraper, NOW)
    before = snapshot(tmp_path)
    scraper.collect.side_effect = failure
    scraper.collect.return_value = []
    with pytest.raises((SourceError, requests.RequestException)):
        run(args_for(tmp_path), scraper, LATER)
    assert snapshot(tmp_path) == before


def test_invalid_render_preserves_files(tmp_path):
    scraper = Mock()
    scraper.collect.return_value = observed()
    run(args_for(tmp_path), scraper, NOW)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        run(args_for(tmp_path, "--site-base-url", "javascript:evil"), scraper, LATER)
    assert snapshot(tmp_path) == before


def test_write_error_rolls_back(tmp_path, monkeypatch):
    import os
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"old1")
    second.write_bytes(b"old2")
    real = os.replace
    count = 0
    def fail_once(src, dst):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("disk error")
        return real(src, dst)
    monkeypatch.setattr(os, "replace", fail_once)
    with pytest.raises(OSError):
        publish_files({first: b"new1", second: b"new2"})
    assert first.read_bytes() == b"old1"
    assert second.read_bytes() == b"old2"
    assert len(list(tmp_path.iterdir())) == 2


def test_corrupt_archive_aborts_before_fetch(tmp_path):
    archive = tmp_path / "data/announcements.json"
    archive.parent.mkdir()
    archive.write_text('{"schema_version": 99, "items": []}')
    scraper = Mock()
    with pytest.raises(ValueError):
        run(args_for(tmp_path), scraper, NOW)
    scraper.collect.assert_not_called()


def test_check_only_on_first_run_writes_nothing(tmp_path):
    scraper = Mock()
    scraper.collect.return_value = observed()
    run(args_for(tmp_path, "--check-only"), scraper, NOW)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("option,value", [("--max-pages", "0"), ("--bootstrap-pages", "-1"), ("--max-feed-items", "0"), ("--delay", "nan")])
def test_invalid_config(option, value):
    with pytest.raises(SystemExit):
        parser().parse_args([option, value])
