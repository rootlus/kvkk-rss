#!/usr/bin/env python3
"""Fetch, validate, merge, and publish KVKK public metadata."""
import argparse
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile

# Support both `python scripts/generate_feed.py` and `python -m scripts.generate_feed`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from scripts.models import Announcement, SOURCE_URL, merge_items
from scripts.render import FEED_LIMITS, json_bytes, render_feed, render_html
from scripts.scraper import Scraper, SourceError

ROOT = Path(__file__).resolve().parent.parent


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("En az 1 olmalı")
    return number


def nonnegative_float(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("Sonlu ve negatif olmayan bir sayı olmalı")
    return number


def load_archive(path):
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("items"), list):
        raise ValueError("Desteklenmeyen / bozuk arşiv şeması")
    items = [Announcement(**row) for row in value["items"]]
    if len({item.id for item in items}) != len(items) or any(not item.first_seen_at for item in items):
        raise ValueError("Arşivde yinelenen kimlik / eksik gözlem zamanı")
    return items


def publish_files(outputs):
    """Stage every file before replacing; restore prior bytes on a write error.

    Each replacement is atomic. Multiple paths cannot form one filesystem transaction;
    a hard crash between replacements requires a rerun (see README).
    """
    staged = {}
    originals = {}
    replaced = []
    try:
        for path, content in outputs.items():
            old = path.read_bytes() if path.exists() else None
            if old == content:
                continue
            originals[path] = old
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                staged[path] = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            staged[path].chmod(0o644)
        for path, temporary in staged.items():
            os.replace(temporary, path)
            replaced.append(path)
    except OSError:
        for path in reversed(replaced):
            old = originals[path]
            if old is None:
                path.unlink(missing_ok=True)
            else:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                    handle.write(old)
                    rollback = Path(handle.name)
                rollback.chmod(0o644)
                os.replace(rollback, path)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def run(args, scraper=None, now=None):
    archive_path = args.output_root / "data/announcements.json"
    previous = load_archive(archive_path)
    scraper = scraper or Scraper(args.source_url, args.timeout, args.delay, args.user_agent)
    observed = scraper.collect(args.bootstrap_pages or args.max_pages)
    if not observed:
        raise SourceError("Boş kaynak sonucu; çıktı üretilmedi")
    logging.info("%d benzersiz duyuru doğrulandı", len(observed))
    if args.check_only:
        return
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    items, added = merge_items(previous, observed, now)
    docs = args.output_root / "docs"
    feed_path = docs / "feed.xml"
    old_feed = feed_path.read_bytes() if feed_path.exists() else None
    feed = render_feed(items, now, old_feed, args.max_feed_items, args.site_base_url)
    status = {
        "schema_version": 1, "last_successful_check_at": now,
        "total_announcements": len(items), "new_announcements": added,
        "observed_announcements": len({item.id for item in observed}),
        "source_url": args.source_url,
    }
    outputs = {
        archive_path: json_bytes({"schema_version": 1, "items": [item.to_dict() for item in items]}),
        feed_path: feed,
        docs / "index.html": render_html(items, now),
        docs / "status.json": json_bytes(status),
        docs / ".nojekyll": b"",
    }
    for limit in FEED_LIMITS:
        path = docs / f"feed-{limit}.xml"
        old = path.read_bytes() if path.exists() else None
        outputs[path] = render_feed(items, now, old, min(limit, args.max_feed_items),
                                    args.site_base_url, path.name)
    json.loads(outputs[archive_path])
    json.loads(outputs[docs / "status.json"])
    publish_files(outputs)
    logging.info("Arşiv: %d; yeni: %d; RSS değişti: %s", len(items), added, feed != old_feed)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--check-only", action="store_true", help="Kaynağı doğrula; hiçbir çıktı yazma")
    result.add_argument("--bootstrap-pages", type=positive_int, help="İlk geçmiş taramasının sayfa sınırı (öneri: 9)")
    result.add_argument("--max-pages", type=positive_int, default=os.getenv("MAX_PAGES", "5"), help="Düzenli tarama sınırı (MAX_PAGES; varsayılan 5)")
    result.add_argument("--max-feed-items", type=positive_int, default=os.getenv("MAX_FEED_ITEMS", "100"), help="RSS kayıt sınırı (varsayılan 100)")
    result.add_argument("--source-url", default=os.getenv("KVKK_SOURCE_URL", SOURCE_URL), help="Resmî KVKK liste adresi")
    result.add_argument("--timeout", type=nonnegative_float, default=os.getenv("HTTP_TIMEOUT_SECONDS", "15"), help="HTTP timeout, saniye (varsayılan 15; sıfırdan büyük)")
    result.add_argument("--delay", type=nonnegative_float, default=os.getenv("REQUEST_DELAY_SECONDS", "1"), help="İstek aralığı, saniye (varsayılan 1)")
    result.add_argument("--site-base-url", default=os.getenv("SITE_BASE_URL", ""), help="İsteğe bağlı HTTPS Pages URL'si (RSS self bağlantısı)")
    result.add_argument("--user-agent", default=os.getenv("KVKK_USER_AGENT", "kvkk-rss/1.0"), help="Tanımlayıcı HTTP User-Agent")
    result.add_argument("--output-root", type=Path, default=ROOT, help="Çıktı kök dizini (varsayılan proje dizini)")
    return result


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    command = parser()
    args = command.parse_args()
    if args.timeout == 0:
        command.error("--timeout sıfırdan büyük olmalı")
    try:
        run(args)
    except (SourceError, requests.RequestException, ValueError, TypeError, OSError) as exc:
        logging.error("Kontrol başarısız; önceki başarılı yayın korunuyor: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
