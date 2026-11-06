"""Strict metadata normalization and append-preserving archive merging."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

SOURCE_URL = "https://www.kvkk.gov.tr/veri-ihlali-bildirimi"
MONTHS = {name: i for i, name in enumerate(
    "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split(), 1)}


def normalize_url(value: str, base: str = SOURCE_URL) -> str:
    parts = urlsplit(urljoin(base, value.strip()))
    if (parts.scheme not in {"http", "https"} or
            parts.hostname not in {"www.kvkk.gov.tr", "kvkk.gov.tr"} or
            parts.username or parts.password or parts.port not in {None, 80, 443}):
        raise ValueError(f"KVKK dışı veya geçersiz URL: {value}")
    if not parts.path or re.search(r"[\s\\\x00-\x1f]", parts.path):
        raise ValueError("Geçersiz URL yolu")
    return urlunsplit(("https", "www.kvkk.gov.tr", parts.path.rstrip("/"), "", ""))


def content_id(url: str) -> str:
    match = re.match(r"/Icerik/(\d+)(?:/|$)", urlsplit(url).path, re.I)
    if match:
        return f"kvkk-{int(match[1])}"
    logging.warning("Beklenmedik içerik URL'si; URL hash kimliği kullanılıyor: %s", url)
    return "kvkk-url-" + hashlib.sha256(url.encode()).hexdigest()[:24]


def parse_date(value: str) -> str:
    match = re.fullmatch(r"\s*(\d{1,2})\s+(\w+)\s+(\d{4})(?:\s*,\s*[^,]+)?\s*", value)
    if not match or match[2] not in MONTHS:
        raise ValueError(f"Tanınmayan Türkçe tarih: {value!r}")
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


@dataclass(frozen=True)
class Announcement:
    id: str
    title: str
    url: str
    published_date: str
    first_seen_at: str = ""

    def __post_init__(self):
        if (not self.title.strip() or self.title != " ".join(self.title.split()) or
                any(ord(c) < 32 for c in self.title)):
            raise ValueError("Geçersiz başlık")
        if normalize_url(self.url) != self.url or content_id(self.url) != self.id:
            raise ValueError("Geçersiz kanonik URL / kimlik")
        if date.fromisoformat(self.published_date).isoformat() != self.published_date:
            raise ValueError("Geçersiz yayın tarihi")
        if self.first_seen_at:
            stamp = datetime.fromisoformat(self.first_seen_at.replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError("first_seen_at saat dilimi içermeli")

    def to_dict(self):
        return asdict(self)


def sort_items(items):
    # Newest first; IDs ascending for equal dates.
    return sorted(sorted(items, key=lambda item: item.id),
                  key=lambda item: item.published_date, reverse=True)


def merge_items(previous, observed, now):
    merged = {item.id: item for item in previous}
    added = 0
    for item in observed:
        old = merged.get(item.id)
        if old is None:
            added += 1
        elif (old.title, old.url, old.published_date) != (item.title, item.url, item.published_date):
            logging.info("İlan metaverisi değişti: %s", item.id)
        merged[item.id] = Announcement(item.id, item.title, item.url, item.published_date,
                                       old.first_seen_at if old else now)
    return sort_items(merged.values()), added
