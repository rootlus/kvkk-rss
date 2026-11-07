"""Serve the published site with optional /feed.xml?limit=N filtering."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from scripts.render import ATOM, limit_feed

ROOT = Path(__file__).resolve().parent.parent


class FeedHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        request = urlsplit(self.path)
        query = parse_qs(request.query, keep_blank_values=True)
        if request.path != "/feed.xml" or "limit" not in query:
            return super().send_head()
        values = query["limit"]
        if len(values) != 1 or not re.fullmatch(r"[0-9]{1,9}", values[0]) or int(values[0]) < 1:
            self.send_error(400, "limit must be a positive integer (1-999999999)")
            return None
        limit = int(values[0])
        try:
            feed = (Path(self.directory) / "feed.xml").read_bytes()
            root = ET.fromstring(feed)
            self_link = root.find(f"channel/{{{ATOM}}}link[@rel='self']")
            feed_url = None
            if self_link is not None:
                feed_url = self_link.get("href", "").split("?", 1)[0] + f"?limit={limit}"
            content = limit_feed(feed, limit, feed_url)
        except FileNotFoundError:
            self.send_error(404, "Feed not found")
            return None
        except (OSError, ValueError, ET.ParseError):
            self.send_error(500, "Feed could not be read")
            return None
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        return BytesIO(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    handler = partial(FeedHandler, directory=str(args.directory.resolve()))
    with ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f"Serving on http://{args.bind}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
