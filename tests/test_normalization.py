from dataclasses import replace
import pytest
from scripts.models import Announcement, MONTHS, content_id, merge_items, normalize_url, parse_date


def test_turkish_dates():
    assert parse_date("4 Kasım 2026, Çarşamba") == "2026-11-04"
    for name, number in MONTHS.items():
        assert parse_date(f"1 {name} 2026") == f"2026-{number:02d}-01"


@pytest.mark.parametrize("value", ["31 Şubat 2026", "tarih yok", "4 November 2026", "2026-11-04"])
def test_invalid_dates(value):
    with pytest.raises(ValueError):
        parse_date(value)


def test_canonical_id():
    url = normalize_url("/Icerik/9092/duyuru/?utm_source=x#details")
    assert url == "https://www.kvkk.gov.tr/Icerik/9092/duyuru"
    assert content_id(url) == "kvkk-9092"
    assert content_id(normalize_url("/yeni-format")) == content_id(normalize_url("/yeni-format"))


@pytest.mark.parametrize("value", ["https://evil.example/Icerik/1/x", "https://www.kvkk.gov.tr.evil.test/x", "javascript:alert(1)", "https://user@www.kvkk.gov.tr/x", "https://www.kvkk.gov.tr:444/x", "https://www.kvkk.gov.tr/x\\evil"])
def test_reject_external_urls(value):
    with pytest.raises(ValueError):
        normalize_url(value)


def test_merge_preserves_history_and_first_seen():
    old = Announcement("kvkk-1", "Eski başlık", "https://www.kvkk.gov.tr/Icerik/1/x", "2026-11-04", "2026-11-05T00:00:00Z")
    missing = replace(old, id="kvkk-2", url="https://www.kvkk.gov.tr/Icerik/2/x")
    updated = replace(old, title="Yeni başlık", first_seen_at="")
    merged, added = merge_items([old, missing], [updated, updated], "2026-11-06T00:00:00Z")
    assert added == 0
    assert len(merged) == 2
    assert merged[0].first_seen_at == old.first_seen_at
    assert merged[0].title == "Yeni başlık"
    assert [row.id for row in merged] == ["kvkk-1", "kvkk-2"]
