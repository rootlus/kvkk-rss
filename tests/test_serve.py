from dataclasses import replace
from io import BytesIO
from unittest.mock import Mock
from xml.etree import ElementTree as ET

import pytest

from scripts.models import Announcement
from scripts.render import ATOM, render_feed
from scripts.serve import FeedHandler


@pytest.fixture
def handler(tmp_path):
    item = Announcement("kvkk-1", "Şirket", "https://www.kvkk.gov.tr/Icerik/1/x", "2026-11-04")
    items = [replace(item, id=f"kvkk-{n}", url=f"https://www.kvkk.gov.tr/Icerik/{n}/x") for n in range(1, 13)]
    (tmp_path / "feed.xml").write_bytes(render_feed(items, "2026-11-06T08:00:00Z", site_base_url="https://example.com/site"))
    request = FeedHandler.__new__(FeedHandler)
    request.directory = str(tmp_path)
    request.send_response = Mock()
    request.send_header = Mock()
    request.end_headers = Mock()
    request.send_error = Mock()
    request.wfile = BytesIO()
    return request


@pytest.mark.parametrize("limit,count", [("1", 1), ("5", 5), ("999", 12)])
def test_query_limit(handler, limit, count):
    handler.path = f"/feed.xml?limit={limit}"
    with handler.send_head() as response:
        content = response.read()
    root = ET.fromstring(content)
    assert len(root.findall("channel/item")) == count
    assert root.find(f"channel/{{{ATOM}}}link").get("href") == f"https://example.com/site/feed.xml?limit={limit}"
    handler.send_response.assert_called_once_with(200)
    handler.send_header.assert_any_call("Content-Length", str(len(content)))
    handler.send_header.assert_any_call("Content-Type", "application/rss+xml; charset=utf-8")


@pytest.mark.parametrize("query", ["limit=", "limit=0", "limit=-1", "limit=1.5", "limit=no", "limit=5&limit=10", "limit=9999999999"])
def test_invalid_limit_returns_400(handler, query):
    handler.path = f"/feed.xml?{query}"
    assert handler.send_head() is None
    assert handler.send_error.call_args.args[0] == 400


def test_get_and_head(handler):
    handler.path = "/feed.xml?limit=5"
    handler.do_HEAD()
    assert handler.wfile.getvalue() == b""
    handler.do_GET()
    assert len(ET.fromstring(handler.wfile.getvalue()).findall("channel/item")) == 5


def test_missing_feed_returns_404(handler, tmp_path):
    (tmp_path / "feed.xml").unlink()
    handler.path = "/feed.xml?limit=5"
    assert handler.send_head() is None
    assert handler.send_error.call_args.args[0] == 404


def test_no_limit_uses_static_handler(handler, monkeypatch):
    static = Mock(return_value=BytesIO(b"static"))
    monkeypatch.setattr("http.server.SimpleHTTPRequestHandler.send_head", static)
    for path in ("/feed.xml", "/favicon.svg", "/feed-5.xml"):
        handler.path = path
        assert handler.send_head().read() == b"static"
        static.return_value.seek(0)
    assert static.call_count == 3
