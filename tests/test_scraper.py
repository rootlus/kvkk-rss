from pathlib import Path
from unittest.mock import Mock
import pytest
import requests
from scripts.models import SOURCE_URL
from scripts.scraper import Scraper, SourceError, parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(page=1):
    return (FIXTURES / f"list-page-{page}.html").read_text()


def response(html="", status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = html.encode()
    result.encoding = "utf-8"
    result.headers.update(headers or {})
    return result


def scraper_with(*responses):
    session = Mock()
    session.get.side_effect = responses
    return Scraper(delay=0, session=session)


def test_real_cards_and_context():
    items, pages = parse_page(fixture())
    assert len(items) == 12
    assert items[0].id == "kvkk-9092"
    assert items[0].title.endswith("NCL (Bahamas) Ltd.")
    assert items[0].published_date == "2026-11-04"
    assert 2 in pages
    assert len(parse_page(fixture(2), 2)[0]) == 12


def test_changed_layout_and_empty_are_errors():
    for html in [(FIXTURES / "changed-layout.html").read_text(), '<section class="news"></section>']:
        with pytest.raises(SourceError):
            parse_page(html)


def test_bad_date_is_never_borrowed_from_adjacent_card():
    html = fixture().replace("4 Kasım 2026, Çarşamba", "tarih yok", 1)
    items, _ = parse_page(html)
    assert len(items) == 11
    assert "kvkk-9092" not in {item.id for item in items}
    with pytest.raises(SourceError):
        parse_page(html.replace("4 Kasım 2026, Çarşamba", "tarih yok"))


def test_pagination_and_duplicates():
    # One duplicate across pages is permitted; an entirely repeated page fails.
    from bs4 import BeautifulSoup
    second = BeautifulSoup(fixture(2), "html.parser")
    first = BeautifulSoup(fixture(), "html.parser")
    second.select_one("section.news .row").append(first.select_one(".news__box"))
    scraper = scraper_with(response("User-agent: *\nAllow: /"), response(fixture()), response(str(second)))
    items = scraper.collect(2)
    assert len(items) == 24
    assert scraper.session.get.call_args_list[-1].args[0] == SOURCE_URL + "?page=2"
    scraper = scraper_with(response("User-agent: *\nAllow: /"), response(fixture()), response(fixture()))
    with pytest.raises(SourceError, match="tekrar"):
        scraper.collect(2)


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_http_errors(status):
    scraper = scraper_with(response("User-agent: *\nAllow: /"), response(status=status))
    with pytest.raises(requests.HTTPError):
        scraper.collect(1)


def test_timeout_and_robots_denial():
    scraper = scraper_with(response("User-agent: *\nAllow: /"), requests.Timeout("timeout"))
    with pytest.raises(requests.Timeout):
        scraper.collect(1)
    scraper = scraper_with(response("User-agent: *\nDisallow: /veri-ihlali-bildirimi"))
    with pytest.raises(SourceError, match="izin"):
        scraper.collect(1)
    assert scraper.session.get.call_count == 1


def test_robots_redirect_and_end_of_list():
    scraper = scraper_with(response(status=302, headers={"Location": "https://www.kvkk.gov.tr/"}),
                           response(fixture().replace('page=2', 'page=1')))
    assert len(scraper.collect(1)) == 12
    with pytest.raises(SourceError, match="yönlendirme"):
        scraper_with(response(status=302)).get(SOURCE_URL)


def test_retry_policy_is_bounded_and_avoids_restriction_codes():
    scraper = Scraper()
    retry = scraper.session.get_adapter("https://").max_retries
    assert retry.total == 2
    assert 403 not in retry.status_forcelist and 429 not in retry.status_forcelist
    assert not retry.respect_retry_after_header


def test_turkish_title_does_not_warn_and_last_page_stops(caplog):
    from bs4 import BeautifulSoup
    last = BeautifulSoup(fixture(), "html.parser")
    for link in last.select(".pagination a[href]"):
        link["href"] = SOURCE_URL + "?page=1"
    scraper = scraper_with(response("User-agent: *\nAllow: /"), response(str(last)))
    assert len(scraper.collect(9)) == 12
    assert scraper.session.get.call_count == 2
    assert "Beklenmedik duyuru başlığı" not in caplog.text
